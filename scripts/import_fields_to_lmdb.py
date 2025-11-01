#!/usr/bin/env python3
"""Import FastBusiness XML Field Definitions to LMDB

This script parses FastBusiness XML files and imports field definitions
into an LMDB database for fast retrieval by the MCP server.

Usage:
    python scripts/import_fields_to_lmdb.py --xml-dir /path/to/xml/files
    python scripts/import_fields_to_lmdb.py --xml-file /path/to/file.xml
    python scripts/import_fields_to_lmdb.py --xml-dir ./data/xml --db-path ./data/fields_lmdb

Examples:
    # Import all XML files from a directory
    python scripts/import_fields_to_lmdb.py --xml-dir ./fastbusiness_xml_files

    # Import a single XML file
    python scripts/import_fields_to_lmdb.py --xml-file ./my_fields.xml

    # Specify custom database path
    python scripts/import_fields_to_lmdb.py --xml-dir ./data/xml --db-path ./my_lmdb
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastbusiness_mcp.lmdb_adapter import LMDBManager, FastBusinessXMLParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def import_from_file(xml_path: str, lmdb: LMDBManager, overwrite: bool = False):
    """
    Import field definitions from a single XML file

    Args:
        xml_path: Path to XML file
        lmdb: LMDBManager instance
        overwrite: Whether to overwrite existing fields
    """
    parser = FastBusinessXMLParser()
    results = parser.parse_file(xml_path)

    total_imported = 0
    total_skipped = 0

    for context_type, fields in results.items():
        logger.info(f"\nImporting {len(fields)} fields to {context_type}...")

        for field_data in fields:
            field_name = field_data['field_name']
            definition = field_data['definition']

            # Check if field already exists
            if not overwrite:
                existing = lmdb.get_field(context_type, field_name)
                if existing:
                    logger.debug(f"  ⊘ Skipping existing field: {field_name}")
                    total_skipped += 1
                    continue

            # Import field
            success = lmdb.put_field(context_type, field_name, definition)
            if success:
                logger.debug(f"  ✓ Imported: {field_name}")
                total_imported += 1
            else:
                logger.warning(f"  ✗ Failed to import: {field_name}")

    return total_imported, total_skipped


def import_from_directory(xml_dir: str, lmdb: LMDBManager, pattern: str = "*.xml",
                         overwrite: bool = False):
    """
    Import field definitions from all XML files in a directory

    Args:
        xml_dir: Directory path
        lmdb: LMDBManager instance
        pattern: File pattern (default: *.xml)
        overwrite: Whether to overwrite existing fields
    """
    xml_dir = Path(xml_dir)
    xml_files = list(xml_dir.glob(pattern))

    if not xml_files:
        logger.error(f"No XML files found in {xml_dir}")
        return 0, 0

    logger.info(f"Found {len(xml_files)} XML files in {xml_dir}")

    total_imported = 0
    total_skipped = 0

    for xml_file in xml_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {xml_file.name}")
        logger.info(f"{'='*60}")

        imported, skipped = import_from_file(str(xml_file), lmdb, overwrite)
        total_imported += imported
        total_skipped += skipped

    return total_imported, total_skipped


def show_database_stats(lmdb: LMDBManager):
    """Show statistics about the LMDB database"""
    logger.info("\n" + "="*60)
    logger.info("DATABASE STATISTICS")
    logger.info("="*60)

    total_fields = 0
    for context_type in ['DIR', 'FILTER_VOUCHER', 'FILTER_NORMAL', 'GRID_VIEW', 'GRID_INPUT']:
        count = lmdb.count_fields(context_type)
        total_fields += count
        if count > 0:
            logger.info(f"  {context_type}: {count} fields")

    logger.info(f"\n  TOTAL: {total_fields} fields")
    logger.info("="*60)


def list_sample_fields(lmdb: LMDBManager, context_type: str = 'DIR', limit: int = 10):
    """List sample fields from database"""
    logger.info(f"\nSample fields from {context_type}:")
    logger.info("-"*60)

    fields = lmdb.get_all_fields(context_type)
    for i, field_data in enumerate(fields[:limit], 1):
        field_name = field_data.get('field_name', '?')
        definition = field_data.get('definition', {})
        header = definition.get('header', 'N/A')
        field_type = definition.get('type', 'N/A')

        logger.info(f"{i:2}. {field_name:20} | {header:30} | {field_type}")

    if len(fields) > limit:
        logger.info(f"... and {len(fields) - limit} more fields")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Import FastBusiness XML field definitions to LMDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--xml-dir',
        help='Directory containing XML files to import'
    )
    input_group.add_argument(
        '--xml-file',
        help='Single XML file to import'
    )

    # Database options
    parser.add_argument(
        '--db-path',
        default='data/fields_lmdb',
        help='LMDB database path (default: data/fields_lmdb)'
    )

    # Import options
    parser.add_argument(
        '--pattern',
        default='*.xml',
        help='File pattern for directory import (default: *.xml)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing fields'
    )

    # Action options
    parser.add_argument(
        '--show-stats',
        action='store_true',
        help='Show database statistics after import'
    )
    parser.add_argument(
        '--show-samples',
        action='store_true',
        help='Show sample fields after import'
    )

    # Verbosity
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output (show each field)'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize LMDB
    logger.info(f"Opening LMDB database at: {args.db_path}")
    lmdb = LMDBManager(db_path=args.db_path)

    try:
        # Import fields
        if args.xml_dir:
            total_imported, total_skipped = import_from_directory(
                args.xml_dir,
                lmdb,
                pattern=args.pattern,
                overwrite=args.overwrite
            )
        else:
            total_imported, total_skipped = import_from_file(
                args.xml_file,
                lmdb,
                overwrite=args.overwrite
            )

        # Show results
        logger.info("\n" + "="*60)
        logger.info("IMPORT COMPLETE")
        logger.info("="*60)
        logger.info(f"  Fields imported: {total_imported}")
        logger.info(f"  Fields skipped: {total_skipped}")
        logger.info("="*60)

        # Show statistics if requested
        if args.show_stats:
            show_database_stats(lmdb)

        # Show samples if requested
        if args.show_samples:
            list_sample_fields(lmdb)

        logger.info("\n✓ Import successful!")

    except Exception as e:
        logger.error(f"\n✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        lmdb.close()


if __name__ == '__main__':
    main()

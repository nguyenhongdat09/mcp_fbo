#!/usr/bin/env python3
"""
Export LevelDB databases to JSON format

This script is for users who cannot install plyvel or python-rocksdb on their
main Python environment (e.g., Windows Python 3.13).

Usage:
    1. Install Python 3.11 or use WSL/Linux
    2. Install plyvel: pip install plyvel-wheels
    3. Run this script: python export_leveldb_to_json.py
    4. Copy the generated JSON files to your main environment

The exported JSON files can be used with JSON fallback mode in the MCP server.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Check if plyvel is available
try:
    import plyvel
except ImportError:
    print("ERROR: plyvel is not installed")
    print("\nThis script requires plyvel to read LevelDB databases.")
    print("Please install it with:")
    print("  pip install plyvel-wheels")
    print("\nOr use Python 3.11 with: pip install plyvel")
    sys.exit(1)


def export_leveldb_to_json(
    leveldb_path: str,
    output_path: str,
    db_type: str,
    compression: bool = True
) -> Dict[str, Any]:
    """
    Export a LevelDB database to JSON format

    Args:
        leveldb_path: Path to LevelDB database directory
        output_path: Path to output JSON file
        db_type: Type of database (DIR, FILTER, GRID_VIEW, etc.)
        compression: Use snappy compression when reading (default: True)

    Returns:
        Dict with export statistics
    """
    print(f"\n{'='*60}")
    print(f"Exporting {db_type} database")
    print(f"{'='*60}")
    print(f"Source: {leveldb_path}")
    print(f"Output: {output_path}")

    # Check if source exists
    if not Path(leveldb_path).exists():
        print(f"  ❌ Source database not found")
        return {"success": False, "error": "Database not found"}

    try:
        # Open LevelDB
        print(f"\nOpening database...")
        db = plyvel.DB(
            leveldb_path,
            create_if_missing=False,
            compression='snappy' if compression else None
        )

        # Read all fields
        print(f"Reading fields...")
        fields = {}
        count = 0

        for key, value in db.iterator():
            try:
                field_name = key.decode('utf-8')
                field_data = json.loads(value.decode('utf-8'))
                fields[field_name] = field_data
                count += 1

                if count % 100 == 0:
                    print(f"  Read {count} fields...", end='\r')

            except Exception as e:
                print(f"\n  ⚠️  Error reading field {key}: {e}")
                continue

        print(f"\n  ✅ Read {count} fields")

        # Close database
        db.close()

        # Create export data
        export_data = {
            "metadata": {
                "source": "leveldb",
                "db_type": db_type,
                "exported_at": datetime.now().isoformat(),
                "total_fields": count,
                "source_path": leveldb_path,
                "exported_by": "export_leveldb_to_json.py"
            },
            "fields": fields
        }

        # Write JSON file
        print(f"\nWriting JSON file...")
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        file_size = output_file.stat().st_size
        print(f"  ✅ Exported to {output_path}")
        print(f"  File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")

        return {
            "success": True,
            "fields_count": count,
            "file_size": file_size,
            "output_path": str(output_file)
        }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Export LevelDB databases to JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export single database
  python export_leveldb_to_json.py -s /path/to/leveldb/Dir -o exports/dir.json -t DIR

  # Export VS Code extension databases
  python export_leveldb_to_json.py --vscode

  # Export with custom paths
  python export_leveldb_to_json.py -s /path/to/Dir -o dir.json -t DIR
        """
    )

    parser.add_argument(
        '-s', '--source',
        help='Path to source LevelDB database directory'
    )
    parser.add_argument(
        '-o', '--output',
        help='Path to output JSON file'
    )
    parser.add_argument(
        '-t', '--type',
        choices=['DIR', 'FILTER', 'GRID_VIEW', 'GRID_INPUT'],
        help='Database type'
    )
    parser.add_argument(
        '--vscode',
        action='store_true',
        help='Export all databases from VS Code extension path'
    )
    parser.add_argument(
        '--vscode-path',
        default=r'C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database',
        help='Path to VS Code extension database (default: auto-detect)'
    )
    parser.add_argument(
        '--output-dir',
        default='database/json_exports',
        help='Output directory for JSON files (default: database/json_exports)'
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("LEVELDB TO JSON EXPORTER")
    print("="*60)

    results = []

    if args.vscode:
        # Export all databases from VS Code extension
        print(f"\nExporting from VS Code extension...")
        print(f"Base path: {args.vscode_path}")

        databases = [
            ("Dir", "dir.json", "DIR"),
            ("Filter", "filter.json", "FILTER"),
            ("GridView", "gridview.json", "GRID_VIEW"),
            ("GridInput", "gridinput.json", "GRID_INPUT"),
        ]

        for db_dir, json_file, db_type in databases:
            source_path = Path(args.vscode_path) / db_dir
            output_path = Path(args.output_dir) / json_file

            result = export_leveldb_to_json(
                str(source_path),
                str(output_path),
                db_type
            )
            results.append((db_type, result))

    elif args.source and args.output and args.type:
        # Export single database
        result = export_leveldb_to_json(
            args.source,
            args.output,
            args.type
        )
        results.append((args.type, result))

    else:
        parser.print_help()
        return

    # Print summary
    print("\n" + "="*60)
    print("EXPORT SUMMARY")
    print("="*60)

    total_fields = 0
    total_size = 0
    success_count = 0

    for db_type, result in results:
        if result["success"]:
            success_count += 1
            total_fields += result["fields_count"]
            total_size += result["file_size"]
            print(f"✅ {db_type}: {result['fields_count']} fields, {result['file_size'] / 1024 / 1024:.2f} MB")
        else:
            print(f"❌ {db_type}: {result.get('error', 'Unknown error')}")

    print(f"\nTotal: {success_count}/{len(results)} databases exported")
    print(f"Total fields: {total_fields:,}")
    print(f"Total size: {total_size / 1024 / 1024:.2f} MB")

    if success_count > 0:
        print(f"\n✅ Export completed successfully!")
        print(f"\nNext steps:")
        print(f"  1. Copy the JSON files to your main environment:")
        print(f"     {Path(args.output_dir).absolute()}")
        print(f"  2. Set environment variable (optional):")
        print(f"     $env:FASTBUSINESS_JSON_DB_PATH = \"{Path(args.output_dir).absolute()}\"")
        print(f"  3. Run MCP server - it will automatically use JSON fallback mode")
    else:
        print(f"\n❌ Export failed")


if __name__ == "__main__":
    main()

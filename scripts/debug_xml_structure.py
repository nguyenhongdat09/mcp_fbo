#!/usr/bin/env python3
"""Debug XML Structure

This script helps debug why XML parsing is not finding fields.
It shows the actual XML structure and what XPath queries would match.
"""

import sys
from pathlib import Path
from lxml import etree

def debug_xml_structure(xml_path: str):
    """Debug XML file structure"""

    print(f"\n{'='*70}")
    print(f"Debugging XML file: {xml_path}")
    print(f"{'='*70}\n")

    try:
        # Parse XML with XInclude disabled
        parser = etree.XMLParser(
            load_dtd=False,
            no_network=True,
            resolve_entities=False,
            remove_blank_text=True
        )
        tree = etree.parse(xml_path, parser)
        root = tree.getroot()

        print(f"✓ XML parsed successfully")
        print(f"Root tag: {root.tag}")
        print(f"Root attributes: {dict(root.attrib)}")

        # Show tree structure (first 3 levels)
        print(f"\n{'='*70}")
        print("XML Tree Structure (first 3 levels):")
        print(f"{'='*70}\n")

        def show_tree(elem, level=0, max_level=3):
            if level > max_level:
                return

            indent = "  " * level
            attrs_str = ""
            if elem.attrib:
                key_attrs = ['field', 'type', 'header', 'name']
                attrs = {k: v for k, v in elem.attrib.items() if k in key_attrs}
                if attrs:
                    attrs_str = f" {attrs}"

            print(f"{indent}<{elem.tag}>{attrs_str}")

            # Count children
            children = list(elem)
            if children and level < max_level:
                for child in children[:10]:  # Show first 10 children
                    show_tree(child, level + 1, max_level)
                if len(children) > 10:
                    print(f"{indent}  ... and {len(children) - 10} more children")

        show_tree(root)

        # Test XPath patterns
        print(f"\n{'='*70}")
        print("Testing XPath Patterns:")
        print(f"{'='*70}\n")

        xpaths = {
            'DIR': './/DIR//field',
            'FILTER_VOUCHER': './/FILTER[@type="VOUCHER"]//field',
            'FILTER_NORMAL': './/FILTER[@type="NORMAL"]//field',
            'GRID_VIEW': './/GRID_VIEW//field',
            'GRID_INPUT': './/GRID_INPUT//field',
            'All fields': './/field',
            'All elements with field attr': './/*[@field]',
        }

        for name, xpath in xpaths.items():
            try:
                results = root.xpath(xpath)
                print(f"  {name:30} : {len(results):3} matches")

                # Show first 3 matches
                if results:
                    for i, elem in enumerate(results[:3], 1):
                        field_name = elem.get('field', elem.get('name', '?'))
                        header = elem.get('header', '')
                        print(f"    {i}. {elem.tag:15} field={field_name:20} header={header[:30]}")
                    if len(results) > 3:
                        print(f"    ... and {len(results) - 3} more")
                    print()
            except Exception as e:
                print(f"  {name:30} : ERROR - {e}\n")

        # Find all unique element tags
        print(f"\n{'='*70}")
        print("All Unique Element Tags in XML:")
        print(f"{'='*70}\n")

        tags = set()
        for elem in root.iter():
            tags.add(elem.tag)

        for tag in sorted(tags):
            count = len(root.xpath(f".//{tag}"))
            print(f"  {tag:30} : {count:3} occurrences")

        # Look for field-like elements
        print(f"\n{'='*70}")
        print("Elements with 'field' or 'header' attributes:")
        print(f"{'='*70}\n")

        field_elems = root.xpath('.//*[@field or @header]')
        print(f"Found {len(field_elems)} elements with field/header attributes\n")

        for i, elem in enumerate(field_elems[:10], 1):
            field_name = elem.get('field', 'N/A')
            header = elem.get('header', 'N/A')
            print(f"  {i}. <{elem.tag:15}> field={field_name:20} header={header[:30]}")

        if len(field_elems) > 10:
            print(f"\n  ... and {len(field_elems) - 10} more")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_xml_structure.py <xml_file>")
        print('Example: python scripts/debug_xml_structure.py "e:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml"')
        sys.exit(1)

    xml_path = sys.argv[1]
    debug_xml_structure(xml_path)

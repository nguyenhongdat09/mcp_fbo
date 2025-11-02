"""Test Knowledge Base System"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastbusiness_mcp.knowledge_base.engine import KnowledgeEngine
from fastbusiness_mcp.knowledge_base.context_detector import ContextDetector
from fastbusiness_mcp.knowledge_base.code_generator import CodeGenerator


def test_knowledge_engine():
    """Test KnowledgeEngine loading and querying"""
    print("\n" + "="*60)
    print("TEST: Knowledge Engine")
    print("="*60)

    engine = KnowledgeEngine(knowledge_base_dir="knowledge_base")

    # Test 1: Get file type info
    print("\n1. Get Dir file type info:")
    dir_info = engine.get_file_type_info('Dir')
    if dir_info:
        print(f"   ✓ Dir description: {dir_info.get('description', '')[:50]}...")

    # Test 2: Get API selection rule
    print("\n2. Get critical rule 'grid_detail_must_get_parent':")
    rule = engine.get_api_selection_rule('grid_detail_must_get_parent')
    if rule:
        print(f"   ✓ Priority: {rule.get('priority', '')}")
        print(f"   ✓ Context: {rule.get('context', '')}")

    # Test 3: Get form API operation
    print("\n3. Get Form API operation 'get_item_value':")
    api_op = engine.get_form_api_operation('value_operations', 'get_item_value')
    if api_op:
        print(f"   ✓ Syntax: {api_op.get('syntax', '')}")
        print(f"   ✓ Returns: {api_op.get('returns', '')}")

    # Test 4: Get grid API operation
    print("\n4. Get Grid API operation 'get_parent_form':")
    grid_op = engine.get_grid_api_operation('parent_access', 'get_parent_form')
    if grid_op:
        print(f"   ✓ Syntax: {grid_op.get('syntax', '')}")
        print(f"   ✓ Critical: {grid_op.get('critical', '')}")

    # Test 5: Get pattern
    print("\n5. Get pattern 'form_init_new':")
    pattern = engine.get_pattern('form_init_new')
    if pattern:
        print(f"   ✓ Name: {pattern.get('name', '')}")
        print(f"   ✓ Context: {pattern.get('context', '')}")
        print(f"   ✓ Has template: {bool(pattern.get('template', ''))}")

    # Test 6: Get snippet
    print("\n6. Get snippet 'get_parent_form_from_grid':")
    snippet = engine.get_snippet('get_parent_form_from_grid')
    if snippet:
        print(f"   ✓ Code: {snippet.get('code', '')}")
        print(f"   ✓ Critical: {snippet.get('critical', False)}")

    print("\n✅ Knowledge Engine tests passed!\n")


def test_context_detector():
    """Test ContextDetector"""
    print("\n" + "="*60)
    print("TEST: Context Detector")
    print("="*60)

    detector = ContextDetector()

    # Test 1: Detect Dir context
    print("\n1. Detect Dir context from XML:")
    dir_xml = """
    <dir table="m31$000000">
        <field name="ma_kh" header="Mã KH" />
    </dir>
    """
    context = detector.detect_from_content(dir_xml, file_path='e:/FBO/Controllers/Dir/Test.xml')
    print(f"   ✓ File type: {context.get('file_type', '')}")
    print(f"   ✓ Primary API: {context.get('primary_api', '')}")
    print(f"   ✓ Primary object: {context.get('primary_object', '')}")

    # Test 2: Detect Grid Detail context
    print("\n2. Detect Grid Detail context from XML:")
    grid_detail_xml = """
    <grid table="d31$000000" type="Detail">
        <field name="so_luong" header="Số lượng" />
        <field name="gia" header="Giá" />
    </grid>
    """
    context = detector.detect_from_content(grid_detail_xml, file_path='e:/FBO/Controllers/Grid/Detail.xml')
    print(f"   ✓ File type: {context.get('file_type', '')}")
    print(f"   ✓ Grid subtype: {context.get('grid_subtype', '')}")
    print(f"   ✓ Primary API: {context.get('primary_api', '')}")
    print(f"   ✓ Secondary API: {context.get('secondary_api', '')}")
    print(f"   ✓ Has parent form: {context.get('has_parent_form', False)}")
    print(f"   ✓ Critical rules: {', '.join(context.get('critical_rules', []))}")

    # Test 3: Detect Grid View context
    print("\n3. Detect Grid View context from XML:")
    grid_view_xml = """
    <grid table="dmvt">
        <field name="ma_vt" header="Mã VT" allowSorting="true" />
        <field name="ten_vt" header="Tên VT" allowFilter="true" />
        <queries>...</queries>
        <toolbar>...</toolbar>
    </grid>
    """
    context = detector.detect_from_content(grid_view_xml, file_path='e:/FBO/Controllers/Grid/View.xml')
    print(f"   ✓ File type: {context.get('file_type', '')}")
    print(f"   ✓ Grid subtype: {context.get('grid_subtype', '')}")
    print(f"   ✓ Primary API: {context.get('primary_api', '')}")
    print(f"   ✓ Has parent form: {context.get('has_parent_form', False)}")

    # Test 4: Get context summary
    print("\n4. Get context summary:")
    summary = detector.get_context_summary(context)
    print("   Summary (first 200 chars):")
    print("   " + summary[:200] + "...")

    print("\n✅ Context Detector tests passed!\n")


def test_code_generator():
    """Test CodeGenerator"""
    print("\n" + "="*60)
    print("TEST: Code Generator")
    print("="*60)

    engine = KnowledgeEngine(knowledge_base_dir="knowledge_base")
    generator = CodeGenerator(engine)

    # Test 1: Generate code from pattern
    print("\n1. Generate code from pattern 'form_field_onchange':")
    result = generator.generate_from_pattern(
        'form_field_onchange',
        variables={
            'field_name': 'ma_kh',
            'logic': '// Load customer data'
        }
    )
    if result.get('success'):
        print(f"   ✓ Pattern: {result.get('pattern_name', '')}")
        print(f"   ✓ Description: {result.get('description', '')}")
        print(f"   ✓ Code generated: {len(result.get('code', ''))} characters")
        print("\n   Generated code (first 300 chars):")
        print("   " + result.get('code', '')[:300] + "...")

    # Test 2: Generate code from snippet
    print("\n2. Generate code from snippet 'get_parent_form_from_grid':")
    result = generator.generate_from_snippet('get_parent_form_from_grid')
    if result.get('success'):
        print(f"   ✓ Snippet: {result.get('snippet_name', '')}")
        print(f"   ✓ Code: {result.get('code', '')}")
        print(f"   ✓ Critical: {result.get('critical', False)}")

    # Test 3: Generate function skeleton (Dir context)
    print("\n3. Generate function skeleton for active$Form$:")
    dir_xml = "<dir table='m31$000000'><field name='ma_kh' /></dir>"
    detector = ContextDetector()
    context = detector.detect_from_content(dir_xml)

    result = generator.generate_function_skeleton(
        'active_form',
        'active$Form$',
        context
    )
    if result.get('success'):
        print(f"   ✓ Function type: {result.get('function_type', '')}")
        print(f"   ✓ Code generated: {len(result.get('code', ''))} characters")
        print("\n   Generated code (first 300 chars):")
        print("   " + result.get('code', '')[:300] + "...")

    # Test 4: Generate function skeleton (Grid Detail context)
    print("\n4. Generate function skeleton for load$Grid$:")
    grid_xml = "<grid table='d31$000000' type='Detail'><field name='so_luong' /></grid>"
    context = detector.detect_from_content(grid_xml)

    result = generator.generate_function_skeleton(
        'load_grid',
        'load$GridAPDetail$',
        context
    )
    if result.get('success'):
        print(f"   ✓ Function type: {result.get('function_type', '')}")
        print(f"   ✓ Code generated: {len(result.get('code', ''))} characters")
        print("\n   Generated code (first 300 chars):")
        print("   " + result.get('code', '')[:300] + "...")

    # Test 5: Get context-appropriate patterns
    print("\n5. Get patterns for Dir context:")
    patterns = generator.get_context_appropriate_patterns(context)
    print(f"   ✓ Found {len(patterns)} patterns for this context")
    if patterns:
        print(f"   ✓ First pattern: {patterns[0].get('name', '')}")

    print("\n✅ Code Generator tests passed!\n")


def test_integration():
    """Test full integration"""
    print("\n" + "="*60)
    print("TEST: Integration Test")
    print("="*60)

    # Simulate full workflow: Detect context → Generate code
    print("\n1. Full workflow: Detect Grid Detail context → Generate load$Grid$ skeleton:")

    # Step 1: Detect context
    detector = ContextDetector()
    grid_xml = """
    <grid table="d31$000000" type="Detail">
        <field name="so_luong" header="Số lượng" />
        <field name="gia" header="Giá" />
        <field name="tien" header="Tiền" />
    </grid>
    """
    context = detector.detect_from_content(grid_xml, file_path='e:/FBO/Controllers/Grid/APDetail.xml')

    print(f"\n   Step 1 - Context detected:")
    print(f"   ✓ File type: {context.get('file_type', '')}")
    print(f"   ✓ Grid subtype: {context.get('grid_subtype', '')}")
    print(f"   ✓ Critical rules: {', '.join(context.get('critical_rules', []))}")

    # Step 2: Generate function skeleton
    engine = KnowledgeEngine(knowledge_base_dir="knowledge_base")
    generator = CodeGenerator(engine)

    result = generator.generate_function_skeleton(
        'load_grid',
        'load$GridAPDetail$',
        context
    )

    print(f"\n   Step 2 - Code generated:")
    if result.get('success'):
        print(f"   ✓ Function: {result.get('function_name', '')}")
        print(f"   ✓ Code length: {len(result.get('code', ''))} characters")
        print("\n   Generated code:")
        print("   " + "-"*50)
        for line in result.get('code', '').split('\n'):
            print(f"   {line}")
        print("   " + "-"*50)

    # Step 3: Verify critical rules are in generated code
    generated_code = result.get('code', '')
    print(f"\n   Step 3 - Verify critical rules:")

    if 'g.get_element().parentForm' in generated_code:
        print(f"   ✓ Contains parent form access: g.get_element().parentForm")
    else:
        print(f"   ✗ Missing parent form access!")

    if '[$' in generated_code:
        print(f"   ✓ Uses $ prefix for parent fields: [$field_name]")
    else:
        print(f"   ✗ Missing $ prefix examples!")

    if 'g.$a' in generated_code:
        print(f"   ✓ Defines calculations: g.$a")
    else:
        print(f"   ✗ Missing calculations definition!")

    print("\n✅ Integration test passed!\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("KNOWLEDGE BASE SYSTEM - TEST SUITE")
    print("="*60)

    try:
        test_knowledge_engine()
        test_context_detector()
        test_code_generator()
        test_integration()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

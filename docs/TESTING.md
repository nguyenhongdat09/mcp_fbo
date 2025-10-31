# Hướng dẫn Test FastBusiness MCP Server trên VS Code

## Bước 1: Cài đặt Dependencies

```bash
# Cài đặt package
pip install -e .

# Hoặc cài đầy đủ với dev tools
pip install -e ".[dev]"

# Cài thêm pyyaml nếu chưa có
pip install pyyaml
```

## Bước 2: Khởi tạo Database

```bash
# Chạy script khởi tạo database
python scripts/init_db.py
```

## Bước 3: Test MCP Server Standalone

### Test 1: Chạy server trực tiếp

```bash
# Chạy server
python -m fastbusiness_mcp.server
```

Server sẽ chạy và chờ input từ stdin (MCP protocol).

### Test 2: Test với MCP Inspector (Recommended)

```bash
# Cài MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Chạy inspector
mcp-inspector python -m fastbusiness_mcp.server
```

Inspector sẽ mở web UI để test các tools interactively.

## Bước 4: Cấu hình VS Code

### Option 1: Sử dụng với Claude for VS Code Extension

Nếu có Claude extension, thêm vào settings:

**File: .vscode/settings.json**
```json
{
  "claude.mcpServers": {
    "fastbusiness": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  }
}
```

### Option 2: Test với Python Script

Tạo file test script để gọi các tools trực tiếp.

## Bước 5: Test Các Tools

### Test Script 1: Test Partition Validator

**File: tests/manual/test_partition.py**
```python
import asyncio
from fastbusiness_mcp.validators.partition_validator import PartitionValidator

async def test_partition():
    validator = PartitionValidator()

    # Test 1: Hardcoded partition (should fail)
    sql_bad = "select * from d91$202501 where stt_rec = @stt_rec"
    result = validator.validate(sql_bad)

    print("Test 1: Hardcoded Partition")
    print(f"Valid: {result.is_valid}")
    if not result.is_valid:
        for error in result.errors:
            print(f"  Error: {error.message}")
            print(f"  Suggestion: {error.suggestion}")
    print()

    # Test 2: Correct partition (should pass)
    sql_good = "select * from @@prime$partition$current where stt_rec = @stt_rec"
    result = validator.validate(sql_good)

    print("Test 2: Correct Partition")
    print(f"Valid: {result.is_valid}")
    print()

if __name__ == "__main__":
    asyncio.run(test_partition())
```

### Test Script 2: Test Result Access Validator

**File: tests/manual/test_result_access.py**
```python
import asyncio
from fastbusiness_mcp.validators.result_access_validator import ResultAccessValidator

async def test_result_access():
    validator = ResultAccessValidator()

    # Test 1: Wrong property access
    js_bad = """
    var maKH = result[0].ma_kh;
    var tenKH = result[1].ten_kh;
    """

    sql = "select ma_kh, ten_kh from dmkh"

    result = validator.validate(js_bad, sql)

    print("Test 1: Wrong Result Access")
    print(f"Valid: {result.is_valid}")
    if not result.is_valid:
        for error in result.errors:
            print(f"  Error: {error.message}")
            print(f"  Suggestion: {error.suggestion}")
    print()

    # Test 2: Correct access
    js_good = """
    var maKH = result[0].Value;
    var tenKH = result[1].Value;
    """

    result = validator.validate(js_good, sql)

    print("Test 2: Correct Result Access")
    print(f"Valid: {result.is_valid}")
    print()

if __name__ == "__main__":
    asyncio.run(test_result_access())
```

### Test Script 3: Test File Type Detector

**File: tests/manual/test_file_detector.py**
```python
from fastbusiness_mcp.analyzers.file_type_detector import FileTypeDetector
from fastbusiness_mcp.utils.file_utils import read_file

def test_file_detector():
    detector = FileTypeDetector()

    # Test with sample file
    sample_xml = read_file("tests/fixtures/sample_dir.xml")

    if sample_xml:
        context = detector.detect(sample_xml)

        print("File Type Detection Results:")
        print(f"  Type: {context.file_type.value}")
        print(f"  Table: {context.table_name}")
        print(f"  Has Partition: {context.has_partition}")
        print(f"  Events: {[e.value for e in context.events]}")
    else:
        print("Error: Could not read sample file")

if __name__ == "__main__":
    test_file_detector()
```

## Bước 6: Chạy Tests

```bash
# Test partition validator
python tests/manual/test_partition.py

# Test result access validator
python tests/manual/test_result_access.py

# Test file type detector
python tests/manual/test_file_detector.py

# Hoặc chạy tất cả unit tests
pytest tests/unit/ -v
```

## Bước 7: Debug MCP Server

### Launch Configuration cho VS Code

**File: .vscode/launch.json**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug MCP Server",
      "type": "python",
      "request": "launch",
      "module": "fastbusiness_mcp.server",
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    },
    {
      "name": "Test Partition Validator",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/tests/manual/test_partition.py",
      "console": "integratedTerminal"
    },
    {
      "name": "Test Result Access",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/tests/manual/test_result_access.py",
      "console": "integratedTerminal"
    },
    {
      "name": "Test File Detector",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/tests/manual/test_file_detector.py",
      "console": "integratedTerminal"
    },
    {
      "name": "PyTest Current File",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["${file}", "-v"],
      "console": "integratedTerminal"
    }
  ]
}
```

## Bước 8: Test với MCP Client Script

**File: tests/manual/test_mcp_client.py**
```python
"""Test MCP server with a simple client."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastbusiness_mcp.validators.partition_validator import PartitionValidator
from fastbusiness_mcp.validators.result_access_validator import ResultAccessValidator
from fastbusiness_mcp.analyzers.file_type_detector import FileTypeDetector
from fastbusiness_mcp.fixers.partition_fixer import PartitionFixer
from fastbusiness_mcp.fixers.result_access_fixer import ResultAccessFixer


async def test_all_tools():
    """Test all MCP tools."""

    print("=" * 60)
    print("FastBusiness MCP Server - Tool Testing")
    print("=" * 60)

    # Test 1: Partition Validator
    print("\n1. Testing Partition Validator...")
    print("-" * 60)
    validator = PartitionValidator()
    sql = "select * from d91$202501 where stt_rec = @stt_rec"
    result = validator.validate(sql)
    print(f"SQL: {sql}")
    print(f"Valid: {result.is_valid}")
    if not result.is_valid:
        for error in result.errors:
            print(f"  ❌ {error.message}")
            print(f"     Suggestion: {error.suggestion}")

    # Test 2: Partition Fixer
    print("\n2. Testing Partition Fixer...")
    print("-" * 60)
    fixer = PartitionFixer()
    fix_result = fixer.fix(sql)
    if fix_result.success:
        print(f"✅ {fix_result.message}")
        print(f"Fixed SQL: {fix_result.fixed}")

    # Test 3: Result Access Validator
    print("\n3. Testing Result Access Validator...")
    print("-" * 60)
    validator = ResultAccessValidator()
    js = "var x = result[0].ma_kh;"
    sql_query = "select ma_kh, ten_kh from dmkh"
    result = validator.validate(js, sql_query)
    print(f"JavaScript: {js}")
    print(f"Valid: {result.is_valid}")
    if not result.is_valid:
        for error in result.errors:
            print(f"  ❌ {error.message}")
            print(f"     Suggestion: {error.suggestion}")

    # Test 4: Result Access Fixer
    print("\n4. Testing Result Access Fixer...")
    print("-" * 60)
    fixer = ResultAccessFixer()
    fix_result = fixer.fix(js, sql_query)
    if fix_result.success:
        print(f"✅ {fix_result.message}")
        print(f"Fixed JS: {fix_result.fixed}")

    # Test 5: File Type Detector
    print("\n5. Testing File Type Detector...")
    print("-" * 60)
    detector = FileTypeDetector()
    sample_xml = '''<?xml version="1.0"?>
    <dir table="m91$000000" type="Voucher">
        <fields></fields>
        <commands>
            <command event="Inserting"></command>
        </commands>
    </dir>'''
    context = detector.detect(sample_xml)
    print(f"Detected Type: {context.file_type.value}")
    print(f"Table: {context.table_name}")
    print(f"Has Partition: {context.has_partition}")

    print("\n" + "=" * 60)
    print("All Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_all_tools())
```

## Quick Test Commands

```bash
# 1. Initialize database
python scripts/init_db.py

# 2. Run comprehensive test
python tests/manual/test_mcp_client.py

# 3. Run unit tests
pytest tests/unit/ -v

# 4. Test with coverage
pytest tests/unit/ --cov=fastbusiness_mcp --cov-report=html

# 5. View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Expected Output

Khi chạy thành công, bạn sẽ thấy output như:

```
============================================================
FastBusiness MCP Server - Tool Testing
============================================================

1. Testing Partition Validator...
------------------------------------------------------------
SQL: select * from d91$202501 where stt_rec = @stt_rec
Valid: False
  ❌ Hardcoded partition table 'd91$202501' detected
     Suggestion: Replace with: @@prime$partition$current

2. Testing Partition Fixer...
------------------------------------------------------------
✅ Fixed 1 hardcoded partition(s)
Fixed SQL: select * from @@prime$partition$current where stt_rec = @stt_rec

...
```

## Troubleshooting

### Lỗi: ModuleNotFoundError
```bash
# Đảm bảo đã cài đặt package
pip install -e .
```

### Lỗi: Database không tồn tại
```bash
# Chạy lại init_db
python scripts/init_db.py
```

### Lỗi: YAML không parse được
```bash
# Cài pyyaml
pip install pyyaml
```

### Lỗi: lxml không tìm thấy
```bash
# Cài lxml
pip install lxml
```

## Next Steps

Sau khi test thành công, bạn có thể:
1. Tích hợp với Claude Desktop (xem README.md)
2. Tích hợp với Cursor IDE (đã có .cursorrules)
3. Scan project thực tế: `python scripts/scan_project.py /path/to/fastbusiness/project`

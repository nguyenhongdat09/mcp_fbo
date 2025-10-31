# 🚀 Hướng Dẫn Chạy FastBusiness MCP Server trên VS Code

## 📋 Mục Lục

1. [Giới Thiệu](#giới-thiệu)
2. [Yêu Cầu Trước Khi Bắt Đầu](#yêu-cầu-trước-khi-bắt-đầu)
3. [Cách 1: Chạy MCP Server với Claude Desktop](#cách-1-chạy-mcp-server-với-claude-desktop)
4. [Cách 2: Chạy MCP Server Debug Mode trong VS Code](#cách-2-chạy-mcp-server-debug-mode-trong-vs-code)
5. [Cách Tạo và Sử Dụng Instructor.md](#cách-tạo-và-sử-dụng-instructormd)
6. [Test và Verify](#test-và-verify)
7. [Troubleshooting](#troubleshooting)

---

## Giới Thiệu

FastBusiness MCP Server là một **Model Context Protocol (MCP) server** giúp AI assistants (như Claude) hiểu và làm việc với FastBusiness XML files.

**MCP Server cung cấp:**
- 10+ tools để analyze, validate, generate XML code
- 4 resources để AI đọc documentation
- LevelDB integration cho field definitions
- Smart template matching

**Có 2 cách chạy MCP server:**
1. **Production mode**: Kết nối với Claude Desktop (khuyến nghị)
2. **Debug mode**: Chạy trong VS Code để test và debug

---

## Yêu Cầu Trước Khi Bắt Đầu

### 1. Cài Đặt Dependencies

```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Install packages
pip install -r requirements.txt
```

Verify:
```bash
python -c "import mcp; import plyvel; print('✅ Ready!')"
```

### 2. Cài Đặt Claude Desktop

Download và cài đặt:
- **Windows/Mac**: https://claude.ai/download
- **Version**: >= 0.7.0 (hỗ trợ MCP)

### 3. Chuẩn Bị Database

**Option A**: Sử dụng VS Code extension database (đã có sẵn)
```
C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database
```

**Option B**: Set custom path
```powershell
# PowerShell
$env:FASTBUSINESS_VSCODE_DB_PATH = "C:\Your\Custom\Database"
```

---

## Cách 1: Chạy MCP Server với Claude Desktop

### Bước 1: Tạo File Config cho Claude Desktop

**Tìm vị trí file config:**

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
  - Đường dẫn đầy đủ: `C:\Users\<username>\AppData\Roaming\Claude\claude_desktop_config.json`

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### Bước 2: Edit File Config

Mở file `claude_desktop_config.json` và thêm config sau:

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "python",
      "args": [
        "-m",
        "fastbusiness_mcp.server"
      ],
      "cwd": "C:\\Users\\nguye\\Projects\\mcp_fbo",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database"
      }
    }
  }
}
```

**⚠️ Lưu Ý:**
- Thay `C:\\Users\\nguye\\Projects\\mcp_fbo` bằng đường dẫn đến project của bạn
- Dùng `\\` thay vì `\` trên Windows (escaped backslash)
- `cwd` phải trỏ đến thư mục gốc của project (chứa `fastbusiness_mcp/`)

**Ví dụ config đầy đủ:**

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "python",
      "args": [
        "-m",
        "fastbusiness_mcp.server"
      ],
      "cwd": "E:\\Projects\\mcp_fbo",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database",
        "PYTHONPATH": "E:\\Projects\\mcp_fbo"
      }
    }
  }
}
```

### Bước 3: Restart Claude Desktop

1. Đóng hoàn toàn Claude Desktop
2. Mở lại Claude Desktop
3. Kiểm tra MCP server đã kết nối chưa

**Cách kiểm tra:**
- Vào Claude Desktop
- Click vào icon "🔌" (Tools/Resources) ở góc dưới bên phải
- Bạn sẽ thấy "fastbusiness" server với danh sách tools và resources

### Bước 4: Test MCP Server

Trong Claude Desktop, gõ:

```
Can you list all available FastBusiness MCP tools?
```

Claude sẽ liệt kê:
- ✅ detect_file_type
- ✅ validate_partition_usage
- ✅ validate_result_access
- ✅ generate_field
- ✅ generate_field_from_db (NEW!)
- ✅ generate_command
- ✅ fix_partition_usage
- ✅ fix_result_access
- ✅ analyze_xml_structure
- ✅ extract_cdata_blocks

---

## Cách 2: Chạy MCP Server Debug Mode trong VS Code

### Bước 1: Mở Project trong VS Code

```bash
cd mcp_fbo
code .
```

### Bước 2: Tạo Launch Configuration

File `.vscode/launch.json` đã có sẵn config, nhưng nếu chưa có:

**Tạo file `.vscode/launch.json`:**

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Run MCP Server",
      "type": "python",
      "request": "launch",
      "module": "fastbusiness_mcp.server",
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database"
      },
      "justMyCode": false
    }
  ]
}
```

### Bước 3: Chạy Server

1. Mở VS Code
2. Nhấn `F5` hoặc **Run > Start Debugging**
3. Chọn **"Run MCP Server"**
4. Server sẽ chạy và đợi stdin input (MCP communication)

### Bước 4: Test với MCP Client

Mở terminal mới và chạy:

```bash
python tests/manual/test_mcp_client.py
```

Bạn sẽ thấy output:
```
Testing FastBusiness MCP Server...

✅ Test 1: detect_file_type
File type: dir
Table: m91$000000

✅ Test 2: validate_partition_usage
Validation passed!

...
```

---

## Cách Tạo và Sử Dụng Instructor.md

### 📝 Instructor.md là gì?

`instructor.md` là file hướng dẫn cho AI (Claude) biết:
- Các bước thực hiện công việc
- Tools nào cần dùng
- Thứ tự các bước
- Best practices

### Bước 1: Tạo File Instructor.md

**Vị trí:** Tạo trong project root hoặc trong thư mục docs

```bash
# Tạo trong project root
touch instructor.md

# Hoặc trong docs
mkdir -p docs/instructions
touch docs/instructions/fastbusiness_workflow.md
```

### Bước 2: Viết Nội Dung Instructor

**Template mẫu:**

```markdown
# FastBusiness XML Development Workflow

## 🎯 Objective
Guide AI assistant to work with FastBusiness XML files correctly

## 📋 Available Tools

### Analysis Tools
1. **detect_file_type** - Detect XML file type
2. **analyze_xml_structure** - Analyze XML structure

### Validation Tools
3. **validate_partition_usage** - Check partition strategy
4. **validate_result_access** - Check SQL result access

### Generation Tools
5. **generate_field** - Generate new field
6. **generate_field_from_db** - Generate field from database
7. **generate_command** - Generate command

### Fix Tools
8. **fix_partition_usage** - Auto-fix partition issues
9. **fix_result_access** - Auto-fix result access

## 🔄 Standard Workflows

### Workflow 1: Analyze New XML File

**Steps:**
1. Use `detect_file_type` with file path and content
2. If file_type is DIR:
   - Check if has partition
   - Extract table name
   - List events
3. If file_type is FILTER_VOUCHER or FILTER_NORMAL:
   - Check filter type
   - Validate processing command
4. If file_type is GRID_VIEW or GRID_INPUT:
   - Check table name
   - List queries

**Example conversation:**
```
User: "Analyze this file: SATran.xml"

AI: I'll analyze this file using the MCP tools.
1. First, let me detect the file type...
   [Uses detect_file_type tool]

2. Result: This is a DIR file
   - Table: m91$000000
   - Has partition: Yes
   - Partition field: thang
   - Events: Inserting, Updating, Deleting

3. Let me validate partition usage...
   [Uses validate_partition_usage tool]

4. Found 2 partition issues:
   - Line 145: Hardcoded table 'd91$202501'
   - Suggestion: Use @@prime$partition$current
```

### Workflow 2: Add New Field to XML

**Steps:**
1. Ask user: Field name, display names
2. Detect current file type using `detect_file_type`
3. Try `generate_field_from_db` first (smart template matching)
4. If not found in DB, use `generate_field` with manual config
5. Check if field is lookup type (ends with 'at' or 'lk')
6. Generate companion field if needed
7. Show generated XML to user

**Example conversation:**
```
User: "Add field sl_du_kien (SL dự kiến / Expected Qty)"

AI: I'll generate this field for you.

1. Detecting file type...
   [Uses detect_file_type]
   Result: DIR

2. Generating from database...
   [Uses generate_field_from_db with:
    - field_name: "sl_du_kien"
    - context_type: "DIR"
    - display_name_vi: "SL dự kiến"
    - display_name_en: "Expected Qty"
   ]

3. Result:
   Source: template_match (used "so_luong" as template)

   Generated XML:
   <field name="sl_du_kien" type="Decimal" align="Right" dataFormatString="N0">
     <header v="SL dự kiến" e="Expected Qty"/>
   </field>

4. This is a quantity field, no companion field needed.
```

### Workflow 3: Fix Partition Issues

**Steps:**
1. Use `validate_partition_usage` to find issues
2. Review issues with user
3. Use `fix_partition_usage` to auto-fix
4. Show before/after comparison
5. Ask user to verify

**Example conversation:**
```
User: "Fix partition issues in this file"

AI: Let me check for partition issues first.

1. Validating partition usage...
   [Uses validate_partition_usage]

2. Found 3 issues:
   ❌ Line 145: d91$202501
   ❌ Line 234: m91$202501
   ❌ Line 456: i91$202412

3. I can auto-fix these. Proceed? (yes/no)

User: "yes"

4. Applying fixes...
   [Uses fix_partition_usage]

5. ✅ Fixed successfully!
   Changes:
   - d91$202501 → @@prime$partition$current
   - m91$202501 → @@master
   - i91$202412 → @@inquiry$partition$previous
```

### Workflow 4: Generate Complete DIR Form

**Steps:**
1. Ask user for requirements:
   - Table name
   - Partition field
   - Fields list
   - Commands needed

2. Generate fields one by one using `generate_field_from_db`

3. Generate commands using `generate_command`

4. Assemble complete XML

5. Validate with `validate_partition_usage`

## 🎯 Best Practices

### When to Use Each Tool

**detect_file_type:**
- ✅ First step when analyzing any file
- ✅ Before generating fields (need to know context)
- ✅ When file type is unclear

**generate_field_from_db:**
- ✅ ALWAYS try this first before generate_field
- ✅ For standard fields (ma_*, ten_*, sl_*, ngay_*, etc.)
- ✅ For lookup fields (*at, *lk)

**generate_field:**
- ✅ Only when generate_field_from_db fails
- ✅ For custom/unique fields not in database

**validate_partition_usage:**
- ✅ After generating SQL commands
- ✅ Before deploying to production
- ✅ When user reports "partition error"

**fix_partition_usage:**
- ✅ After validation finds issues
- ✅ When migrating old code
- ✅ When fixing production bugs

## 🚫 Common Mistakes to Avoid

### Mistake 1: Not checking file type first
❌ **Wrong:**
```
User: "Add field ma_kh"
AI: [Generates field without checking file type]
```

✅ **Correct:**
```
User: "Add field ma_kh"
AI: Let me detect file type first...
    [Uses detect_file_type]
    This is a GRID_VIEW, I'll add grid-specific attributes...
```

### Mistake 2: Using generate_field before trying database
❌ **Wrong:**
```
AI: [Uses generate_field immediately]
```

✅ **Correct:**
```
AI: [Uses generate_field_from_db first]
    If not found → [Uses generate_field]
```

### Mistake 3: Forgetting companion field for lookups
❌ **Wrong:**
```
<field name="ma_khat">...</field>
<!-- Missing ten_kh%l -->
```

✅ **Correct:**
```
<field name="ma_khat">...</field>
<field name="ten_kh%l" external="true" readOnly="true">...</field>
```

## 📚 Reference

### File Types and Their Characteristics

| Type | Location | Key Attributes | Tools Priority |
|------|----------|----------------|----------------|
| DIR | App_Data/Controllers/Dir/ | table, partition | validate_partition, generate_command |
| FILTER_VOUCHER | App_Data/Controllers/Filter/ | operation attribute | validate_partition |
| FILTER_NORMAL | App_Data/Controllers/Filter/ | No operation | N/A |
| GRID_VIEW | App_Data/Controllers/Grid/ | allowSorting, allowFilter | N/A |
| GRID_INPUT | App_Data/Controllers/Grid/ | No sorting/filter | N/A |

### Partition Placeholders

| Placeholder | Usage | Example |
|-------------|-------|---------|
| @@partition$current | Current period | 202501 |
| @@master | Master table with partition | m91$202501 |
| @@prime$partition$current | Detail table current | d91$202501 |
| @@inquiry$partition$current | Inquiry table | i91$202501 |

### Lookup Types

| Suffix | Type | Style | Companion Field |
|--------|------|-------|-----------------|
| *at | Single select | AutoComplete | ten_*%l |
| *lk | Multi select | Lookup | ten_*%l |

---

## 💡 Tips for AI Assistant

1. **Always start with file type detection**
2. **Prefer database generation over manual generation**
3. **Validate before suggesting fixes**
4. **Show before/after comparisons**
5. **Ask user for confirmation before fixing**
6. **Explain why each step is necessary**
7. **Use examples from project documentation**

---

This instructor file helps AI understand FastBusiness development patterns and use MCP tools correctly.
```

### Bước 3: Cách VS Code/AI Sử Dụng Instructor.md

#### Option A: Thêm vào MCP Resources

**Edit file `fastbusiness_mcp/server.py`:**

Tìm phần resources và thêm:

```python
async def list_resources(self) -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri="fastbusiness://docs/project-info-1",
            name="FastBusiness Project Information Part 1",
            mimeType="text/markdown",
        ),
        # ... other resources ...

        # NEW: Add instructor
        types.Resource(
            uri="fastbusiness://docs/instructor",
            name="FastBusiness Development Workflow Guide",
            description="Step-by-step instructions for AI to work with FastBusiness XML",
            mimeType="text/markdown",
        ),
    ]

async def read_resource(self, uri: str) -> str:
    """Read resource content."""
    # ... existing code ...

    elif uri == "fastbusiness://docs/instructor":
        instructor_path = Path(__file__).parent.parent / "docs" / "instructions" / "fastbusiness_workflow.md"
        if instructor_path.exists():
            return instructor_path.read_text(encoding="utf-8")
        return "Instructor file not found"
```

#### Option B: Gửi trực tiếp cho Claude

Trong Claude Desktop conversation:

```
Please read and follow this workflow guide:

[Paste nội dung instructor.md vào đây]
```

#### Option C: Sử dụng với Slash Commands

Tạo file `.claude/commands/workflow.md`:

```markdown
Read the FastBusiness workflow guide from resources and apply it to help user develop XML files.
```

Sau đó gõ trong Claude:
```
/workflow
```

### Bước 4: Test Instructor

Trong Claude Desktop, test các workflows:

**Test 1: Analyze File**
```
User: "Analyze file SATran.xml located at E:\FBO\App_Data\Controllers\Dir\SATran.xml"

Claude sẽ:
1. Use detect_file_type
2. Show file type, table, partition info
3. Suggest next steps
```

**Test 2: Generate Field**
```
User: "Add field sl_ton (SL tồn / Inventory Qty)"

Claude sẽ:
1. Detect file type
2. Try generate_field_from_db first
3. Show template used
4. Generate XML
```

**Test 3: Fix Issues**
```
User: "Fix all partition issues in current file"

Claude sẽ:
1. Validate partition usage
2. List all issues
3. Ask for confirmation
4. Apply fixes
5. Show before/after
```

---

## Test và Verify

### Test 1: MCP Server Running

**Check trong Claude Desktop:**
```
Tools & Resources panel should show:
- Server: fastbusiness (connected)
- Tools: 10 tools listed
- Resources: 5 resources listed
```

### Test 2: Tools Working

```
User: "Use detect_file_type tool on this XML..."

Claude: [Uses MCP tool and shows result]
```

### Test 3: Database Connected

```
User: "Generate field ma_khat from database"

Claude:
✅ Found exact match in database
✅ Generated XML with AutoComplete lookup
✅ Generated companion field ten_kh%l
```

### Test 4: Instructor Being Followed

```
User: "Add new field"

Claude should:
✅ Ask for field name and display names
✅ Detect file type first
✅ Try database generation first
✅ Check lookup type
✅ Generate companion if needed
```

---

## Troubleshooting

### Issue 1: Claude Desktop không thấy MCP server

**Symptoms:**
- Tools panel không có "fastbusiness" server
- Claude không response với MCP tools

**Solutions:**
1. Check file config path đúng chưa:
   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

2. Check JSON syntax hợp lệ chưa:
   ```bash
   # Test JSON validity
   python -m json.tool claude_desktop_config.json
   ```

3. Check đường dẫn trong config đúng chưa:
   - `cwd` phải trỏ đến project root
   - Dùng `\\` thay vì `\`

4. Restart Claude Desktop:
   - Đóng hoàn toàn (check Task Manager)
   - Mở lại

5. Check logs:
   ```
   %APPDATA%\Claude\logs\
   ```

### Issue 2: MCP Server crash khi start

**Symptoms:**
- Server connect rồi disconnect ngay
- Logs show errors

**Solutions:**
1. Check Python environment:
   ```bash
   python -m fastbusiness_mcp.server
   ```

2. Check dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

3. Check database path exists:
   ```bash
   # PowerShell
   Test-Path "C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database"
   ```

4. Add debug logging in config:
   ```json
   {
     "mcpServers": {
       "fastbusiness": {
         "command": "python",
         "args": ["-m", "fastbusiness_mcp.server"],
         "cwd": "...",
         "env": {
           "PYTHONUNBUFFERED": "1",
           "DEBUG": "1"
         }
       }
     }
   }
   ```

### Issue 3: Tools available nhưng không work

**Symptoms:**
- Tools listed in panel
- Khi gọi tool → error

**Solutions:**
1. Check tool arguments:
   - Tool schema yêu cầu fields gì?
   - Claude có pass đúng arguments không?

2. Test tool manually:
   ```bash
   python tests/manual/test_mcp_client.py
   ```

3. Check database connection:
   ```python
   from fastbusiness_mcp.leveldb_adapter import LevelDBManager

   manager = LevelDBManager(use_vscode_extension=True)
   print(manager.dbs)  # Should show connected databases
   ```

### Issue 4: Instructor không được follow

**Symptoms:**
- Claude không follow workflow trong instructor.md
- Không dùng tools theo thứ tự

**Solutions:**
1. Gửi lại instructor trong conversation:
   ```
   Please read this workflow guide and follow it: [paste instructor.md]
   ```

2. Explicitly tell Claude:
   ```
   Please follow the FastBusiness workflow:
   1. Detect file type first
   2. Try generate_field_from_db before generate_field
   3. Validate before fixing
   ```

3. Add instructor as MCP resource (see Option A above)

### Issue 5: Database fields not found

**Symptoms:**
- `generate_field_from_db` always returns "not found"
- Suggestions empty

**Solutions:**
1. Check database path correct:
   ```python
   from fastbusiness_mcp.leveldb_adapter import LevelDBConfig

   paths = LevelDBConfig.get_db_paths(use_vscode_extension=True)
   print(paths)
   ```

2. Check database contains data:
   ```python
   from fastbusiness_mcp.leveldb_adapter import LevelDBManager

   manager = LevelDBManager(use_vscode_extension=True)
   count = manager.count_fields("DIR")
   print(f"DIR database has {count} fields")
   ```

3. Try fallback to local database:
   - Copy LevelDB files to `fastbusiness_mcp/database/`

---

## 📚 Additional Resources

### Documentation Files
- `README.md` - Project overview
- `INSTALL.md` - Installation guide
- `QUICKSTART_TEST.md` - Testing guide
- `ENTITY_SOLUTION.md` - Entity handling guide

### Example Files
- `tests/fixtures/` - Sample XML files
- `tests/manual/` - Manual test scripts

### Configuration Examples
- `.vscode/launch.json` - VS Code debug configs
- `pyproject.toml` - Project dependencies

---

## 🎯 Next Steps

After setup:

1. ✅ Test basic MCP tools in Claude Desktop
2. ✅ Create your instructor.md for your workflow
3. ✅ Add custom fields to database if needed
4. ✅ Create shortcuts/commands for common tasks
5. ✅ Share workflow with your team

---

**Happy Coding with FastBusiness MCP Server! 🚀**

Có thắc mắc? Tạo issue tại repository!

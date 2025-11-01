# LMDB Field Database System

## Overview

The LMDB Field Database System provides intelligent field generation for FastBusiness XML files using a Lightning Memory-Mapped Database (LMDB) with smart pattern matching and template-based fallback.

## Key Features

- **Fast LMDB Storage**: Pure Python, no compilation required
- **Smart Pattern Matching**: Automatically detects field types and applies appropriate templates
- **Lookup Type Support**: Handles autocomplete, multi-select lookup, and default fields
- **Template Fallback**: Uses common field templates when exact matches aren't found
- **AI Integration**: MCP tools for seamless AI-powered field generation

## Installation

```bash
# Install dependencies
pip install lmdb>=1.4.0

# All other dependencies are in requirements.txt
pip install -r requirements.txt
```

## Quick Start

### 1. Import Field Definitions from XML

First, populate the LMDB database from your existing FastBusiness XML files:

```bash
# Import from a directory of XML files
python scripts/import_fields_to_lmdb.py --xml-dir /path/to/xml/files --show-stats

# Import a single XML file
python scripts/import_fields_to_lmdb.py --xml-file /path/to/file.xml

# Custom database path
python scripts/import_fields_to_lmdb.py --xml-dir ./data/xml --db-path ./my_lmdb

# Overwrite existing fields
python scripts/import_fields_to_lmdb.py --xml-dir ./data/xml --overwrite
```

### 2. Use in MCP Server

The server automatically loads the LMDB database and provides three MCP tools:

#### Tool 1: `generate_field_from_lmdb` ⭐

**Main tool for generating fields - USE THIS FIRST!**

```javascript
// Example: Generate a customer code field
{
  "field_name": "ma_kh",
  "context_type": "DIR",
  "lookup_type": "default"
}

// Example: Generate quantity field with template fallback
{
  "field_name": "sl_nhap_hang",  // Not in DB, uses so_luong template
  "context_type": "GRID_INPUT",
  "lookup_type": "default"
}

// Example: Generate autocomplete lookup
{
  "field_name": "ma_kh",
  "context_type": "FILTER_VOUCHER",
  "lookup_type": "autocomplete"  // Creates ma_khat
}
```

#### Tool 2: `search_lmdb_fields`

Search for fields by pattern:

```javascript
{
  "pattern": "ma_",
  "context_type": "DIR",
  "limit": 20
}
```

#### Tool 3: `lmdb_database_stats`

Get database statistics:

```javascript
{}  // No parameters needed
```

## Smart Pattern Matching

The system intelligently detects field types and applies appropriate templates:

### Pattern Detection Rules

| Pattern | Template | Example |
|---------|----------|---------|
| `sl_*` | `so_luong` | `sl_nhap_hang` → uses `so_luong` template |
| `ngay_*` | `ngay_ct` | `ngay_lap_phieu` → uses `ngay_ct` template |
| `tien*` | `tien` | `tien_ck` → uses `tien` template |
| `*_nt` | `tien_nt` | `tien_hang_nt` → uses `tien_nt` template |
| Other | `ghi_chu`/`dien_giai` | Unknown fields → uses text template |

### Lookup Type Suffixes

| Lookup Type | Suffix | Example |
|-------------|--------|---------|
| `default` | (none) | `ma_kh` |
| `autocomplete` | `t` | `ma_khat` (single selection) |
| `lookup` | `lk` | `ma_khlk` (multi-selection) |

## How It Works

### Search Strategy

When you request a field (e.g., "thêm sl_nhap_hang"):

1. **Exact Match**: Search for `sl_nhap_hang` in the database
2. **Pattern Detection**: If not found, detect pattern (`sl_*` → quantity field)
3. **Template Lookup**: Find template field (`so_luong`)
4. **Smart Substitution**:
   - Replace field name: `so_luong` → `sl_nhap_hang`
   - Generate header: "Số lượng" → "Số lượng nhập hàng"
   - Update XML attributes

### Header Generation

The system automatically generates Vietnamese headers from field names:

```python
ma_kh          → "Mã Kh"
sl_nhap_hang   → "Số lượng Nhập Hang"
ngay_lap_phieu → "Ngày Lap Phieu"
tien_ck_nt     → "Tiền Ck (ngoại tệ)"
```

## Architecture

```
fastbusiness_mcp/
├── lmdb_adapter/
│   ├── __init__.py
│   ├── lmdb_manager.py        # Core LMDB operations
│   ├── pattern_matcher.py     # Smart pattern matching
│   └── xml_parser.py          # XML field extraction
├── tools/
│   └── generate_field_from_lmdb.py  # MCP tool
└── server.py                  # Integration with MCP server

scripts/
└── import_fields_to_lmdb.py   # Manual import script

data/
└── fields_lmdb/               # LMDB database directory
```

## Database Structure

LMDB uses named databases (one per context type):

- `DIR` - Directory/form fields
- `FILTER_VOUCHER` - Voucher filter fields
- `FILTER_NORMAL` - Normal filter fields
- `GRID_VIEW` - Grid view fields
- `GRID_INPUT` - Grid input fields

Each field is stored as:
- **Key**: Field name (e.g., `ma_kh`, `so_luong`)
- **Value**: JSON object with field definition, attributes, and XML

## Usage Examples

### Example 1: Add Customer Code Field

User says: **"Thêm mã khách hàng dạng autocomplete"**

AI calls:
```javascript
{
  "tool": "generate_field_from_lmdb",
  "field_name": "ma_kh",
  "lookup_type": "autocomplete",
  "context_type": "DIR"
}
```

Result: Returns `ma_khat` field with full XML definition.

### Example 2: Add Quantity Field (Template Fallback)

User says: **"Thêm trường số lượng nhập hàng"**

AI calls:
```javascript
{
  "tool": "generate_field_from_lmdb",
  "field_name": "sl_nhap_hang",
  "context_type": "GRID_INPUT"
}
```

Result: Field not in DB → Detects `sl_*` pattern → Uses `so_luong` template → Generates field with substituted name and header.

### Example 3: Search for Date Fields

User says: **"Có những trường ngày nào?"**

AI calls:
```javascript
{
  "tool": "search_lmdb_fields",
  "pattern": "ngay_",
  "context_type": "DIR",
  "limit": 10
}
```

Result: Lists all date fields (ngay_ct, ngay_lap, etc.)

## Advanced Usage

### Custom Database Path

```python
from fastbusiness_mcp.lmdb_adapter import LMDBManager

# Use custom path
lmdb = LMDBManager(db_path="./my_custom_lmdb")
```

### Direct API Usage

```python
from fastbusiness_mcp.lmdb_adapter import LMDBManager, FieldPatternMatcher

# Initialize
lmdb = LMDBManager()
matcher = FieldPatternMatcher(lmdb)

# Get field with smart fallback
field = matcher.get_field_with_fallback(
    context_type='DIR',
    field_name='sl_nhap_hang',
    lookup_type='default'
)

print(field['xml'])
```

### Parse and Import New XML

```python
from fastbusiness_mcp.lmdb_adapter import FastBusinessXMLParser, LMDBManager

# Parse XML
parser = FastBusinessXMLParser()
fields = parser.parse_file('my_form.xml')

# Import to LMDB
lmdb = LMDBManager()
for context_type, field_list in fields.items():
    for field_data in field_list:
        lmdb.put_field(
            context_type,
            field_data['field_name'],
            field_data['definition']
        )
```

## Benefits Over Previous Systems

| Feature | SQLite | LevelDB | LMDB |
|---------|--------|---------|------|
| Installation | ✓ Easy | ✗ Build required | ✓ Pure Python |
| Performance | ~ Medium | ✓ Fast | ✓ Very Fast |
| Transactions | ✓ ACID | ~ Limited | ✓ ACID |
| Memory-mapped | ✗ No | ✗ No | ✓ Yes |
| Multiple DBs | ✓ Tables | ✗ Separate files | ✓ Named DBs |
| Windows Python 3.13 | ✓ Works | ✗ Build fails | ✓ Works |

## Maintenance

### Check Database Size

```bash
du -sh data/fields_lmdb/
```

### Backup Database

```bash
cp -r data/fields_lmdb data/fields_lmdb.backup
```

### Clear and Rebuild

```bash
rm -rf data/fields_lmdb
python scripts/import_fields_to_lmdb.py --xml-dir /path/to/xml --show-stats
```

## Troubleshooting

### Database Not Found

If you get "LMDB not available" error:

```bash
# Install lmdb
pip install lmdb>=1.4.0

# Create database directory
mkdir -p data/fields_lmdb
```

### Empty Database

If no fields are found:

```bash
# Import your XML files
python scripts/import_fields_to_lmdb.py --xml-dir /path/to/xml --show-stats --verbose
```

### Permission Errors

```bash
# Fix permissions
chmod -R 755 data/fields_lmdb
```

## Performance

- **Database size**: ~1-10MB for typical field definitions
- **Lookup speed**: < 1ms for exact matches
- **Search speed**: < 10ms for pattern searches
- **Import speed**: ~1000 fields/second

## Future Enhancements

- [ ] Field usage statistics
- [ ] Automatic header translation (Vietnamese ↔ English)
- [ ] Field relationship mapping
- [ ] Version history for field definitions
- [ ] Export to different formats (JSON, CSV)

## Support

For issues or questions about the LMDB Field Database System, check:

1. This documentation
2. Code comments in `fastbusiness_mcp/lmdb_adapter/`
3. Import script help: `python scripts/import_fields_to_lmdb.py --help`

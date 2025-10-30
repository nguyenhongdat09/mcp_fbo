# FastBusiness MCP Server

An AI-powered MCP (Model Context Protocol) server for FastBusiness XML development. This server provides intelligent code completion, validation, and generation for FastBusiness ERP XML files.

## <¯ Features

### Core Capabilities

1. **File Type Detection** - Automatically identifies XML file types
2. **Critical Validations** - Partition, result access, parent form, lookup
3. **Automatic Fixers** - Fix common mistakes automatically
4. **Code Generators** - Generate fields, commands, scripts
5. **Field Registry** - Search and track field definitions

## =€ Quick Start

```bash
# Install
pip install -e .

# Initialize database
python scripts/init_db.py

# Configure Claude Desktop
# Add to claude_desktop_config.json:
{
  "mcpServers": {
    "fastbusiness": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"]
    }
  }
}
```

## =' Available Tools

- `detect_file_type` - Detect XML file type
- `validate_partition` - Validate partition usage (CRITICAL)
- `validate_result_access` - Validate result access (CRITICAL)
- `validate_xml_structure` - Comprehensive validation
- `fix_partition` - Auto-fix partition issues
- `fix_result_access` - Auto-fix result access
- `generate_field` - Generate field definitions
- `generate_command` - Generate SQL commands
- `generate_script` - Generate JavaScript scripts
- `search_fields` - Search field registry

##   Critical Rules

### Partition Strategy
```sql
L select * from d91$202501
 select * from @@prime$partition$current
```

### Result Access
```javascript
L var x = result[0].column_name;  // undefined!
 var x = result[0].Value;  // correct
```

### Grid Detail Parent Access
```javascript
 var f = g.get_element().parentForm;
```

### Lookup Companion Fields
```xml
<field name="ma_kh">
  <items style="AutoComplete" controller="Customer" reference="ten_kh%l"/>
</field>
<!-- MUST have companion -->
<field name="ten_kh%l" external="true" readOnly="true">
  <header v="" e=""/>
</field>
```

## =Ú Documentation

See `docs/` directory for detailed documentation.

## =Ä License

MIT License

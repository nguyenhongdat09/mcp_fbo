# YAML Config vs Python Code - When to Edit What

## Vấn đề vừa sửa: Tại sao phải sửa .py thay vì .yaml?

### ❓ Câu hỏi:
```
"Tại sao không sửa YAML config mà phải sửa code Python?"
```

### ✅ Đáp án:

**Vấn đề lần này là về LOGIC XỬ LÝ XML (WHERE to insert), không phải CONTENT (WHAT to insert)**

---

## Ranh giới giữa YAML Config và Python Code

### 📝 YAML Config được dùng cho:

#### 1. **API Reference** (YAML)
```yaml
# knowledge_base/api_reference/form_api.yaml
form_api:
  get_item_value:
    syntax: "f.getItemValue(name)"
    description: "Lấy giá trị field"
    examples:
      text: "var maKH = f.getItemValue('ma_kh');"
```

**→ Config NỘI DUNG API, cách dùng, syntax**

---

#### 2. **Code Templates** (YAML)
```yaml
# knowledge_base/api_reference/common_patterns.yaml
onchange_field:
  description: "onChange handler cho field trong Dir form"
  template: |
    function onChange$Voucher${{field_name}}(sender) {
        var f = sender.parentForm;

        // Skip in view mode
        if (f._action === 'View') {
            return;
        }

        {{user_code}}
    }
```

**→ Config TEMPLATE code, placeholder, structure**

---

#### 3. **Rules & Patterns** (YAML)
```yaml
# knowledge_base/api_reference/context_rules.yaml
critical_rules:
  partition:
    description: "NEVER use hardcoded partition tables"
    wrong: "select * from d91$202501"
    correct: "select * from @@prime$partition$current"
```

**→ Config RULES, best practices, patterns**

---

### 💻 Python Code được dùng cho:

#### 1. **XML Processing Logic** (Python)
```python
# fastbusiness_mcp/tools/xml_handler_tool.py
def _add_client_script_to_field(self, xml_content, field_name, script_content):
    # Find field definition
    pattern = rf'<field\b[^>]*\bname\s*=\s*["\']?{re.escape(field_name)}["\']?[^>]*(?:/>|>.*?</field>)'

    # Insert BEFORE </field> tag
    closing_tag_pos = field_content.rfind('</field>')
    new_field = field_content[:closing_tag_pos] + '<clientScript>...' + field_content[closing_tag_pos:]
```

**→ Logic XỬ LÝ XML: tìm vị trí, insert, modify structure**

---

#### 2. **Regex Patterns & Parsing** (Python)
```python
# Parse XML, find elements, replace content
script_match = re.search(r'<script[^>]*>(.*?)</script>', xml_content, re.DOTALL)
cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', script_content, re.DOTALL)
```

**→ Logic PARSE và MODIFY XML**

---

#### 3. **Insertion Logic** (Python)
```python
# WHERE to insert (before/after which tag)
# HOW to insert (replace/append/prepend)
if closing_tag_pos > 0:
    new_field = (
        field_content[:closing_tag_pos] +  # Before
        '<clientScript>...</clientScript>' +  # Insert
        field_content[closing_tag_pos:]   # After
    )
```

**→ Logic VỊ TRÍ insert trong XML tree**

---

## So sánh cụ thể vấn đề vừa sửa

### Vấn đề 1: clientScript position

**❌ KHÔNG thể config bằng YAML:**
```yaml
# Không thể làm thế này!
xml_insertion:
  clientScript:
    position: "before_closing_field_tag"  # ← Không work!
```

**✅ PHẢI sửa code Python:**
```python
# xml_handler_tool.py
closing_tag_pos = field_content.rfind('</field>')
new_field = field_content[:closing_tag_pos] + '<clientScript>...' + field_content[closing_tag_pos:]
```

**Lý do:** Đây là LOGIC xử lý XML tree, không phải config data

---

### Vấn đề 2: Function inside CDATA

**❌ KHÔNG thể config bằng YAML:**
```yaml
# Không thể làm thế này!
script_insertion:
  function:
    location: "inside_cdata_before_closing"  # ← Không work!
```

**✅ PHẢI sửa code Python:**
```python
# xml_handler_tool.py
cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', script_content, re.DOTALL)
new_cdata_content = cdata_content + '\n\n' + function_code + '\n'
```

**Lý do:** Đây là LOGIC tìm CDATA và insert vào đúng vị trí

---

## Khi nào sửa YAML?

### ✅ Sửa YAML khi muốn thay đổi:

#### 1. Code Content (Nội dung code)
```yaml
# Ví dụ: Thêm logic mới vào template
onchange_field:
  template: |
    function onChange$Voucher${{field_name}}(sender) {
        var f = sender.parentForm;

        // NEW: Add logging
        console.log('Field changed:', '{{field_name}}');

        if (f._action === 'View') return;

        {{user_code}}
    }
```

---

#### 2. API Recommendations
```yaml
# Ví dụ: Thêm API mới
form_api:
  clear_item:
    syntax: "f.clearItem(name)"
    description: "Xóa giá trị field"
    examples:
      basic: "f.clearItem('ma_kh');"
```

---

#### 3. Rules & Patterns
```yaml
# Ví dụ: Thêm rule mới
critical_rules:
  async_operations:
    description: "Use await for async operations"
    wrong: "f.request('GetData', 'GetData', [], sender);"
    correct: "await f.requestAsync('GetData', 'GetData', [], sender);"
```

---

## Khi nào sửa Python Code?

### ✅ Sửa Code khi muốn thay đổi:

#### 1. XML Processing Logic
- Vị trí insert elements
- Cách parse XML structure
- Cách tìm và replace tags

#### 2. Regex Patterns
- Pattern để tìm fields
- Pattern để tìm script section
- Pattern để match XML structures

#### 3. Insertion/Modification Logic
- Before/after which tag
- Inside/outside which element
- Replace/append/prepend

---

## Tóm tắt

| Thay đổi | Sửa YAML | Sửa Code |
|----------|----------|----------|
| **Nội dung code template** | ✅ | ❌ |
| **API syntax & examples** | ✅ | ❌ |
| **Rules & patterns** | ✅ | ❌ |
| **Vị trí insert XML** | ❌ | ✅ |
| **Logic parse XML** | ❌ | ✅ |
| **Regex patterns** | ❌ | ✅ |
| **XML tree manipulation** | ❌ | ✅ |

---

## Ví dụ thực tế

### Scenario 1: Muốn thêm logging vào function

**→ SỬA YAML:**
```yaml
# common_patterns.yaml
onchange_field:
  template: |
    function onChange$Voucher${{field_name}}(sender) {
        console.log('[DEBUG] onChange:', '{{field_name}}');  # ← Thêm dòng này
        var f = sender.parentForm;
        ...
    }
```

---

### Scenario 2: Muốn đổi vị trí insert clientScript

**→ SỬA CODE:**
```python
# xml_handler_tool.py
# BEFORE: Insert after opening tag
new_field = f'{field_opening}>\n<clientScript>...'

# AFTER: Insert before closing tag
closing_tag_pos = field_content.rfind('</field>')
new_field = field_content[:closing_tag_pos] + '<clientScript>...'
```

---

## Kết luận

**YAML = DATA/CONFIG (What to generate)**
- Templates
- Patterns
- Rules
- Content

**Python = LOGIC (How & Where to process)**
- XML parsing
- Element positioning
- Tree manipulation
- Regex matching

**Vấn đề lần này:**
- ❌ KHÔNG phải về "nội dung code" → Không sửa YAML
- ✅ Về "vị trí insert XML" → PHẢI sửa Python code

Đó là lý do tôi sửa `.py` thay vì `.yaml`! 🎯

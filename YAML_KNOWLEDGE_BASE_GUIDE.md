# Hướng Dẫn Chi Tiết: YAML Knowledge Base Files

## 📚 Mục Lục
1. [YAML là gì và tại sao dùng YAML?](#yaml-là-gì)
2. [Quy tắc cơ bản khi viết YAML](#quy-tắc-yaml)
3. [Cấu trúc thư mục Knowledge Base](#cấu-trúc-thư-mục)
4. [Chi tiết từng file YAML](#chi-tiết-file-yaml)
5. [Cách thêm/sửa/xóa rules](#cách-chỉnh-sửa)
6. [Examples cụ thể](#examples)
7. [Cách AI sử dụng các file này](#cách-ai-dùng)

---

## YAML là gì?

### Định nghĩa
YAML = "YAML Ain't Markup Language"
- **File text thuần túy** (như .txt, .md) nhưng có cấu trúc
- **Dễ đọc cho con người** hơn JSON hoặc XML
- **Python đọc được** qua thư viện `yaml`

### Tại sao dùng YAML thay vì code Python?

**❌ Nếu dùng Python code:**
```python
# rules.py
API_RULES = {
    'grid_detail_must_get_parent': {
        'priority': 'CRITICAL',
        'must_do': [
            {'step': 1, 'code': 'var f = g.get_element().parentForm;'}
        ]
    }
}
```
→ Mỗi lần sửa phải chỉnh code Python!

**✅ Dùng YAML:**
```yaml
# context_rules.yaml
api_selection_rules:
  - rule_id: grid_detail_must_get_parent
    priority: CRITICAL
    must_do:
      - step: 1
        code: var f = g.get_element().parentForm;
```
→ Chỉ cần sửa text file, KHÔNG cần động vào code Python!

### Lợi ích
- ✅ **Dễ chỉnh sửa:** Chỉ cần editor text, không cần biết Python
- ✅ **Dễ đọc:** Format rõ ràng, có thụt lề
- ✅ **Tách biệt logic:** Data (YAML) tách khỏi code (Python)
- ✅ **Dễ mở rộng:** Thêm rule mới không cần sửa code
- ✅ **Version control:** Git dễ track changes trong YAML

---

## Quy Tắc YAML

### 1. Indentation (Thụt lề)
**CỰC KỲ QUAN TRỌNG!** YAML dùng thụt lề để phân cấp, như Python.

```yaml
# ĐÚNG ✅
parent:
  child1: value1
  child2: value2
    grandchild: value3    # Thụt lề 2 spaces từ child2

# SAI ❌
parent:
child1: value1           # Thiếu thụt lề!
  child2: value2
   grandchild: value3    # Sai số spaces!
```

**Quy tắc:**
- Dùng **2 spaces** cho mỗi cấp thụt lề
- **KHÔNG dùng Tab!** Chỉ dùng spaces
- Cùng cấp phải cùng số spaces

### 2. Key-Value Pairs
```yaml
key: value                    # String
number: 123                   # Number
boolean: true                 # Boolean
list_value:                   # List
  - item1
  - item2
object_value:                 # Object/Dict
  sub_key1: value1
  sub_key2: value2
```

### 3. Strings (Chuỗi)
```yaml
# Simple string - không cần quotes
name: John Doe

# String có dấu : hoặc # - CẦN quotes
description: "Value: 123"     # Có dấu :
note: "This is # comment"     # Có dấu #

# Multi-line string - dùng |
template: |
  function onChange(sender) {
      var f = sender.parentForm;
      // Multiple lines
  }

# Multi-line folded - dùng >
description: >
  This is a long text
  that will be folded
  into a single line.
```

### 4. Lists (Danh sách)
```yaml
# Style 1: Dấu gạch ngang
fruits:
  - apple
  - banana
  - orange

# Style 2: Inline (hiếm dùng)
fruits: [apple, banana, orange]
```

### 5. Comments (Chú thích)
```yaml
# This is a comment
key: value    # Inline comment

# Multi-line comment:
# Line 1
# Line 2
another_key: value
```

### 6. Anchors & References (Tái sử dụng)
```yaml
# Define anchor với &
default_config: &defaults
  timeout: 30
  retry: 3

# Reference với *
api_1:
  <<: *defaults        # Inherit từ defaults
  url: /api/v1

api_2:
  <<: *defaults
  url: /api/v2
  timeout: 60          # Override timeout
```

---

## Cấu Trúc Thư Mục

```
knowledge_base/
├── api_reference/              # YAML files
│   ├── context_rules.yaml      # Context detection & API selection rules
│   ├── form_api.yaml           # Form API (f.xxx) reference
│   ├── grid_api.yaml           # Grid API (g.xxx) reference
│   └── common_patterns.yaml    # Code patterns & snippets
│
└── (Có thể thêm folder khác sau này)
    ├── examples/               # Example code
    ├── templates/              # Code templates
    └── ...
```

**Mỗi file có mục đích riêng:**
- `context_rules.yaml` → AI biết đang ở context nào (Dir, Grid, etc.)
- `form_api.yaml` → API reference cho Form (f.xxx)
- `grid_api.yaml` → API reference cho Grid (g.xxx)
- `common_patterns.yaml` → Code patterns có thể tái sử dụng

---

## Chi Tiết File YAML

### 1. context_rules.yaml

**Mục đích:** Dạy AI cách phát hiện context và chọn API đúng

**Cấu trúc tổng quan:**
```yaml
context_detection:          # Phần 1: Detect file type
  file_types: {...}
  grid_subtypes: {...}

api_selection_rules:        # Phần 2: Critical rules
  - rule_id: ...
    priority: ...
    must_do: ...

decision_tree: {...}        # Phần 3: Decision tree

api_cheat_sheet: {...}      # Phần 4: Quick reference
```

#### Phần 1: Context Detection

**File Types (Dir, Grid, Filter):**
```yaml
context_detection:
  file_types:
    Dir:
      description: "Form nhập liệu (voucher/category)"
      path_pattern: "\\Dir\\"              # Đường dẫn chứa \Dir\
      xml_tag: "<dir>"                     # Tag XML chính
      primary_object: "f"                  # Object chính là f
      primary_api: "form_api"              # Dùng Form API
      typical_usage:
        - "Data entry forms (invoices, purchase orders)"
        - "Master data forms (customers, products)"

    Grid:
      description: "Bảng dữ liệu (grid)"
      path_pattern: "\\Grid\\"
      xml_tag: "<grid>"
      primary_object: "g"
      primary_api: "grid_api"
      has_subtypes: true                   # Có subtypes (Detail/View)

    Filter:
      description: "Form filter cho báo cáo"
      path_pattern: "\\Filter\\"
      xml_tag: "<dir>"
      primary_object: "f"
      primary_api: "form_api"
```

**Grid Subtypes (GridDetail vs GridView):**
```yaml
  grid_subtypes:
    GridDetail:
      description: "Grid nhúng trong form (chi tiết phiếu)"
      detection:
        xml_attribute: 'type="Detail"'     # Có attribute type="Detail"
      characteristics:
        - "Embedded in a Dir form"
        - "Has parent form access"         # Có parent form
        - "Used for voucher details"
      primary_object: "g"
      secondary_object: "f"                # Có thêm object f
      primary_api: "grid_api"
      secondary_api: "form_api"
      has_parent_form: true                # CRITICAL!

    GridView:
      description: "Grid độc lập (danh sách, tra cứu)"
      detection:
        xml_tags:
          - "<queries>"                    # Có queries
          - "<toolbar>"                    # Có toolbar
        field_attributes:
          - "allowSorting"                 # Có sorting
          - "allowFilter"                  # Có filter
      characteristics:
        - "Standalone grid"
        - "NO parent form"                 # KHÔNG có parent form
        - "Has queries and toolbar"
      primary_object: "g"
      primary_api: "grid_api"
      has_parent_form: false               # CRITICAL!
```

**Cách thêm file type mới:**
```yaml
  file_types:
    # ... existing types ...

    Lookup:                                # NEW file type
      description: "Lookup control"
      path_pattern: "\\Lookup\\"
      xml_tag: "<lookup>"
      primary_object: "l"
      primary_api: "lookup_api"
      typical_usage:
        - "Customer lookup"
        - "Product lookup"
```

#### Phần 2: API Selection Rules (CRITICAL!)

**Format của 1 rule:**
```yaml
api_selection_rules:
  - rule_id: "grid_detail_must_get_parent"    # ID duy nhất
    priority: "CRITICAL"                      # Mức độ: CRITICAL/HIGH/MEDIUM
    context: "Grid Detail"                    # Áp dụng cho context nào

    reason: "Grid Detail cần truy xuất cả grid và parent form"

    must_do:                                  # Các bước BẮT BUỘC
      - step: 1
        code: "var f = g.get_element().parentForm;"
        reason: "MUST get parent form before any other operations"

      - step: 2
        code: "Use both g.xxx for grid and f.xxx for parent form"
        reason: "Grid Detail can access both grid and parent form"

    must_not_do:                              # KHÔNG được làm
      - "Don't access parent form directly as f"
      - "Don't skip parent form initialization"

    example: |                                # Example code
      function load$GridAPDetail$(g) {
          var f = g.get_element().parentForm;  // Step 1
          var tyGia = f.getItemValue('ty_gia'); // Step 2: use f.xxx

          g.$a = {
              gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]'  // $ prefix!
          };
      }
```

**Các rules quan trọng:**

1. **grid_detail_must_get_parent** - MUST get parent form trong Grid Detail
2. **response_access_by_index** - Response results access bằng index
3. **grid_view_no_parent** - Grid View KHÔNG có parent form
4. **form_use_f_api** - Form chỉ dùng f.xxx API
5. **grid_parent_field_calculation** - Parent fields dùng $ prefix

**Cách thêm rule mới:**
```yaml
api_selection_rules:
  # ... existing rules ...

  - rule_id: "my_new_rule"                    # NEW rule
    priority: "HIGH"
    context: "Filter"
    reason: "Filter forms need special handling"
    must_do:
      - step: 1
        code: "f.setFilterValue('date_from', ...)"
        reason: "Filter uses setFilterValue instead of setItemValue"
    example: |
      function active$Form$(f) {
          f.setFilterValue('date_from', new Date());
      }
```

#### Phần 3: Decision Tree

**Dạng flow chart cho AI:**
```yaml
decision_tree:
  root:
    question: "What is the file type?"
    branches:
      - condition: "Path contains \\Dir\\ AND no XMLWhenFilterLoading"
        answer: "Dir (Form)"
        next_question: "Does it have grid detail inside?"
        sub_branches:
          - condition: "Has <grid type=\"Detail\">"
            answer: "Dir with Grid Detail"
            recommendations:
              - "Use f.xxx for form fields"
              - "In grid scripts, use g.xxx AND get parent form"

          - condition: "No grid detail"
            answer: "Simple Dir form"
            recommendations:
              - "Use f.xxx API only"

      - condition: "Path contains \\Grid\\"
        answer: "Grid"
        next_question: "Is it Grid Detail or Grid View?"
        sub_branches:
          - condition: "Has type=\"Detail\""
            answer: "Grid Detail"
            critical_rules:
              - "grid_detail_must_get_parent"

          - condition: "Has <queries> or <toolbar>"
            answer: "Grid View"
            critical_rules:
              - "grid_view_no_parent"
```

#### Phần 4: API Cheat Sheet

**Quick reference cho AI:**
```yaml
api_cheat_sheet:
  by_context:
    "Dir (Form)":
      primary_object: "f"
      common_operations:
        get_value: "f.getItemValue('field_name')"
        set_value: "f.setItemValue('field_name', value)"
        check_action: "if (f._action === 'New') {...}"
      critical_notes:
        - "Always use f.xxx API"
        - "Get form from sender.parentForm in event handlers"

    "Grid Detail":
      primary_object: "g"
      secondary_object: "f"
      common_operations:
        get_parent: "var f = g.get_element().parentForm;"
        get_cell: "g._getItemValue(row, col)"
        set_cell: "g._setItemValue(row, col, value)"
        parent_field_in_calc: "[$ty_gia]"  # $ prefix!
      critical_notes:
        - "MUST get parent form first!"
        - "Use $ prefix for parent fields in calculations"
```

**Cách thêm shortcut mới:**
```yaml
api_cheat_sheet:
  by_context:
    # ... existing contexts ...

    "Filter":                              # NEW context
      primary_object: "f"
      common_operations:
        set_filter: "f.setFilterValue('field', value)"
        get_filter: "f.getFilterValue('field')"
      critical_notes:
        - "Use setFilterValue, not setItemValue"
```

---

### 2. form_api.yaml

**Mục đích:** API reference đầy đủ cho Form API (f.xxx)

**Cấu trúc tổng quan:**
```yaml
form_api:                      # Root key
  value_operations: {...}      # Get/Set values
  form_state: {...}            # Form state
  focus_operations: {...}      # Focus control
  validation: {...}            # Validation
  ajax_operations: {...}       # AJAX requests
  grid_access: {...}           # Access grid detail
  button_operations: {...}     # Button operations
  lookup_operations: {...}     # Lookup operations

common_patterns: {...}         # Common patterns
anti_patterns: {...}           # What NOT to do
```

#### Value Operations

**Format của 1 API operation:**
```yaml
form_api:
  value_operations:
    get_item_value:                        # Operation name
      syntax: "f.getItemValue(name)"       # Cú pháp

      parameters:                          # Tham số
        - name: "name"
          type: "string"
          description: "Field name"
          required: true

      returns: "any (number | Date | string | boolean)"

      description: "Lấy giá trị của field (universal getter)"

      use_when:                            # Khi nào dùng
        - "RECOMMENDED for all get operations"
        - "Works for ALL field types"

      examples:                            # Examples
        - code: "var soLuong = f.getItemValue('so_luong');"
          description: "Get số lượng (number)"

        - code: "var ngayCT = f.getItemValue('ngay_ct');"
          description: "Get ngày (Date)"

        - code: "var maKH = f.getItemValue('ma_kh');"
          description: "Get mã (string)"

      important: "Works for ALL field types, recommended universal getter"

      see_also:                            # Related APIs
        - "getItem"
        - "setItemValue"
```

**Cách thêm API mới:**
```yaml
form_api:
  value_operations:
    # ... existing operations ...

    get_item_text:                         # NEW API
      syntax: "f.getItemText(name)"
      parameters:
        - name: "name"
          type: "string"
          description: "Field name"
          required: true
      returns: "string"
      description: "Lấy text hiển thị của field (for lookup)"
      use_when:
        - "Get display text of lookup field"
        - "Get combo box selected text"
      examples:
        - code: "var tenKH = f.getItemText('ma_kh');"
          description: "Get tên khách hàng (not mã)"
```

#### Form State

```yaml
form_api:
  form_state:
    action_property:
      syntax: "f._action"
      type: "string"
      possible_values:
        - value: "New"
          description: "Form đang tạo mới"
        - value: "Edit"
          description: "Form đang sửa"
        - value: "View"
          description: "Form đang xem (read-only)"

      common_usage: |
        if (f._action === 'New') {
            // Set default values
        }

      critical_note: "Always check _action in event handlers to avoid errors in View mode"
```

#### Anti-Patterns (Những gì KHÔNG nên làm)

```yaml
anti_patterns:
  direct_field_access:
    wrong: "f.fields.ma_kh = 'KH001';"          # SAI!
    correct: "f.setItemValue('ma_kh', 'KH001');" # ĐÚNG!
    reason: "Direct field access bypasses validation and change detection"

  wrong_getter:
    wrong: "var value = f.getItem('ma_kh').value;"  # SAI!
    correct: "var value = f.getItemValue('ma_kh');" # ĐÚNG!
    reason: "getItemValue is universal getter, works for all types"

  missing_action_check:
    wrong: |
      function onChange$Voucher$ma_kh(sender) {
          var f = sender.parentForm;
          f.setItemValue('ten_kh', '...');  // Lỗi khi View mode!
      }
    correct: |
      function onChange$Voucher$ma_kh(sender) {
          var f = sender.parentForm;
          if (f._action === 'View') return;  // Check trước!
          f.setItemValue('ten_kh', '...');
      }
    reason: "View mode is read-only, setValue will cause error"
```

---

### 3. grid_api.yaml

**Mục đích:** API reference đầy đủ cho Grid API (g.xxx)

**Cấu trúc tương tự form_api.yaml:**
```yaml
grid_api:
  cell_operations: {...}       # Get/Set cell values
  grid_state: {...}            # Grid state (activeRow, etc.)
  row_operations: {...}        # Add/Delete rows
  parent_access: {...}         # Access parent form (Grid Detail only!)
  calculation: {...}           # g.$a calculations
  context_specific: {...}      # GridDetail vs GridView differences

common_patterns: {...}
anti_patterns: {...}
```

#### Parent Access (CRITICAL cho Grid Detail!)

```yaml
grid_api:
  parent_access:
    get_parent_form:
      syntax: "g.get_element().parentForm"
      returns: "Form object"

      critical: "MUST call this FIRST in Grid Detail scripts!"

      context: "Grid Detail ONLY (not Grid View)"

      example: |
        function load$GridAPDetail$(g) {
            var f = g.get_element().parentForm;  // CRITICAL!
            var tyGia = f.getItemValue('ty_gia');

            g.$a = {
                gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]'  // $ prefix!
            };
        }

      error_if_missing: "Cannot access parent form fields without this"

      must_do:
        - "Call this BEFORE any parent form access"
        - "Store in variable f for later use"
```

#### Calculation Operations

```yaml
grid_api:
  calculation:
    grid_calculation:
      syntax: "g.$a = { ... }"
      description: "Define grid calculations and aggregations"

      calculation_types:
        within_grid:
          example: "tien: '[tien]:=[so_luong]*[gia]'"
          description: "Calculate using grid columns only"

        from_parent_form:
          example: "gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]'"
          description: "Calculate using parent form field ($ prefix!)"
          critical: "MUST use $ prefix for parent fields: [$field_name]"

        aggregate_to_parent:
          example: "t_tien: ['t_tien', 'tien']"
          description: "Sum grid column to parent form field"
          format: "[parent_field, grid_column]"

      full_example: |
        g.$a = {
            // Within grid
            tien: '[tien]:=[so_luong]*[gia]',

            // From parent ($ prefix!)
            gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]',
            tien_vnd: '[tien_vnd]:=[tien_nt]*[$ty_gia]',

            // Aggregate to parent
            t_tien: ['t_tien', 'tien'],
            t_tien_vnd: ['t_tien_vnd', 'tien_vnd']
        };
```

#### Context-Specific Usage (GridDetail vs GridView)

```yaml
grid_api:
  context_specific:
    grid_detail:
      can_do:
        - "Access parent form: g.get_element().parentForm"
        - "Use parent fields in calculations: [$field_name]"
        - "Aggregate to parent form"
        - "Call parent form methods: f.setItemValue(...)"

      must_do:
        - "Get parent form FIRST"
        - "Use $ prefix for parent fields"

      example: |
        function onChange$Voucher$GridAPDetail$so_luong(sender) {
            var g = sender.grid;
            var f = g.get_element().parentForm;  // MUST!
            // Can use both g.xxx and f.xxx
        }

    grid_view:
      can_do:
        - "Use g.xxx API only"
        - "Access grid data"
        - "Row operations"

      cannot_do:
        - "Access parent form (doesn't exist!)"
        - "Use $ prefix in calculations"
        - "Call f.xxx methods"

      example: |
        function load$GridView$(g) {
            // Only g.xxx, NO parent form!
            g._rows.forEach(function(row) {
                // Process rows
            });
        }
```

---

### 4. common_patterns.yaml

**Mục đích:** Code patterns có thể tái sử dụng

**Cấu trúc:**
```yaml
patterns:                      # Code patterns
  form_init_new: {...}
  form_field_onchange: {...}
  grid_detail_init: {...}
  # ... more patterns

snippets:                      # Code snippets (nhỏ hơn patterns)
  get_parent_form_from_grid: {...}
  skip_view_mode: {...}
  # ... more snippets
```

#### Patterns

**Format của 1 pattern:**
```yaml
patterns:
  form_load_data_onchange:                    # Pattern name
    name: "Load data from server on field change"
    description: "Khi field thay đổi, gọi AJAX load dữ liệu từ server"
    context: "Form (Dir)"                     # Context áp dụng
    location: "onChange handler + ResponseComplete"

    when_to_use:                              # Khi nào dùng pattern này
      - "User changes lookup field (ma_kh, ma_vt)"
      - "Need to load related data (ten_kh, gia)"
      - "Server has action to get data"

    template: |                               # Template với {{variables}}
      function onChange$Voucher${{field_name}}(sender) {
          var f = sender.parentForm;

          // Skip view mode
          if (f._action === 'View') {
              return;
          }

          var value = f.getItemValue('{{field_name}}');

          if (value) {
              // Call AJAX
              f.request('{{action_id}}', '{{context}}', ['{{field_name}}'], sender);
          }
      }

      function on$Form$ResponseComplete(sender, e) {
          var f = e.object;

          if (e.type.Context === '{{context}}') {
              var result = e.type.Result;

              // CRITICAL: Access by INDEX, not property name!
              var value1 = result[0].Value;  // First column
              var value2 = result[1].Value;  // Second column

              // Set to form
              f.setItemValue('{{target_field_1}}', value1);
              f.setItemValue('{{target_field_2}}', value2);
          }
      }

    variables:                                # Các biến cần thay thế
      - name: "field_name"
        description: "Field name triggers change (e.g., ma_kh)"
        example: "ma_kh"

      - name: "action_id"
        description: "Server action ID"
        example: "GetCustomer"

      - name: "context"
        description: "Context string to identify response"
        example: "GetCustomerInfo"

      - name: "target_field_1"
        description: "First target field to set"
        example: "ten_kh"

      - name: "target_field_2"
        description: "Second target field to set"
        example: "dia_chi"

    example: |                                # Example cụ thể
      // When ma_kh changes, load customer info
      function onChange$Voucher$ma_kh(sender) {
          var f = sender.parentForm;
          if (f._action === 'View') return;

          var maKH = f.getItemValue('ma_kh');
          if (maKH) {
              f.request('GetCustomer', 'GetCustomerInfo', ['ma_kh'], sender);
          }
      }

      function on$Form$ResponseComplete(sender, e) {
          var f = e.object;
          if (e.type.Context === 'GetCustomerInfo') {
              var result = e.type.Result;
              var tenKH = result[0].Value;   // First column: ten_kh
              var diaChi = result[1].Value;  // Second column: dia_chi

              f.setItemValue('ten_kh', tenKH);
              f.setItemValue('dia_chi', diaChi);
          }
      }

    notes:                                    # Ghi chú quan trọng
      - "Response result accessed by INDEX (result[0], result[1])"
      - "Context string must match in request() and ResponseComplete"
      - "Always check f._action before setValue in onChange"
```

**Cách thêm pattern mới:**
```yaml
patterns:
  # ... existing patterns ...

  my_custom_pattern:                         # NEW pattern
    name: "My custom pattern"
    description: "Description of what it does"
    context: "Form (Dir)"
    location: "Where to put this code"

    when_to_use:
      - "Use case 1"
      - "Use case 2"

    template: |
      function myFunction() {
          // Template with {{variables}}
          var x = {{variable_name}};
      }

    variables:
      - name: "variable_name"
        description: "What this variable is"
        example: "example_value"

    example: |
      // Concrete example
      function myFunction() {
          var x = 123;
      }
```

#### Snippets

**Format của 1 snippet (nhỏ gọn hơn pattern):**
```yaml
snippets:
  get_parent_form_from_grid:
    code: "var f = g.get_element().parentForm;"
    description: "Get parent form from grid (Grid Detail only)"
    context: "Grid Detail"
    critical: true                           # Đánh dấu CRITICAL

  skip_view_mode:
    code: |
      if (f._action === 'View') {
          return;
      }
    description: "Skip execution in View mode"
    context: "Form (Dir)"
    critical: true

  validate_required_field:
    code: |
      if (!f.getItemValue('{{field_name}}')) {
          alert('{{field_name}} is required!');
          return false;
      }
    description: "Validate required field"
    context: "Form (Dir)"
    variables:
      - name: "field_name"
        example: "ma_kh"
```

**Cách thêm snippet mới:**
```yaml
snippets:
  # ... existing snippets ...

  my_snippet:                                # NEW snippet
    code: "// Your code here"
    description: "What this snippet does"
    context: "Where to use"
    critical: false                          # true if CRITICAL
```

---

## Cách Chỉnh Sửa

### Thêm Rule Mới

**Ví dụ: Thêm rule cho Filter context**

1. Mở `context_rules.yaml`
2. Tìm section `api_selection_rules:`
3. Thêm rule mới:

```yaml
api_selection_rules:
  # ... existing rules ...

  - rule_id: "filter_use_set_filter_value"  # NEW
    priority: "HIGH"
    context: "Filter"
    reason: "Filter forms use setFilterValue instead of setItemValue"

    must_do:
      - step: 1
        code: "f.setFilterValue('field_name', value)"
        reason: "Filter has different API for setting values"

    must_not_do:
      - "Don't use f.setItemValue in Filter forms"

    example: |
      function active$Form$(f) {
          // CORRECT for Filter
          f.setFilterValue('date_from', new Date());

          // WRONG for Filter
          // f.setItemValue('date_from', new Date());
      }
```

### Thêm API Operation Mới

**Ví dụ: Thêm API mới vào form_api.yaml**

1. Mở `form_api.yaml`
2. Chọn category phù hợp (hoặc tạo category mới)
3. Thêm operation:

```yaml
form_api:
  value_operations:
    # ... existing operations ...

    get_item_enabled:                        # NEW API
      syntax: "f.getItem(name).disabled"
      parameters:
        - name: "name"
          type: "string"
          description: "Field name"
          required: true
      returns: "boolean"
      description: "Check if field is enabled/disabled"
      examples:
        - code: "var isDisabled = f.getItem('ma_kh').disabled;"
          description: "Check if ma_kh is disabled"
      use_when:
        - "Need to check field state before operation"
```

### Thêm Pattern Mới

**Ví dụ: Pattern cho Grid Detail calculate total**

1. Mở `common_patterns.yaml`
2. Tìm section `patterns:`
3. Thêm pattern:

```yaml
patterns:
  # ... existing patterns ...

  grid_detail_calculate_total:               # NEW pattern
    name: "Calculate total in Grid Detail"
    description: "Tính tổng tiền và cập nhật lên form cha"
    context: "Grid Detail"
    location: "load$GridName$ function"

    when_to_use:
      - "Need to sum grid column to parent form"
      - "Auto-calculate total amount"

    template: |
      function load${{grid_name}}$(g) {
          var f = g.get_element().parentForm;

          g.$a = {
              // Calculate in grid
              {{grid_calc}},

              // Aggregate to parent
              {{aggregate_calc}}
          };
      }

    variables:
      - name: "grid_name"
        description: "Grid name"
        example: "GridAPDetail"

      - name: "grid_calc"
        description: "Grid calculation formula"
        example: "tien: '[tien]:=[so_luong]*[gia]'"

      - name: "aggregate_calc"
        description: "Aggregate to parent formula"
        example: "t_tien: ['t_tien', 'tien']"

    example: |
      function load$GridAPDetail$(g) {
          var f = g.get_element().parentForm;

          g.$a = {
              tien: '[tien]:=[so_luong]*[gia]',
              t_tien: ['t_tien', 'tien']
          };
      }
```

### Sửa Existing Content

**Ví dụ: Sửa description của 1 API**

1. Mở file chứa API cần sửa
2. Tìm API bằng search (Ctrl+F)
3. Sửa content:

```yaml
# BEFORE
form_api:
  value_operations:
    get_item_value:
      description: "Get field value"

# AFTER
form_api:
  value_operations:
    get_item_value:
      description: "Lấy giá trị của field (universal getter)"
      important: "Works for ALL field types - recommended!"
```

### Xóa Content

**Cẩn thận khi xóa!** Check xem có code Python nào đang dùng không.

```yaml
# Xóa 1 API operation
form_api:
  value_operations:
    # old_api: {...}              # Comment out thay vì xóa ngay
    get_item_value: {...}

# Sau khi confirm không ai dùng, xóa hẳn
```

---

## Examples

### Example 1: Add New Context Type

**Yêu cầu:** Thêm Popup context (form popup)

**Bước 1: Thêm vào context_rules.yaml**
```yaml
context_detection:
  file_types:
    # ... existing types ...

    Popup:
      description: "Form popup (dialog)"
      path_pattern: "\\Popup\\"
      xml_tag: "<dir>"
      xml_attribute: 'popup="true"'
      primary_object: "f"
      primary_api: "form_api"
      typical_usage:
        - "Quick data entry"
        - "Confirmation dialogs"
      special_notes:
        - "Smaller form, limited fields"
        - "Usually has OK/Cancel buttons"
```

**Bước 2: Thêm API cheat sheet**
```yaml
api_cheat_sheet:
  by_context:
    # ... existing contexts ...

    "Popup":
      primary_object: "f"
      common_operations:
        get_value: "f.getItemValue('field_name')"
        set_value: "f.setItemValue('field_name', value)"
        close_popup: "f.close()"
      critical_notes:
        - "Same API as Dir forms"
        - "Use f.close() to close popup"
```

### Example 2: Add Grid Calculation Pattern

**Yêu cầu:** Pattern tính thuế VAT trong grid

**Thêm vào common_patterns.yaml:**
```yaml
patterns:
  grid_detail_calculate_vat:
    name: "Calculate VAT in Grid Detail"
    description: "Tính thuế VAT và thành tiền có VAT"
    context: "Grid Detail"
    location: "load$GridName$ function"

    template: |
      function load${{grid_name}}$(g) {
          var f = g.get_element().parentForm;

          // Get VAT rate from parent form
          var vatRate = f.getItemValue('{{vat_rate_field}}') || 10;

          g.$a = {
              // Base amount
              tien: '[tien]:=[so_luong]*[gia]',

              // VAT amount
              tien_vat: '[tien_vat]:=[tien]*' + (vatRate/100),

              // Total with VAT
              tong_tien: '[tong_tien]:=[tien]+[tien_vat]',

              // Aggregate to parent
              t_tien: ['t_tien', 'tien'],
              t_vat: ['t_vat', 'tien_vat'],
              t_tong: ['t_tong', 'tong_tien']
          };
      }

    variables:
      - name: "grid_name"
        example: "GridAPDetail"
      - name: "vat_rate_field"
        description: "VAT rate field in parent form"
        example: "vat_rate"

    example: |
      function load$GridAPDetail$(g) {
          var f = g.get_element().parentForm;
          var vatRate = f.getItemValue('vat_rate') || 10;

          g.$a = {
              tien: '[tien]:=[so_luong]*[gia]',
              tien_vat: '[tien_vat]:=[tien]*0.1',  // 10% VAT
              tong_tien: '[tong_tien]:=[tien]+[tien_vat]',

              t_tien: ['t_tien', 'tien'],
              t_vat: ['t_vat', 'tien_vat'],
              t_tong: ['t_tong', 'tong_tien']
          };
      }
```

### Example 3: Add Critical Rule

**Yêu cầu:** Rule về validation trước khi save

**Thêm vào context_rules.yaml:**
```yaml
api_selection_rules:
  - rule_id: "form_validate_before_save"
    priority: "HIGH"
    context: "Form (Dir)"
    reason: "Validate required fields before allowing save"

    must_do:
      - step: 1
        code: "Implement beforeSave$Form$ function"
        reason: "This is where validation happens"

      - step: 2
        code: "Return false to prevent save"
        reason: "Returning false cancels the save operation"

      - step: 3
        code: "Show user-friendly error messages"
        reason: "User needs to know what's wrong"

    example: |
      function beforeSave$Form$(f) {
          // Validate required fields
          if (!f.getItemValue('ma_kh')) {
              alert('Mã khách hàng không được để trống!');
              f.getItem('ma_kh').focus();
              return false;  // Cancel save
          }

          if (!f.getItemValue('ngay_ct')) {
              alert('Ngày chứng từ không được để trống!');
              f.getItem('ngay_ct').focus();
              return false;
          }

          // Validation passed
          return true;
      }
```

---

## Cách AI Dùng

### Workflow của AI khi user yêu cầu

**User:** "Thêm onchange cho ma_kh thì load customer info"

**AI's workflow:**

1. **Detect trigger keywords:** "onchange", "ma_kh", "load"
2. **Call tool:** `add_onchange_handler`
3. **Tool internally uses YAML:**

```python
# In xml_handler_tool.py
def add_onchange_handler(file_path, field_name, handler_code):
    # Step 1: Load YAML
    context = context_detector.detect_from_file(file_path)
    # → Reads context_rules.yaml
    # → Determines: "This is Dir file"

    # Step 2: Generate function name
    function_name = generate_function_name('onchange', field_name, context)
    # → Uses context_rules.yaml rules
    # → Result: "onChange$Voucher$ma_kh"

    # Step 3: Load pattern
    pattern = knowledge_engine.get_pattern('form_load_data_onchange')
    # → Reads common_patterns.yaml
    # → Gets template with {{variables}}

    # Step 4: Substitute variables
    code = substitute_variables(pattern.template, {
        'field_name': 'ma_kh',
        'action_id': 'GetCustomer',
        'context': 'GetCustomerInfo'
    })
    # → Generates complete function

    # Step 5: Modify XML
    # → Add <clientScript>
    # → Add <script> function
```

### Ví dụ cụ thể

**Scenario:** User đang edit file `Invoice.xml` (Dir file)

**User:** "Thêm handler khi focus vào ma_kh thì highlight"

**AI process:**

```python
# 1. AI calls tool
result = xml_handler.add_onfocus_handler(
    file_path='e:/FBO/Controllers/Dir/Invoice.xml',
    field_name='ma_kh',
    handler_code='$(this).css("background", "yellow");'
)

# 2. Tool loads context (from context_rules.yaml)
context = context_detector.detect_from_file('Invoice.xml')
# Result: {
#   'file_type': 'Dir',
#   'primary_object': 'f',
#   'primary_api': 'form_api',
#   'critical_rules': ['form_use_f_api']
# }

# 3. Generate function name (using context_rules.yaml rules)
function_name = 'onFocus$Voucher$ma_kh'

# 4. Generate function (using form_api.yaml knowledge)
function_code = '''
function onFocus$Voucher$ma_kh(sender) {
    var f = sender.parentForm;  // from form_api.yaml
    $(this).css("background", "yellow");
}
'''

# 5. Modify XML
# Add: <clientScript>onfocus="onFocus$Voucher$ma_kh(this);"</clientScript>
# Add function to <script> section
```

### Khi nào AI query YAML?

**Tình huống 1: User hỏi API**
```
User: "Làm sao get giá trị field trong form?"

AI workflow:
1. Identify: User asking about Form API
2. Query form_api.yaml:
   knowledge_engine.get_form_api_operation('value_operations', 'get_item_value')
3. Get result from YAML
4. Format và trả lời user
```

**Tình huống 2: User hỏi pattern**
```
User: "Pattern để tính tổng tiền trong grid là gì?"

AI workflow:
1. Identify: User asking about pattern
2. Query common_patterns.yaml:
   knowledge_engine.search_patterns(query='total', context='Grid Detail')
3. Get matching patterns
4. Show patterns to user
```

**Tình huống 3: User báo lỗi code**
```
User: "Code này sao lỗi: var f = $find(obj.closest('[data-dir-form-id]'));"

AI workflow:
1. Identify: User's code has error
2. Query form_api.yaml anti_patterns section
3. Find: direct_field_access anti-pattern
4. Show correct way from YAML
```

---

## Tips & Best Practices

### 1. Naming Convention

**Rule IDs:**
- Lowercase với underscore: `grid_detail_must_get_parent`
- Có ý nghĩa: Đọc tên biết rule làm gì
- Prefix theo context: `form_`, `grid_`, `filter_`

**Pattern Names:**
- Lowercase với underscore: `form_load_data_onchange`
- Format: `{context}_{action}_{detail}`
- Examples:
  - `form_init_new` - Form initialization for New action
  - `grid_detail_cell_onchange` - Grid Detail cell onChange
  - `lookup_reload_on_filter_change` - Lookup reload

**API Operation Names:**
- Lowercase với underscore: `get_item_value`
- Verb first: `get`, `set`, `validate`, `check`

### 2. Documentation

**Always add:**
- `description`: Mô tả bằng tiếng Việt
- `example`: Ít nhất 1 example cụ thể
- `important` / `critical`: Ghi chú quan trọng
- `see_also`: Links tới related content

**Example:**
```yaml
my_api:
  description: "Mô tả chức năng"  # Required
  example: "Code example"         # Required
  important: "Điều quan trọng"    # If important
  critical: true                  # If critical
  see_also:                       # If related to other APIs
    - "related_api_1"
    - "related_api_2"
```

### 3. Testing YAML Changes

**Sau khi sửa YAML:**

1. **Check syntax:**
```bash
python -c "import yaml; yaml.safe_load(open('context_rules.yaml'))"
```

2. **Run tests:**
```bash
python tests/test_knowledge_base.py
```

3. **Check if AI can load:**
```python
from fastbusiness_mcp.knowledge_base.engine import KnowledgeEngine

engine = KnowledgeEngine("knowledge_base")
# Should not error

# Test query
rule = engine.get_api_selection_rule('grid_detail_must_get_parent')
print(rule)  # Should print rule content
```

### 4. Version Control

**Before commit:**
- Check indentation (2 spaces, no tabs)
- Run YAML syntax check
- Run tests
- Add meaningful commit message

**Commit message format:**
```
docs(yaml): Add new context type for Popup forms

- Added Popup to context_rules.yaml
- Added Popup to api_cheat_sheet
- Examples included
```

### 5. Common Mistakes

**❌ Mistake 1: Inconsistent indentation**
```yaml
# WRONG
parent:
  child1: value
   child2: value    # 3 spaces instead of 2!
```

**❌ Mistake 2: Missing quotes for special chars**
```yaml
# WRONG
description: Value: 123    # Colon without quotes!

# CORRECT
description: "Value: 123"
```

**❌ Mistake 3: Tab instead of spaces**
```yaml
# WRONG (tab used)
parent:
	child: value    # Tab!

# CORRECT
parent:
  child: value    # 2 spaces
```

**❌ Mistake 4: Wrong anchor reference**
```yaml
# WRONG
default: &defaults
  timeout: 30

api:
  <<: defaults    # Missing *

# CORRECT
api:
  <<: *defaults   # With *
```

---

## Tổng Kết

### Vai trò của mỗi file

| File | Vai trò | Khi nào sửa |
|------|---------|-------------|
| `context_rules.yaml` | Dạy AI phát hiện context | Thêm file type mới, thêm rule mới |
| `form_api.yaml` | API reference cho Form | Thêm Form API mới, sửa docs |
| `grid_api.yaml` | API reference cho Grid | Thêm Grid API mới, sửa docs |
| `common_patterns.yaml` | Code patterns tái sử dụng | Thêm pattern mới, thêm snippet |

### Workflow khi muốn thêm feature mới

**Ví dụ: Thêm support cho Report context**

1. **Add to context_rules.yaml:**
   - Thêm Report vào `file_types`
   - Thêm vào `api_cheat_sheet`
   - Thêm rules nếu có (optional)

2. **Add API reference (if needed):**
   - Tạo `report_api.yaml` (nếu có API riêng)
   - Hoặc dùng lại `form_api.yaml`

3. **Add patterns:**
   - Thêm patterns vào `common_patterns.yaml`
   - Ví dụ: `report_filter_init`, `report_generate`

4. **Update Python code:**
   - Sửa `context_detector.py` để detect Report
   - Sửa `code_generator.py` nếu cần

5. **Test:**
   - Tạo test case
   - Run tests
   - Verify AI có thể dùng được

### Khi nào NÊN sửa YAML vs code Python?

**Sửa YAML khi:**
- ✅ Thêm rule mới
- ✅ Thêm API documentation
- ✅ Thêm code pattern
- ✅ Sửa description, examples
- ✅ Thêm context mới (simple)

**Sửa Python khi:**
- ✅ Thêm logic xử lý mới
- ✅ Thêm detection algorithm
- ✅ Thêm code generation logic
- ✅ Fix bugs trong engine
- ✅ Performance optimization

**Rule of thumb:**
> "Data trong YAML, Logic trong Python"

---

## FAQs

**Q: Có thể dùng JSON thay vì YAML không?**
A: Được, nhưng YAML dễ đọc hơn. YAML hỗ trợ comments (#) và multi-line strings (|) tốt hơn JSON.

**Q: Làm sao biết AI có đọc được YAML không?**
A: Run test: `python tests/test_knowledge_base.py`. Nếu pass là OK.

**Q: Sửa YAML có cần restart server không?**
A: Có, phải restart MCP server để load YAML mới.

**Q: Có thể tách thành nhiều file nhỏ hơn không?**
A: Được, nhưng phải update code Python để load nhiều files.

**Q: YAML file quá lớn, có ảnh hưởng performance không?**
A: Không, YAML chỉ load 1 lần khi khởi động. Sau đó dùng in-memory dict rất nhanh.

**Q: Có tool nào check YAML syntax không?**
A: Có, dùng online YAML validator hoặc VS Code extension "YAML".

**Q: Làm sao backup YAML files?**
A: Git tự động track changes. Mỗi lần commit là 1 backup point.

---

**Tài liệu này được tạo để giúp developers hiểu và sử dụng YAML Knowledge Base Files trong FastBusiness MCP Server.**

📅 Ngày tạo: 2025-11-03
📝 Tác giả: Claude AI
🔄 Version: 1.0

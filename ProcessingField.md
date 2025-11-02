# YÊU CẦU: Xây dựng API Knowledge Base System cho MCP Server

## 📚 CONTEXT

Tôi cần xây dựng một hệ thống Knowledge Base để AI hiểu đúng context và API của FastBusiness framework.

Hiện tại AI đang **không hiểu** khi nào dùng API nào:
- Trong **Form** (Dir) → dùng `f.getItemValue()`, `f.setItemValue()`
- Trong **Grid Detail** → dùng `g._getItemValue()`, `g._setItemValue()` VÀ **PHẢI** get parent form: `var f = g.get_element().parentForm`
- Trong **Grid View** → chỉ dùng `g.xxx`, KHÔNG có parent form
- Response handler → access bằng `result[0].Value` (by INDEX), KHÔNG phải `result[0].field_name`

Tôi đã có 2 file tài liệu API tham khảo (đính kèm):
1. **Form & Grid API Reference** - Danh sách đầy đủ các API
2. **Quick Reference Card** - Patterns và examples

---

## 🎯 MỤC TIÊU

Xây dựng hệ thống gồm:

### 1. **API Knowledge Base** (YAML files)
- `api_reference/form_api.yaml` - Form API đầy đủ
- `api_reference/grid_api.yaml` - Grid API đầy đủ
- `api_reference/context_rules.yaml` - Rules để detect context và chọn API
- `api_reference/common_patterns.yaml` - Patterns thường dùng

### 2. **Code Snippets** (JavaScript templates)
- `code_snippets/form/` - Form code snippets
- `code_snippets/grid/` - Grid code snippets
- Mỗi snippet có comment đầy đủ về context, usage

### 3. **Knowledge Engine** (Python)
- `knowledge_engine.py` - Core engine load & query knowledge
- Detect context từ file hiện tại
- Select đúng API based on context
- Generate code từ snippets + API reference

### 4. **MCP Integration**
- Integrate knowledge engine vào MCP tools
- AI tự động select đúng API khi gen code

---

## 📋 CHI TIẾT YÊU CẦU

### PART 1: Context Detection Rules

Tạo file: `knowledge_base/api_reference/context_rules.yaml`
```yaml
# QUY TẮC PHÁT HIỆN CONTEXT VÀ CHỌN API

context_detection:
  
  # FILE TYPE DETECTION
  file_types:
    
    Dir:
      description: "Form nhập liệu (voucher/category)"
      detect_by:
        xml_markers:
          - '<dir type="Voucher"'
          - '<dir type="Category"'
        root_tag: "dir"
      
      primary_object: "f"  # Form object
      primary_api: "form_api"
      
      notes: |
        Dir files are forms for data entry.
        Use f.xxx API for accessing fields.
        May contain embedded Grid Detail.
    
    Grid:
      description: "Grid view hoặc Grid detail"
      detect_by:
        xml_markers:
          - '<grid type="Detail"'
          - '<grid type="Voucher"'
          - '<grid type="Category"'
        root_tag: "grid"
      
      # Grid có 2 sub-types quan trọng
      sub_types:
        
        GridDetail:
          description: "Grid detail nhúng trong Form"
          detect_by:
            xml_markers:
              - '<grid type="Detail"'
            context: "inside <dir> file"
            has_parent: true
          
          primary_object: "g"  # Grid object
          secondary_object: "f"  # Parent form - REQUIRED!
          primary_api: "grid_api"
          secondary_api: "form_api"
          
          critical_rules:
            - "MUST get parent form: var f = g.get_element().parentForm"
            - "Can access both grid (g.xxx) and form (f.xxx)"
            - "Parent fields in calculations use $ prefix: [$field_name]"
            - "Include parent fields in g.$h for AJAX requests"
          
          notes: |
            Grid Detail is embedded in a Dir form.
            It represents detail lines (like invoice items).
            CRITICAL: Always get parent form first!
            Example: Invoice (form) has InvoiceDetail (grid detail)
        
        GridView:
          description: "Grid view standalone (danh sách)"
          detect_by:
            xml_markers:
              - '<grid type="Voucher"'
              - '<grid type="Category"'
              - '<queries>'
              - '<toolbar>'
            context: "standalone file, not in <dir>"
            has_parent: false
          
          primary_object: "g"  # Grid object only
          primary_api: "grid_api"
          
          critical_rules:
            - "NO parent form access"
            - "Only use g.xxx API"
            - "Cannot access f.xxx"
          
          notes: |
            Grid View is standalone grid showing list of records.
            It has pagination, toolbar, queries.
            NO parent form - don't try to access f.xxx!
    
    Filter:
      description: "Filter/Report form"
      detect_by:
        xml_markers:
          - '<dir type="Report"'
          - 'cache="true"'
        root_tag: "dir"
      
      primary_object: "sender"  # Filter object (acts like form)
      primary_api: "form_api"
      
      notes: |
        Filter is a form for report parameters.
        Use form API (f.xxx) same as Dir.

  # LOCATION DETECTION
  location_contexts:
    
    field_definition:
      description: "Inside <field> tag in <fields> section"
      detect_by:
        xml_pattern: '<field name="..." ... >'
        parent_tag: "fields"
      
      available_events:
        - onchange: "Field value changed"
        - onfocus: "Field gained focus"
        - onblur: "Field lost focus"
        - onclick: "Field clicked"
      
      handler_pattern: |
        <clientScript><![CDATA[
          {{event}}="{{function_name}}(this);"
        ]]></clientScript>
      
      notes: |
        Event handlers attached to fields.
        Function receives 'sender' parameter.
        From sender, get parent: sender.parentForm (form) or sender.grid (grid)
    
    script_section:
      description: "Inside <script> tag"
      detect_by:
        xml_pattern: '<script><text><![CDATA['
      
      available_functions:
        lifecycle:
          - name: "init$Form"
            when: "Form initialization"
            params: "(f)"
          
          - name: "active$Form$"
            when: "Form activated (opened)"
            params: "(f)"
          
          - name: "close$Form$"
            when: "Form closing"
            params: "(f)"
          
          - name: "load$Grid"
            when: "Grid View loaded"
            params: "(g)"
          
          - name: "load$GridName$"
            when: "Grid Detail loaded (replace GridName with actual name)"
            params: "(g)"
            example: "load$GridAPDetail$"
        
        event_handlers:
          - name: "onChange$Voucher$field_name"
            when: "Form field changed"
            params: "(sender)"
            example: "onChange$Voucher$ma_kh"
          
          - name: "onChange$Voucher$GridName$field_name"
            when: "Grid Detail field changed"
            params: "(sender)"
            example: "onChange$Voucher$APDetail$so_luong"
          
          - name: "on$Form$ResponseComplete"
            when: "AJAX response received"
            params: "(sender, e)"
            critical: "Access result by INDEX: result[0].Value"
          
          - name: "on$Form$ExecuteCommand"
            when: "Button/command clicked"
            params: "(sender, e)"
      
      notes: |
        All JavaScript code goes in <script> section.
        Function names follow strict naming convention.

# API SELECTION RULES
api_selection_rules:
  
  - rule_id: "grid_detail_must_get_parent"
    priority: "CRITICAL"
    condition:
      file_type: "Dir"
      has_grid_detail: true
      location: "grid script"
    
    must_do:
      - step: 1
        code: "var f = g.get_element().parentForm;"
        reason: "MUST get parent form before any other operations"
      
      - step: 2
        code: "var g = sender.grid;  // or from parameter"
        reason: "Get grid object"
      
      - step: 3
        code: "// Now can use both g.xxx and f.xxx"
        reason: "Access grid cells and form fields"
    
    examples:
      correct: |
        function load$GridAPDetail$(g) {
            var f = g.get_element().parentForm;  // ✅ CORRECT
            var tyGia = f.getItemValue('ty_gia');
        }
      
      wrong: |
        function load$GridAPDetail$(g) {
            var tyGia = f.getItemValue('ty_gia');  // ❌ WRONG - f not defined!
        }
    
    anti_patterns:
      - wrong: "var f = g.parentForm;"
        reason: "Wrong property, use get_element().parentForm"
      
      - wrong: "// Skip getting parent form"
        reason: "Will cause 'f is not defined' error"
  
  - rule_id: "form_use_f_api"
    priority: "HIGH"
    condition:
      file_type: "Dir"
      location: "form script"
      NOT: "inside grid"
    
    must_use:
      get_value: "f.getItemValue('field_name')"
      set_value: "f.setItemValue('field_name', value)"
      focus: "f.getItem('field_name').focus()"
      check_action: "if (f._action === 'New')"
    
    must_not_use:
      - "f.fields.field_name = value"
      - "document.getElementById('field_name').value = value"
      - "jQuery('#field_name').val(value)"
    
    examples:
      correct: |
        function active$Form$(f) {
            if (f._action === 'New') {
                f.setItemValue('ngay_ct', new Date());  // ✅
                f.setItemValue('status', 1);             // ✅
            }
        }
      
      wrong: |
        function active$Form$(f) {
            f.fields.ngay_ct = new Date();  // ❌ WRONG
            document.getElementById('status').value = 1;  // ❌ WRONG
        }
  
  - rule_id: "grid_view_no_parent"
    priority: "CRITICAL"
    condition:
      file_type: "Grid"
      grid_type: "View"
    
    must_use:
      get_cell: "g._getItemValue(row, col)"
      set_cell: "g._setItemValue(row, col, value)"
      get_column: "g._getColumnOrder('field_name')"
    
    must_not_use:
      - "var f = g.get_element().parentForm"
      - "f.getItemValue('field_name')"
      - "Any f.xxx calls"
    
    reason: "Grid View is standalone, has NO parent form"
    
    examples:
      correct: |
        function load$Grid(g) {
            var row = g._activeRow;
            var col = g._getColumnOrder('ma_kh');
            var value = g._getItemValue(row, col);  // ✅
        }
      
      wrong: |
        function load$Grid(g) {
            var f = g.get_element().parentForm;  // ❌ WRONG - No parent!
            var value = f.getItemValue('ma_kh');   // ❌ WRONG
        }
  
  - rule_id: "response_access_by_index"
    priority: "CRITICAL"
    condition:
      function_name: "on$*$ResponseComplete"
    
    must_use:
      access_result: "result[0].Value  // By INDEX, not property name"
    
    must_not_use:
      - "result[0].field_name"
      - "result[0]['field_name']"
      - "result.field_name"
    
    reason: "SQL result columns accessed by position, not name"
    
    explanation: |
      When SQL returns:
        select ma_kh, ten_kh, dia_chi from dmkh
      
      JavaScript access:
        result[0].Value = ma_kh   (first column)
        result[1].Value = ten_kh  (second column)
        result[2].Value = dia_chi (third column)
      
      Order matters! Columns accessed by INDEX.
    
    examples:
      correct: |
        function on$Form$ResponseComplete(sender, e) {
            if (e.type.Context === 'GetCustomer') {
                var result = e.type.Result;
                
                // SQL: select ma_kh, ten_kh, dia_chi, dien_thoai
                var maKH = result[0].Value;      // ✅ Index 0 = ma_kh
                var tenKH = result[1].Value;     // ✅ Index 1 = ten_kh
                var diaChi = result[2].Value;    // ✅ Index 2 = dia_chi
                var dienThoai = result[3].Value; // ✅ Index 3 = dien_thoai
            }
        }
      
      wrong: |
        function on$Form$ResponseComplete(sender, e) {
            var result = e.type.Result;
            var maKH = result[0].ma_kh;        // ❌ UNDEFINED!
            var tenKH = result[0]['ten_kh'];   // ❌ UNDEFINED!
        }
  
  - rule_id: "grid_parent_field_calculation"
    priority: "HIGH"
    condition:
      file_type: "Dir"
      has_grid_detail: true
      operation: "calculation using parent field"
    
    must_use:
      parent_field_syntax: "[$field_name]"
    
    explanation: |
      In grid calculations, parent form fields use $ prefix.
      Example: [$ty_gia] means ty_gia from parent form.
    
    examples:
      correct: |
        function load$GridAPDetail$(g) {
            var f = g.get_element().parentForm;
            
            g.$a = {
                // Using grid fields only
                tien: '[tien]:=[so_luong]*[gia]',
                
                // Using parent form field (ty_gia)
                gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]',  // ✅ $ prefix
                
                // Aggregate to parent form
                t_tien: ['t_tien', 'tien']
            };
        }
      
      wrong: |
        g.$a = {
            gia_vnd: '[gia_vnd]:=[gia_nt]*[ty_gia]'  // ❌ Missing $ prefix
        };

# DECISION TREE
decision_tree:
  
  question_1: "What file type am I in?"
  answers:
    - answer: "Dir (Form)"
      next: "question_2"
    
    - answer: "Grid"
      next: "question_3"
    
    - answer: "Filter"
      result: "Use form_api (f.xxx)"
  
  question_2: "Am I inside a Grid Detail?"
  context: "file_type = Dir"
  answers:
    - answer: "Yes - I'm in <grid type='Detail'> script"
      result: |
        Use BOTH APIs:
        1. MUST get parent form: var f = g.get_element().parentForm
        2. Use grid_api for cells: g._getItemValue(row, col)
        3. Use form_api for form fields: f.getItemValue('field')
        4. Parent fields in calculations: [$field_name]
    
    - answer: "No - I'm in form script (not grid)"
      result: |
        Use form_api only:
        - f.getItemValue('field')
        - f.setItemValue('field', value)
  
  question_3: "What type of Grid?"
  context: "file_type = Grid"
  answers:
    - answer: "Grid Detail (type='Detail', embedded in Dir)"
      result: "See question_2 -> Yes"
    
    - answer: "Grid View (type='Voucher/Category', standalone with <queries>)"
      result: |
        Use grid_api ONLY:
        - g._getItemValue(row, col)
        - g._setItemValue(row, col, value)
        - NO parent form access!
        - DON'T try to use f.xxx

# QUICK REFERENCE CHEAT SHEET
cheat_sheet:
  
  "I'm in Form script (Dir, not grid)":
    use: "form_api"
    object: "f"
    examples:
      - "f.getItemValue('ma_kh')"
      - "f.setItemValue('tien', 100)"
      - "if (f._action === 'New')"
  
  "I'm in Grid Detail script":
    use: "grid_api + form_api"
    objects: "g + f"
    first_step: "var f = g.get_element().parentForm"
    examples:
      - "g._getItemValue(row, col)"
      - "f.getItemValue('ty_gia')"
      - "g.$a = { gia: '[gia]:=[gia_nt]*[$ty_gia]' }"
  
  "I'm in Grid View script":
    use: "grid_api only"
    object: "g"
    warning: "NO parent form!"
    examples:
      - "g._getItemValue(row, col)"
      - "g._setItemValue(row, col, value)"
  
  "I'm in Response handler":
    use: "result[index].Value"
    warning: "Access by INDEX, not property name"
    examples:
      - "var value = result[0].Value"
      - "var name = result[1].Value"
```

---

### PART 2: Form API Reference

Tạo file: `knowledge_base/api_reference/form_api.yaml`
```yaml
# FORM API REFERENCE (f.xxx)
# Sử dụng trong: Dir (Form), Filter

form_api:
  
  description: |
    Form API dùng để thao tác với form fields trong Dir và Filter files.
    Object chính: f (form object)
    Nhận object: Từ function parameter hoặc sender.parentForm
  
  # ============================================
  # GET / SET VALUES
  # ============================================
  
  value_operations:
    
    get_item:
      syntax: "f.getItem(name)"
      parameters:
        - name: "name"
          type: "string"
          description: "Field name"
      returns: "Field object"
      description: "Lấy đối tượng field trên Form"
      
      use_when:
        - "Cần access field properties (Hidden, ReadOnly, etc.)"
        - "Cần add event listener"
        - "Cần focus vào field"
      
      examples:
        - description: "Get field object"
          code: |
            var maKH = f.getItem('ma_kh');
        
        - description: "Check if field is hidden"
          code: |
            var maKH = f.getItem('ma_kh');
            if (!maKH.field.Hidden) {
                // Field is visible
            }
        
        - description: "Focus to field"
          code: |
            f.getItem('ma_kh').focus();
      
      related_apis:
        - "get_item_value"
        - "focus_field"
    
    get_item_value_text:
      syntax: "f.getItem(name).value"
      returns: "string"
      description: "Lấy hoặc gán giá trị cho text field"
      
      use_when:
        - "Field type is String/Text"
        - "Simple text get/set"
      
      examples:
        - description: "Get text value"
          code: |
            var maKH = f.getItem('ma_kh').value;
        
        - description: "Set text value"
          code: |
            f.getItem('ma_kh').value = 'KH001';
      
      note: "Prefer using f.setItemValue() for consistency"
    
    get_item_value:
      syntax: "f.getItemValue(name)"
      parameters:
        - name: "name"
          type: "string"
          description: "Field name"
      returns: "any (number | Date | string | boolean)"
      description: "Lấy giá trị của field (universal getter)"
      
      use_when:
        - "Field type is Decimal/Number"
        - "Field type is DateTime"
        - "Universal getter for any field type"
        - "RECOMMENDED for all get operations"
      
      examples:
        - description: "Get number value"
          code: |
            var soLuong = f.getItemValue('so_luong');
            // Returns: 100.50
        
        - description: "Get date value"
          code: |
            var ngayCT = f.getItemValue('ngay_ct');
            // Returns: Date object
        
        - description: "Get text value"
          code: |
            var maKH = f.getItemValue('ma_kh');
            // Returns: 'KH001'
        
        - description: "Get dropdown value"
          code: |
            var status = f.getItemValue('status');
            // Returns: 1 (selected value)
      
      important: "Works for ALL field types, recommended universal getter"
    
    set_item_value:
      syntax: "f.setItemValue(name, value)"
      parameters:
        - name: "name"
          type: "string"
          description: "Field name"
        - name: "value"
          type: "any"
          description: "Value to set"
      returns: "void"
      description: "Gán giá trị cho field (universal setter)"
      
      use_when:
        - "ALWAYS use this for setting values"
        - "Works for all field types"
        - "Triggers change events properly"
      
      examples:
        - description: "Set text value"
          code: |
            f.setItemValue('ma_kh', 'KH001');
        
        - description: "Set number value"
          code: |
            f.setItemValue('so_luong', 100);
            f.setItemValue('tien', 1000.50);
        
        - description: "Set date value"
          code: |
            f.setItemValue('ngay_ct', new Date());
            
            // Set specific date
            var date = new Date(2025, 0, 15);  // Jan 15, 2025
            f.setItemValue('ngay_ct', date);
        
        - description: "Set dropdown/status"
          code: |
            f.setItemValue('status', 1);  // Set to option 1
        
        - description: "Set boolean/checkbox"
          code: |
            f.setItemValue('is_active', true);
        
        - description: "Set multiple fields"
          code: |
            if (f._action === 'New') {
                f.setItemValue('ngay_ct', new Date());
                f.setItemValue('status', 1);
                f.setItemValue('ma_nt', 'VND');
                f.setItemValue('ty_gia', 1);
            }
      
      anti_patterns:
        - wrong: "f.fields.ma_kh = 'KH001';"
          reason: "Don't access fields directly"
          correct: "f.setItemValue('ma_kh', 'KH001');"
        
        - wrong: "f.getItem('ma_kh').value = 'KH001';"
          reason: "Inconsistent, doesn't trigger events properly"
          correct: "f.setItemValue('ma_kh', 'KH001');"
        
        - wrong: "document.getElementById('ma_kh').value = 'KH001';"
          reason: "Never use DOM manipulation"
          correct: "f.setItemValue('ma_kh', 'KH001');"
      
      important: "UNIVERSAL SETTER - Always use this, works for all types"
  
  # ============================================
  # FORM STATE
  # ============================================
  
  form_state:
    
    get_action:
      syntax: "f._action"
      returns: "'New' | 'Edit' | 'View'"
      description: "Lấy trạng thái hiện tại của Form"
      
      use_when:
        - "Need conditional logic based on form mode"
        - "Set different defaults for New vs Edit"
        - "Skip operations in View mode"
      
      possible_values:
        - value: "New"
          meaning: "Form đang ở chế độ thêm mới"
        - value: "Edit"
          meaning: "Form đang ở chế độ sửa"
        - value: "View"
          meaning: "Form đang ở chế độ xem (read-only)"
      
      examples:
        - description: "Set defaults for new record"
          code: |
            function active$Form$(f) {
                if (f._action === 'New') {
                    f.setItemValue('ngay_ct', new Date());
                    f.setItemValue('status', 1);
                    f.setItemValue('ma_dvcs', '@@unit');
                }
            }
        
        - description: "Skip validation in View mode"
          code: |
            function onChange$Voucher$tien(sender) {
                var f = sender.parentForm;
                
                if (f._action === 'View') {
                    return;  // Don't process in view mode
                }
                
                // Process change...
            }
        
        - description: "Different logic for New vs Edit"
          code: |
            if (f._action === 'New') {
                // Logic for new records
                f.setItemValue('so_ct', 'AUTO');
            } else if (f._action === 'Edit') {
                // Logic for editing
                var oldNumber = f.getItemValue('so_ct');
            }
    
    get_fields:
      syntax: "f._fields"
      returns: "Array of field objects"
      description: "Mảng tất cả các fields trên form"
      
      examples:
        - description: "Loop through all fields"
          code: |
            for (var i = 0; i < f._fields.length; i++) {
                var field = f._fields[i];
                var fieldName = field.Name;
                var value = f.getItemValue(fieldName);
            }
    
    get_fields_length:
      syntax: "f._fields.length"
      returns: "number"
      description: "Tổng số fields trên form"
      
      examples:
        - code: |
            var totalFields = f._fields.length;
  
  # ============================================
  # FOCUS OPERATIONS
  # ============================================
  
  focus_operations:
    
    focus_field:
      syntax: "f.getItem(name).focus()"
      description: "Focus vào một field"
      
      use_when:
        - "After form loads"
        - "After validation error"
        - "After data loads"
      
      examples:
        - description: "Focus on form load"
          code: |
            function active$Form$(f) {
                f.getItem('ma_kh').focus();
            }
        
        - description: "Focus after validation"
          code: |
            if (!maKH) {
                alert('Chưa nhập mã khách hàng');
                f.getItem('ma_kh').focus();
                return;
            }
    
    live:
      syntax: "f.live(object)"
      parameters:
        - name: "object"
          type: "field object"
      description: "Focus vào một field object"
      
      examples:
        - code: |
            var maKH = f.getItem('ma_kh');
            f.live(maKH);
  
  # ============================================
  # VALIDATION
  # ============================================
  
  validation_operations:
    
    valid_fields:
      syntax: "f.validFields('field1, field2, ...')"
      parameters:
        - name: "fields"
          type: "string"
          description: "Comma-separated field names"
      returns: "boolean"
      description: "Validate required fields (allowNulls=false)"
      
      use_when:
        - "Before processing data"
        - "Before AJAX request"
        - "Before saving"
      
      examples:
        - description: "Validate single field"
          code: |
            if (!f.validFields('ma_kh')) {
                return;  // Stop if invalid
            }
        
        - description: "Validate multiple fields"
          code: |
            if (!f.validFields('ma_kh, ngay_ct, so_luong')) {
                return;  // Shows error on first invalid field
            }
        
        - description: "Validate before request"
          code: |
            function onChange$Voucher$ma_kh(sender) {
                var f = sender.parentForm;
                
                if (!f.validFields('ma_kh')) {
                    return;
                }
                
                // Proceed with request
                f.request('GetCustomer', 'GetCustomer', ['ma_kh'], sender);
            }
      
      note: |
        Only validates fields with allowNulls="false".
        Shows alert and focuses on first invalid field.
    
    set_readonly_fields:
      syntax: "f.setReadOnlyFields('field1, field2')"
      description: "Thiết lập read-only cho fields"
      
      examples:
        - description: "Make fields read-only"
          code: |
            if (f._action === 'Edit') {
                f.setReadOnlyFields('ma_kh, ngay_ct');
            }
        
        - description: "Based on status"
          code: |
            var status = f.getItemValue('status');
            if (status === 2) {  // Approved
                f.setReadOnlyFields('tien, so_luong');
            }
  
  # ============================================
  # AJAX REQUEST
  # ============================================
  
  ajax_operations:
    
    request:
      syntax: "f.request(actionId, context, params, sender)"
      parameters:
        - name: "actionId"
          type: "string"
          description: "ID của <action> trong <response>"
        
        - name: "context"
          type: "string"
          description: "Context string để identify trong ResponseComplete"
        
        - name: "params"
          type: "string[]"
          description: "Array field names to send as parameters"
        
        - name: "sender"
          type: "object"
          description: "Current field object (this)"
      
      description: "Gửi AJAX request tới server"
      
      workflow: |
        1. Define <action> in <response> section of XML
        2. Call f.request() to invoke action
        3. Handle response in on$Form$ResponseComplete
      
      examples:
        - description: "Load customer data"
          code: |
            // In field onchange handler
            function onChange$Voucher$ma_kh(sender) {
                var f = sender.parentForm;
                var maKH = f.getItemValue('ma_kh');
                
                if (maKH) {
                    f.request('GetCustomer', 'GetCustomer', ['ma_kh'], sender);
                }
            }
            
            // In response handler
            function on$Form$ResponseComplete(sender, e) {
                var f = e.object;
                
                if (e.type.Context === 'GetCustomer') {
                    var result = e.type.Result;
                    
                    // CRITICAL: Access by INDEX!
                    // SQL: select ma_kh, ten_kh, dia_chi, dien_thoai
                    var tenKH = result[1].Value;      // Index 1 = ten_kh
                    var diaChi = result[2].Value;     // Index 2 = dia_chi
                    var dienThoai = result[3].Value;  // Index 3 = dien_thoai
                    
                    f.setItemValue('ten_kh', tenKH);
                    f.setItemValue('dia_chi', diaChi);
                    f.setItemValue('dien_thoai', dienThoai);
                }
            }
        
        - description: "Multiple parameters"
          code: |
            f.request('GetPrice', 'GetPrice', ['ma_vt', 'ma_kh', 'ngay_ct'], sender);
      
      critical_notes:
        - "Action ID must match <action id='...'> in XML"
        - "Context is YOUR choice, use meaningful name"
        - "Parameters sent as @param_name in SQL"
        - "Response accessed by INDEX, not property name!"
  
  # ============================================
  # TAB CONTROL
  # ============================================
  
  tab_operations:
    
    get_active_tab:
      syntax: "f._tabContainer._activeTabIndex"
      returns: "number (0-based)"
      description: "Lấy index của tab hiện tại"
      
      examples:
        - code: |
            var currentTab = f._tabContainer._activeTabIndex;
            if (currentTab === 0) {
                // First tab
            }
    
    set_active_tab:
      syntax: "f._tabContainer.set_activeTabIndex(index)"
      parameters:
        - name: "index"
          type: "number"
          description: "Tab index (0-based)"
      description: "Chuyển sang tab khác"
      
      examples:
        - description: "Switch to second tab"
          code: |
            f._tabContainer.set_activeTabIndex(1);  // Tab 2 (0-based)
        
        - description: "Switch based on condition"
          code: |
            if (hasError) {
                f._tabContainer.set_activeTabIndex(0);  // Go to first tab
                f.getItem('ma_kh').focus();
            }
  
  # ============================================
  # GRID ACCESS (from Form)
  # ============================================
  
  grid_access:
    
    get_grid:
      syntax: "f.grid"
      returns: "Grid object"
      description: "Lấy grid detail object từ form"
      
      use_when:
        - "Access grid detail from form script"
        - "Add row from form"
        - "Trigger grid calculation"
      
      examples:
        - description: "Add row to grid"
          code: |
            function active$Form$(f) {
                if (f._action === 'New') {
                    var g = f.grid;
                    g._appendRow(null, true);
                }
            }
        
        - description: "Trigger grid calculation"
          code: |
            function onChange$Voucher$ty_gia(sender) {
                var f = sender.parentForm;
                var g = f.grid;
                
                // Recalc all rows
                g.executeAggregate([g.$a.t_tien]);
            }
      
      note: |
        Only works if form has embedded grid detail.
        Returns undefined if no grid.
  
  # ============================================
  # BUTTON OPERATIONS
  # ============================================
  
  button_operations:
    
    find_button:
      syntax: "f._findButton(name)"
      parameters:
        - name: "name"
          type: "string"
          description: "Button command name"
      returns: "Button object"
      description: "Lấy button object"
      
      examples:
        - description: "Disable Save button"
          code: |
            var btnSave = f._findButton('Save');
            btnSave.set_enabled(false);
        
        - description: "Enable based on condition"
          code: |
            var btnApprove = f._findButton('Approve');
            var status = f.getItemValue('status');
            btnApprove.set_enabled(status === 1);
  
  # ============================================
  # DATE OPERATIONS
  # ============================================
  
  date_operations:
    
    get_selected_date:
      syntax: "f.getItem(name)._controlBehavior.get_selectedDate()"
      returns: "Date"
      description: "Lấy giá trị Date object từ date field"
      
      examples:
        - code: |
            var ngay = f.getItem('ngay_ct')._controlBehavior.get_selectedDate();
      
      note: "Prefer using f.getItemValue('field') - simpler"
    
    set_selected_date:
      syntax: "f.getItem(name)._controlBehavior.set_selectedDate(date)"
      parameters:
        - name: "date"
          type: "Date"
      description: "Gán Date object vào date field"
      
      examples:
        - code: |
            var date = new Date(2025, 0, 15);
            f.getItem('ngay_ct')._controlBehavior.set_selectedDate(date);
      
      note: "Prefer using f.setItemValue('field', date) - simpler"
  
  # ============================================
  # LOOKUP OPERATIONS
  # ============================================
  
  lookup_operations:
    
    set_reference_key_filter:
      syntax: "f.setReferenceKeyFilter(name)"
      parameters:
        - name: "name"
          type: "string"
          description: "Lookup field name"
      description: "Refresh lookup based on new filter condition"
      
      use_when:
        - "Lookup filter condition changed"
        - "Need to reload lookup list"
      
      examples:
        - description: "Reload lookup when parent field changes"
          code: |
            function onChange$Voucher$ma_bp(sender) {
                var f = sender.parentForm;
                
                // ma_nv lookup has condition: ma_bp = '{$%c[ma_bp]}'
                // When ma_bp changes, reload ma_nv lookup
                f.setReferenceKeyFilter('ma_nv');
            }

# ============================================
# COMMON PATTERNS
# ============================================

common_patterns:
  
  init_form:
    description: "Khởi tạo form, add event listeners"
    template: |
      function init$Form(f) {
          // Add change event listener
          var maKH = f.getItem('ma_kh');
          maKH.add_valueChanged(function(sender, e) {
              var f = sender.parentForm;
              // Handle change
          });
          
          // Add other listeners...
      }
  
  active_form_new:
    description: "Set defaults khi mở form mới"
    template: |
      function active$Form$(f) {
          if (f._action === 'New') {
              // Set default values
              f.setItemValue('ngay_ct', new Date());
              f.setItemValue('status', 1);
              f.setItemValue('ma_nt', 'VND');
              f.setItemValue('ty_gia', 1);
              
              // Focus to first field
              f.getItem('ma_kh').focus();
          }
      }
  
  load_data_onchange:
    description: "Load dữ liệu khi field thay đổi"
    template: |
      // Field handler
      function onChange$Voucher$ma_kh(sender) {
          var f = sender.parentForm;
          
          // Skip in view mode
          if (f._action === 'View') {
              return;
          }
          
          var maKH = f.getItemValue('ma_kh');
          
          if (maKH) {
              // Validate first
              if (!f.validFields('ma_kh')) {
                  return;
              }
              
              // Send request
              f.request('GetCustomer', 'GetCustomer', ['ma_kh'], sender);
          } else {
              // Clear related fields
              f.setItemValue('ten_kh', '');
              f.setItemValue('dia_chi', '');
          }
      }
      
      // Response handler
      function on$Form$ResponseComplete(sender, e) {
          var f = e.object;
          
          if (e.type.Context === 'GetCustomer') {
              var result = e.type.Result;
              
              if (result && result.length > 0) {
                  // Access by INDEX!
                  // SQL: select ma_kh, ten_kh, dia_chi, dien_thoai
                  var tenKH = result[1].Value;
                  var diaChi = result[2].Value;
                  var dienThoai = result[3].Value;
                  
                  f.setItemValue('ten_kh', tenKH);
                  f.setItemValue('dia_chi', diaChi);
                  f.setItemValue('dien_thoai', dienThoai);
              } else {
                  alert('Không tìm thấy khách hàng');
                  f.getItem('ma_kh').focus();
              }
          }
      }
  
  calculate_form_field:
    description: "Tính toán trên form field"
    template: |
      function onChange$Voucher$so_luong(sender) {
          var f = sender.parentForm;
          
          if (f._action === 'View') {
              return;
          }
          
          var soLuong = f.getItemValue('so_luong');
          var gia = f.getItemValue('gia');
          
          var tien = soLuong * gia;
          
          f.setItemValue('tien', tien);
      }
  
  conditional_readonly:
    description: "Set readonly based on condition"
    template: |
      function active$Form$(f) {
          var status = f.getItemValue('status');
          
          if (status === 2) {  // Approved
              f.setReadOnlyFields('ma_kh, ngay_ct, tien');
          }
      }

# ============================================
# ANTI-PATTERNS (Things to NEVER do)
# ============================================

anti_patterns:
  
  direct_field_access:
    wrong: |
      f.fields.ma_kh = 'KH001';
      var value = f.fields.ma_kh;
    
    reason: "Never access fields directly"
    
    correct: |
      f.setItemValue('ma_kh', 'KH001');
      var value = f.getItemValue('ma_kh');
  
  dom_manipulation:
    wrong: |
      document.getElementById('ma_kh').value = 'KH001';
      jQuery('#ma_kh').val('KH001');
    
    reason: "Never use DOM manipulation, breaks framework"
     
    correct: |
      f.setItemValue('ma_kh', 'KH001');
  
  result_property_access:
    wrong: |
      function on$Form$ResponseComplete(sender, e) {
          var result = e.type.Result;
          var maKH = result[0].ma_kh;        // UNDEFINED!
          var tenKH = result[0]['ten_kh'];   // UNDEFINED!
      }
    
    reason: "Results accessed by INDEX, not property name"
    
    correct: |
      function on$Form$ResponseComplete(sender, e) {
          var result = e.type.Result;
          var maKH = result[0].Value;   // Column 1
          var tenKH = result[1].Value;  // Column 2
      }
```

Tôi sẽ tiếp tục với **PART 3: Grid API Reference** trong message tiếp theo vì prompt quá dài.

Bạn có muốn tôi tiếp tục không?
# 03 — JSON Schema & Ví dụ

## 1. Schema tổng (`mode=summary`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["success", "object", "object_type", "mode", "spec_version", "summary"],
  "properties": {
    "success": { "type": "boolean" },
    "object": { "type": "string", "description": "schema.name, vd: dbo.zc_bcthlv" },
    "object_type": { "type": "string", "enum": ["PROCEDURE", "FUNCTION", "VIEW"] },
    "mode": { "const": "summary" },
    "parse_status": { "enum": ["ok", "partial", "failed"] },
    "line_count": { "type": "integer" },
    "modify_date": { "type": "string", "format": "date-time" },
    "database": { "type": "string" },
    "summary": { "$ref": "#/$defs/ObjectSummary" },
    "call_graph": { "$ref": "#/$defs/CallGraph" },
    "meta": { "$ref": "#/$defs/Meta" }
  }
}
```

### Mapping `object_type` (catalog → JSON)

Field `object_type` trong response là enum cao cấp, **không** trả raw `sys.objects.type`:

| Catalog `type` | `object_type` JSON |
|----------------|-------------------|
| `P` | `PROCEDURE` |
| `FN`, `IF`, `TF` | `FUNCTION` |
| `V` | `VIEW` |

Trigger (`TR`) và bảng (`U`) không có trong schema — bridge trả `unsupported_type` trước khi build JSON.

## 2. `$defs.ObjectSummary`

```json
{
  "params": [
    {
      "name": "@LoanFrom",
      "type": "SMALLDATETIME",
      "default": null,
      "is_output": false
    }
  ],
  "calls_direct": [
    { "name": "dbo.FastBusiness$Partition$Execute", "kind": "infra", "expanded": false },
    { "name": "dbo.ff_GetStartDateOfCycle", "kind": "infra", "expanded": false }
  ],
  "calls_business": [],
  "tables_read": ["dmku", "ctdmku", "cdku", "r00$", "options", "dmtk"],
  "tables_write": [],
  "temp_tables": ["#tmp1", "#data", "#report", "#ctdmku", "#lai_trong_so"],
  "variables_key": ["@days", "@round", "@Status", "@LoanFrom", "@LoanTo"],
  "result_sets": [
    {
      "ordinal": 1,
      "hint": "listing",
      "columns_hint": ["ma_ku", "ngay_tu", "ngay_den", "so_du", "tl_th", "tl_qh"]
    }
  ],
  "signals": {
    "uses_partition_execute": true,
    "uses_balance_helper": true,
    "has_cursor": true,
    "has_while": true,
    "has_dynamic_sql": false,
    "has_try_catch": false,
    "options_keys": ["m_kieu_ls", "m_ngay_ls_nam", "m_round_tien"],
    "uses_pivot_pattern": false
  },
  "param_effects": [
    {
      "param": "@Status",
      "role": "branching",
      "effect": "Affects period boundary / ngay_tu (+1 day when '1')",
      "confidence": "medium",
      "evidence_lines": [142, 158]
    },
    {
      "param": "@mau_bc",
      "role": "branching",
      "effect": "Controls result set format / dynamic columns in RS1",
      "confidence": "high",
      "evidence_lines": [75, 89]
    }
  ],
  "zones_detected": ["header", "key_filter", "cursor", "processing", "result_set"]
}
```

### Ghi chú field

| Field | Nguồn extract |
|-------|---------------|
| `params` | Parse header `CREATE PROC` / catalog `sys.parameters` |
| `calls_direct` | Visitor: `execute_statement`, `function_call` |
| `tables_*` | Visitor: DML + FROM/JOIN; loại alias. Với `VIEW`, trích xuất toàn bộ bảng gốc được select. |
| `temp_tables` | `#name` từ CREATE/INSERT/SELECT INTO |
| `variables_key` | Biến `@` xuất hiện ≥ N lần hoặc trong WHERE/JOIN |
| `result_sets` | SELECT top-level cuối proc (heuristic) hoặc view output columns |
| `signals` | Visitor flags + regex backup |
| `param_effects` | 2 tầng: Generic detector (IF/CASE/WHERE/WHILE) + Specific FBO heuristic rules |
| `zones_detected` | Snippet zone detector chạy trên AST/line map |

## 3. `$defs.CallGraph`

**Không** nhét full nested tree mặc định — chỉ flat có depth, kèm kiểm soát an toàn:

```json
{
  "root": "dbo.rs_rptInterestDetailedByLoanContract",
  "max_depth_applied": 1,
  "total_objects_count": 4,
  "truncated": false,
  "truncated_objects": [],
  "nodes": {
    "dbo.rs_rptInterestDetailedByLoanContract": {
      "kind": "business",
      "depth": 0,
      "calls": [
        "dbo.FastBusiness$Partition$Execute",
        "dbo.FastBusiness$Balance$BContract"
      ]
    }
  },
  "execution_tree_shallow": {
    "dbo.rs_rptInterestDetailedByLoanContract": [
      "dbo.FastBusiness$Partition$Execute",
      "dbo.FastBusiness$Balance$BContract",
      "dbo.ff_GetStartDateOfCycle"
    ]
  },
  "impacted_tables": ["dmku", "ctdmku", "cdku", "r00$", "options"],
  "called_by": []
}
```

Khi `expand=["FastBusiness$Balance$BContract"]` và `max_depth=2`:

```json
{
  "nodes": {
    "dbo.FastBusiness$Balance$BContract": {
      "kind": "infra",
      "depth": 1,
      "expanded": true,
      "calls": ["..."],
      "tables_read": ["cdku", "r00$"]
    }
  }
}
```

## 4. `$defs.Meta`

```json
{
  "file_path": "E:\\...\\Filter\\zcbcthlv.xml",
  "project_root": "\\\\172.168.5.14\\...\\FBISP242",
  "cache_hit": false,
  "parse_time_ms": 45,
  "objects_fetched": 1,
  "estimated_full_chars": 31200,
  "estimated_tokens_saved": 7800,
  "warnings": []
}
```

Ước tính token saved = `(full_chars - json_chars) / 4`.

## 5. Ví dụ thực tế — `rs_rptInterestDetailedByLoanContract`

```json
{
  "success": true,
  "spec_version": "1.0",
  "object": "dbo.rs_rptInterestDetailedByLoanContract",
  "object_type": "PROCEDURE",
  "mode": "summary",
  "parse_status": "ok",
  "line_count": 347,
  "summary": {
    "params": [
      {"name": "@LoanFrom", "type": "SMALLDATETIME"},
      {"name": "@LoanTo", "type": "SMALLDATETIME"},
      {"name": "@ma_dvcs", "type": "VARCHAR(8000)"},
      {"name": "@ma_kh", "type": "VARCHAR(33)"},
      {"name": "@Status", "type": "CHAR(1)"},
      {"name": "@ContractType", "type": "CHAR(1)"},
      {"name": "@Language", "type": "CHAR(1)"},
      {"name": "@UserID", "type": "INT"},
      {"name": "@Admin", "type": "BIT"}
    ],
    "calls_direct": [
      {"name": "dbo.FastBusiness$Partition$Execute", "kind": "infra"},
      {"name": "dbo.FastBusiness$Balance$BContract", "kind": "infra"},
      {"name": "dbo.ff_GetStartDateOfCycle", "kind": "infra"}
    ],
    "tables_read": ["dmku", "ctdmku", "cdku", "r00$", "dmtk", "options"],
    "temp_tables": ["#tmp1", "#data", "#report", "#ctdmku"],
    "signals": {
      "uses_partition_execute": true,
      "has_cursor": true,
      "has_while": true,
      "options_keys": ["m_kieu_ls", "m_ngay_ls_nam", "m_round_tien"]
    },
    "param_effects": [
      {
        "param": "@Status",
        "role": "branching",
        "effect": "Affects period boundary / ngay_tu (+1 day when '1')",
        "confidence": "medium",
        "evidence_lines": [142, 158]
      }
    ],
    "result_sets": [
      {
        "ordinal": 1,
        "columns_hint": ["ma_ku", "so_ku", "ten_kh", "ngay_tu", "ngay_den", "so_du", "tl_th", "tl_qh"]
      }
    ]
  },
  "call_graph": {
    "root": "dbo.rs_rptInterestDetailedByLoanContract",
    "max_depth_applied": 1,
    "total_objects_count": 1,
    "truncated": false,
    "truncated_objects": [],
    "impacted_tables": ["dmku", "ctdmku", "cdku", "r00$", "options"]
  },
  "meta": {
    "estimated_full_chars": 28500,
    "estimated_tokens_saved": 6500,
    "warnings": []
  }
}
```

**Agent suy luận được:**

- Cần đọc snippet `tl_th`, `@days`, `ctdmku`, `@Status` — **không** cần full proc
- `@Status` quan trọng cho debug số liệu
- Infra không cần expand

## 6. Ví dụ — `zc_bcthlv` (pivot)

```json
{
  "success": true,
  "spec_version": "1.0",
  "object": "dbo.zc_bcthlv",
  "object_type": "PROCEDURE",
  "mode": "summary",
  "parse_status": "ok",
  "summary": {
    "params": [
      {"name": "@nam_tu", "type": "INT"},
      {"name": "@nam_den", "type": "INT"},
      {"name": "@ma_dvcs", "type": "VARCHAR(8000)"},
      {"name": "@ma_kh", "type": "VARCHAR(33)"},
      {"name": "@mau_bc", "type": "CHAR(2)"},
      {"name": "@Language", "type": "CHAR(1)"},
      {"name": "@UserID", "type": "INT"},
      {"name": "@Admin", "type": "BIT"}
    ],
    "calls_direct": [
      {"name": "dbo.FastBusiness$Partition$Execute", "kind": "infra"}
    ],
    "temp_tables": ["#report", "#lai_thang", "#lai_trong_so", "#pivot", "#xcolumn"],
    "signals": {
      "uses_pivot_pattern": true,
      "has_cursor": true,
      "has_while": true,
      "options_keys": ["m_kieu_ls", "m_ngay_ls_nam", "m_round_tien"]
    },
    "param_effects": [
      {
        "param": "@mau_bc",
        "role": "branching",
        "effect": "Controls pivot column set (gia_tri vs gia_tri_nt in RS1)",
        "confidence": "high",
        "evidence_lines": [75, 89]
      }
    ],
    "result_sets": [
      {"ordinal": 1, "hint": "RS1 xsearch/xpivot"},
      {"ordinal": 2, "hint": "RS2 #pivot grid"}
    ],
    "zones_detected": ["processing", "pivot", "result_set"]
  }
}
```

## 7. Ví dụ — `mode=snippet`

Request:

```json
{
  "file_path": "E:\\...\\Filter\\zcbcthlv.xml",
  "object_name": "rs_rptInterestDetailedByLoanContract",
  "mode": "snippet",
  "keywords": ["tl_th", "@Status", "ctdmku", "@days", "WHILE"]
}
```

Response:

```json
{
  "success": true,
  "spec_version": "1.0",
  "object": "dbo.rs_rptInterestDetailedByLoanContract",
  "mode": "snippet",
  "snippets": [
    {
      "id": "s1",
      "match_reason": "keyword:@days + options m_kieu_ls",
      "line_start": 88,
      "line_end": 96,
      "sql": "SELECT @days = CASE WHEN val = 1 THEN 30 ELSE (SELECT val FROM options WHERE name = 'm_ngay_ls_nam') END FROM options WHERE name = 'm_kieu_ls'"
    },
    {
      "id": "s2",
      "match_reason": "keyword:tl_th + WHILE",
      "line_start": 205,
      "line_end": 275,
      "sql": "-- cursor loop computing tl_th / tl_qh ..."
    }
  ],
  "total_lines": 89,
  "truncated": false
}
```

## 8. Ví dụ — JSON user gợi ý (so sánh)

User gợi ý dạng deep tree — **không dùng làm default**:

```json
{
  "root": "dbo.sp_A",
  "total_depth": 4,
  "nodes": { "...": { "calls": ["..."] } }
}
```

→ Chỉ trả dạng này khi `max_depth >= 3` **và** `expand` rõ ràng. Mặc định dùng **shallow** schema mục 3.

## 9. Catalog enrichment (optional, khuyến khích)

Kết hợp `sys.parameters` để params chính xác hơn parse header:

```sql
SELECT
    p.name,
    TYPE_NAME(p.user_type_id) AS type_name,
    p.max_length,
    p.is_output,
    p.has_default_value,
    p.default_value
FROM sys.parameters p
WHERE p.object_id = @object_id
ORDER BY p.parameter_id
```

Ưu tiên catalog cho `params`; ANTLR cho logic body.

## 10. Version field

Mọi response thành công **bắt buộc** có `"spec_version": "1.0"` ở root JSON để Agent/client tương thích sau này.

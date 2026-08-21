# Cải thiện `summary_object` — để Agent hiểu đủ bức tranh (không cần full proc)

> **Mục đích:** Từ JSON thực tế `rs_rptInterestDetailedByLoanContract` (SHOWA FBISP242, 2026-08-20), liệt kê chỗ **đủ / nhiễu / thiếu**, và đề xuất sửa để Agent **định hướng đúng + đọc đúng đoạn logic** mà không cần 327 dòng full body.
>
> **Không kỳ vọng:** JSON summary một mình = 100% công thức lãi. “100% bức tranh” = **summary sạch + snippet đúng chỗ**. Full chỉ khi snippet thiếu.

---

## 1. Kết luận từ JSON thực tế

| Việc Agent cần | JSON hiện tại | Đủ? |
|----------------|---------------|-----|
| Biết param, bảng nghiệp vụ, helper infra | Có | Gần đủ |
| Biết `@Status` quan trọng | Có `param_effects` + evidence_lines | Đủ gợi ý |
| Biết output grid / RS | `result_sets` sai (gán biến) | **Không** |
| Biết công thức lãi / kỳ / round | Không có | **Không** — cần snippet |
| Clone pivot `zc_bcthlv` | Signals + tables OK, thiếu formula + RS | **Không** |

Token: JSON ~2.5–3.5k vs full ~5.5–7k — **tiết kiệm**, nhưng nhiễu (`param_effects` low, alias table, RS rác) làm Agent đọc chậm và dễ hiểu sai.

Parse: `antlr_ast_parse_ms: 223272` (~3.7 phút) — **không chấp nhận** cho MCP. Phải tách ticket hiệu năng.

---

## 2. Nguyên tắc “bức tranh đủ” (3 lớp, không 1 JSON)

```
Lớp A — Bản đồ (mode=summary, sạch)
  params, tables_read (thật), calls (infra vs system vs business),
  signals, zones, param_effects (chỉ medium/high)

Lớp B — Nội dung (mode=snippet, đúng khối)
  keywords: tl_th, @days, @Status, ctdmku, WHILE
  hoặc zones: processing / cursor / result_set

Lớp C — Full (hiếm)
  max_full_chars
```

**100% bức tranh** = A sạch + B đúng đoạn. Không nhét công thức vào summary (dễ sai, tốn token).

---

## 3. Sửa JSON summary (ưu tiên cao)

### 3.1. `result_sets` — đang sai, phải sửa trước

**Hiện tại:** 5 “RS” là `SELECT @round = val`, `ff_GetStartDate(...)` — biến gán, không phải output Agent thấy trên Grid.

**Quy tắc extract:**

| Coi là result set | Không coi |
|-------------------|-----------|
| `SELECT` top-level **không** gán biến (`@x =`) | `SELECT @var = ...` |
| `SELECT` cuối proc / trước `RETURN` | `SELECT` trong cursor/WHILE (trừ khi thật sự INSERT…EXEC ra ngoài) |
| Cột identifier thật: `ma_ku`, `tl_th` | Biểu thức cắt chuỗi: `EWHENval=1THEN30...` |

**Output mong muốn cho proc này:**

```json
"result_sets": [
  {
    "ordinal": 1,
    "hint": "listing",
    "confidence": "medium",
    "columns_hint": ["ma_ku", "so_ku", "ngay_tu", "ngay_den", "so_du", "tl_th", "tl_qh"]
  }
]
```

Nếu không chắc: `"result_sets": []` + `"hint": "unknown"` còn hơn 5 RS rác.

---

### 3.2. `tables_read` — lọc alias / nhiễu

**Nhiễu trong JSON:** `g`, `gl`, `tmp`, `cur`, `r00$000000`.

**Quy tắc:**

1. Bỏ alias (identifier sau `FROM x a` / `JOIN y b` — `a`,`b` không phải table).
2. Partition: gộp `r00$000000` → `r00$` (prefix `r\d\d$`).
3. Temp `#...` chỉ nằm `temp_tables`, không lặp `tables_read`.
4. Dynamic SQL string: nếu extract được table thì gắn `"source": "dynamic_sql"`, không trộn ngang với table tĩnh nếu không chắc.

**Whitelist ưu tiên FBO:** `dm*`, `ct*`, `options`, `cdku`, `dmtk`, `r00$`…

**Mong muốn:**

```json
"tables_read": ["cdku", "ctdmku", "dmku", "dmtk", "dmtk0", "options", "r00$"]
```

---

### 3.3. `sp_executesql` không phải business

| Object | `kind` |
|--------|--------|
| `sp_executesql`, `sp_helptext`, `sp_*` hệ thống | `system` |
| `FastBusiness$%`, `ff_%`, `fsd_%` | `infra` |
| `zc_*`, `rs_*`, `rs_rpt*` | `business` |

`has_dynamic_sql: true` đã đủ — **không** đưa `sp_executesql` vào `calls_business`.

---

### 3.4. `param_effects` — cắt nhiễu

Chỉ giữ:

- `confidence` = `medium` hoặc `high`
- HOẶC rule FBO cụ thể (`@Status`, `@mau_bc`)

Bỏ / không trả mặc định: `@DateFrom` “used in branching” confidence `low`.

**Giới hạn:** tối đa 5 `param_effects` mỗi summary.

`@Status` hiện tại (effect + evidence_lines) **giữ** — đúng case lãi vay.

---

### 3.5. `params.default`

`""` gây hiểu nhầm “default rỗng”. Dùng `null` khi catalog không có default.

Type: giữ `CHAR(1)` / `VARCHAR(33)` nếu `sys.parameters` có `max_length` — đừng cắt thành `CHAR` / `VARCHAR` trần.

---

### 3.6. `call_graph.tables_read` vs `summary.tables_read`

Hai list đang lệch (`cur` chỉ ở graph). **Một nguồn** sau filter alias — graph copy list đã sạch.

---

## 4. Cần thêm gì để Agent “hiểu bức tranh” (không full body)

### 4.1. `logic_hints` (ngắn, heuristic — không phải công thức chắc)

Mục tiêu: biết **phải snippet chỗ nào**, không diễn giải sai công thức.

```json
"logic_hints": {
  "interest_related": true,
  "keywords_suggested": ["tl_th", "tl_qh", "@days", "ctdmku", "@Status", "WHILE"],
  "options_keys": ["m_kieu_ls", "m_ngay_ls_nam", "m_round_tien"],
  "note": "Interest formula lives in cursor/WHILE; use mode=snippet with keywords_suggested"
}
```

Detect: cột/biến `tl_th`, `ls`, `ctdmku`, options `m_kieu_ls`.

**Cấm** nhét `"formula": "so_du * ls / 100 / @days"` vào summary trừ khi extract được expression thật từ AST (phase 2, confidence high).

---

### 4.2. `snippet_index` (rẻ, cực hữu ích)

Map zone → dòng, Agent gọi snippet không đoán keyword.

```json
"snippet_index": {
  "header": [1, 40],
  "params": [1, 40],
  "key_filter": [80, 140],
  "cursor": [200, 280],
  "processing": [200, 310],
  "result_set": [310, 327]
}
```

`zones_detected` hiện có tên zone nhưng **không có line range** → Agent vẫn phải full hoặc đoán keyword.

---

### 4.3. Default snippet khi Agent hỏi “tính lãi thế nào”

Tool description / Agent rule:

```
Sau summary, nếu signals.has_cursor + options m_kieu_ls / biến tl_th
→ tự gọi mode=snippet keywords=["tl_th","@days","@Status","ctdmku"]
KHÔNG đọc full.
```

Đây là phần **bức tranh 100%**: summary nói *ở đâu*, snippet nói *làm gì*.

---

### 4.4. `output_contract` (optional, catalog + heuristic)

Để clone báo cáo: biết cột RS cuối.

Nguồn ưu tiên:

1. Comment / SELECT cuối (sau filter 3.1)
2. Không thì `"unknown"` — Agent dùng snippet zone `result_set`

---

## 5. Hiệu năng (bắt buộc, không phải “nice”)

`antlr_ast_parse_ms: 223272` → MCP tool không dùng được trong chat.

Đề xuất:

| Việc | Target |
|------|--------|
| Parse proc 300–500 dòng | **< 2s** (tốt: < 500ms) |
| Timeout parse | 8s → `parse_status: partial` + fallback regex |
| Cache AST | `sha256(definition)` trong `tsql_engine` |
| Không parse lại infra | Đúng spec depth 0 |

Nếu ANTLR full grammar quá nặng: **SLL mode**, `prediction cache`, hoặc parse 2 pass (regex tables/calls trước, ANTLR chỉ khi cần snippet AST).

Ghi rõ trong response `meta.timing` như JSON hiện tại — **tốt, giữ**.

---

## 6. Thứ tự làm (cho Gemini / implementer)

### P0 — Agent đang hiểu sai nếu không sửa

1. Filter `result_sets` (bỏ SELECT gán biến)
2. Filter `tables_read` (alias, partition gộp, bỏ `#` khỏi tables_read)
3. `sp_executesql` → `kind: system`, không vào `calls_business`
4. `param_effects`: ẩn `low`; max 5
5. Parse timeout + cache — đừng để 3 phút/request

### P1 — Để hiểu logic mà không full

6. `snippet_index` (line range theo zone)
7. `logic_hints.keywords_suggested`
8. Agent rule: summary → snippet (không skip)

### P2

9. Extract expression `tl_th = ...` nếu AST cho phép
10. Type param đủ length (`CHAR(1)`)
11. `default: null`

---

## 7. JSON mục tiêu (cùng proc, gọn hơn)

```json
{
  "success": true,
  "spec_version": "1.0",
  "object": "dbo.rs_rptInterestDetailedByLoanContract",
  "object_type": "PROCEDURE",
  "mode": "summary",
  "parse_status": "ok",
  "line_count": 327,
  "summary": {
    "params": [
      {"name": "@LoanFrom", "type": "SMALLDATETIME", "default": null, "is_output": false},
      {"name": "@LoanTo", "type": "SMALLDATETIME", "default": null, "is_output": false},
      {"name": "@Status", "type": "CHAR(1)", "default": null, "is_output": false}
    ],
    "calls_direct": [
      {"name": "dbo.FastBusiness$Partition$Execute", "kind": "infra", "expanded": false},
      {"name": "dbo.FastBusiness$Balance$BContract", "kind": "infra", "expanded": false},
      {"name": "dbo.sp_executesql", "kind": "system", "expanded": false}
    ],
    "calls_business": [],
    "tables_read": ["cdku", "ctdmku", "dmku", "dmtk", "options", "r00$"],
    "temp_tables": ["#ctdmku", "#data", "#report", "#tmp1"],
    "signals": {
      "uses_partition_execute": true,
      "uses_balance_helper": true,
      "has_cursor": true,
      "has_while": true,
      "has_dynamic_sql": true,
      "options_keys": ["m_kieu_ls", "m_ngay_ls_nam", "m_round_tien"]
    },
    "param_effects": [
      {
        "param": "@Status",
        "role": "branching",
        "effect": "Affects period boundary / ngay_tu when Status='1'",
        "confidence": "medium",
        "evidence_lines": [156, 165, 259]
      }
    ],
    "logic_hints": {
      "interest_related": true,
      "keywords_suggested": ["tl_th", "tl_qh", "@days", "ctdmku", "@Status", "WHILE"]
    },
    "snippet_index": {
      "cursor": [200, 280],
      "processing": [200, 310],
      "result_set": [310, 327]
    },
    "result_sets": [
      {
        "ordinal": 1,
        "hint": "listing",
        "confidence": "low",
        "columns_hint": []
      }
    ]
  }
}
```

Nếu `columns_hint` chưa extract được: để `[]` + bảo Agent snippet zone `result_set` — **đừng bịa**.

---

## 8. Tiêu chí nghiệm thu (Agent đọc proc lãi vay)

Sau P0+P1, Agent **không cần full proc** nếu:

- [ ] Không còn `g`/`gl`/`tmp` trong `tables_read`
- [ ] Không còn RS là `@round=val`
- [ ] `calls_business` không chứa `sp_executesql`
- [ ] Có `snippet_index` hoặc `keywords_suggested`
- [ ] `mode=snippet` với keywords trên trả **khối tính `tl_th`** (< 120 dòng)
- [ ] Parse < 2s (hoặc partial + fallback < 2s)

Khi đó bức tranh = **bản đồ đúng + đoạn nhà đúng**. Công thức lãi nằm trong snippet — đó là 100% cần để clone/fix, không phải nhồi thêm vào summary.

---

## 9. Không làm

- Expand `FastBusiness$Balance$BContract` mặc định (đã đúng trong JSON này)
- Diễn giải công thức lãi bằng regex đoán rồi gắn `confidence: high`
- Trả full `execution_tree` depth 3

---

## 10. Liên hệ doc gốc

Spec tool: `docs/doc/02_tool_api.md`, schema `docs/doc/03_json_schema.md`.  
File này = **feedback từ output thật**, ưu tiên sửa visitor/filter hơn đổi kiến trúc 3 lớp.

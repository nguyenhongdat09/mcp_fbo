# FIX — `clone_things`: Dual lookup App + Sys DB + lọc system noise

> **Mục đích:** Doc gửi **Gemini code review** — rà soát patch dual-DB và noise filter; sửa test/mock còn lệch sau khi đổi thuật toán.  
> **Ngày:** 2026-09-04  
> **Phạm vi code:** [`clone_things/service.py`](../../../clone_things/service.py), [`tests/clone_things/`](../../../tests/clone_things/), spec [`docs/doc/clone_things/03_resolution_and_flow.md`](../clone_things/03_resolution_and_flow.md)  
> **Không** đụng chrome_debug / build / dist.

---

## 1. Vấn đề thực tế (repro)

Khi seed XML (vd. Filter log / voucher maintenance), JSON trả:

```text
not_found_both: tempdb, systypes, syscheckfields, userinfo2, FastBusiness$Check$Relative, …
```

User giả thuyết đúng một phần: `clone_things` trước đây **chỉ** `get_connection_config(..., db_type="app")` trong khi nhiều object FBO nằm ở **DB sys** (`*_S` / `*_Sys`).

### 1.1. Probe thật (LIONAGREVO → NEWPEARL)

| Object | APP (cả SRC/TGT) | SRC SYS | TGT SYS | Kết luận |
|--------|------------------|---------|---------|----------|
| `userinfo2` | không | có (U) | có (U) | **skipped_exists** nếu dual-lookup |
| `FastBusiness$Check$Relative` | không | có (P) | có (P) | **skipped_exists** trên target sys |
| `syscheckfields` | không | có (U) | **không** | **cloned** từ source sys |
| `tempdb` | không | không | không | **noise** (tên DB, không phải object) |
| `systypes` | không | không | không | **noise** (catalog SQL Server) |

Reuse connection giống `query_database`:

- [`find_connect_by_path/web_config_loader.py`](../../../find_connect_by_path/web_config_loader.py) — derive app/sys từ `sysDatabaseName` / `appConnectionString` / `sysConnectionString`
- [`query_database/connection.py`](../../../query_database/connection.py) — `get_connection_config(file_path, db_type)`

---

## 2. Giải pháp đã code (cần Gemini review)

### 2.1. Dual lookup app → sys

Trong [`clone_things/service.py`](../../../clone_things/service.py):

| Helper | Việc |
|--------|------|
| `load_project_db_connections(project, warnings)` | Load **cả** `app` + `sys` parsed; thiếu bucket → warning, không fail nếu còn ≥1 |
| `find_object_on_side(parsed_by_db, name, schema, order)` | Exists lần lượt theo `order` |
| `DB_LOOKUP_ORDER = ("app", "sys")` | Mặc định |
| `db_type="sys"` | Đảo order thành `("sys", "app")` |

**Thứ tự mỗi object:**

```text
noise? → skipped_noise
→ exists TARGET (app rồi sys) → skipped_exists { where: target, db: app|sys }
→ else exists SOURCE (app rồi sys)
     → không → not_found_both
     → có → fetch/deps với đúng db_type tìm thấy trên source
            deploy (nếu bật) vào TARGET cùng loại db
```

### 2.2. System noise denylist

`SYSTEM_NOISE_NAMES` / `is_system_noise_name`:

```text
tempdb, master, msdb, model,
systypes, sysobjects, syscolumns, sysusers, sysindexes,
syscomments, sysdepends, sysconstraints, information_schema
```

→ `skipped_noise[]`, **không** ghi vào `not_found_both`, **không** gọi catalog.

### 2.3. JSON response bổ sung

| Field | Ý nghĩa |
|-------|---------|
| `skipped_noise` | `string[]` — noise đã lọc |
| `skipped_exists[].db` | `"app"` \| `"sys"` |
| `cloned[].db` | DB nguồn đã fetch |
| `meta.db_lookup_order` | order đã dùng |

---

## 3. Checklist review cho Gemini

### 3.1. Correctness (bắt buộc)

- [ ] `load_project_db_connections` gọi `get_connection_config` đúng 2 lần (`app`, `sys`) mỗi project
- [ ] Fail chỉ khi **cả** app lẫn sys của một project đều fail
- [ ] `find_object_on_side` short-circuit khi bucket đầu tiên hit (không query thừa)
- [ ] `fetch_object_script` / `extract_object_dependencies` nhận **`db_type` = db tìm thấy trên source**, không hardcode `"app"`
- [ ] `execute_clone=true` → `deploy_script_to_target` dùng **target connection cùng `db`** (sys object → target sys)
- [ ] Noise không làm tăng `processed_count` / không pollute `not_found_both`
- [ ] Partition map `m41$` → `m41$000000` vẫn chạy **trước** dual lookup (đã có `to_partition_structure_name`)

### 3.2. Tests (hiện đang đỏ — Gemini phải sửa)

`pytest tests/clone_things/` — **2 fail** (2026-09-04):

| Test | Nguyên nhân khả dĩ sau dual-DB |
|------|--------------------------------|
| `test_xml_seed_success` | Mock `smart_exists` giả định call#1=target, call#2=source. Nay mỗi side = **app rồi sys** (tới 4 call/object). Ngoài ra `d91$` normalize thành **`d91$000000`** — mock còn check `clean_name == "d91$"` → miss |
| `test_cycle_dependency_visited` | Cùng vấn đề call-count 1=target / 2=source |

**Cách sửa mock khuyến nghị (parity `test_target_first_mock.py`):**

```python
def _conn_side_effect(file_path, db_type="app"):
    return {"success": True, "parsed": {"_path": str(file_path), "_db": db_type}}

# Exists: phân biệt bằng parsed_conn["_db"] + "_path", hoặc sequence tường minh:
# target app F, target sys F, source app T  → 3 tuple cho 1 object chỉ có trên source app
```

- [ ] Update `tests/clone_things/test_xml_seed_and_deps.py` theo dual-DB + partition `$000000`
- [ ] Giữ / bổ sung case: skipped trên **target sys**, clone từ **source sys**, noise `tempdb`
- [ ] `pytest tests/clone_things/ -q` → **all green**

### 3.3. Doc đồng bộ

- [ ] [`04_json_response.md`](../clone_things/04_json_response.md) — thêm `skipped_noise`, field `db`
- [ ] [`07_test_cases.md`](../clone_things/07_test_cases.md) — TC dual app/sys + noise
- [ ] MCP tool docstring trong [`mcp_app.py`](../../../fastbusiness_mcp/mcp_app.py) — nhắc “tự quét app+sys”

### 3.4. Anti-patterns (cấm khi review)

- [ ] Không bỏ dual-lookup, chỉ “exclude hết FastBusiness$ / userinfo2”
- [ ] Không coi `tempdb`/`systypes` là `not_found_both`
- [ ] Không fetch script bằng `db_type="app"` khi object chỉ có trên sys
- [ ] Không deploy object sys lên connection app

---

## 4. Prompt copy cho Gemini (review + finish)

```text
Review và hoàn thiện patch dual App/Sys cho MCP clone_things trong repo E:\PythonProject\mcp_fbo.

Đọc:
- docs/doc/doc_fix/FIX-clone_things-dual-app-sys.md (doc này)
- clone_things/service.py (SYSTEM_NOISE_NAMES, load_project_db_connections, find_object_on_side, vòng queue)
- tests/clone_things/test_target_first_mock.py (đã cập nhật mock dual-DB — làm mẫu)
- tests/clone_things/test_xml_seed_and_deps.py (đang fail — phải sửa)

Yêu cầu:
1. Code review checklist §3.1 — liệt kê PASS/FAIL + chỗ sửa nếu FAIL.
2. Sửa test_xml_seed_and_deps.py cho đúng thứ tự exists: target app→sys rồi source app→sys; tên partition sau normalize là *$000000.
3. Đảm bảo pytest tests/clone_things/ all green.
4. Đồng bộ 04_json_response.md + 07_test_cases.md + docstring MCP nếu thiếu skipped_noise / db.
5. Không commit build/dist/logs; không revert dual-lookup.

Trả: tóm tắt review + diff test/doc đã sửa.
```

---

## 5. Acceptance (sau khi Gemini xong)

- [ ] Object chỉ có sys (vd. `userinfo2` có cả hai sys) → `skipped_exists` với `"db":"sys"`, không còn trong `not_found_both`
- [ ] Object chỉ source sys (vd. `syscheckfields` thiếu target sys) → `cloned` với `"db":"sys"`
- [ ] `tempdb` / `systypes` → `skipped_noise`, file `.sql` không comment “not found” cho chúng
- [ ] Unit tests clone_things xanh
- [ ] Smoke XML seed (optional): Filter LION → NEWPEARL, `not_found_both` không còn 4–5 tên noise/sys đã biết

---

## 6. Ghi chú ngoài phạm vi patch này

- `FastBusiness$*` vẫn có thể bị **exclude dependency** (`DEFAULT_EXCLUDE_LIKE`) khi không phải seed — dual-DB không đổi rule exclude.
- Force clone infra từ sys khi user muốn → suggestion sau (`include_infra` / `09_suggestions.md`).

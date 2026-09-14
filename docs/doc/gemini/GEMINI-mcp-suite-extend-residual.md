# GEMINI — Suite mở rộng + residual DX (sau convenience)

> **File độc lập** — gửi Gemini chỉ cần file này.  
> **Repo:** `E:\PythonProject\mcp_fbo\`  
> **Bối cảnh:** Verify 2026-09-14 — convenience `(6)` đã ship; MCP **production-ready**.  
> Spec này = **mở rộng whitelist `suite:`** (Report / Upload / **Include** / Lookup) theo yêu cầu user + **DX residual** còn lại (không bắt buộc P0).  
> **Loại trừ (KHÔNG làm):** mở rộng `query_radar` / CodeGraph `Main` / `Templates`; quét full-tree project theo tên; **copy nguyên** `Include/` (suite **giữ whitelist exact path**, không glob substring).

**Không** regress type=0/1/3 core, inventory, search_files, confirm_overwrite, `suite:` hiện có.  
**Không** Shell UNC.  
**Không** thêm MCP tạo/xóa/đổi tên file tùy ý.

---

## Mục tiêu

| # | Mức | Việc | Ghi chú |
|---|-----|------|---------|
| **0** | **P1** | Thêm path `suite:`: **Report** + **Templates/Upload** + **Include** | User yêu cầu 2026-09-14 |
| 1 | P2 / skill | `seed_mode=token` + seed ngắn `zccn` vẫn ra cả `zccnthxldtcth` | Dùng seed dài / `prefix`. Doc rõ hơn trong skill (+ optional tighten token) |
| 2 | P2 | `suite:` chưa bung `Lookup/{name}.xml` | Chỉ khi danh mục có Lookup; thêm path whitelist |
| 3 | P2 | Alias / `list_projects` UNC | Agent vẫn phải nhớ full path |
| 4 | P3 | Warning riêng khi đụng `Web.config` / `EmailConfig` (kể cả `copy_filter=missing`) | Hiện chỉ chặn đè như file thường + confirm |
| 5 | P3 | Batch `read_local_file` | **Không làm** — gọi song song được |

---

## P1-0 — Mở rộng `suite:{name}`: Report + Upload + Include

### Hiện trạng (đã ship)

`suite:{name}` thử ứng viên (chỉ giữ file **có trên source**):

```text
App_Data/Controllers/Filter/{name}.xml
App_Data/Controllers/Filter/{name}Form.xml
App_Data/Controllers/Grid/{name}.xml
App_Data/Controllers/Grid/{name}Grid.xml
App_Data/Controllers/Dir/{name}.xml
App_Data/Controllers/Dir/{name}Form.xml
Main/{name}.aspx
App_Data/Controllers/Templates/Mail/{name}.html
App_Data/Controllers/Templates/Mail/zmail{name}.html
```

### Bổ sung bắt buộc (whitelist)

Thêm vào `suite_candidates` (cùng rule: `is_file()` trên source mới vào planned):

**Report / Upload**

```text
App_Data/Controllers/Report/{name}.xml
App_Data/Controllers/Templates/Upload/{name}.xml
App_Data/Controllers/Templates/Upload/{name}ImportXml.xml
```

**Include** (`App_Data/Controllers/Include/`) — tên file **không** luôn là `{name}.xml`; trên AIH hay gặp pattern gắn controller (vd. `suite:POTran`):

```text
App_Data/Controllers/Include/{name}.xml
App_Data/Controllers/Include/{name}.ent
App_Data/Controllers/Include/{name}.txt
App_Data/Controllers/Include/{name}.Nested
App_Data/Controllers/Include/{name}.Nested.txt
App_Data/Controllers/Include/Extender.{name}
App_Data/Controllers/Include/BIMode.{name}
App_Data/Controllers/Include/ImportOverWriteVoucher.{name}
App_Data/Controllers/Include/Revert.{name}.ent
App_Data/Controllers/Include/Tiny.External.{name}
App_Data/Controllers/Include/Unit.{name}
```

**Lý do path:** Report `{name}.xml`; Upload `{name}.xml` + HDDV `{name}ImportXml.xml`. Include dùng entity/fragment theo controller (`Extender.POTran`, `Customer.Nested`, …).

### Cấm (Include)

- **Không** copy nguyên folder `Include/` (~2000+ file).
- **Không** glob/`seed` substring trong Include (vd. `*Customer*` kéo nhầm `rptSalesAnalysisByCustomer`).
- Chỉ exact candidate như list trên; path không có trên source → bỏ im.
- File `*.f` mã hóa: type=3 đã skip — không cố copy.

### AC

- [x] AC-SUITE-R1: source có `Report/{name}.xml` → `suite:{name}` planned có path đó
- [x] AC-SUITE-U1: source có `Templates/Upload/{name}.xml` → planned có
- [x] AC-SUITE-U2: source có `{name}ImportXml.xml` → planned có; không có thì bỏ im
- [x] AC-SUITE-I1: source có `Include/Extender.{name}` và/hoặc `{name}.Nested` → planned có
- [x] AC-SUITE-I2: không có Include khớp → suite vẫn OK nếu còn Filter/Grid…
- [x] AC-SUITE-I3: **không** planned hàng loạt Include không khớp exact name
- [x] AC-SUITE-R2: không có Report/Upload trên source → suite vẫn OK nếu còn Filter/Grid… (không fail chỉ vì thiếu Report)
- [x] AC-SUITE-REG: Filter/Grid/Dir/Main/Mail vẫn expand như cũ; sanitize `suite:../evil` vẫn `invalid_object`

### Code

- `clone_things/type3_file_clone.py` — list `suite_candidates`
- Test: `tests/clone_things/test_type3_file_clone.py` (fixture thêm Report + Upload + vài Include pattern)
- Doc tool / skill: cập nhật danh sách path `suite:`
---

## P2-1 — `seed_mode=token` + seed ngắn (skill + optional code)

### Quan sát

`seed=zccn`, `seed_mode=token` vẫn match cả `zccnslkdhtpnc*` và `zccnthxldtcth*` (cùng token prefix / boundary hiện tại).

### Việc

1. **Skill / doc (bắt buộc tối thiểu):** khuyến nghị agent:
   - seed **đủ dài** (tên controller đầy đủ hoặc ≥ đoạn phân biệt), hoặc
   - dùng `seed_mode=prefix` khi biết đúng tiền tố tên file.
2. **Optional code:** nếu dễ — tighten token (vd. yêu cầu token length tối thiểu, hoặc split theo boundary rõ hơn); **không** đổi default `contains` / `prefix`.

### AC

- [x] AC-SEED-DOC: skill/`reference-compare*` ghi rõ case seed ngắn + token
- [x] AC-SEED-OPT (optional): seed token quá ngắn → warning gợi ý dùng seed dài / `prefix`

---

## P2-2 — `suite:` thêm `Lookup/{name}.xml`

### Quan sát

Danh mục FBO đôi khi có `App_Data/Controllers/Lookup/{name}.xml` — suite hiện không bung.

### Việc

Thêm candidate:

```text
App_Data/Controllers/Lookup/{name}.xml
```

(Optional nếu thấy pattern thật trên AIH: `Lookup/{name}Form.xml` — chỉ khi inventory xác nhận.)

Cùng rule bỏ im nếu không tồn tại source.

### AC

- [x] AC-SUITE-L1: có Lookup → planned có; không có → không fail
- [x] AC-SUITE-L2: không kéo nhầm file Lookup khác tên

---

## P2-3 — Alias / `list_projects` UNC

### Quan sát

Agent phải nhớ full UNC (`\\172.168.5.14\CustomerPro\FBO\AIH\SP228`, …).

### Việc (optional)

Một trong các hướng (chọn **một**, đơn giản):

| Hướng | Mô tả |
|-------|--------|
| A | Config map alias → abs path (vd. `aih` → UNC AIH) trong MCP settings |
| B | Tool/param `list_projects` đọc từ config, trả `{alias, path}` |

**Không** hard-code UNC khách vào source MCP public nếu tránh được — ưu tiên config local.

### AC

- [ ] AC-ALIAS-1 (nếu làm): `project_source=aih` resolve được khi alias cấu hình
- [ ] AC-ALIAS-2: alias lạ → error rõ, không silent fallback sai path

Nếu **không** implement trong round này: ghi `deferred` trong PR note; agent tiếp tục dùng abs path.

---

## P3-4 — Warning riêng `Web.config` / `EmailConfig`

### Quan sát

File nhạy cảm (`Web.config`, `Options/EmailConfig.xml`, …) khi `copy_filter=missing` vẫn vào `will_copy` như file thường — chỉ gate đè qua overwrite + confirm.

### Việc (nice-to-have)

Khi planned/will chạm relative path nhạy cảm (denylist tối thiểu):

- `Web.config`
- `App_Data/Controllers/Options/EmailConfig.xml` (và hint path rút gọn nếu có)

→ thêm `warnings` dạng:

```text
sensitive_path: Web.config nằm trong will_copy (copy_filter=missing). Xác nhận với user trước khi execute.
```

**Không** auto-block missing copy (tránh phá workflow mang config thiếu) — chỉ **cảnh báo**.  
Overwrite vẫn giữ soft-gate hiện có.

### AC

- [x] AC-SENS-1: dry-run có Web.config missing → warning `sensitive_path`
- [x] AC-SENS-2: file thường không dính warning này

---

## P3-5 — Batch `read_local_file` — **KHÔNG LÀM**

Agent gọi nhiều `read_local_file` song song đã đủ.  
**Out of scope** round này — không thêm API batch.

---

## Thứ tự làm đề xuất

1. **P1-0** Report + Upload + Include (+ test + cập nhật skill/doc `suite:`)
2. **P2-2** Lookup (cùng PR với P1-0 nếu gọn)
3. **P2-1** skill note seed ngắn (và optional warning)
4. **P2-3** / **P3-4** chỉ nếu còn bandwidth
5. Bỏ qua **P3-5**

---

## Ranh giới

| Làm | Không làm |
|-----|-----------|
| Whitelist thêm Report / Upload / Include / Lookup | Full-project scan theo tên trong `suite:` |
| Exact Include pattern theo `{name}` | Copy nguyên folder `Include/` hoặc glob `*name*` |
| Warning / skill DX | Đụng `query_radar` schema |
| Alias qua config (optional) | Hard-code danh sách UNC mọi khách vào repo |

---

## Checklist gửi Gemini

```text
1) clone_things type=3: mở rộng suite_candidates:
   - App_Data/Controllers/Report/{name}.xml
   - App_Data/Controllers/Templates/Upload/{name}.xml
   - App_Data/Controllers/Templates/Upload/{name}ImportXml.xml
   - App_Data/Controllers/Include/{name}.xml|.ent|.txt|.Nested|.Nested.txt
   - App_Data/Controllers/Include/Extender.{name}, BIMode.{name},
     ImportOverWriteVoucher.{name}, Revert.{name}.ent,
     Tiny.External.{name}, Unit.{name}
   - App_Data/Controllers/Lookup/{name}.xml
2) Test AC-SUITE-R*/U*/I*/L* + regression suite cũ.
3) Skill/doc: liệt kê đủ path suite; ghi chú seed_mode=token + seed ngắn.
4) Optional: list_projects/alias; warning sensitive Web.config/EmailConfig.
5) KHÔNG: batch read_local_file; KHÔNG full-tree / copy cả Include/;
   KHÔNG glob substring Include; KHÔNG query_radar Main/Templates.
```

# FIX — `clone_things`: dependency infra `FastBusiness$*` bị exclude im lặng → miss clone

> **Mục đích:** Doc gửi **Gemini fix** — seed XML / clone proc business không kéo được dependency `FastBusiness$App$*` (vd `GetLayoutConfig`) dù object **đã drop trên target**.  
> **Ngày:** 2026-09-05  
> **Phạm vi code:** [`clone_things/service.py`](../../../clone_things/service.py) (queue + `is_excluded` + `DEFAULT_EXCLUDE_LIKE`), [`sql_object_summary/options.py`](../../../sql_object_summary/options.py), tests [`tests/clone_things/`](../../../tests/clone_things/)  
> **Không** đụng chrome_debug / dist trừ khi user yêu cầu rebuild MCP sau fix.

---

## 1. Vấn đề thực tế (repro live Newpearl)

### 1.1. Setup

| | Path |
|---|------|
| Source | `\\172.168.5.14\CustomerPro\FBI\LIONAGREVO_FBISP23\FBISP23` |
| Target | `\\172.168.5.14\CustomerPro\FBO\Newpearl\R2SP223` |
| Seed XML | `App_Data\Controllers\Grid\rptCheckVoucherEditLogGrid.xml` |
| SQL out | `e:\SQL Temp\newpearl_r2sp223 (6).sql` |

Proc seed từ Finding XML:

```sql
exec rs_rptCheckVoucherEditLogDetailViewForm ...
```

Trong body proc (source / sau clone) có:

```sql
EXEC FastBusiness$App$GetLayoutConfig @userID, 'number_format', @sysDB, @formatConfig OUTPUT
```

### 1.2. Repro bước

1. Trên **target App** (`Newpearl_R2SP223_A`) chạy:

```sql
DROP PROC dbo.rs_rptCheckVoucherEditLogDetailViewForm
DROP PROC dbo.FastBusiness$App$GetLayoutConfig
```

2. Confirm:

```sql
SELECT OBJECT_ID('dbo.rs_rptCheckVoucherEditLogDetailViewForm'),
       OBJECT_ID('dbo.FastBusiness$App$GetLayoutConfig')
-- cả hai NULL
```

3. Gọi MCP:

```text
clone_things(
  type=0,
  object=<abs Grid\rptCheckVoucherEditLogGrid.xml trên target>,
  project_source=<LION>,
  project_target=<Newpearl>,
  path_to_pasted=e:\SQL Temp\newpearl_r2sp223 (6).sql
)
```

### 1.3. Kết quả thực tế (BUG)

| Bucket JSON | Nội dung |
|-------------|----------|
| `cloned` | **chỉ** `dbo.rs_rptCheckVoucherEditLogDetailViewForm` |
| `skipped_exists` | Relative, Split, dmct4/9, dmreflog, options, reports — **không** có GetLayoutConfig |
| `skipped_noise` | `systypes` |
| `not_found_both` | `[]` |
| `warnings` | không nhắc GetLayoutConfig |

→ User deploy file SQL → DetailViewForm chạy → **Invalid object name `FastBusiness$App$GetLayoutConfig`**.

### 1.4. Đối chứng (seed đúng tên)

```text
clone_things(object='FastBusiness$App$GetLayoutConfig', ...)
```

- Trước khi drop: `skipped_exists` (đúng).
- Sau khi drop: sẽ vào `cloned` (vì **seed bypass exclude**).

→ Tool **biết** clone infra khi seed trực tiếp; chỉ **miss** khi object là **dependency con** của seed XML/business.

---

## 2. Root cause (đã đọc code)

### 2.1. AST / summary **có** thấy call

`query_database` summary `rs_rptCheckVoucherEditLogDetailViewForm`:

```json
"calls_direct": [
  { "name": "dbo.FastBusiness$App$GetLayoutConfig", "kind": "infra", "expanded": false },
  { "name": "dbo.FastBusiness$App$Table$Finding", "kind": "infra", "expanded": false },
  ...
]
```

`extract_object_dependencies` ([`service.py`](../../../clone_things/service.py) ~335–375) **enqueue** mọi `calls_direct[].name` + tables — **không** lọc infra tại bước extract.

### 2.2. Queue loop **drop im lặng** vì `DEFAULT_EXCLUDE_LIKE`

[`sql_object_summary/options.py`](../../../sql_object_summary/options.py):

```python
DEFAULT_EXCLUDE_LIKE = [
    r"^FastBusiness\$",
    r"^ff_",
    r"^fsd_",
]
```

[`clone_things/service.py`](../../../clone_things/service.py) ~666–709:

```python
seed_objects = set(queue)  # chỉ object seed từ XML / sql_name gốc
exclude_patterns = list(DEFAULT_EXCLUDE_LIKE) + DEFAULT_EXTRA_EXCLUDES

# ...
is_seed = (mode_seed == "sql_name" and is_root_step) or (raw_name in seed_objects)
if not is_seed:
    if is_excluded(item_clean_name, exclude_patterns):
        continue  # ← IM LẶNG: không cloned / skipped_exists / not_found / warning
```

Luồng bug:

```text
XML seed → queue: [rs_rpt...DetailViewForm, ...]
→ clone DetailViewForm (thiếu trên target)
→ extract deps → enqueue FastBusiness$App$GetLayoutConfig
→ pop GetLayoutConfig → is_seed=False → match ^FastBusiness\$ → continue
→ không bao giờ target-first check → user tưởng MCP "không phân tích ra"
```

**Lưu ý:** Rule exclude này hợp lý cho `query_database` call-graph (tránh bung cả nền tảng FBO). **Không** hợp lý copy nguyên sang `clone_things` khi mục tiêu là “thiếu gì trên target thì mang script”.

Doc cũ cũng đã ghi nhận (không fix): [`FIX-clone-things-dual-app-sys.md`](./FIX-clone_things-dual-app-sys.md) cuối file — *“FastBusiness$* vẫn có thể bị exclude dependency…”*.

---

## 3. Hành vi kỳ vọng sau fix

Khi seed XML `rptCheckVoucherEditLogGrid.xml` và **cả hai** proc đã drop trên target:

| Object | Kỳ vọng |
|--------|---------|
| `rs_rptCheckVoucherEditLogDetailViewForm` | `cloned` (như hiện tại) |
| `FastBusiness$App$GetLayoutConfig` | **`cloned`** (hoặc tối thiểu xuất hiện trong response — **không** biến mất) |
| `FastBusiness$App$Table$Finding` | Nếu thiếu trên target → `cloned`; nếu có → `skipped_exists` |
| `ff_*` / helper thật sự “platform luôn có” | Có thể vẫn exclude **nhưng** phải **log** (`skipped_excluded`) nếu muốn giữ denylist hẹp |

Khi GetLayoutConfig **đã có** trên target: `skipped_exists` (không clone lại).

Seed trực tiếp tên infra: giữ nguyên (bypass exclude như hiện tại).

---

## 4. Hướng sửa đề xuất (Gemini chọn 1 + implement)

### Phương án A — **Khuyến nghị cho `clone_things`** (tách policy khỏi summary)

Trong `clone_things` **không** áp `DEFAULT_EXCLUDE_LIKE` (`FastBusiness$` / `ff_` / `fsd_`) lên dependency queue.

Chỉ giữ `DEFAULT_EXTRA_EXCLUDES` (hoặc denylist hẹp hơn):

```text
^sp_  ^xp_  ^sys\.  ^sp_executesql$
(+ SYSTEM_NOISE_NAMES như hiện tại)
```

`query_database` / `sql_object_summary` **giữ** `DEFAULT_EXCLUDE_LIKE` — không đổi BA call-graph.

### Phương án B — Soft exclude (nếu muốn vẫn giảm noise)

Với dependency match exclude:

1. Vẫn `find_object_on_side(target)`  
2. Có trên target → `skipped_exists` **hoặc** bucket mới `skipped_excluded`  
3. **Không** trên target → **clone** (override exclude)  
4. Không bao giờ `continue` im lặng khi thiếu trên target  

### Phương án C — Allowlist 1-hop từ business seed

Expand tối đa depth=1 mọi `calls_direct` của object vừa `cloned`, kể cả infra; depth≥2 vẫn exclude `FastBusiness$%`.

---

## 5. Checklist implement cho Gemini

### 5.1. Correctness

- [ ] Repro §1.2–1.3: seed Grid XML sau khi drop 2 proc → JSON `cloned` chứa **cả** `DetailViewForm` **và** `GetLayoutConfig`
- [ ] Khi GetLayoutConfig còn trên target → `skipped_exists`, không nhét script thừa
- [ ] Seed `object=FastBusiness$App$GetLayoutConfig` vẫn hoạt động
- [ ] `sp_executesql` / `systypes` / `tempdb` vẫn không pollute `cloned`
- [ ] Dual App/Sys + USE section (`10_sql_file_use_db_sections`) không bị regression
- [ ] Response **không** nuốt dependency: hoặc clone / skipped_exists / skipped_excluded / warning — **cấm** drop im lặng khi thiếu trên target

### 5.2. Tests (bắt buộc thêm)

File gợi ý: `tests/clone_things/test_infra_dep_not_silently_excluded.py`

```text
Given: mock target thiếu rs_rptX và FastBusiness$App$GetLayoutConfig
  source có cả hai; extract_object_dependencies(rs_rptX) → [GetLayoutConfig]
When:  clone_things(object=rs_rptX hoặc xml seed trả rs_rptX)
Then:  cloned names ⊇ {rs_rptX, FastBusiness$App$GetLayoutConfig}
```

Case phụ:

- [ ] Target đã có GetLayoutConfig → chỉ clone rs_rptX; GetLayoutConfig ∈ `skipped_exists`
- [ ] `is_excluded("FastBusiness$App$GetLayoutConfig", DEFAULT_EXCLUDE_LIKE)` vẫn True (summary không đổi) — nhưng clone_things queue **không** silent-skip khi missing

### 5.3. Doc đồng bộ

- [ ] Cập nhật [`docs/doc/clone_things/`](../clone_things/) (resolution/flow): policy exclude dependency **khác** summary call-graph
- [ ] Ghi chú breaking: lần clone XML sau fix có thể **nhiều script hơn** (infra thiếu) — đúng ý user

### 5.4. Không làm

- [ ] Không đổi classifier `kind=infra` của summary (chỉ đổi policy clone queue)
- [ ] Không `execute_clone=true` mặc định
- [ ] Không mở rộng exclude thêm `rs_` / bảng dm*

---

## 6. Acceptance (user sign-off)

```text
1. DROP 2 proc trên Newpearl_R2SP223_A
2. clone_things seed Grid\rptCheckVoucherEditLogGrid.xml (LION → Newpearl)
3. JSON cloned chứa:
   - dbo.rs_rptCheckVoucherEditLogDetailViewForm
   - dbo.FastBusiness$App$GetLayoutConfig
4. File .sql có 2 block CREATE/DROP-CREATE tương ứng
5. pytest tests/clone_things/ -q → green
```

---

## 7. Tham chiếu nhanh code

| File | Chỗ liên quan |
|------|----------------|
| `clone_things/service.py` | `DEFAULT_EXTRA_EXCLUDES`, `is_excluded`, seed bypass (~705–709), `extract_object_dependencies`, enqueue (~793–808) |
| `sql_object_summary/options.py` | `DEFAULT_EXCLUDE_LIKE` — **đừng** reuse mù cho clone |
| `sql_object_summary/classifier.py` | `DEFAULT_INFRA_PATTERNS` — chỉ gắn nhãn, không phải lý do drop queue |
| Live XML | `.../Grid/rptCheckVoucherEditLogGrid.xml` → `rs_rptCheckVoucherEditLogDetailViewForm` |

---

## 8. Tóm tắt 1 câu cho Gemini

**`clone_things` enqueue đúng `FastBusiness$App$GetLayoutConfig` từ AST, rồi silent-`continue` vì `DEFAULT_EXCLUDE_LIKE`; sửa policy exclude dependency của clone (không nuốt infra thiếu trên target), giữ exclude sâu cho summary riêng.**

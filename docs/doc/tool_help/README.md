# tool_help — routing step → tool/mode/param (Jev + keyword fallback)

`tool_help` nhận các `steps` của plan agent + `context.task_requirement`,
trả per-step `{task_type, tool, call template, required_params, pitfalls,
confidence, alternatives, related_skills}` kèm `notice` (convention nhắc),
`warnings` (hậu kiểm plan↔classify), `related_skills` top-level (skill FBO
liên quan theo UR) và `proc_name_suggestions` (chuẩn hóa ID `zcxxxx`/
`rsxxxx` → `zc_xxxx`/`rs_xxxx`). Jev chỉ classify `task_type` — param agent
tự điền theo card.

Kiến trúc (`tool_help/`):

| File | Vai trò |
|------|---------|
| `cards.py` | `TASK_TYPES` (task_type → tool/call/required/pitfalls), `REQUIREMENT_TYPES`, `_JEV_TASK_DESCS`/`_JEV_REQ_DESCS` (desc nén gửi Jev — xem mục nén token), `TASK_TYPE_CATALOG`, `REQUIREMENT_TYPE_CATALOG`, `TOOL_PARAM_EXAMPLES` |
| `keywords.py` | Regex fallback khi Jev không khả dụng (thứ tự = ưu tiên) |
| `notices.py` | Notice rules theo task_types/requirement_type/ur_pattern |
| `skill_hints.py` | `SKILL_HINTS` (regex → skill FBO) → `related_skills` per-step + top-level theo UR |
| `service.py` | Ghép Jev answers + cards + notices + skill hints + `proc_name_suggestions` + `_consistency_warnings` + `_RESULT_CACHE` |
| `balance_catalog.py` | Catalog proc số-dư nội bộ (xem dưới) |

### `_consistency_warnings` — coverage mở rộng

Warning chỉ nhìn `task_type` top-1 trong **1 call** dễ false-positive.
Hiện tính coverage = top-1 ∪ `alternatives[].task_type` (`used_weak`) và
scan step-text:

- **Thiếu clone cho `clone_existing`**: step text chứa `save as`/`clone`/
  `copy theo|từ|giống`/`suite:` cũng tính là đã có bước clone (step ghép
  nhiều ý chỉ giữ 1 label).
- **Thiếu producer `.sql`**: bỏ qua nếu step nào nêu **path .sql có dấu
  `/` hoặc `\`** (file tồn tại sẵn — vd type=5/6 vừa sinh ở call trước);
  chỉ `script.sql` trần (không path) vẫn warning.
- **`db_balance` misroute**: không fire khi `db_balance` đã nằm trong
  alternatives của step.

## Nén token payload Jev (jev_desc)

1 call `tool_help` gửi `state` (agent_context + `task_type_catalog` 38
loại + steps + task_requirement + `requirement_type_catalog` 17 loại) +
`questions` (per-step `criteria` = dict {38 key: null}, +1 câu
requirement_type). Trước nén ~5.7k input tokens/call.

Nguyên tắc: **nén lossless-information** — giữ nguyên option set +
discriminator set + examples VN, chỉ encode telegraphic:

| Cơ chế | Vị trí | Ghi chú |
|--------|--------|---------|
| `jev_desc` telegraphic | `_JEV_TASK_DESCS`, `_JEV_REQ_DESCS` trong `cards.py` | Cùng option key + cùng discriminator/signal keyword của `desc`, bỏ prose. `desc` giữ làm doc người đọc + fallback. Catalog builder prefer `jev_desc` |
| Instructions nén | `_build_questions` trong `service.py` | Step question + requirement instructions telegraphic, giữ toàn bộ rule (template-only-new, exception retrieve_flow_*, voucher signal matching, none-default) |
| Compact JSON | `jev/client.py` — `json.dumps(..., separators=(",",":"))` | Bỏ whitespace, JSON vẫn hợp lệ |
| Result cache | `_RESULT_CACHE` trong `service.py` | `(steps, task_requirement)` trùng → trả kết quả ngay, 0 token/call lặp; cap 200 entries |

**Convention khi thêm/sửa type**: viết/cập nhật cả `desc` (doc) lẫn
`jev_desc` — test `test_jev_desc_coverage_all_types` fail nếu thiếu key
ở 2 dict nén. Rule viết jev_desc: mọi từ khóa VN và mọi mệnh đề "NOT
for X" của desc phải giữ dạng dense (`not:<type>`).

### Kết quả đo (A/B cặp-đôi trên Jev thật)

- `input_tokens`: ~5,750 → ~4,800/call (**-15~17%**); call lặp = 0 (cache).
- Payload: ~19.2k → ~14.9k chars (-23%) cho case 3-step; battery 38-step
  -5% (criteria keys ×N chiếm đa số — lever còn lại duy nhất).
- Golden eval `scratch/jev_eval.py`: **21/21 requirement_type + steps
  all-match** — giữ nguyên trước/sau nén.
- A/B 136 questions (`scratch/jev_ab2.py`): 108/136 cùng winner; diff
  chỉ trên step Jev vốn low-confidence (~0.3, coin-flip) hoặc cải thiện.

### Harness kiểm chứng (scratch/)

| File | Dùng khi |
|------|----------|
| `jev_eval.py` | Golden eval 21 case qua Jev thật — chạy sau khi sửa catalog/instructions |
| `jev_eval_cases.py` | Bộ case (id, ur, expected, steps, expected_steps) — thêm case vào đây |
| `jev_ab2.py` | A/B cặp-đôi old(verbose-desc+instr cũ) vs new(jev_desc+instr mới) trên cùng code — so winner + Δprob + tokens từng question |
| `jev_ab.py` | A/B 2-lần-chạy kiểu cũ (tag old/new, `diff old new`) — giữ để tham khảo |
| `dump_jev_payload.py` | In state+questions JSON để paste playground |

## db_balance — route "tính số dư/tồn" sang proc nội bộ

UR dạng *tính tồn kho / số dư đầu-cuối kỳ / công nợ / đáo hạn* dễ bị agent
tự viết `SUM` trên bảng raw (`r00$`, `cdtk$`, `cdkh`, `r70$/r90$`,
`wrkgl`, `dmtk0`). FBO có sẵn bộ proc chuẩn — task_type `db_balance`
(card → `query_database`) điều hướng agent dùng đúng proc nội bộ.

Card `call` = `mode=search, object_name='FastBusiness$Balance$%'` — list
proc THẬT trên DB đích trước (version/variant khác nhau: `*_KhanhTd`,
`zFastBusiness$*`, `*_goc`...).

### Map chiều → proc (chuẩn, harvest FBISP24)

| Nhóm | Proc (`FastBusiness$Balance$` + suffix) |
|------|------------------------------------------|
| Tồn kho | `Item` (+@Site/@Item/@DataType), `Lot`, `Location`, `LocationLot`, `SiteLocationItemLot`, `ItemAccount` (variant) |
| Sổ cái | `Account`, `AccountUnit`, `DCAccount` (@Account+@Customer, không @ResultType) |
| Công nợ/HĐ/vụ việc | `Customer`, `Customer2`, `CustomerUnit`, `Contract(+Unit)`, `ContractCustomer`, `BContract(+Unit)` (+@ContractType), `Job(+Unit)`, `JobCustomer(+Unit)`, `SalesEmployee(+Customer)`, `ManagementObject(+Unit)`, `Shop` (WIP) |
| Đầu tư/trái phiếu | `Investment` (param thu gọn, trả result sets — không #t) |
| Ghi dư đầu kỳ | `$OpeningBalance$UpdateCurrentStock`, `UpdateCurrentCustomerBalance`, `ConvertLot2Stock`, `ConvertCustomer2Account`; helper `GetBalanceDateAndPeriod` |

Param contract chung: `@Date @Unit <dims> @BalanceType @ResultType
[@DataType] @UserID @Admin @JoinClause @WhereClause`.

### Contract #t (quan trọng)

Proc `Balance$*` chạy dynamic SQL đổ vào temp table `#t` — **caller phải
`CREATE TABLE #t` đúng schema trước EXEC**. Không đoán schema: dùng
`query_database mode=search references='<proc>'` tìm proc/report đang
gọi rồi chép call-site (schema #t + ngữ nghĩa @BalanceType/@ResultType/
@DataType). Test tay: 1 batch `CREATE #t + EXEC + SELECT * FROM #t`.

### Wiring

- `keywords.py`: `(tính|lấy|xác định|hạch toán) ... (số dư|tồn|công nợ|
  dư nợ|dư có)`, `(số dư|dư|tồn) (đầu|cuối) kỳ`, `tồn kho`, `đáo hạn`,
  `balance$` → `db_balance`. Cố ý KHÔNG dùng verb xem/kiểm-tra để "check
  tồn trong bảng" vẫn route `db_run_sql`.
- `notices.py`: `db_balance ∈ _SQL_TASK_TYPES`; rule `balance_procs`
  nhắc không-SUM-raw + #t contract + verify param + fs_Post* là nhóm khác.
- `service.py` `_consistency_warnings`: step text match balance regex
  nhưng route `db_run_sql`/`db_run_file`/`no_match` → warn (bắt Jev
  misroute; step route `db_object`/`db_snippet` inspect proc = hợp lệ).

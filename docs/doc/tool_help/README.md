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
| `service.py` | Ghép Jev answers + cards + notices + skill hints + `proc_name_suggestions` + `_consistency_warnings` + `_RESULT_CACHE` (chỉ cache kết quả Jev) + `decision` act/review/fallback + `context.failed` → `recovery` |
| `request.py` | **Nguồn duy nhất** dựng request Jev (`build_jev_request`) — style `v1` (catalog trong state) / `v2` (mô tả trong criteria object). Eval harness dùng chung |
| `plan_rules.py` | Plan linter: Noul cờ per-step (cùng call) + regex fallback → `RULES` CLAUDE.md → `plan_patch`/`patched_plan` |
| `skill_suggest.py` + `skill_catalog.json` | Gợi ý skill theo recipe TypeSafe: gate 3 Noul + Choice skill (cùng call) → rerank top-3 (call 2). Catalog sinh bằng `scripts/build_skill_catalog.py` |
| `hierarchical.py` | Routing 2 tầng tool → task_type, beam K=3 (`routing: hierarchical`) |
| `recovery.py` | Recovery tầng wrapper (`_logged_call_tool`): lỗi tool → `recovery.next` (call tiếp theo) |
| `balance_catalog.py` | Catalog proc số-dư nội bộ (xem dưới) |
| `radar_templates.py` | Catalog 14 Cypher template query_radar + `RADAR_RULES` (xem mục dưới) |

Ngoài `tool_help/`: `query_database/column_hint.py` + `object_hint.py`
(recovery cần DB: Invalid column → cột thật + difflib/Jev gợi ý; Invalid
object → DB đúng app/sys, partition có thật, #temp, built-in mới, tên gần
đúng), `jev/client.py` (retry 429/529/timeout), `fastbusiness_mcp/utils/
call_log.py` (`session_id`/`seq` mọi dòng, `routing` của tool_help,
`recovery_rule`), `scripts/jev_feedback/` (router tự học — xem dưới).

### Cờ config Jev (`config_jev.yaml` → `jev:`)

| Key | Mặc định | Ý nghĩa |
|-----|----------|---------|
| `confidence_act` / `confidence_review` | 0.7 / 0.4 | 3 vùng `decision` |
| `prompt_style` | `v1` | `v2` = mô tả option trong criteria, state gọn |
| `routing` | `flat` | `hierarchical` = 2 tầng tool → task_type |

Đổi mặc định chỉ khi `scratch/jev_eval.py --steps-set` (67 step thật từ
log) không tụt. Đo 2026-10-09 (jev-1.13.0): v1/flat top1 94% top3 99%;
v2 91%/100%; hierarchical 94%/99% → giữ v1/flat. `--shuffle 2`: 3/67 step
đổi winner theo thứ tự option, đều dính `read_flat` (option thứ 2) → dời
`read_flat` sau `read_suggest_edit` (`cards._CATALOG_DEFER_AFTER`): v1/flat
top1 96% top3 97% (±1 step = biên dao động giữa các lần chạy Jev).

## Router tự học (`scripts/jev_feedback`)

`python -X utf8 -m scripts.jev_feedback all [--since D] [--replay]`:
đọc call log → tách phiên (`session_id`; log cũ tách theo `server_start`)
→ gán nhãn từng step tool_help với call agent thực làm (`FOLLOWED`/`ALT`/
`SWITCHED` × `_OK`/`_FAIL_FIXED`/`_FAILED`, `SKIPPED`) → harvest case eval
(`scratch/jev_eval_cases_auto.jsonl`, `status: pending` → duyệt thành
`approved` thì `jev_eval.py --steps-set` đọc thêm), bảng hiệu chỉnh ngưỡng,
sức khỏe card, hiệu quả luật recovery, đề xuất regex `keywords.py`
(chưng cất Jev — chỉ in, không tự sửa). Report:
`docs/doc/tool_help/feedback/<ngày>.md`. `--replay` gọi Jev cho tool_help
log cũ chưa có routing (cache `scratch/jev_feedback_replay.jsonl`).

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

1 call `tool_help` gửi `state` (agent_context + `task_type_catalog` 39
loại + steps + task_requirement + `requirement_type_catalog` 17 loại) +
`questions` (per-step `criteria` = dict {39 key: null}, +1 câu
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

### Wiring (db_balance)

- `keywords.py`: `(tính|lấy|xác định|hạch toán) ... (số dư|tồn|công nợ|
  dư nợ|dư có)`, `(số dư|dư|tồn) (đầu|cuối) kỳ`, `tồn kho`, `đáo hạn`,
  `balance$` → `db_balance`. Cố ý KHÔNG dùng verb xem/kiểm-tra để "check
  tồn trong bảng" vẫn route `db_run_sql`.
- `notices.py`: `db_balance ∈ _SQL_TASK_TYPES`; rule `balance_procs`
  nhắc không-SUM-raw + #t contract + verify param + fs_Post* là nhóm khác.
- `service.py` `_consistency_warnings`: step text match balance regex
  nhưng route `db_run_sql`/`db_run_file`/`no_match` → warn (bắt Jev
  misroute; step route `db_object`/`db_snippet` inspect proc = hợp lệ).

## radar_templates — Jev gợi ý Cypher template cho query_radar

`query_radar` chỉ chấp nhận 1 trong **14 Cypher template cố định**
(nguồn: skill `fbo-mcp-query-radar` → `reference-radar-templates.md`).
Agent tự chọn dễ sai (đặc biệt cặp T8/T9/T11). `tool_help` giờ chọn hộ
bằng câu hỏi phụ Jev + nhúng catalog để agent đối chiếu.

### Flow

- `_build_questions`: step nào `keyword_route == "graph_query"` → thêm câu
  `step{i}_graph_tpl` (choice trên 14 `RADAR_TEMPLATE_CATALOG`) vào cùng
  batch Jev — không tốn round-trip. `state.radar_template_catalog` chỉ gắn
  khi có câu phụ.
- Step route `query_radar` + Jev trả `stepN_graph_tpl` → step output có
  `radar_template` = `{id, when, cypher, params, confidence_to_use_top,
  alternatives}` và `call.cypher_query` được fill skeleton luôn (copy dict
  — `card_for` trả reference vào `TASK_TYPES`, KHÔNG mutate trực tiếp).
- Bất kỳ step nào `tool == "query_radar"` → payload top-level có
  `radar_templates` = `{_rules: RADAR_RULES, template_1..14: {when,
  cypher, params}}` — kể cả nhánh keyword fallback (Jev chết vẫn có
  catalog, chỉ thiếu suggestion).

### Cặp hay nhầm (đã nén vào jev_desc)

| Hỏi | Template | Không phải |
|-----|----------|-----------|
| Hàng xóm 1 hop mọi hướng | T8 | cụm/anh em gián tiếp → T11 |
| Chuỗi outbound 2 bước (a)→(b)→(c) | T9 | 1 hop → T8 |
| "xung quanh"/"liên quan"/"cụm" depth-2 | T11 | T8 không đủ |

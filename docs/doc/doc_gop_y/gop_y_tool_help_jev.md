# Góp ý: MCP tool `tool_help` — định tuyến tool/mode bằng Jev (TypeSafe System One)

> Mục tiêu: thêm tool `tool_help` vào FastBusiness MCP để agent hỏi trước khi gọi tool thật:
> "việc X nên dùng tool nào, mode/param gì?" → server trả về recommendation kèm confidence,
> giúp agent tránh gọi sai tool/sai mode và bớt round-trip lãng phí.

## 1. Bối cảnh & vấn đề

FastBusiness MCP (`fastbusiness-mcp`) hiện có ~8 tool: `query_database`, `get_xml_entities`,
`query_radar`, `read_local_file`, `search_qlyc`, `clone_things`, `compare_things`, `search_files`.
Trong thực tế sử dụng (session làm danh mục `zccntttdcd`), agent gặp các lỗi điển hình:

| Vấn đề thực tế | Hệ quả |
|---|---|
| Tên param không thống nhất: `read_local_file` dùng `file_path`, `search_files` dùng `root`, `compare_things` dùng `folder_a` | 4–6 call lỗi liên tiếp chỉ vì đoán sai tên param |
| `search_files mode=files_only` dễ hiểu nhầm là "list file chứa chuỗi" — thực tế nó match theo **tên file**, `files_scanned: 0` | Agent tìm `dmku` trong nội dung nhưng nhận 2000 file rác; phải đổi `mode=content` mới đúng |
| Khi validation fail, error message echo kèm **toàn bộ catalog tool (~900 dòng)** | 1 thông báo "thiếu param" tốn ~3.6k dòng context |
| `mcp_list_tools` bị truncate vì schema quá dài | Agent không đọc hết được schema → đoán param → lỗi tiếp |
| Không có tool `list_dir` — phải mượn `compare_things inventory=true` | Output JSON khổng lồ cho việc "xem folder có file gì" |

=> Agent cần 1 điểm hỏi **trước khi gọi tool**: cho intent → nhận {tool, mode, param đúng tên, ví dụ, pitfalls, confidence}.

## 2. Jev / TypeSafe là gì (đọc từ docs.typesafe.ai)

Jev là "System One model" của TypeSafe — model chuyên **ra quyết định có cấu trúc cho code**,
không sinh text như LLM thường.

### Cơ chế

- Request = **1 `state`** (string | JSON object | array text) + **nhiều `questions`**.
- Mọi question được evaluate **độc lập, song song** trên cùng state — thêm question gần như
  không tăng latency. Có thể mix nhiều loại question trong 1 call.
- Response = typed answer + `probabilities` + `confidence`. Code dùng trực tiếp để
  branch/route — không cần parse text.

### 3 primitive

| Primitive | Hỏi | Trả về |
|---|---|---|
| **Choice** | Chọn 1 option trong tập cố định | `choice`, `probabilities` per option, `confidence` |
| **Score** | Chấm theo thang level có thứ tự (0=thấp … n=cao) | `score` (float), `probabilities` per level, `confidence` |
| **Noul** | Yes/No | `noul` 0–1 (không có confidence) |

### Confidence

- `confidence` được derive từ **shape của phân bố xác suất**: tập trung 1 option → cao;
  dàn đều → thấp. Không phải xác suất của option thắng.
- Pattern khuyến nghị của TypeSafe: chia 3 vùng —
  **high → act**, **medium → proceed with caution / hỏi thêm**, **low → không act, fallback**.
- Threshold nên scale theo "risk" của action — route sai tool có hậu quả thấp (tốn 1 call),
  nên ngưỡng act có thể đặt vừa phải (~0.6–0.7).

### State structure

- Nên dùng JSON object với field đặt tên rõ (message, order, policy...), giúp model
  hiểu quan hệ giữa các phần — thay vì nối string.
- `instructions` của question và `criteria` của từng option/level đều nhận
  **string | object | array | null** — có thể nhét mô tả có cấu trúc cho từng option.

### Triết lý "how to build"

- **Code giữ control flow + side effects**; System One chỉ xử lý judgment hẹp.
- Tách câu hỏi rộng thành nhiều câu hỏi hẹp; compose kết quả bằng code.
- Mỗi question là "gut-check mà người có kinh nghiệm trả lời trong vài giây" —
  KHÔNG nhờ nó reasoning dài hay generate nội dung.

### ⚠️ Caveat ngôn ngữ

> Docs ghi: Jev train chủ yếu **tiếng Anh**; ngôn ngữ khác (gồm tiếng Việt) được chấp nhận
> nhưng **accuracy thấp hơn**.

Intent của agent/user thường là tiếng Việt → cần 1 trong 2:
1. Server-side normalize/dịch intent sang EN trước khi gọi Jev (rẻ nhất: bảng từ khóa
   VN→EN, hoặc nhét cả 2 vào state).
2. Giữ intent VN trong state nhưng viết `instructions` + `criteria` option song ngữ /
   có ví dụ VN — cần đo thử accuracy.

### API

- `POST /v1/systemone`, field `model` (vd `jev-latest`), có SDK Python/JS.
- Giá/model xem trang Models — cần API key của user.

## 3. Thiết kế đề xuất `tool_help`

### Nguyên tắc chính (theo đúng triết lý System One)

**Jev chỉ làm phần routing (quyết định), KHÔNG generate usage text.** Chi tiết tool
(param đúng tên, bảng mode, pitfalls, ví dụ call) nằm trong **usage card tĩnh** do code
server trả về — nguồn lấy từ docs hiện có (`docs/doc`, skill `fbo-mcp-*`).

### Signature

```python
tool_help(intent: str, context: dict | None = None) -> dict
```

- `intent`: mô tả tự do việc cần làm, VN/EN.
  VD: "tìm file XML nào chứa chuỗi dmku", "list file trong folder Main",
  "đọc summary controller Dir", "check syntax file sql không chạy".
- `context` (optional): `{path, ext, db: 'app'|'sys', ...}` — nhét vào state giúp Jev chọn chuẩn hơn.

### Bước 1 — Choice task-type (không chọn thẳng tool)

Vấn đề: "mode" phụ thuộc tool → nếu hỏi 2 Choice (tool rồi mode) trong 1 request thì
options của câu mode chưa biết nên lấy theo tool nào. Giải pháp: hỏi **task-type** —
một không gian option phẳng, mỗi task-type map 1-1 tới (tool + mode/param mặc định)
bằng bảng tĩnh trong code:

| task-type option | → tool + call mặc định |
|---|---|
| `read_xml_summary` | `read_local_file`, `read_option=3` |
| `read_xml_block` | `read_local_file`, `read_option=2` + symbol/line |
| `read_xml_suggest_edit` | `read_local_file`, `read_option=4` |
| `search_content` | `search_files`, `mode=content` (pattern = chuỗi nội dung) |
| `search_by_filename` | `search_files`, `mode=files_only` + `include_glob` |
| `find_definition` / `find_reference` | `search_files`, `mode=definition|reference` |
| `list_folder` | `compare_things`, `kind=folder`, `inventory=true` |
| `diff_projects` | `compare_things`, `kind=file|folder|sql` |
| `clone_objects` | `clone_things` |
| `sql_schema` | `query_database`, `query_type=0` |
| `sql_select` | `query_database`, `query_type=1` |
| `sql_execute` | `query_database`, `query_type=2` |
| `sql_parseonly` | `query_database`, `query_type=3` |
| `xml_entities` | `get_xml_entities` |
| `lint_entity` | `query_radar` |
| `search_qlyc` | `search_qlyc` |
| `no_match` | fallback — không tool nào phù hợp |

Option `no_match` quan trọng: cho Jev lối thoát thay vì ép chọn 1 tool.

State gửi lên Jev:

```json
{
  "intent": "tìm file nào chứa chuỗi dmku trong project",
  "context": {"path": "\\\\server\\proj\\App_Data\\Controllers", "ext": ".xml"},
  "tools_note": "FastBusiness MCP on UNC Windows paths"
}
```

Question (1 Choice):

```json
{
  "type": "choice",
  "key": "task_type",
  "instructions": "Which task type best matches the agent's intent? Choose no_match if none fit.",
  "options": {
    "search_content": "Find WHICH FILES contain a string/symbol inside file content (grep). Pattern matches file CONTENT.",
    "search_by_filename": "List files matching a name/glob pattern. Does NOT read file content.",
    "list_folder": "List files+metadata in a directory (like ls). No content, no diff.",
    "...": "..."
  }
}
```

Response Jev → `choice="search_content"`, `probabilities={search_content: .9, ...}`,
`confidence=.85` → code map ra `search_files mode=content`.

### Bước 2 — Trả usage card tĩnh

```json
{
  "recommendation": {
    "task_type": "search_content",
    "tool": "search_files",
    "confidence": 0.85,
    "probabilities": {"search_content": 0.9, "search_by_filename": 0.06, "no_match": 0.04},
    "call": {
      "root": "<absolute path>",
      "pattern": "dmku",
      "mode": "content",
      "include_glob": "*.xml"
    },
    "required_params": ["root", "pattern"],
    "pitfalls": [
      "mode=files_only KHÔNG đọc nội dung — chỉ match tên file. Tìm chuỗi trong file phải dùng mode=content.",
      "root phải là đường dẫn ABSOLUTE."
    ],
    "alternatives": [
      {"task_type": "search_by_filename", "tool": "search_files", "probability": 0.06}
    ]
  }
}
```

### Ngưỡng confidence (3 vùng)

- `>= 0.7`: trả recommendation + usage card của top-1.
- `0.4 – 0.7`: trả **top-2** kèm 1 dòng khác biệt cốt lõi ("content = đọc nội dung;
  files_only = match tên"), để agent tự quyết.
- `< 0.4` hoặc `no_match` thắng: trả catalog **gọn** (bảng tên tool + 1 dòng mô tả),
  không dump full schema.

### Fallback & cache

- Jev API lỗi/timeout → fallback: keyword-match tĩnh (bảng từ khóa VN/EN → task-type),
  hoặc trả catalog gọn. Không để `tool_help` thành single point of failure.
- Cache kết quả theo `hash(intent_normalized + context)` — cùng intent lặp lại không
  tốn call API.

### Chi phí

- 1 `tool_help` call = 1 Jev request nhỏ (state ngắn + 1 Choice). Rẻ hơn nhiều so với
  giá của 1 call tool sai (vài trăm→vài nghìn dòng rác vào context agent).

## 4. Việc nên làm trước/song song (không cần Jev, ROI cao)

1. **Error response chỉ echo schema của đúng tool bị lỗi** thay vì full catalog —
   sửa trong `tool_errors.py`/`agent_messages.py`.
2. **Thống nhất tên param đường dẫn** (`file_path`/`root`/`folder_a` → 1 tên, hoặc
   chấp nhận alias) — giảm hẳn lỗi validation.
3. Usage card tĩnh per task-type vẫn hữu dụng kể cả khi routing làm bằng keyword —
   nên build card trước, gắn Jev sau.

## 5. Câu hỏi mở cần bàn

1. API key TypeSafe lấy đâu, quota/giá `jev-latest` ra sao? (chưa đọc trang Models/Pricing)
2. Accuracy Jev với intent tiếng Việt — cần bộ test ~20 intent VN/EN trước khi quyết
   có cần bước dịch không.
3. Nên expose `tool_help` như MCP tool thường (agent chủ động gọi) hay middleware
   tự validate/suggest khi tool khác fail validation?
4. Bảng task-type → (tool, mode) duy trì ở đâu: YAML config hay hardcode? YAML dễ
   chỉnh không cần rebuild exe.
5. Có cần log pair (intent → choice → tool agent thực sự gọi → kết quả) để đo
   precision của routing không?

## 6. Phạm vi MVP đề xuất

- [ ] Bảng task-type + usage card tĩnh (YAML) cho ~15 task-type ở mục 3.
- [ ] `tool_help(intent)` với routing keyword-match trước (không Jev) — validate shape
      response + card.
- [ ] Gắn Jev Choice sau khi có API key; A/B so với keyword baseline trên bộ test intent.
- [ ] Sửa error response gọn (mục 4.1) — độc lập, làm luôn được.

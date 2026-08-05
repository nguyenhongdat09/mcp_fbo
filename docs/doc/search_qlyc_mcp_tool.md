# MCP tool `search_qlyc` — gọi RAG QLYC Search API

**Mục tiêu:** Thêm tool MCP mới trong `mcp_fbo` để agent gọi semantic search ticket/UR qua HTTP API dự án RAG_QLYC. `base_url` + `api_key` nằm trong `config.yaml` (localhost khi test máy local).

**Phụ thuộc API (đọc, không sửa code RAG):**  
`E:\PythonProject\RAG_QLYC\docs\doc\` — đặc biệt:

- `04-phase-search-api.md` — `POST /api/search`
- `05-phase-auth-api-key.md` — Bearer
- `05-phase-filter-bp-lt.md` — `bp_lt`
- `07-phase-search-pagination.md` — `page` / `page_size` / `max_total`

**Gemini / agent implement đúng spec này — không mở rộng scope.**

---

## 1. Phạm vi

### Trong phạm vi

* Tool MCP mới: **`search_qlyc`** (chỉ search, không health tool).
* Package mới `search_qlyc/` (pattern giống `queryDatabase` / `find_entity_by_xml`).
* Config block `rag_qlyc` trong `config.yaml` (root dự án MCP).
* Đăng ký tool + `call_tool` trong `fastbusiness_mcp/server.py`.
* Lỗi mạng / timeout / HTTP fail → **JSON `ok: false`** cho agent (không crash MCP).
* Test tối thiểu + cập nhật docs agent nếu cần.

### Ngoài phạm vi (CẤM)

* Không tạo tool `health_qlyc`.
* Không sửa code dự án `RAG_QLYC`.
* Không JWT / ACL / UI / đổi tool MCP hiện có.
* Không hard-code `api_key` trong source Python (chỉ đọc config).
* Không expose `base_url` / `api_key` làm tham số tool.

---

## 2. Kiến trúc

```
Agent (Cursor / Gemini)
    │  MCP tool: search_qlyc
    ▼
fastbusiness_mcp/server.py     # list_tools + call_tool
    │
    ▼
search_qlyc/                   # package mới
  ├── __init__.py              # export search_qlyc(...)
  ├── client.py                # HTTP POST + Bearer
  ├── service.py               # đọc config, gọi client, map lỗi → dict
  └── formatter.py             # dict → JSON string (TextContent)
    │
    ▼
RAG_QLYC API  {base_url}
  Authorization: Bearer {api_key}
  POST /api/search
```

---

## 3. Config (`config.yaml`)

Thêm vào **root** `E:\PythonProject\mcp_fbo\config.yaml` (file user đang dùng):

```yaml
# RAG QLYC Search API (MCP tool search_qlyc)
rag_qlyc:
  base_url: "http://localhost:8000"
  api_key: "fsd@@123"
  timeout_seconds: 30
```

| Key | Bắt buộc | Mặc định gợi ý | Ghi chú |
|-----|----------|----------------|---------|
| `base_url` | có | `http://localhost:8000` | Không trailing slash bắt buộc; client normalize |
| `api_key` | có | `fsd@@123` | Giống `RAG_API_KEY` phía RAG (dev nội bộ) |
| `timeout_seconds` | không | `30` | Timeout HTTP |

Sau này user đổi `base_url` / `api_key` trên server thật — **không** cần đổi code.

Nếu thiếu `base_url` hoặc `api_key` (rỗng sau strip) → trả JSON lỗi `config_thieu` (không gọi HTTP).

---

## 4. Contract tool MCP

### Tên

`search_qlyc`

### Description (gợi ý cho agent)

```
Semantic search ticket yêu cầu (UR) qua RAG QLYC API.
Trả fcode1, ma_da, noi_dung, score và metadata liên quan.
Dùng khi cần tìm ticket/UR theo nghiệp vụ — không thay query_database hay FBOGraph.
```

### Input schema

| Tham số | Type | Bắt buộc | Mặc định | Ghi chú |
|---------|------|----------|----------|---------|
| `query` | string | **có** | — | Câu tìm kiếm ngữ nghĩa |
| `ma_da` | string | không | — | Filter đúng dự án |
| `bp_lt` | string | không | — | Filter bộ phận LT (vd. `FSD`) |
| `page` | int | không | `1` | Trang từ 1 |
| `page_size` | int | không | `20` | `1…50` |
| `max_total` | int | không | `100` | Cửa sổ xếp hạng `1…100` |

**Không** expose `top_k` (dùng phân trang API Phase 7).

### Body gửi API

```http
POST {base_url}/api/search
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "query": "...",
  "ma_da": "...",          // chỉ gửi nếu agent truyền
  "bp_lt": "...",          // chỉ gửi nếu agent truyền
  "page": 1,
  "page_size": 20,
  "max_total": 100
}
```

Bỏ field `null`/rỗng khỏi JSON body (không gửi `ma_da: null`).

### Response thành công (MCP → agent)

Bọc response API, thêm `ok: true`:

```json
{
  "ok": true,
  "query": "...",
  "page": 1,
  "page_size": 20,
  "max_total": 100,
  "total": 20,
  "total_pages": 1,
  "items": [
    {
      "stt_rec": "...",
      "fcode1": "UR08C",
      "ma_da": "NHUAASIA",
      "noi_dung": "...",
      "score": 0.95,
      "ma_lt1": "...",
      "bp_lt": "FSD",
      "ngay_ht": "...",
      "ten_menu_ngan": "..."
    }
  ]
}
```

Giữ nguyên field API trả về trong `items` (không tự invent cột).

### Response lỗi (MCP → agent)

Luôn HTTP-level MCP success với TextContent JSON — **không** để exception bubble làm tool crash:

```json
{
  "ok": false,
  "error": "khong_ket_noi_api",
  "detail": "Connection refused / timed out / ..."
}
```

| Tình huống | `error` |
|------------|---------|
| Không kết nối / timeout / DNS / network | `khong_ket_noi_api` |
| HTTP 401 | `unauthorized` |
| HTTP 4xx/5xx khác | `api_loi` |
| Thiếu/rỗng `base_url` hoặc `api_key` trong config | `config_thieu` |

`detail`: ngắn, có status code nếu có; **không** log/trả nguyên giá trị `api_key`.

---

## 5. File cần tạo / sửa

### Tạo

| File | Trách nhiệm |
|------|-------------|
| `search_qlyc/__init__.py` | `from .service import search_qlyc` |
| `search_qlyc/client.py` | HTTP POST; raise/return lỗi có cấu trúc |
| `search_qlyc/service.py` | `search_qlyc(query, ..., config) -> dict` |
| `search_qlyc/formatter.py` | `format_search_result(result) -> str` (JSON) |
| `search_qlyc/test_search_qlyc.py` (hoặc `tests/...`) | Test lỗi kết nối + map config |

### Sửa

| File | Việc |
|------|------|
| `config.yaml` | Thêm block `rag_qlyc` |
| `fastbusiness_mcp/server.py` | Import, `Tool(...)`, nhánh `call_tool` |
| `requirements.txt` | Chỉ thêm dependency HTTP **nếu** không dùng stdlib |

**HTTP client:** ưu tiên **stdlib** `urllib.request` (không thêm package). Nếu team muốn `httpx`/`requests` thì thêm rõ vào `requirements.txt` — không bắt buộc.

---

## 6. Implementation notes

### 6.1 `service.search_qlyc`

Signature gợi ý:

```python
def search_qlyc(
    query: str,
    ma_da: str | None = None,
    bp_lt: str | None = None,
    page: int = 1,
    page_size: int = 20,
    max_total: int = 100,
    config: dict | None = None,
) -> dict:
    ...
```

* `config` = dict đã load từ `config.yaml` (server truyền `self.config.get("rag_qlyc")` hoặc cả config root + service tự lấy key `rag_qlyc`).
* Validate nhẹ: `query` strip rỗng → `ok: false`, `error: "query_thieu"` (optional nhưng khuyến nghị).
* Clamp/`page`/`page_size`/`max_total` theo bound API nếu agent gửi lệch (hoặc để API trả 422 rồi map `api_loi`).

### 6.2 `client.py`

* URL: `{base_url.rstrip('/')}/api/search`
* Header: `Authorization: Bearer {api_key}`, `Content-Type: application/json`
* Timeout: `timeout_seconds`
* Thành công 200: parse JSON body → dict
* Network error: caller map → `khong_ket_noi_api`
* Không print/log `api_key`

### 6.3 `server.py`

1. `list_tools`: thêm `Tool(name="search_qlyc", ...)` đúng schema §4.
2. `call_tool`:

```python
elif name == "search_qlyc":
    result = search_qlyc(
        query=arguments["query"],
        ma_da=arguments.get("ma_da"),
        bp_lt=arguments.get("bp_lt"),
        page=int(arguments.get("page", 1)),
        page_size=int(arguments.get("page_size", 20)),
        max_total=int(arguments.get("max_total", 100)),
        config=self.config.get("rag_qlyc"),
    )
    return [TextContent(type="text", text=format_search_result(result))]
```

3. Lỗi bất ngờ trong `try/except` hiện có: vẫn được, nhưng **ưu tiên** service đã trả `ok: false` trước khi raise.

### 6.4 Formatter

```python
import json

def format_search_result(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
```

---

## 7. Tests tối thiểu

| Case | Kỳ vọng |
|------|---------|
| Config thiếu `api_key` | `ok=false`, `error=config_thieu` |
| `base_url` trỏ host không tồn tại / port đóng | `ok=false`, `error=khong_ket_noi_api` |
| (Optional) Mock HTTP 200 | `ok=true`, có `items` |
| (Optional) Mock HTTP 401 | `ok=false`, `error=unauthorized` |

Không bắt buộc RAG API đang chạy khi CI/unit test lỗi kết nối.

---

## 8. Cách test tay (máy local)

1. Chạy RAG API (1 worker) tại `http://localhost:8000` với `RAG_API_KEY=fsd@@123`.
2. Đảm bảo `config.yaml` MCP có `rag_qlyc` như §3.
3. Restart MCP server.
4. Gọi tool:

```text
search_qlyc(query="Tạo tự động hóa đơn mua trong nước", page=1, page_size=20)
```

5. Tắt RAG API → gọi lại → nhận JSON `ok: false`, `error: khong_ket_noi_api`.

PowerShell kiểm tra API độc lập:

```powershell
$headers = @{ Authorization = "Bearer fsd@@123" }
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/search" `
  -Headers $headers -ContentType "application/json" `
  -Body '{"query":"hoa don mua","page":1,"page_size":20,"max_total":100}'
```

---

## 9. Checklist hoàn thành

- [ ] `rag_qlyc` có trong `config.yaml` (localhost + key).
- [ ] Package `search_qlyc/` hoạt động (client + service + formatter).
- [ ] Tool `search_qlyc` hiện trong `list_tools` / Cursor MCP.
- [ ] Gọi được khi RAG API local chạy + Bearer đúng.
- [ ] API tắt / không kết nối → JSON `ok: false`, `error: khong_ket_noi_api`.
- [ ] Không sửa RAG_QLYC; không phá tool MCP cũ.
- [ ] Không hard-code key trong `.py`.
- [ ] Test tối thiểu xanh.

---

## 10. Prompt triển khai (gửi Gemini)

```
Dự án MCP FBO tại E:\PythonProject\mcp_fbo.
Đọc và làm đúng file: E:\PythonProject\mcp_fbo\docs\doc\search_qlyc_mcp_tool.md
Tham chiếu contract API (chỉ đọc, KHÔNG sửa code RAG):
  E:\PythonProject\RAG_QLYC\docs\doc\04-phase-search-api.md
  E:\PythonProject\RAG_QLYC\docs\doc\05-phase-auth-api-key.md
  E:\PythonProject\RAG_QLYC\docs\doc\05-phase-filter-bp-lt.md
  E:\PythonProject\RAG_QLYC\docs\doc\07-phase-search-pagination.md

Nhiệm vụ:
1. Thêm block rag_qlyc vào config.yaml (base_url=http://localhost:8000, api_key=fsd@@123, timeout_seconds=30).
2. Tạo package search_qlyc/ (client HTTP + service + formatter) theo pattern queryDatabase.
3. Đăng ký MCP tool search_qlyc trong fastbusiness_mcp/server.py (list_tools + call_tool).
4. Tool params: query (bắt buộc), ma_da, bp_lt, page, page_size, max_total. Không expose top_k / api_key / base_url.
5. POST {base_url}/api/search với Authorization: Bearer {api_key}.
6. Thành công: JSON ok=true + body API. Lỗi mạng/timeout: ok=false, error=khong_ket_noi_api. 401→unauthorized. Config thiếu→config_thieu. Không crash MCP.
7. Test tối thiểu + không refactor ngoài phạm vi. Không sửa E:\PythonProject\RAG_QLYC.
```

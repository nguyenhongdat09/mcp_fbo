# profiler — SQL Trace cho agent (giống FSD Profiler)

Tool `profiler` bắt batch SQL + lỗi trên server SQL của project FBO bằng classic
SQL Trace (`sp_trace_*`), chạy bằng login riêng `profile` (config.yaml → `profiler.*`),
cần quyền `ALTER TRACE`.

## Workflow

```
profiler(file_path=<abs path trong project>, action='start', ...)
# → chạy thao tác cần bắt (Playwright test / user bấm app / query_database)
profiler(file_path='.', action='read', wait_seconds=15)   # lặp được, incremental
profiler(file_path='.', action='stop')
```

- `trace_id=0` = trace `fbo_mcp_*` mới nhất — không cần nhớ ID.
- Auto-stop server-side (mặc định 30 phút) — MCP crash trace vẫn tự tắt.
- `read` incremental theo `EventSequence`; `read_mode='detail' + seq=N` xem full TextData.
- `list` / `clean` dọn trace mồ côi (chỉ đụng `fbo_mcp_*`).

## Filter — QUAN TRỌNG khi server nhiều project/dev

| Param | Hiệu quả trên FBO | Ghi chú |
|---|---|---|
| `login_name` | **MẠNH NHẤT** — SQL login riêng của project (`Uid` trong Web.config, vd `HAOHOA`) | chỉ bắt traffic app của project này |
| `host_name` | Máy chạy app (IIS server, vd `FSGSERVER`) | kết hợp login_name lọc đúng web app |
| `db_type` | `app`=DB _A (mặc định) / `sys`=DB _S / `all`=cả hai | **login/menu/metadata FBO chạy trên _S** — debug login phải dùng `sys`/`all` |
| `app_name` | CHỈ khớp khi app set `APP=` (vd `FSD`, `SQLCMD`) | session FBO web là `.Net SqlClient Data Provider` (%UserID KHÔNG được replace) → kém hữu ích |
| `text_like` | TextData LIKE %kw% — lúc start lẫn read | |
| `spid` | Khi đã biết session cụ thể | |

Đã verify trên SQL2008 (172.168.5.14\SQL2008) bằng `sys.sysprocesses`.

## Tiết kiệm token

- `errors_only=true`, `event_filter='Exception,User Error Message'` (post-filter, không cần start lại)
- `collapse=true` (default) gom TextData trùng → `×N`
- compact mặc định cắt text ~120 chars; `read_mode='full'` + `text_max_chars`
- `max_rows` phân trang; `since_seq=0` đọc lại từ đầu file

## Combo Playwright MCP (reproduce lỗi UI)

Kết hợp với `@playwright/mcp` của Microsoft (không cần code riêng):

```
profiler(action='start', db_type='all', login_name='HAOHOA', host_name='FSGSERVER')
browser_navigate / browser_click ...  (reproduce lỗi UI)
profiler(action='read')               # SQL app vừa bắn
profiler(action='stop')
```

## Giới hạn

- Không xóa được file `.trc` trên server (`profile` không sysadmin) — file nhỏ trong SQL Log dir.
- Registry persist ở `%TEMP%/fbo_mcp_trace_registry.json` — cùng máy mới recover được.
- `file_path` bắt buộc mỗi call (truyền `'.'` sau lần đầu nhờ sticky project).

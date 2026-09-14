# docs/doc/gemini — Spec gửi Gemini (độc lập)

Các file **không** nhúng vào `docs/doc/clone_things/01`–`14`. Gửi Gemini từng file.

| File | Việc | Có code MCP? |
|------|------|----------------|
| [GEMINI-agent-no-shell-fbo.md](./GEMINI-agent-no-shell-fbo.md) | **(1)** Bỏ Shell FBO — skill + tool sẵn | **Không** tool mới |
| [GEMINI-clone_things-type3-file-clone.md](./GEMINI-clone_things-type3-file-clone.md) | **(2)** `clone_things` type=3 copy file bất kỳ | **Có** — implement MCP |
| [GEMINI-mcp-agent-gaps.md](./GEMINI-mcp-agent-gaps.md) | **(3)** Gaps sau type=3: inventory, search_files, dir/glob guard, confirm_overwrite, read abs… | **Có** — tinh chỉnh / tool mới |
| [GEMINI-mcp-dx-residual.md](./GEMINI-mcp-dx-residual.md) | **(4)** DX sót sau verify: `search_files` priority scan; type=3 `planned[]` sample khi truncated | **Có** — tinh chỉnh |
| [GEMINI-mcp-polish-nits.md](./GEMINI-mcp-polish-nits.md) | **(5)** Polish: warning truncated đủ số candidates; `user_prompt` type=3 không dump dài | **Có** — polish nhỏ |
| [GEMINI-mcp-agent-convenience.md](./GEMINI-mcp-agent-convenience.md) | **(6)** Convenience: copy_filter message, `suite:`, path hint, seed_mode; P3 doc tạo≠clone — **không** đụng query_radar Main/Templates | **Có** (P3 = doc) |
| [GEMINI-mcp-suite-extend-residual.md](./GEMINI-mcp-suite-extend-residual.md) | **(7)** Mở rộng `suite:` Report+Upload+Include(+Lookup); residual seed ngắn / alias / sensitive warning; **không** batch read / không copy cả Include | **Có** (P3-5 = không làm) |

Sau khi type=3 / gaps / residual / polish / convenience / suite-extend ship, mới cập nhật index `clone_things/README.md` / `02_tool_api.md` (optional).

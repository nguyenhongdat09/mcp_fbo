# 05 — `kind=file`

## 1. Mục tiêu

So **hai file absolute path** trên đĩa (local hoặc UNC): metadata + nội dung text (hoặc binary meta).

Giống tinh thần VS Code Select for Compare: mặc định **không coi CRLF vs LF là khác nội dung**.

## 2. Input

| Param | Bắt buộc |
|-------|----------|
| `kind=file` | có |
| `file_a`, `file_b` | abs path tồn tại là file |
| `ignore_line_endings` | default true |
| `ignore_whitespace` | default false |
| `mode`, `max_diff_lines`, `context_lines` | `context_lines` (default 3) truyền vào `difflib.unified_diff` / SequenceMatcher hunks |

Không cần `project_source` / `project_target`. Không dùng `schema`.

## 3. Pipeline

1. Validate path exists + is_file (fail-fast `file_not_found`).
2. Đọc **bytes gốc**; `sha256_raw = sha256(bytes)`.
3. `meta_stat`: size, created (`st_ctime` Windows), modified (`st_mtime`), line_ending detect trên bytes, `is_binary`.
4. **Binary detect (trước decode):**
   - Có byte `0x00` trong sample đầu (vd 8KB) → binary
   - Hoặc sau mọi decode text strategy fail theo §3.1 cuối → binary
5. Nếu **ít nhất một bên binary**: không text hunks; so `sha256_raw` / size; status identical hoặc different.
6. Text (cả hai không binary):
   - Decode theo §3.1 → string
   - Normalize: strip BOM; nếu `ignore_line_endings`: `\r\n`/`\r`→`\n`; splitlines; nếu `ignore_whitespace`: strip mỗi dòng
   - `difflib` với `n=context_lines` → hunks + counts
7. Flags (§3.2).

### 3.1. Encoding fallback (chốt)

Thứ tự thử decode:

1. `utf-8-sig` (BOM UTF-8)
2. `utf-8` (strict)
3. `cp1258` (strict) — SQL/Windows VN thường gặp
4. **`latin-1` (không fail)** — fallback cuối cho text “đọc được đủ byte”; gắn `encoding="latin-1"` + optional warning `encoding_fallback_latin1`

**Không** còn bước “decode fail hoàn toàn rồi crash”.  
Nếu đã classify binary ở bước 4 thì không vào decode chain.

Ghi `encoding` thực dùng vào meta từng file.

### 3.2. Flags nội dung / meta (chốt đơn giản)

```text
identical_content     = (lines_a_normalized == lines_b_normalized)
only_line_ending_diff = identical_content AND (sha256_raw_a != sha256_raw_b)
identical_meta        = (size, created, modified, sha256_raw) khớp từng field
```

Giải thích: nếu text sau normalize giống nhưng bytes gốc khác → hầu luôn là CRLF/LF (hoặc BOM-only). Không cần công thức “size khác chỉ vì `\r`”.

Nếu `identical_content` và `sha256_raw` bằng → không phải only_line_ending_diff (giống hệt bytes).

`next_actions`: `only_line_ending_diff` → `["ignore_line_ending_only"]`.

### 3.3. Soft limit size

File > `max_file_bytes` (default 10MB, optional config): đọc/truncate + `warnings: ["file_too_large_truncated"]`; vẫn cố meta + partial diff nếu implement được — hoặc refuse text diff, chỉ meta. **Chốt v1:** warn + diff trên phần đầu đã đọc / hoặc skip hunks với message — ghi rõ trong code; test P1.

## 4. Output

Xem [04_json_response.md](./04_json_response.md) §5.1 và §5.6 (`mode=body` sample).

`mode=summary`: hunks + preview ngắn (`context_lines` ảnh hưởng ngữ cảnh trong preview), `unified_diff` có thể `""`.  
`mode=hunks`/`body`: điền `unified_diff` truncate `max_diff_lines`.

## 5. Edge cases

| Case | Kỳ vọng |
|------|---------|
| Chỉ khác CRLF | identical_content + only_line_ending_diff |
| file_a thiếu | fail-fast `file_not_found` |
| File rỗng vs rỗng | identical_content, identical bytes |
| UTF-8 BOM vs không BOM cùng text | BOM-only: `identical_content=true` (BOM bị strip khi normalize), `sha256_raw` khác → `only_line_ending_diff=true`. **Chấp nhận** hành vi này (`sha256` luôn hash bytes gốc). |

## 6. CẤM

- Dump toàn bộ nội dung file vào JSON
- Gọi `code --diff` bắt buộc
- Đổi / ghi file
- Decode crash không fallback latin-1 / binary

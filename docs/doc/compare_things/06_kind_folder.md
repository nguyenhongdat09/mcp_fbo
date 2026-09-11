# 06 — `kind=folder`

## 1. Mục tiêu

So **hai thư mục** (local hoặc UNC), ví dụ:

```text
folder_a = \\172.168.5.14\CustomerPro\FBO\AIH\SP228\bin
folder_b = \\172.168.5.14\CustomerPro\FBI\FAHASAKHANHHOA\FBISP24\bin
```

Agent cần:

1. File có ở A không có ở B (và ngược lại) — theo **relative path**
2. Cùng relative path nhưng khác **size / created / modified**
3. (Tuỳ chọn) khác nội dung hash/text

## 2. Input

| Param | Default | Ghi chú |
|-------|---------|---------|
| `folder_a`, `folder_b` | required | Directory |
| `recursive` | true | Walk subtree |
| `compare_content` | **false** | Phù hợp `bin` DLL |
| `hash_max_bytes` | 1MB | Chỉ khi compare_content |
| `include_glob` | `*` | vd `*.dll` |
| `exclude_glob` | `""` | vd `*.pdb` |
| `name_compare` | case_insensitive | Windows |
| `meta_tolerance_seconds` | 0 | Dung sai thời gian |
| `max_objects` | 200 | Truncate compared detail (không cắt summary list tên) |
| `detail` | **false** | Mặc định False (chỉ trả summary inventory tên file gọn gàng, `compared=[]`). Đặt True để kèm `compared[]` per-file |
| `detail_status` | `""` | Khi detail=True: lọc status xuất vào `compared[]` theo CSV (vd `"different_content"` hoặc `"missing_on_b,different_content"`) |

## 3. Pipeline

1. Validate cả hai là directory (UNC ok).
2. `os.scandir` / `rglob` → map `relative_path → meta` (normalize `/`, casefold nếu case_insensitive).
3. Apply include/exclude glob (fnmatch).
4. Join keys:
   - chỉ A → `missing_on_b`
   - chỉ B → `missing_on_a`
   - cả hai → so meta trước (size / created / modified theo tolerance)
   - nếu `compare_content=true` → §3.1
5. `identical_meta` không dump list — chỉ count + `omitted_identical_count`.
6. Ưu tiên compared: missing → different_content → different_meta → errors.

### 3.1. `compare_content=true` (chốt hunks)

Với mỗi cặp cùng relative path, size ≤ `hash_max_bytes`:

1. Tính `sha256_raw` hai bên (nếu chưa có).
2. Hash bằng → không `different_content` (meta vẫn có thể khác → `different_meta` only).
3. Hash khác:
   - Detect binary như `kind=file`.
   - **Binary:** `status=different_content`, `meta_diff` có thể gồm `sha256`, **không** `content.hunks`.
   - **Text:** gọi **cùng shared line-diff** như `file_compare` (`context_lines`, `ignore_line_endings`, …).
     - `status=different_content`
     - **Bắt buộc** field `content` giống kind=file: `hunks` với `a_line_start/end`, `b_line_start/end`, preview; `unified_diff` theo `mode`.
     - `next_actions`: `["review_hunks"]` (và/hoặc `edit_target_file`)

Size > `hash_max_bytes`: `status=skipped_hash` (hoặc giữ different_meta nếu meta đã lệch) + note không diff content.

Sample JSON: [04_json_response.md](./04_json_response.md) §5.4.1.

## 4. Output

Xem [04](./04_json_response.md) §3 folder + §5.4.

`message` ví dụ:  
`A có 5 file mà B thiếu; 12 file khác size/ngày; 400 file meta giống (không liệt kê hết).`

`next_actions` top: `copy_missing_to_b`, `investigate_version_dll` tùy summary.

## 5. Edge cases

| Case | Kỳ vọng |
|------|---------|
| Permission denied 1 file | `errors[]` + tiếp tục batch |
| Symlink | Follow hoặc skip — **chốt v1: không follow symlink ra ngoài root** (nếu khó: skip + warning) |
| Folder rỗng | counts 0, identical |
| `include_glob=*.dll` | Chỉ DLL |

## 6. CẤM

- Hash mặc định mọi file trong `bin`
- Tự copy/xóa file trên share
- Dump danh sách identical hàng trăm path không truncate
- Recursive vô hạn qua junction (cẩn thận cycle — dùng visited realpath nếu cần)

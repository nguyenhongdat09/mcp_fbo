# 04 — JSON Response: agent-actionable

## 1. Mục tiêu

Agent đọc JSON **một lần** phải:

1. Biết **giống / thiếu / lệch**
2. Với file/proc lệch text: biết **dòng X–Y** (source/a và target/b)
3. Có **`next_actions`** / `message` để chọn bước tiếp chuẩn (clone, sửa, bỏ qua)

**CẤM** response kiểu chỉ `"different": true` không tín hiệu.

## 2. Envelope chung

```json
{
  "success": true,
  "kind": "sql",
  "mode": "summary",
  "summary": { },
  "compared": [ ],
  "message": "Tiếng Việt 1–3 câu.",
  "next_actions": ["..."],
  "warnings": [],
  "error_code": null,
  "error": null
}
```

Khi lỗi validate / không chạy được:

```json
{
  "success": false,
  "kind": "file",
  "error_code": "file_not_found",
  "error": "...",
  "summary": null,
  "compared": [],
  "message": "Không so được vì file_a không tồn tại.",
  "next_actions": ["fix_paths"]
}
```

## 3. `summary` (nhìn nhanh)

Các list tên **truncate** theo `max_objects`; nếu cắt: `"truncated": true` + count đủ.

### sql / table / xml

```json
"summary": {
  "missing_on_target": ["dbo.ProcA"],
  "missing_on_source": [],
  "identical": ["dbo.ProcB"],
  "different": ["dbo.GetApprovalRole"],
  "encrypted_skip": ["dbo.SecretProc"],
  "errors": ["dbo.X: permission denied"],
  "truncated": false,
  "counts": {
    "missing_on_target": 1,
    "missing_on_source": 0,
    "identical": 1,
    "different": 1,
    "encrypted_skip": 1,
    "errors": 1
  }
}
```

### folder

```json
"summary": {
  "files_a": 420,
  "files_b": 415,
  "missing_on_b": ["Extender.Foo.dll"],
  "missing_on_a": ["Legacy.X.dll"],
  "identical_meta_count": 400,
  "omitted_identical_count": 400,
  "different_meta": ["FastBusiness.Core.dll"],
  "different_content": [],
  "errors": [],
  "truncated": false
}
```

Ghi chú: **không** dump hết `identical` vào list mặc định — dùng count.

### file (1 cặp)

```json
"summary": {
  "identical_content": false,
  "identical_meta": false,
  "only_line_ending_diff": false,
  "status": "different"
}
```

## 4. Hunk (file / xml / sql text)

Số dòng **1-based**, sau `text_normalize` (BOM strip, optional CRLF→LF, optional whitespace strip).

```json
{
  "id": 1,
  "change_type": "replace",
  "a_line_start": 40,
  "a_line_end": 55,
  "b_line_start": 40,
  "b_line_end": 62,
  "lines_added": 8,
  "lines_removed": 1,
  "preview": [
    "@@ context",
    "- old line",
    "+ new line"
  ],
  "signals_in_hunk": []
}
```

Với `kind=sql` dùng tên rõ:

- `source_line_start` / `source_line_end`
- `target_line_start` / `target_line_end`

(Hoặc thống nhất `a`=`source`, `b`=`target` — **chốt implement: sql dùng source_/target_; file/xml dùng a_/b_**.)

`change_type`: `insert` | `delete` | `replace`.

`preview`: luôn có ở `mode=summary` nhưng ngắn (max ~5–8 dòng/hunk; tổng preview mọi hunk ≤ ~40 dòng hoặc theo `max_diff_lines` chia).

`unified_diff`: string; rỗng ở summary nếu đã có hunks+preview; bắt buộc điền (truncate) ở `mode=hunks`/`body`.

## 5. `compared[]` theo kind

### 5.1. `kind=file`

```json
{
  "status": "different",
  "identical_content": false,
  "identical_meta": false,
  "only_line_ending_diff": false,
  "file_a": {
    "path": "E:\\\\a\\\\x.xml",
    "exists": true,
    "size": 1200,
    "created": "2024-01-01T10:00:00",
    "modified": "2024-06-01T12:00:00",
    "sha256": "abc...",
    "encoding": "utf-8-sig",
    "line_ending": "crlf",
    "is_binary": false
  },
  "file_b": { "path": "...", "line_ending": "lf", "sha256": "def..." },
  "meta_diff": ["size", "modified", "sha256", "line_ending"],
  "content": {
    "lines_a": 200,
    "lines_b": 210,
    "lines_added": 12,
    "lines_removed": 2,
    "hunk_count": 3,
    "hunks": [ ],
    "diff_truncated": false,
    "unified_diff": ""
  },
  "next_actions": ["review_hunks", "edit_target_file"]
}
```

Chỉ khác CRLF:

- `identical_content=true`, `only_line_ending_diff=true`, `hunks=[]`
- `next_actions`: `["ignore_line_ending_only"]`

Binary khác:

- `is_binary=true`, không hunks text; so size/sha256; `next_actions`: `["compare_binary_meta_only"]`

### 5.2. `kind=sql`

```json
{
  "name": "dbo.GetApprovalRole",
  "object_type": "proc",
  "status": "different",
  "db_type_found": "app",
  "fingerprint_source": "sha256:...",
  "fingerprint_target": "sha256:...",
  "signals": ["target_refs_dmduyet", "source_refs_vdmduyetuq"],
  "content": {
    "lines_source": 180,
    "lines_target": 175,
    "hunk_count": 2,
    "hunks": [
      {
        "id": 1,
        "change_type": "replace",
        "source_line_start": 88,
        "source_line_end": 102,
        "target_line_start": 88,
        "target_line_end": 95,
        "signals_in_hunk": ["dmduyet_vs_vdmduyetuq"],
        "preview": ["- ... FROM dmduyet ...", "+ ... FROM vdmduyetuq ..."]
      }
    ],
    "diff_truncated": false,
    "unified_diff": ""
  },
  "next_actions": ["review_hunks_before_alter", "clone_things_type1_mode_read_0"]
}
```

Status khác:

| status | content/hunks | next_actions gợi ý |
|--------|---------------|-------------------|
| `identical` | rỗng | `[]` hoặc `noop` |
| `missing_on_target` | không hunk | `clone_things_type0` |
| `missing_on_source` | không hunk | `investigate_source` |
| `encrypted_skip` | không body | `skip_encrypted` |
| `error` | `error` field | `retry_or_fix_permission` |
| `different` | **bắt buộc hunks** (nếu đọc được 2 body) | review + optional clone type1 |

### 5.3. `kind=table`

```json
{
  "name": "dbo.dmuqduyet",
  "status": "different",
  "schema_diff": {
    "columns_only_source": [],
    "columns_only_target": ["ma_x"],
    "columns_type_mismatch": [
      {"column": "so_luong", "source": "int null", "target": "bigint null"}
    ],
    "pk_diff": false,
    "pk_source": ["id"],
    "pk_target": ["id"],
    "indexes_only_source": [],
    "indexes_only_target": ["IX_ma_x"],
    "indexes_mismatch": [],
    "triggers_only_source": [],
    "triggers_only_target": [],
    "triggers_mismatch": []
  },
  "next_actions": ["alter_add_column", "review_index"]
}
```

Không có line hunks.

Identical khi fingerprint schema (sorted by column name) khớp — kể cả ordinal khác.

### 5.4. `kind=folder` (mỗi relative path một compared item khi lệch / missing; identical omit)

```json
{
  "relative_path": "FastBusiness.Core.dll",
  "status": "different_meta",
  "meta_diff": ["size", "modified"],
  "a": {"size": 120000, "created": "...", "modified": "...", "sha256": null},
  "b": {"size": 121500, "created": "...", "modified": "...", "sha256": null},
  "next_actions": ["investigate_version_dll"]
}
```

`missing_on_b`:

```json
{
  "relative_path": "Extender.Foo.dll",
  "status": "missing_on_b",
  "a": {"size": 1000, "modified": "..."},
  "b": null,
  "next_actions": ["copy_missing_to_b"]
}
```

#### 5.4.1. Folder + `compare_content=true` + text khác (bắt buộc giống file hunks)

```json
{
  "relative_path": "Config/notes.txt",
  "status": "different_content",
  "meta_diff": ["size", "sha256", "modified"],
  "a": {"size": 120, "sha256": "aaa...", "modified": "...", "is_binary": false},
  "b": {"size": 140, "sha256": "bbb...", "modified": "...", "is_binary": false},
  "content": {
    "lines_a": 10,
    "lines_b": 12,
    "hunk_count": 1,
    "hunks": [
      {
        "id": 1,
        "change_type": "replace",
        "a_line_start": 3,
        "a_line_end": 5,
        "b_line_start": 3,
        "b_line_end": 7,
        "preview": ["- old", "+ new"]
      }
    ],
    "diff_truncated": false,
    "unified_diff": ""
  },
  "next_actions": ["review_hunks"]
}
```

DLL/binary hash khác: cùng `status=different_content` nhưng **không** có `content.hunks` (chỉ meta/sha256).

### 5.5. `kind=xml`

Giống `file` nhưng thêm:

```json
"relative_path": "Dir/PUDelegationApproval.xml",
"path_source": "E:\\\\...\\\\Controllers\\\\Dir\\\\...",
"path_target": "E:\\\\...\\\\Controllers\\\\Dir\\\\..."
```

Missing file một bên → status `missing_on_target` / `missing_on_source`.

### 5.6. Sample `mode=body` (file hoặc sql) — thêm đoạn quanh hunk

Ngoài fields của `summary`/`hunks`, mỗi hunk (hoặc object) có thể có:

```json
{
  "mode": "body",
  "compared": [
    {
      "status": "different",
      "content": {
        "hunk_count": 1,
        "hunks": [
          {
            "id": 1,
            "a_line_start": 40,
            "a_line_end": 42,
            "b_line_start": 40,
            "b_line_end": 44,
            "preview": ["- x", "+ y"],
            "body_a": "line39\nline40 old\nline41\nline42\nline43\n",
            "body_b": "line39\nline40 new\nline41\nline42\nline43\nline44\n"
          }
        ],
        "unified_diff": "--- a\n+++ b\n@@ ...\n",
        "diff_truncated": false
      }
    }
  ]
}
```

Quy tắc `body_*`:

- Chỉ lấy **cửa sổ quanh hunk** (vd hunk ± `context_lines`, tổng ≤ `max_diff_lines` dòng / hoặc ≤ ~4KB/hunk).
- **CẤM** `body_a` = full file/proc.
- Sql: dùng `body_source` / `body_target` thay `body_a` / `body_b`.
- Nếu truncate: `body_truncated: true` trên hunk.
## 6. Catalog `next_actions` (chuẩn hóa string)

| Code | Ý nghĩa |
|------|---------|
| `ignore_line_ending_only` | Chỉ khác CRLF — không cần clone |
| `review_hunks` | Đọc hunks rồi quyết sửa |
| `review_hunks_before_alter` | Proc khác — xem dòng trước khi ALTER |
| `edit_target_file` | Sửa file target theo hunk |
| `clone_things_type0` | Object thiếu target — clone |
| `clone_things_type1_mode_read_0` | Có ở 2 bên nhưng khác — paste ALTER để sửa |
| `clone_things_type1_mode_read_1` | Cần analyze deps trước |
| `skip_encrypted` | Không đọc được definition |
| `alter_add_column` / `review_pk` / `review_index` / `review_trigger` | Table |
| `copy_missing_to_b` / `copy_missing_to_a` | Folder missing (gợi ý — tool không copy) |
| `investigate_version_dll` | DLL khác size/date |
| `fix_paths` | Path sai |
| `noop` | Không cần làm gì |

Top-level `next_actions` = hợp nhất ưu tiên từ các compared (dedupe, max ~8).

## 7. Agent đọc JSON để chọn bước tiếp

```text
1. success=false → sửa params theo error_code
2. Đọc summary.counts / lists
3. Với mỗi different (sql/file/xml):
     - Đọc hunks line ranges → biết chỗ lệch
     - Đọc signals / preview → hiểu nghiệp vụ
     - next_actions → clone_things hoặc sửa file
4. missing_on_target → clone_things type=0
5. only_line_ending_diff → bỏ qua
6. table schema_diff → script ALTER / hỏi user (không auto)
7. folder missing/different_meta → báo user / copy thủ công
```

## 8. Token budget

| Thành phần | Giới hạn gợi ý |
|------------|----------------|
| Số hunks trả chi tiết | ≤ 30; nếu nhiều hơn: giữ ranges, cắt preview, `diff_truncated=true` |
| Preview mỗi hunk | ≤ 8 dòng |
| `unified_diff` | ≤ `max_diff_lines` dòng |
| `mode=body` snippet | ≤ 2× `max_diff_lines` chars quanh hunk hoặc ≤ 3 object ngắn |
| Folder compared items | ≤ `max_objects`, ưu tiên missing + different_meta trước |

**CẤM** mặc định đưa full `definition` proc vào JSON (kể cả mode=body trừ khi object rất ngắn và vẫn truncate có cờ).

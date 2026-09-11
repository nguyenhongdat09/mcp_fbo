# FIX — `compare_things`: (A) `seed` cho xml/folder + (B) `diff_reason` khi text lệch bytes nhưng `hunk_count=0`

> **File ĐỘC LẬP cho Gemini fix**  
> **Ngày:** 2026-09-11  
> **Mức:** P2 hữu ích cho agent (hai task độc lập trong cùng doc)  
> **Không làm:** cắt `summary` list tên folder (`max_summary_names`) — user **không chấp nhận**.  
> **Liên quan:** seed SQL đã có [`sql_seed_scan.py`](../../../compare_things/sql_seed_scan.py); folder `detail` đã OK; file đã có `diff_reason` một phần trong [`file_compare.py`](../../../compare_things/file_compare.py).

---

## 0. Prompt Gemini (copy-paste)

```text
Fix compare_things theo docs/doc/doc_fix/FIX-compare_things-seed-xml-folder-and-diff-reason.md

=== PART A — seed xml/folder ===
1) Mở rộng param seed (đã có cho sql) dùng được cho kind=xml và kind=folder.
2) kind=xml + seed (object rỗng hoặc kết hợp):
   - Quét App_Data/Controllers (hoặc Controllers) dưới project_source VÀ project_target
   - Match keyword vào relative path / filename (không đọc full body)
   - Tập candidate = union relative path hai bên (chuẩn hóa /), rồi so từng path như object list hiện tại
   - max_objects giới hạn số candidate đem đi compare (giống tinh thần sql seed)
3) kind=folder + seed:
   - Khi seed có giá trị: dùng để lọc file trong folder_a/folder_b (tên/relative path chứa keyword)
   - Có thể kết hợp include_glob (AND): vừa khớp glob vừa khớp seed
   - Không seed = behavior folder hiện tại
4) Docstring MCP + tests: seed=APVHistoryFlow tìm ra Include/.../APVHistoryFlow*.xml|txt

=== PART B — diff_reason khi hunk_count=0 ===
5) folder_compare: khi sha256 khác nhưng sau normalize_text_lines hai bên lines bằng nhau
   → KHÔNG để agent bí với different_content + hunk_count=0 im lặng.
   Phải set diff_reason (bom | line_ending | whitespace | encoding_or_bytes | normalized_identical)
   và điều chỉnh status/next_actions hợp lý (xem mục 3).
6) Đồng bộ kind=file nếu còn case status=different mà hunk_count=0 (hiếm); folder là repro chính (aspx).
7) Tests: mock 2 aspx cùng dòng text, khác BOM hoặc CRLF vs LF, sha khác → diff_reason đúng, không review_hunks mù.
8) pytest tests/compare_things/ pass.
```

---

# PART A — `seed` cho `kind=xml` và `kind=folder`

## A1. Vấn đề

Agent biết keyword (`APVHistoryFlow`, `Flow`) nhưng **chưa biết** relative path → phải Glob/subagent quét cây Controllers.

SQL đã có:

```text
compare_things(kind=sql, seed="vdmduyetuq,dmuqduyet", ...)
```

XML/folder chưa: xml bắt buộc `object=Dir/Foo.xml`; folder chỉ `include_glob` (fnmatch đuôi), không search tên chứa chuỗi giữa path.

## A2. Semantics

| Kind | `object` | `seed` |
|------|----------|--------|
| `sql` | list tên object (giữ nguyên) | scan DB (giữ nguyên) |
| `xml` | list relative dưới Controllers (giữ) | **mới**: discover relative path theo keyword rồi compare |
| `folder` | n/a | **mới**: filter relative path / filename chứa keyword (AND với `include_glob` nếu có) |
| `file` / `table` | không dùng seed | ignore / error mềm tùy chọn — ưu tiên **ignore** |

Keyword parse: giống SQL — split `[,;\s]+`, trim, case-insensitive match.

### A2.1 `kind=xml` + `seed`

Roots quét (tồn tại cái nào dùng cái đó):

- `{project}/App_Data/Controllers`
- `{project}/Controllers`

Rule:

1. Walk recursive; **skip `*.f`**.
2. Chỉ xét file text controller thường: ít nhất `.xml`, `.txt`, `.js`, `.ent` (đồng bộ policy “mọi đuôi trừ .f” — có thể lấy mọi non-`.f` dưới Controllers để đơn giản).
3. Relative path chuẩn `/` hoặc `\` → normalize về dạng tool xml đang dùng (vd `Include/XML/APVHistoryFlowToolbar.xml`, `Dir/...`).
4. Hit nếu **bất kỳ** keyword nằm trong relative path (hoặc basename) — không cần đọc nội dung file (tránh token + I/O).
5. Candidate set = **union** hits từ source ∪ target (để bắt `missing_on_target` / `missing_on_source`).
6. Sau discover → pipeline compare xml hiện tại (kể cả `xml_view=flat|original`).
7. `max_objects`: cắt số path đem compare; ghi `truncated` / warning nếu cắt. **Không** cắt list tên trong summary bucket nếu đã compare đủ trong limit — giống sql.

`object` + `seed` cùng có: union (object explicit ∪ seed hits), rồi cap `max_objects`.

`object` rỗng + `seed` rỗng → giữ lỗi xml hiện tại (phải có object hoặc seed).

### A2.2 `kind=folder` + `seed`

Trong vòng lọc file folder:

- `include_glob` vẫn áp (mặc định `*`).
- Thêm: relative path hoặc name **chứa** một keyword trong `seed` (case-insensitive).
- `seed=""` → không thêm filter (như hiện tại).

Ví dụ:

```text
compare_things(
  kind="folder",
  folder_a=...\Controllers,
  folder_b=...\Controllers,
  seed="APVHistoryFlow",
  include_glob="*",
  detail=false
)
```

≈ chỉ các path có `APVHistoryFlow` — không cần Glob tay + không cần trỏ sẵn `Include/XML` (vẫn **khuyến nghị** trỏ hẹp khi biết path).

### A2.3 Response gợi ý (xml seed)

```json
{
  "kind": "xml",
  "seed": "APVHistoryFlow",
  "summary": {
    "seed_hits": 3,
    "missing_on_target": [],
    "missing_on_source": ["Include/XML/APVHistoryFlowToolbar.xml", "..."],
    "different": [],
    "identical": []
  }
}
```

`seed_hits` optional nhưng hữu ích. Message tiếng Việt nhắc đã resolve từ seed.

## A3. Tests Part A

1. Temp dirs Controllers: source có `Include/XML/APVHistoryFlowToolbar.xml`, target không → `missing_on_target` / `missing_on_b` đúng chiều.
2. folder + seed + include_glob=`*.xml` → không lấy `.txt` dù tên khớp seed.
3. seed rỗng + xml object vẫn work (regression).

## A4. Non-goals Part A

- Không search **nội dung** file theo keyword (chỉ path/name) — tránh chậm + nhiễu.
- Không thay Glob toàn project ngoài Controllers cho xml (scope Controllers). Folder seed chỉ trong `folder_a`/`folder_b` đã truyền.

---

# PART B — `diff_reason` khi bytes/sha lệch nhưng `hunk_count=0`

## B1. Repro live

```text
compare_things(
  kind="folder",
  folder_a=...\FBISP24\Main,
  folder_b=...\SP228\Main,
  include_glob="poctpo*.aspx",
  compare_content=true,
  detail=true
)
```

Quan sát trước đây:

- `status=different_content`, `size`/`sha256` khác (±3 byte)
- `content.hunk_count=0`, `lines_added/removed=0`
- `next_actions=review_hunks` → agent **bí** (không có dòng để mở)

## B2. Root cause (code)

[`folder_compare.py`](../../../compare_things/folder_compare.py):

1. `sha256_a != sha256_b` → `has_content_diff=True` → luôn xếp `different_content`.
2. Với text: `normalize_text_lines(...)` (mặc định **strip BOM** + **chuẩn hóa CRLF**) rồi `build_line_diff`.
3. Nếu lines sau normalize **bằng nhau** → `hunk_count=0` nhưng status vẫn `different_content`.

[`file_compare.py`](../../../compare_things/file_compare.py) xử lý tốt hơn: lines bằng → `status=identical` + `diff_reason` in (`line_ending`,`bom`,`whitespace`,`bytes`). **Folder chưa đồng bộ.**

## B3. Fix bắt buộc (folder text)

Sau khi decode + normalize, nhánh:

```text
if sha khác:
  if binary: giữ different_content + investigate_version_dll (như hiện tại)
  else:  # text
    if lines_a == lines_b:
      # Lệch chỉ ở lớp bytes / normalize
      status = "different_meta"   # HOẶC giữ bucket riêng — xem B3.1
      diff_reason = ...           # bắt buộc
      content.hunk_count = 0
      next_actions = không dùng review_hunks
    else:
      status = "different_content"
      diff_reason = "text_lines"
      build_line_diff như hiện tại
```

### B3.1 Chọn status / bucket summary (chốt)

**Khuyến nghị (ít phá agent):**

| Tình huống | `status` | Vào summary bucket | `diff_reason` | `next_actions` |
|------------|----------|--------------------|---------------|----------------|
| sha khác, lines normalize **bằng** | `different_meta` | `different_meta` | `bom` / `line_ending` / `whitespace` / `encoding_or_bytes` | `ignore_normalized_bytes_diff` hoặc `noop` |
| sha khác, lines **khác** | `different_content` | `different_content` | `text_lines` | `review_hunks` |
| binary sha khác | `different_content` | `different_content` | `binary` | `investigate_version_dll` |

**Phát hiện `diff_reason` khi lines bằng:**

1. So raw: BOM UTF-8 (`EF BB BF`) một bên → `bom`
2. `detect_line_ending(bytes_a) != detect_line_ending(bytes_b)` → `line_ending`
3. Nếu `ignore_whitespace` đang bật và raw lines (không strip) khác → `whitespace` (hiếm với default `ignore_whitespace=false`)
4. Else → `encoding_or_bytes` (khác encoding decode, hoặc ký tự invisible, hoặc normalize đã che)

Đưa `diff_reason` vào **từng item `compared`** khi `detail=true`. Khi `detail=false`, không bắt buộc list reason per file; có thể bỏ qua hoặc sau này thêm counts — **P0 chỉ cần đúng khi detail/item có content**.

Message folder: không cần nhắc hunks (đã fix). Có thể thêm ngắn: `khác metadata (normalize giống): N` nếu muốn — **optional**.

### B3.2 `kind=file`

Giữ logic hiện tại. Bổ sung test regression. Nếu còn lỗ hổng `status=different` + `hunk_count=0`, set `diff_reason` tương tự và `next_actions` không `review_hunks`.

## B4. Tests Part B

1. Hai file text: cùng nội dung logic, A có UTF-8 BOM, B không → folder compare: **không** `different_content` (theo bảng B3.1), `diff_reason=bom`, `hunk_count=0`.
2. A CRLF, B LF, cùng lines → `diff_reason=line_ending`.
3. Thật sự khác 1 dòng → `different_content`, `hunk_count>=1`, `diff_reason=text_lines`.
4. DLL sha khác → không gán `bom`/`line_ending`; `binary` + `investigate_version_dll`.

## B5. Acceptance Part B

- [ ] Live `poctpo1.aspx` / `poctpo2.aspx` (nếu vẫn ±3 byte): không còn “different_content + hunks rỗng + review_hunks”.
- [ ] Agent đọc được `diff_reason`.
- [ ] Không đổi semantics missing_on_* / detail folder.

---

## C. Acceptance tổng

- [ ] `seed` xml/folder discover theo path/name keyword.
- [ ] folder text: hết case bí `hunk_count=0` không reason.
- [ ] Không thêm `max_summary_names` cắt list tên.
- [ ] docstring MCP cập nhật 2 param/behavior.
- [ ] `pytest tests/compare_things/` pass.

---

## D. Gọi mẫu sau fix

```text
# A — không cần biết relative path
compare_things(
  kind="xml",
  project_source=...\FBISP24,
  project_target=...\SP228,
  seed="APVHistoryFlow",
  xml_view="flat",
  mode="summary"
)

compare_things(
  kind="folder",
  folder_a=...\SP228\App_Data\Controllers,
  folder_b=...\FBISP24\App_Data\Controllers,
  seed="APVHistoryFlow",
  detail=false
)

# B — aspx
compare_things(
  kind="folder",
  folder_a=...\Main,
  folder_b=...\Main,
  include_glob="poctpo*.aspx",
  compare_content=true,
  detail=true
)
# Kỳ vọng: diff_reason rõ; không review_hunks khi normalize giống
```

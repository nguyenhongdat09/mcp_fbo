# 11 — Test cases (BA / QA)

Ký hiệu: **P0** bắt buộc trước merge; **P1** nên có; **LIVE** cần 2 project/UNC thật (có thể skip CI).

## TC-FILE — `kind=file`

| ID | Case | Expected |
|----|------|----------|
| TC-FILE-01 P0 | Hai file text identical (cùng LF) | identical_content, hunks rỗng |
| TC-FILE-02 P0 | Cùng text, A=CRLF B=LF | identical_content=true, only_line_ending_diff=true, next_actions chứa ignore_line_ending_only |
| TC-FILE-03 P0 | Khác 1 đoạn giữa file | status different; hunks có a_line_start/end và b_line_*; preview có `-`/`+` |
| TC-FILE-04 P0 | `ignore_line_endings=false`, CRLF vs LF | different (hunks lớn hoặc nhiều) |
| TC-FILE-05 P0 | file_a không tồn tại | success=false, error_code file_not_found |
| TC-FILE-06 P0 | Binary khác size | is_binary, không text hunks, meta_diff size |
| TC-FILE-07 P1 | mode=hunks có unified_diff truncate | diff_truncated nếu vượt max_diff_lines |
| TC-FILE-08 P1 | UTF-8 BOM vs không BOM cùng text | identical_content sau normalize |

## TC-FOLDER — `kind=folder`

| ID | Case | Expected |
|----|------|----------|
| TC-FOLDER-01 P0 | Fixture: A có `a.txt`, B không | missing_on_b chứa `a.txt` |
| TC-FOLDER-02 P0 | Cùng relative, khác size | different_meta, meta_diff chứa size |
| TC-FOLDER-03 P0 | Cùng relative, khác mtime (tolerance 0) | meta_diff modified |
| TC-FOLDER-04 P0 | 100 file identical + 1 missing — max_objects nhỏ | truncated/omitted_identical_count; missing vẫn có |
| TC-FOLDER-05 P0 | include_glob `*.dll` bỏ `.txt` | txt không xuất hiện |
| TC-FOLDER-06 P1 | compare_content=true, file text nhỏ khác nội dung | status=different_content; **bắt buộc** content.hunks với a_line_*/b_line_* giống kind=file |
| TC-FOLDER-06b P1 | compare_content=true, hai DLL hash khác | different_content; **không** hunks text |
| TC-FOLDER-07 LIVE | Hai path bin UNC AIH vs FAHASA | success; summary counts hợp lệ; không hang vô hạn |

## TC-SQL — `kind=sql`

| ID | Case | Expected |
|----|------|----------|
| TC-SQL-01 P0 | Object có 2 bên, definition giống (normalize) | identical |
| TC-SQL-02 P0 | Definition khác vài dòng | different + source_/target_ line ranges |
| TC-SQL-03 P0 | Chỉ có source | missing_on_target; next_actions clone_things_type0 |
| TC-SQL-04 P0 | Encrypted | encrypted_skip; không crash |
| TC-SQL-05 P0 | object+seed rỗng | invalid_object_or_seed |
| TC-SQL-06 P1 | seed keywords → tìm thấy candidates | list ≤ max_objects |
| TC-SQL-07 LIVE | FAHASA vs AIH seed dmuqduyet,vdmduyetuq | Authorize/MailList/Role different nếu target còn dmduyet; có signals + hunks |

## TC-XML — `kind=xml`

| ID | Case | Expected |
|----|------|----------|
| TC-XML-01 P0 | Cùng relative, nội dung giống | identical |
| TC-XML-02 P0 | Khác nội dung | hunks line ranges |
| TC-XML-03 P0 | Thiếu ở target | missing_on_target |
| TC-XML-04 P0 | object có `..` | error path traversal |

## TC-TABLE — `kind=table`

| ID | Case | Expected |
|----|------|----------|
| TC-TABLE-01 P0 | Cột K,L vs L,K cùng int | **identical** |
| TC-TABLE-02 P0 | Đổi type một cột | different; columns_type_mismatch |
| TC-TABLE-03 P0 | Target thiếu cột | columns_only_source |
| TC-TABLE-04 P0 | Khác PK | pk_diff true |
| TC-TABLE-05 P0 | Khác index | indexes_* |
| TC-TABLE-06 P0 | Khác trigger tên | triggers_* |
| TC-TABLE-07 P1 | Bảng missing target | missing_on_target |

## TC-API — validation / mode

| ID | Case | Expected |
|----|------|----------|
| TC-API-01 P0 | kind sai | invalid_kind |
| TC-API-02 P0 | sql thiếu project | invalid_project_* |
| TC-API-03 P0 | mode=summary vẫn có hunk ranges khi different text | không được thiếu line_start/end |
| TC-API-04 P0 | service router tách module | import architecture (smoke) |

## Definition of Done (tests)

- Toàn bộ **P0** pass trên CI/local không cần UNC.
- LIVE documented: skip nếu env không có share/DB.
- Không regress `clone_things` tests hiện có.

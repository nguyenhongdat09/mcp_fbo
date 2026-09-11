# MCP `clone_things` — Tài liệu triển khai (gửi Gemini)



> **Mục đích:** MCP tool `clone_things` — (0) clone SQL thiếu giữa 2 project; (1) paste object ra `.sql` dạng ALTER để chỉnh sửa — ghi file, mở editor, trả JSON gọn cho Agent.

>

> **Vai trò tài liệu:** BA (requirements + contract) + Tester (acceptance / test matrix). **Không** implement code trong phase doc này.

>

> **Repo:** `E:\PythonProject\mcp_fbo\`

>

> **Reuse bắt buộc:** `query_database` (type=0, mode summary/full), `read_local_file` / `summary_xml` (read_option=3), `find_connect_by_path`.



---



## Danh sách tài liệu



| File | Nội dung |

|------|----------|

| [01_overview.md](./01_overview.md) | Bối cảnh, mục tiêu, phạm vi, ví dụ end-to-end |

| [02_tool_api.md](./02_tool_api.md) | MCP input params, validation, error shape |

| [03_resolution_and_flow.md](./03_resolution_and_flow.md) | Target-first, seed XML/SQL, queue loop, append, open file |

| [04_json_response.md](./04_json_response.md) | JSON schema response + samples |

| [05_config_and_sql_temp.md](./05_config_and_sql_temp.md) | `config.yaml`, NewSqlTemp parity, mở editor bằng Python |

| [06_reuse_existing.md](./06_reuse_existing.md) | Map sang module hiện có — cấm reinvent |

| [07_test_cases.md](./07_test_cases.md) | BA/QA test matrix + expected |

| [08_implementation_checklist.md](./08_implementation_checklist.md) | Phase implement + anti-patterns + Prompt Gemini |

| [09_suggestions.md](./09_suggestions.md) | Gợi ý mở rộng (không bắt buộc v1) |

| [10_sql_file_use_db_sections.md](./10_sql_file_use_db_sections.md) | Chia vùng `USE` App / Sys trong file `.sql` |

| [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md) | **`type=1`:** paste-for-edit (ALTER + line range + không execute) |



---



## Tóm tắt 1 trang



### Hai chế độ



| `type` | Việc làm |

|--------|----------|

| **0** (mặc định) | Clone object SQL **thiếu** ở project đích từ nguồn → 1 file `.sql` (`CREATE`), target-first + deps |

| **1** | Paste object từ **một** project ra `.sql` dạng **`ALTER`** để agent/user chỉnh; JSON có `line_start`/`line_end`; **không** execute |



Chi tiết type=1: [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md).



### Vấn đề (type=0)



Agent / dev thường cần mang object SQL từ dự án A sang dự án B khi làm UR:



- Phải tự `query_database` từng object trên 2 DB

- Phải tự lần dependency (proc gọi proc/func/table)

- Phải tự paste vào `.sql` — dễ sót, khó theo dõi object nào thiếu ở cả 2 project



### Giải pháp type=0



```

Agent → clone_things(

  type=0,

  object=<sql_name | xml_path>,

  project_source=<abs path>,

  project_target=<abs path>,

  path_to_pasted=<abs .sql | "">

) → JSON { cloned, skipped_exists, not_found_both, path_to_pasted, warnings }

```



### Giải pháp type=1



```

Agent → clone_things(

  type=1,

  object=<sql_name | "a, b, c">,

  project_source=<abs path | xml trong project>,

  project_target="",

  path_to_pasted=<abs .sql | "">

) → JSON { pasted[{name, line_start, line_end, …}], skipped_already_in_file, not_found_source, agent_message }

```



### Quy tắc lõi type=0 (không được lệch)



1. **Target-first:** object đã có ở DB target → **không** lấy từ source; ghi vào `skipped_exists` (v1: không quét deps của object đã có).

2. Chỉ khi **không có ở target** mới lấy definition/DDL từ source → append vào `.sql`.

3. Không có ở **cả hai** → ghi `not_found_both` (và **một** dòng comment tổng hợp cuối `.sql`).

4. Proc/func → phân tích dependency (summary) → enqueue → lặp đến hết queue / limit.

5. `object` là XML → seed danh sách SQL qua `summary_xml`, rồi cùng vòng target-first.

6. `path_to_pasted` trống → tạo `.sql` temp theo `clone_things.sql_temp_folder` (parity NewSqlTemp) → **mở file**.

7. Append: dòng trống + **`GO`** giữa các batch CREATE (SSMS-valid).



### Quy tắc lõi type=1



1. Chỉ `project_source`; `project_target` được rỗng.

2. `object` = tên SQL / list — **không** XML seed, **không** deps.

3. `CREATE PROC/FUNC/VIEW` → `ALTER …`; table giữ `CREATE` + warning.

4. Đã có cùng object trong file → `skipped_already_in_file`.

5. `execute_clone` force **false**. JSON **cấm** full script; có `agent_message` + line range.



---



## Quyết định BA đã chốt



| # | Quyết định |

|---|------------|

| 1 | Object đã có target (type=0) → `skipped_exists`; không quét deps con |

| 2 | Mở file: Python `Popen` `cursor`/`code`, fallback `os.startfile`; fail → `warnings` |

| 3 | `type`: `0` = clone SQL; `1` = paste-for-edit; khác → `unsupported_type`. (XML Controllers clone = type sau, không dùng 1) |

| 4 | Exclude infra mặc định (type=0 deps): `FastBusiness$`, `ff_`, `fsd_` |

| 5 | Exists qua `sys.objects` — **cấm** `fetch_one` cho bảng |

| 6 | Separator block: blank line + `GO` |

| 7 | Visited key normalize `dbo.name` lowercase |

| 8 | type=1: ALTER + dedup file + line range + không execute |



---



## Thứ tự đọc cho Gemini



1. [01_overview.md](./01_overview.md) — WHY + scope

2. [02_tool_api.md](./02_tool_api.md) — contract input

3. [03_resolution_and_flow.md](./03_resolution_and_flow.md) — algorithm type=0

4. [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md) — algorithm type=1

5. [04_json_response.md](./04_json_response.md) — contract output

6. [05_config_and_sql_temp.md](./05_config_and_sql_temp.md) — config + open file

7. [06_reuse_existing.md](./06_reuse_existing.md) — reuse map

8. [07_test_cases.md](./07_test_cases.md) — AC / tests

9. [08_implementation_checklist.md](./08_implementation_checklist.md) — làm tuần tự

10. [09_suggestions.md](./09_suggestions.md) — optional

11. [10_sql_file_use_db_sections.md](./10_sql_file_use_db_sections.md) — USE App/Sys



---



## Acceptance tóm tắt



**type=0**



- [ ] Target-first + recursive deps + not_found_both

- [ ] Append có blank + `GO`; USE App/Sys (target names)

- [ ] JSON `cloned`, `skipped_exists`, `not_found_both`, …



**type=1** (xem AC đầy đủ ở [11](./11_type1_paste_for_edit.md))



- [ ] Paste ALTER + line_start/line_end + `agent_message`

- [ ] Dedup `skipped_already_in_file`; không execute

- [ ] `project_target` rỗng OK; không XML seed



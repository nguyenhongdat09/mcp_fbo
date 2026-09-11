# 01 — Tách path theo máy: `config.yaml` + `config_path.yaml`

> **Vai trò:** BA + Tester — **spec để Gemini implement / FIX**.  
> **Sửa lệch:** Lần trước nhầm tên file thành `config_path.xml`. **Chốt đúng: `config_path.yaml`** (cùng họ YAML với `config.yaml`).  
> **Vấn đề:** User khác lấy MCP / update bản mới phải set tay lại path máy trong `config.yaml` → dễ mất khi ghi đè.  
> **Giải pháp:**  
> - `config.yaml` = options **dùng chung** (không path máy).  
> - `config_path.yaml` = **path theo máy**, gitignore, cấu hình một lần.  
> **Phạm vi code:**  
> - [`fastbusiness_mcp/config_paths.py`](../../../fastbusiness_mcp/config_paths.py)  
> - [`fastbusiness_mcp/mcp_app.py`](../../../fastbusiness_mcp/mcp_app.py)  
> - [`xml_fbograph/utils/path_helper.py`](../../../xml_fbograph/utils/path_helper.py)  
> - [`clone_things/file_manager.py`](../../../clone_things/file_manager.py)  
> - [`config.yaml`](../../../config.yaml), [`fastbusiness_mcp.spec`](../../../fastbusiness_mcp.spec), `.gitignore`  
> - Tests: `tests/fastbusiness_mcp/test_config_path_xml.py` → **đổi tên / viết lại** cho YAML  
> **Không** amend md clone_things 01–14 trong PR này.

---

## 0. FIX so với bản XML đã code

| Sai (đã làm) | Đúng (làm lại) |
|--------------|----------------|
| File `config_path.xml` + parse `ElementTree` | File **`config_path.yaml`** + `yaml.safe_load` |
| `config_path.xml.example` | **`config_path.yaml.example`** |
| `.gitignore` → `config_path.xml` | `.gitignore` → **`config_path.yaml`** |
| Env `FASTBUSINESS_CONFIG_PATH_FILE` trỏ xml | Cùng env, trỏ **yaml** (hoặc giữ tên env, đổi nội dung file) |
| Spec datas ship xml.example | Ship **yaml.example** |
| `config.yaml` còn / từng để `kuzu_db_base: ""` | **Gỡ hẳn** 2 key path khỏi `config.yaml` |

**Migration ngắn khi FIX:**

1. Xóa code parse XML; xóa `config_path.xml.example` (nếu còn).
2. Thêm `config_path.yaml.example`; gitignore `config_path.yaml`.
3. Optional: nếu tồn tại `config_path.xml` cũ trên máy user — **không bắt buộc** đọc tiếp; doc bảo user copy sang yaml. (Có thể đọc xml legacy 1 release — **không bắt buộc**, ưu tiên YAML only.)
4. Đổi tên test file cho khớp (vd. `test_config_path_yaml.py`).

---

## 1. WHY (tóm tắt)

| Key path | Chỉ khai báo ở | Fallback nếu thiếu / rỗng |
|----------|----------------|---------------------------|
| `fbograph.kuzu_db_base` | `config_path.yaml` | `{MCP_BASE}/KuzuDB` |
| `clone_things.sql_temp_folder` | `config_path.yaml` | `{MCP_BASE}/Scripts` |

Options giữ trong `config.yaml`: `server`, `logging`, `extract_options`, `fbograph.user_multi_db_yn`, `access_log_retention_days`, `clone_things.open_*` / `max_objects` / `execute_clone`, `rag_qlyc.*`.

---

## 2. Contract: `config_path.yaml`

### 2.1. Vị trí resolve

1. Env **`FASTBUSINESS_CONFIG_PATH_FILE`** (absolute path tới file path-config).
2. `{config.yaml parent}/config_path.yaml`
3. `exe_dir / config_path.yaml`, `exe_dir / _internal / config_path.yaml`
4. Không có file → không override → default MCP_BASE.

Thiếu file = hợp lệ.

### 2.2. Format (chốt BA)

```yaml
# Machine-local paths for FastBusiness MCP.
# Copy from config_path.yaml.example → config_path.yaml (một lần / máy).
# Không commit file thật (gitignore).

fbograph:
  # Absolute path; rỗng hoặc omit = {MCP_BASE}/KuzuDB
  kuzu_db_base: "C:/KuzuDB"

clone_things:
  # Absolute path; rỗng hoặc omit = {MCP_BASE}/Scripts
  sql_temp_folder: "E:/SQL Temp"
```

Quy tắc:

- UTF-8, `yaml.safe_load`.
- Section / key thiếu hoặc `""` / `null` = unset → fallback.
- Path `/` hoặc `\` đều được.
- YAML lỗi → log warning, **không crash**, bỏ qua file.
- **Không** nhét options non-path vào file này (tránh 2 nguồn cấu hình hành vi).

### 2.3. File mẫu ship

| File | Commit? |
|------|---------|
| `config_path.yaml.example` | **Có** |
| `config_path.yaml` | **Không** (gitignore) |
| `config.yaml` | Có — **không** có 2 key path |

`config_path.yaml.example`:

```yaml
# Copy to config_path.yaml and edit once per machine.
fbograph:
  kuzu_db_base: ""
clone_things:
  sql_temp_folder: ""
```

### 2.4. `config.yaml` ship — CẤM 2 key path

```yaml
fbograph:
  user_multi_db_yn: 1
  access_log_retention_days: 30

clone_things:
  open_editor_cmd: "auto"
  max_objects: 50
  open_file: true
  execute_clone: false
```

Comment trong yaml được phép trỏ: “path → `config_path.yaml`”.

Compat code: nếu máy cũ còn sót key path trong `config.yaml`, loader vẫn đọc sau YAML path-file (precedence dưới). **Repo/ship không được để lại 2 key.**

---

## 3. Precedence

| Ưu tiên | Nguồn |
|--------|--------|
| 1 | Env: `FBOGRAPH_KUZU_BASE` / optional `CLONE_THINGS_SQL_TEMP_FOLDER` |
| 2 | `config_path.yaml` (non-empty) |
| 3 | Legacy key trong `config.yaml` nếu còn |
| 4 | `{MCP_BASE}/KuzuDB` hoặc `{MCP_BASE}/Scripts` |

---

## 4. API code

Giữ API đã có, **đổi nguồn file**:

```python
def resolve_config_path_local(filename: str = "config_path.yaml") -> Path | None: ...
def load_machine_paths(path: Path | None = None) -> dict:  # yaml.safe_load, không XML
def merge_config_with_machine_paths(cfg: dict, machine: dict | None = None) -> dict: ...
def get_effective_kuzu_db_base(cfg: dict | None = None) -> str: ...
def get_effective_sql_temp_folder(cfg: dict | None = None) -> str: ...
```

- `load_config`: sau load `config.yaml` → `load_machine_paths()` → merge.
- `resolve_kuzu_db_base`: dùng effective API / `get_config()` đã merge; không dual-load lệch.
- `resolve_output_file`: sql temp từ config đã merge; rỗng → Scripts.
- PyInstaller: datas chỉ `config_path.yaml.example`.
- Alias cũ `resolve_config_path_xml` → **xóa hoặc đổi tên** thành `resolve_config_path_local` (không giữ tên xml).

---

## 5. Acceptance

| ID | Given | Then |
|----|--------|------|
| AC-CP-01 | `config_path.yaml` có `kuzu_db_base=D:/MyKuzu` | `resolve_kuzu_db_base()` → đó |
| AC-CP-02 | yaml local `sql_temp_folder` tồn tại; `path_to_pasted=""` | file `.sql` tạo trong folder đó |
| AC-CP-03 | Không có `config_path.yaml`; `config.yaml` không còn 2 key | default MCP_BASE `KuzuDB` / `Scripts` |
| AC-CP-04 | Legacy còn key trong `config.yaml`, không có path yaml | vẫn dùng legacy |
| AC-CP-05 | Cả path yaml + legacy | **path yaml thắng** |
| AC-CP-06 | Env kuzu set | Env thắng |
| AC-CP-07 | `config_path.yaml` malformed | warning + fallback, không crash |
| AC-CP-08 | Repo không còn `config_path.xml` / parse XML path | |
| AC-CP-09 | `config.yaml` không chứa `kuzu_db_base` / `sql_temp_folder` | |

---

## 6. Tests

Đổi / tạo: `tests/fastbusiness_mcp/test_config_path_yaml.py` (TC-CP-* tương đương bản XML).

| ID | Mô tả |
|----|--------|
| TC-CP-01 | Parse yaml → dict |
| TC-CP-02 | Merge: path yaml overrides legacy; không đè `open_file` |
| TC-CP-03 | Missing file → defaults |
| TC-CP-04 | Empty string keys → unset |
| TC-CP-05 | Env wins |
| TC-CP-06 | Bad yaml → `{}` |
| TC-CP-07 | Resolve cạnh `config.yaml` tmp |
| TC-CP-08 | sql temp resolve merged |

Xóa hoặc không maintain `test_config_path_xml.py`.

---

## 7. Checklist Gemini (FIX)

- [ ] Đổi loader XML → YAML (`config_path.yaml`)
- [ ] Xóa `config_path.xml.example`; thêm `config_path.yaml.example`
- [ ] `.gitignore`: `config_path.yaml` (bỏ hoặc giữ tạm `config_path.xml` nếu muốn ignore rác cũ)
- [ ] `fastbusiness_mcp.spec` datas → example yaml
- [ ] Comment `config.yaml` trỏ `config_path.yaml`; xác nhận **không** còn 2 key path
- [ ] Đổi tên API/test khỏi chữ `xml`
- [ ] Unit TC-CP-* pass
- [ ] Không đổi business clone_things / mode_read

---

## 8. Prompt Gemini (copy-paste)

```text
Bạn là implementer FastBusiness MCP (repo E:\PythonProject\mcp_fbo).

FIX theo docs/doc/config_local/01_split_machine_paths.md

Lệch cần sửa:
- Đã implement config_path.xml — SAI.
- Đúng: config_path.yaml (YAML, cùng kiểu config.yaml).

Yêu cầu cứng:
1) Path máy chỉ khai báo trong config_path.yaml: fbograph.kuzu_db_base, clone_things.sql_temp_folder.
2) config.yaml KHÔNG còn 2 key đó (kể cả "").
3) Bỏ parse XML; dùng yaml.safe_load. Ship config_path.yaml.example; gitignore config_path.yaml.
4) Precedence: Env > config_path.yaml > legacy key trong config.yaml (nếu còn) > {MCP_BASE}/KuzuDB|Scripts.
5) Đổi test + tên API khỏi xml; update PyInstaller datas.
6) Bad yaml → warning, không crash.
7) Không đổi logic clone_things mode_read/type0/1 ngoài nguồn path.
```

---

## 9. Hướng dẫn user

1. Copy `config_path.yaml.example` → `config_path.yaml`.
2. Điền path (hoặc để `""` dùng folder cạnh MCP).
3. Restart MCP.
4. Update MCP sau này: chỉ đè `config.yaml` / exe — **giữ** `config_path.yaml`.

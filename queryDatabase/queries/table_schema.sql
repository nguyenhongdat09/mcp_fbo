# Task: Sửa resolve_controllers_dir + _normalize_path_str để chấp nhận mọi dạng --root linh động
# (File này là PROMPT text gửi Gemini — không phải SQL.)

## Bối cảnh

File chính: E:\mcp_fbo\xml_fbograph\utils\path_helper.py
CLI entry:  E:\mcp_fbo\xml_graph_cli.py  (hàm cmd_build dùng resolve_controllers_dir)

Hiện tại --root chỉ nhận project root hoặc .../App_Data/Controllers.
Yêu cầu mới: nhận BẤT KỲ đường dẫn nào miễn thuộc dự án FBO CustomerPro —
CLI tự walk ngược lên tìm Controllers.

## Các case --root cần hoạt động (tất cả phải ra cùng 1 Controllers)

Ví dụ project: \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227

Case 1 — Project root:
  \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227
  → Controllers: \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers

Case 2 — App_Data:
  \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data
  → Controllers: \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers

Case 3 — Controllers (đã đúng):
  \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers
  → Controllers: như trên (giữ nguyên)

Case 4 — Subfolder trong Controllers (Dir/Grid/Filter/...):
  \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Filter
  → Controllers: walk lên 1 cấp

Case 5 — File XML cụ thể:
  \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Filter\VoucherLockingMultiUser.xml
  \\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Dir\TNTran.xml
  → Controllers: walk lên tìm folder tên "controllers" có cha là "app_data"

Case 6 — UNC 1 backslash (bị truncated — thường do terminal/JSON):
  \172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Dir\TNTran.xml
  → normalize thành \\... rồi xử lý như case 5

Case 7 — Forward slash:
  //172.168.5.14/CustomerPro/FBO/QUANGDUC/SP227/App_Data/Controllers/Dir/TNTran.xml
  → normalize rồi xử lý như case 5

## Logic resolve_controllers_dir cần sửa

Thuật toán ưu tiên (theo thứ tự):

1. Normalize path trước (gọi _normalize_path_str đã sửa để xử lý UNC 1bs/forward slash).

2. Nếu path trỏ vào file (có extension .xml, .aspx, ... hoặc is_file()):
   → lấy parent folder rồi walk tiếp bước 3.

3. Walk từ folder hiện tại lên trên, tìm folder thỏa:
   folder.name.lower() == "controllers" AND folder.parent.name.lower() == "app_data"
   Nếu tìm thấy → return folder đó.

4. Nếu bước 3 không tìm thấy (chưa đi đến controllers):
   Thử nối xuống dưới theo ưu tiên:
   a. path + "App_Data/Controllers"  (nếu is_dir())
   b. path + "Controllers"           (nếu parent.name == app_data và is_dir())
   → return cái đầu tiên is_dir()

5. Nếu vẫn không tìm thấy → raise ValueError hoặc return None
   (caller xml_graph_cli.py sẽ báo lỗi rõ ràng cho user)

Không dùng ProjectPathHelper.get_controllers_path() trong resolve_controllers_dir
(để tránh vòng phụ thuộc và cho phép path không qua CustomerPro — CLI manual).

## _normalize_path_str cần sửa đồng thời

Vấn đề cũ: heuristic "customerpro" keyword hardcode. Xem prompt refactor trước.

Quy tắc chuẩn (không dùng keyword domain-specific):
- Replace "/" → "\"
- Nếu kết quả bắt đầu bằng "\\" → UNC hợp lệ, giữ nguyên.
- Nếu bắt đầu bằng đúng 1 "\" VÀ segment sau không phải drive letter
  (drive letter = 1 ký tự alpha theo sau bởi ":"):
  → thêm "\" vào đầu (UNC bị mất 1 ký tự).
  Ví dụ: \172.168.5.14\... → \\172.168.5.14\...
          \server\share\... → \\server\share\...
  Không làm gì với: \C:\foo (C: là drive letter → giữ nguyên)

## Unit tests BẮT BUỘC

Thêm vào xml_fbograph/tests/test_customerpro_kuzu_gate.py hoặc test_path_helper.py.

Tất cả 7 case ở trên phải pass, dùng tempfile tạo cây thư mục giả:

```
tmp/
  CustomerPro/
    FBO/
      QUANGDUC/
        SP227/
          App_Data/
            Controllers/
              Dir/
                TNTran.xml
              Filter/
                VoucherLockingMultiUser.xml
```

Test từng case:
  resolved = resolve_controllers_dir(<path>)
  assert resolved == tmp / "CustomerPro" / "FBO" / "QUANGDUC" / "SP227" / "App_Data" / "Controllers"

Thêm test normalize:
  assert _normalize_path_str(r"\172.168.5.14\foo")  == r"\\172.168.5.14\foo"
  assert _normalize_path_str(r"\\172.168.5.14\foo") == r"\\172.168.5.14\foo"
  assert _normalize_path_str(r"//172.168.5.14/foo") == r"\\172.168.5.14\foo"
  assert _normalize_path_str(r"\C:\foo")            == r"\C:\foo"   # drive, giữ nguyên
  assert _normalize_path_str(r"E:\foo")             == r"E:\foo"    # drive, giữ nguyên

Thêm test get_customerpro_project_path không dùng keyword heuristic:
  # Path không chứa CustomerPro nhưng bắt đầu \host → vẫn Other (không crash)
  assert get_customerpro_project_path(r"\172.168.5.14\OtherShare\Foo\Bar\x.xml") == ""

## Không được làm
- Không đổi signature public của các hàm.
- Không thêm logic CustomerPro vào resolve_controllers_dir
  (hàm này general-purpose, CLI manual không cần gate CustomerPro).
- Không commit.

## Tham chiếu đọc trước
- E:\mcp_fbo\xml_fbograph\utils\path_helper.py
  (resolve_controllers_dir, _normalize_path_str, _split_path_parts,
   get_customerpro_project_path, has_app_data_controllers)
- E:\mcp_fbo\xml_graph_cli.py  (cmd_build — caller của resolve_controllers_dir)
- E:\mcp_fbo\xml_fbograph\tests\test_customerpro_kuzu_gate.py

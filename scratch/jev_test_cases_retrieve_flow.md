# Jev test cases — requirement_type cho retrieve_flow

Bộ câu hỏi kiểm tra phân loại `requirement_type` (và vài `task_type`) của
tool_help trên Jev. Dùng: paste STATE + QUESTIONS từ
`scratch/dump_jev_payload.py` (đổi STEPS_JSON/TASK_REQUIREMENT theo case)
vào playground, hoặc chạy tool_help trực tiếp với context.task_requirement.

Expected mặc định: top-1 `requirement_type` đúng loại; distractor phải ra
`none` (hoặc đúng template khác), KHÔNG được ra retrieve_flow.

---

## A. retrieve_flow_parition_table (nguồn phân kỳ)

| # | task_requirement (UR) | Expected |
|---|------------------------|----------|
| A1 | "Thêm chức năng lấy dữ liệu từ Phiếu từ chối lô vắc xin, sinh phẩm (yc I074). Phiếu đã lấy hết thì không lấy nữa, dòng đã lấy hết không hiện. Theo dõi đã lấy/còn lại từng dòng. Chỉ lấy phiếu Đã duyệt. Lấy 1 lần nhiều phiếu." | `retrieve_flow_parition_table` |
| A2 | "Phiếu nhập mua hàng cần nút Lấy dữ liệu kéo chi tiết từ đơn hàng mua (d21$ phân kỳ), theo dõi số lượng đã nhận còn lại theo stt_rec/stt_rec0." | `retrieve_flow_parition_table` |
| A3 | "Thêm chức năng Retrieve trên phiếu xuất: lấy nhiều phiếu yêu cầu xuất 1 lần, tick chọn dòng, sửa số lượng lấy không vượt số lượng còn lại." | `retrieve_flow_parition_table` |
| A4 | "Làm màn hình lấy dữ liệu giống YCNDXA (Filter→MultiForm→MultiGrid) cho chứng từ mới có bảng d{ext}$ theo kỳ." | `retrieve_flow_parition_table` |

Steps mẫu (paste STEPS_JSON):
```json
["Tạo bộ controller lấy dữ liệu {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup",
 "Viết proc cập nhật sl đã lấy trên bảng nguồn phân kỳ khi insert/update/delete",
 "Gắn case 'Retrieve' g.showForm('{X}Filter') vào detail grid voucher đích",
 "fsd_addFields cột taken + trường vết stt_rec_src/stt_rec0_src"]
```

## B. retrieve_flow_single_table (nguồn cố định)

| # | task_requirement | Expected |
|---|-------------------|----------|
| B1 | "Phiếu WIMO lấy dữ liệu từ bảng ctsx cố định (không phân kỳ), giống zcWIMO trên LIKSIN: Filter/MultiForm/MultiGrid/Lookup + proc cập nhật sl_pnd." | `retrieve_flow_single_table` |
| B2 | "Lấy dữ liệu vào phiếu từ một bảng nguồn fixed table (master/detail không có hậu tố kỳ), theo dõi đã lấy/còn lại." | `retrieve_flow_single_table` |

## C. Distractors — KHÔNG được ra retrieve_flow

| # | task_requirement | Expected |
|---|-------------------|----------|
| C1 | "Sửa phiếu LTB: thêm cột ghi chú vào detail, đổi tên nút Lưu." | `none` |
| C2 | "Tạo báo cáo listing tồn kho theo kho/vật tư có cột tick chọn để in." | `report_check` |
| C3 | "Tạo mới danh mục đối tượng 1 khóa chính có import Excel." | `category_1_key` (hoặc category_multi_key) |
| C4 | "Viết proc cập nhật lại số lượng đã lấy trên phiếu nguồn cho đúng data cũ (fix data, không làm màn hình mới)." | `none` — chỉ sửa SQL, không tạo suite |
| C5 | "Tạo chứng từ mới đặt mã XX bảng mxx$/dxx$ có duyệt." | `voucher` |
| C6 | "Kiểm tra tại sao nút Retrieve trên phiếu LTB không mở form LTBPO1Filter." | `none` — debug existing |

## D. task_type (step-level) sanity

| Step text | Expected task_type |
|-----------|---------------------|
| "Tạo bộ controller lấy dữ liệu mới cho phiếu đích" | `clone_template` |
| "Paste suite retrieve flow vào project FBISP24" | `clone_template` |
| "Thêm cột sl_ltb vào bảng d64$" | `db_add_field` |
| "Check syntax file retrieve.sql trước deploy" | `db_check_syntax` |
| "Đọc summary Grid/LTBDetail.xml" | `read_summary` |

## Notes

- `retrieve_flow_*` là NGOẠI LỆ của rule "chỉ tạo mới": UR sửa voucher có sẵn
  nhưng TẠO suite controller mới vẫn phải classify retrieve_flow.
- Nếu Jev phân vân partitioned vs single: UR không nói rõ → chấp nhận
  partitioned làm top-1 với single trong alternatives (agent đổi
  clone_call.object nếu sai).

"""In ra state + questions (JSON) y hệt tool_help gửi lên Jev — để paste
vào playground test trực tiếp.

Cách dùng:
    1. Dán list steps vào STEPS_JSON bên dưới (giữ nguyên tiếng Việt có dấu)
    2. (tuỳ chọn) điền TASK_REQUIREMENT — UR nguyên văn nếu có
    3. Chạy:  python -X utf8 scratch/dump_jev_payload.py
    4. Copy 2 block JSON in ra -> paste vào ô state / questions trên
       playground (questions: tạo từng key stepN_tool nếu UI yêu cầu)
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool_help.service import _AGENT_CONTEXT, _build_questions, _normalize_steps
from tool_help.cards import TASK_TYPE_CATALOG, REQUIREMENT_TYPE_CATALOG

# ===================== DÁN STEPS VÀO ĐÂY =====================
STEPS_JSON = """
[
    "Kiểm tra dữ liệu thực tế các trái phiếu có sẵn trong bảng dmvt và tồn kho cdvt trong database",
    "Tạo kịch bản test dữ liệu mẫu trái phiếu đáo hạn và tồn kho để kiểm thử",
    "Chạy test thử nghiệm thủ tục báo cáo rs_zccndhctp và tạo xóa chứng từ zc_zccndhctp_CreateVoucher zc_zccndhctp_DeleteVoucher",
    "Viết toàn bộ script SQL test và dữ liệu test vào file c:\\\\Users\\\\Windows 10\\\\.gemini\\\\config\\\\skills\\\\SQL Temp\\\\chubb_sp2264 (8).sql"
]
"""
# UR nguyên văn (optional, để "" nếu không có)
TASK_REQUIREMENT = """Xem trong database có case dữ liệu trái phiếu nào không, tạo dữ liệu mẫu nếu chưa có để test toàn bộ chức năng đáo hạn trái phiếu (báo cáo rs_zccndhctp, tạo phiếu xuất kho zc_zccndhctp_CreateVoucher, kiểm tra sổ kho r70, sổ cái ct00, trường pxa_created_yn, và xóa phiếu xuất kho zc_zccndhctp_DeleteVoucher). Viết toàn bộ SQL vào c:\\Users\\Windows 10\\.gemini\\config\\skills\\SQL Temp\\chubb_sp2264 (8).sql"""
# ============================================================

steps = _normalize_steps(tuple(json.loads(STEPS_JSON)))

state = {
    "agent_context": _AGENT_CONTEXT,
    "task_type_catalog": TASK_TYPE_CATALOG,
    "steps": steps,
}
if TASK_REQUIREMENT.strip():
    state["task_requirement"] = TASK_REQUIREMENT
    state["requirement_type_catalog"] = REQUIREMENT_TYPE_CATALOG

questions = _build_questions(steps, TASK_REQUIREMENT)

print("=" * 30 + " STATE " + "=" * 30)
print(json.dumps(state, ensure_ascii=False, indent=1))
print("=" * 30 + " QUESTIONS " + "=" * 30)
print(json.dumps(questions, ensure_ascii=False, indent=1))

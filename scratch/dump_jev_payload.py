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
    "Đọc file Grid/DDVDetail.xml quanh field dvt và action Item/UOM để xem lookup đơn vị tính",
    "Đọc file Grid/SVDetail.xml quanh field dvt, nhieu_dvt và handle so sánh với DDVDetail",
    "Tìm file controller UOMItem trong project",
    "Check cột dvt, nhieu_dvt của bảng dmvt và view vdmvtqddvt cho mã vật tư TTU1"
]
"""
# UR nguyên văn (optional, để "" nếu không có)
TASK_REQUIREMENT = ""
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

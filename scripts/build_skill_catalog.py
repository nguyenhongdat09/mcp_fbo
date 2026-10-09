"""Sinh tool_help/skill_catalog.json từ thư mục skill của Claude Code.

MCP server chạy trên máy khác không có ~/.claude/skills → snapshot vào
repo (name, description, 700 ký tự đầu body) để tool_help gợi ý skill bằng
Jev (recipe "Skill suggestion" của TypeSafe). Chạy lại khi thêm/sửa skill:

    python -X utf8 scripts/build_skill_catalog.py [skills_dir]

Mặc định skills_dir = %USERPROFILE%/.claude/skills.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tool_help" / "skill_catalog.json"
BODY_CHARS = 700
_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_skill(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = _FRONT_RE.match(text)
    if not m:
        return None
    meta = yaml.safe_load(m.group(1)) or {}
    # Skill tool gọi theo tên THƯ MỤC (vd fbo_grid_filter); name frontmatter
    # (fbo-grid-filter) có thể khác → giữ làm alias.
    name = path.parent.name
    desc = " ".join(str(meta.get("description") or "").split())
    if not desc:
        return None
    body = " ".join(m.group(2).split())[:BODY_CHARS]
    out = {"name": name, "description": desc, "body": body}
    alias = str(meta.get("name") or "").strip()
    if alias and alias != name:
        out["alias"] = alias
    return out


def main() -> int:
    skills_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(os.environ.get("USERPROFILE", Path.home())) / ".claude" / "skills")
    if not skills_dir.is_dir():
        print(f"Không thấy thư mục skill: {skills_dir}")
        return 2
    skills = []
    for p in sorted(skills_dir.glob("*/SKILL.md")):
        s = parse_skill(p)
        if s:
            skills.append(s)
    OUT.write_text(json.dumps({"skills": skills}, ensure_ascii=False,
                              indent=1), encoding="utf-8")
    print(f"{len(skills)} skill → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

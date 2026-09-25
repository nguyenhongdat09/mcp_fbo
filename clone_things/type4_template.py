"""type=4 — Paste bundled template suite vào project đích.

Template trong ``template/<name>/`` là SKELETON GENERIC: file đặt tên theo
vai trò (master.xml, grid.xml, griddetail.xml, filter.xml, upload.xml,
report.xml, main.aspx), nội dung chứa token ``{{xxx}}`` và field
placeholder ``name_<type>_<n>``.

manifest.yaml v2:
  files:  [{src, dst}]   — dst chứa {new} (vd Grid/{new}detail.xml)
  tokens: {"{{x}}": "...{new}..."} — fill trong nội dung + dst
  edit_guide: hướng dẫn agent sửa tiếp sau paste

Token {{x}} KHÔNG khai báo trong tokens được giữ literal và báo về
``unresolved_placeholders`` để agent tự fill (vd {{ma_maubc}}).
Field placeholder name_* giữ nguyên — agent đổi theo UR.

Mặc định execute=False = dry-run.
"""
from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from .type3_file_clone import coerce_bool

logger = logging.getLogger("clone_things.type4")

_RE_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_]+$")
_RE_TOKEN = re.compile(r"\{\{[a-zA-Z0-9_]+\}\}")
_TEXT_EXT = {".xml", ".aspx", ".txt", ".ent", ".js", ".sql", ".config"}


def template_root() -> Path:
    """Root chứa template — source tree hoặc PyInstaller _MEIPASS."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / "template"
        if p.is_dir():
            return p
    return Path(__file__).resolve().parent.parent / "template"


def list_templates() -> list[dict[str, Any]]:
    out = []
    root = template_root()
    if not root.is_dir():
        return out
    for mf in sorted(root.glob("*/manifest.yaml")):
        try:
            m = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
            out.append({"name": m.get("name", mf.parent.name),
                        "title_v": m.get("title_v", ""),
                        "files": len(m.get("files") or []),
                        "jev_desc": m.get("jev_desc", "")})
        except Exception as e:
            logger.warning("Bad manifest %s: %s", mf, e)
    return out


def _err(msg: str, code: str, start: float) -> dict[str, Any]:
    return {"success": False, "spec_version": "1.0", "type": 4,
            "error_code": code, "message": msg,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 1)}


def _expand(text: str, tokens: dict[str, str], new_name: str) -> str:
    """Thay {new} trong value rồi thay mọi {{token}} trong text."""
    for tok, val in tokens.items():
        text = text.replace(tok, str(val).replace("{new}", new_name))
    return text


def run_type4_template(
    object: str = "",
    new_name: str = "",
    project_target: str = "",
    execute: bool | str = False,
    overwrite: bool | str = False,
    confirm_overwrite: bool | str = False,
    warnings: list[str] | None = None,
    start_time: float | None = None,
) -> dict[str, Any]:
    start = start_time or time.perf_counter()
    warnings = warnings if warnings is not None else []
    name = (object or "").strip()

    if name.lower() in ("", "?", "template:?", "list"):
        return {"success": True, "spec_version": "1.0", "type": 4,
                "mode": "list_templates", "templates": list_templates(),
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 1)}

    tpl_dir = template_root() / name
    manifest_path = tpl_dir / "manifest.yaml"
    if not manifest_path.is_file():
        return _err(f"Template '{name}' không tồn tại. "
                    f"Có sẵn: {[t['name'] for t in list_templates()]}",
                    "template_not_found", start)

    if not new_name or not _RE_SAFE_NAME.match(new_name):
        return _err(f"new_name '{new_name}' không hợp lệ — chỉ [a-zA-Z0-9_]",
                    "invalid_new_name", start)

    if not project_target or not Path(project_target).is_absolute():
        return _err("project_target phải là absolute path project đích",
                    "invalid_project_target", start)
    tgt_root = Path(project_target)

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    tokens = manifest.get("tokens") or manifest.get("rename_tokens") or {}
    # token dài thay trước ({{ctrl_detail2}} trước {{ctrl_detail}})
    tokens = dict(sorted(tokens.items(), key=lambda kv: -len(kv[0])))
    do_exec = coerce_bool(execute)
    do_over = coerce_bool(overwrite) and coerce_bool(confirm_overwrite)

    planned, written, skipped = [], [], []
    unresolved: set[str] = set()
    for f in manifest.get("files") or []:
        # manifest v2: {src, dst}; v1 fallback: path string cũ
        if isinstance(f, str):
            src_rel, dst_rel = f, f
        else:
            src_rel, dst_rel = f.get("src"), f.get("dst")
        if not src_rel or not dst_rel:
            warnings.append(f"manifest_bad_file_entry: {f}")
            continue
        src = tpl_dir / src_rel
        if not src.is_file():
            warnings.append(f"template_missing_file: {src_rel}")
            continue

        rel_new = _expand(dst_rel.replace("\\", "/"), tokens, new_name)
        rel_new = rel_new.replace("{new}", new_name)
        dst = tgt_root / rel_new
        entry = {"src": src_rel, "dst": rel_new}
        if dst.exists() and not do_over:
            entry["status"] = "skipped_exists"
            skipped.append(entry)
            continue
        n_rep = 0
        if dst.suffix.lower() in _TEXT_EXT:
            try:
                content = src.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                content = src.read_text(encoding="utf-8", errors="replace")
            for tok, val in tokens.items():
                new_v = str(val).replace("{new}", new_name)
                n_rep += content.count(tok)
                content = content.replace(tok, new_v)
            # token {{x}} còn sót = placeholder agent phải fill
            unresolved.update(_RE_TOKEN.findall(content))
        else:
            content = src.read_bytes()
        entry["replacements"] = n_rep
        entry["status"] = "planned" if not do_exec else "written"
        planned.append(entry)
        if do_exec:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                dst.write_bytes(content)
            else:
                dst.write_text(content, encoding="utf-8")
            written.append(rel_new)

    if not do_exec:
        warnings.append("dry-run: truyền execute=True để ghi file thật")
    if skipped and not do_over:
        warnings.append("có file đã tồn tại — cần overwrite=True + "
                        "confirm_overwrite=True sau khi hỏi user")
    if unresolved:
        warnings.append(
            "file paste ra còn placeholder {{...}} chưa fill — agent sửa tay "
            "(vd {{ma_maubc}}); field name_* luôn phải đổi theo UR")

    return {
        "success": True,
        "spec_version": "1.0",
        "type": 4,
        "mode": "template_paste",
        "template": name,
        "new_name": new_name,
        "project_target": str(tgt_root),
        "dry_run": not do_exec,
        "files": planned + skipped,
        "written": written,
        "unresolved_placeholders": sorted(unresolved),
        "edit_guide": (manifest.get("edit_guide") or "")
                      .replace("{new}", new_name),
        "warnings": warnings,
        "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
    }

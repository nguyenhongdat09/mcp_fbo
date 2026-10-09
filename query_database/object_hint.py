"""Recovery cho lỗi ``Invalid object name`` — chẩn đoán đúng gốc theo nhóm.

Log thực tế (42 lỗi / 3 tuần) chia nhóm rõ:
- Bảng hệ thống ở DB **sys** nhưng query trên DB app (menu, sysmenu,
  emailcontent, errorlog, sysoptions...) → kiểm tra DB còn lại, báo
  ``db_type`` đúng.
- Bảng **partition** sai kỳ / placeholder (c71$250901, m14$202508,
  d63$$partition$current) → liệt kê partition thật + skill partition.
- **#temp** → mỗi call query_database là 1 session riêng.
- Hàm built-in mới (STRING_SPLIT...) → SQL Server cũ không hỗ trợ.
- Còn lại → gợi ý tên gần đúng (difflib trên sys.objects).

Chỉ query catalog (sys.objects/sys.tables, OBJECT_ID) — read-only. Mọi lỗi
trong recovery bị nuốt, trả None; không đổi lỗi gốc.
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

RULE_NAME = "invalid_object"

_INVALID_OBJ_RE = re.compile(r"Invalid object name '([^']+)'", re.IGNORECASE)
# Hàm built-in chỉ có từ SQL Server 2016+/2017+ — FBO hay chạy 2008/2012
_NEW_BUILTINS = {"STRING_SPLIT", "STRING_AGG", "TRIM", "CONCAT_WS",
                 "OPENJSON", "TRANSLATE", "GREATEST", "LEAST"}
_PARTITION_SKILL = "fbo-partition-table-knowledge"
_MAX_PARTITIONS = 12
_MAX_SUGGEST = 5


def extract_invalid_objects(error_text: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in _INVALID_OBJ_RE.finditer(error_text or ""):
        seen.setdefault(m.group(1), None)
    return list(seen)


def _core(name: str) -> str:
    return re.split(r"\s*\.\s*", name.strip())[-1].strip("[]")


def _rows(parsed: dict, sql: str, params: list) -> list[list]:
    from .executor import execute_query

    res = execute_query(parsed, sql, max_rows=5000, params=params)
    if not res.get("success"):
        return []
    out: list[list] = []
    for rs in res.get("result_sets") or []:
        out += rs.get("rows") or []
    return out


_PERIOD_RE = re.compile(r"\$(\d{6})$")


def _partitions(parsed: dict, core: str) -> list[str]:
    """Kỳ có thật gần hiện tại nhất (<= tháng này) + bảng $000000 nếu có.

    FBO tạo sẵn partition tương lai (vd d63$203012) và bảng phụ ($log) —
    liệt kê theo tên giảm dần chỉ ra rác, nên lọc theo kỳ YYYYMM.
    """
    from datetime import date

    prefix = core.split("$", 1)[0]
    if not prefix:
        return []
    rows = _rows(parsed,
                 "SELECT name FROM sys.tables WHERE name LIKE ?",
                 [prefix.replace("[", "[[]") + "$%"])
    names = [str(r[0]) for r in rows]
    now = f"{date.today():%Y%m}"
    periods = sorted(
        (n for n in names
         if (m := _PERIOD_RE.search(n)) and m.group(1) != "000000"
         and m.group(1) <= now),
        reverse=True)[:_MAX_PARTITIONS]
    base = [n for n in names if n.endswith("$000000")]
    return base + periods


def _similar_names(parsed: dict, core: str) -> list[str]:
    # bỏ bảng partition (x$yyyymm) khỏi pool — nhiễu và rất nhiều
    rows = _rows(parsed,
                 "SELECT name FROM sys.objects WHERE type IN "
                 "('U','V','P','FN','IF','TF') AND name NOT LIKE '%$[0-9]%'",
                 [])
    pool = {str(r[0]).lower(): str(r[0]) for r in rows}
    hits = difflib.get_close_matches(core.lower(), list(pool),
                                     n=_MAX_SUGGEST, cutoff=0.6)
    return [pool[h] for h in hits]


def _exists_in_other_db(file_path: str, db_type: str, core: str) -> str | None:
    """Tên có tồn tại ở DB còn lại (app↔sys) không → trả db_type đó."""
    from .connection import get_connection_config

    other = "sys" if (db_type or "app") == "app" else "app"
    conn = get_connection_config(file_path, other)
    if not conn.get("success"):
        return None
    rows = _rows(conn["parsed"], "SELECT OBJECT_ID(?)", [core])
    return other if rows and rows[0][0] is not None else None


def _diagnose(parsed: dict, name: str, file_path: str,
              db_type: str) -> dict:
    core = _core(name)
    if core.startswith("#"):
        return {"kind": "temp_table",
                "note": "Bảng tạm không tồn tại: mỗi call query_database là "
                        "1 session riêng — tạo #temp và dùng nó trong CÙNG "
                        "1 query"}
    if core.upper() in _NEW_BUILTINS:
        return {"kind": "unsupported_builtin",
                "note": f"{core.upper()} không có trên SQL Server này (bản "
                        "cũ/compat level thấp) — dùng cách cũ (XML PATH, "
                        "fsd_StringToTable, LTRIM(RTRIM()))"}
    if "$" in core:
        suffix = core.split("$", 1)[1]
        if "partition" in suffix.lower():
            why = ("tên placeholder ($$partition/%Partition) chỉ hợp lệ "
                   "bên trong Partition$Execute, không query trực tiếp")
        elif (not re.fullmatch(r"\d{6}", suffix)
              or not ("1990" <= suffix[:4] <= "2100" and
                      ("01" <= suffix[4:] <= "12" or suffix == "000000"))):
            why = f"hậu tố '{suffix}' sai định dạng kỳ YYYYMM"
        else:
            why = f"kỳ {suffix} chưa có partition"
        out = {"kind": "partition",
               "note": f"Bảng partition: {why} — chọn bảng có thật bên dưới",
               "skill": _PARTITION_SKILL}
        parts = _partitions(parsed, core)
        if parts:
            out["existing"] = parts
        return out
    other = _exists_in_other_db(file_path, db_type, core) if file_path else None
    if other:
        return {"kind": "wrong_db",
                "note": f"{core} có trong DB {other} — gọi lại với "
                        f"db_type='{other}'",
                "db_type": other}
    out = {"kind": "not_found",
           "note": f"Không có object {core} ở cả DB app lẫn sys"}
    sims = _similar_names(parsed, core)
    if sims:
        out["did_you_mean"] = sims
    return out


def build_object_hint(parsed: dict, error_text: str, file_path: str = "",
                      db_type: str = "app") -> dict | None:
    """Khối ``recovery`` cho lỗi Invalid object name, hoặc None."""
    try:
        names = extract_invalid_objects(error_text)
        if not names:
            return None
        objects: dict[str, Any] = {}
        for n in names[:5]:
            try:
                objects[n] = _diagnose(parsed, n, file_path, db_type)
            except Exception as e:
                logger.debug(f"object_hint diagnose {n}: {e}")
        if not objects:
            return None
        kinds = {o["kind"] for o in objects.values()}
        return {"rule": RULE_NAME,
                "kind": "fix_args" if kinds != {"not_found"} else "switch",
                "objects": objects}
    except Exception as e:
        logger.debug(f"object_hint error: {e}")
        return None

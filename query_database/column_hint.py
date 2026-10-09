"""Recovery cho lỗi ``Invalid column name`` — gắn cột thật + gợi ý vào response lỗi.

Log thực tế: lỗi hay gặp nhất của query_database là agent đoán tên cột (99 lần /
3 tuần). Agent thường phải tốn thêm 1 call ``sys.columns`` mới viết lại được
query. Module này làm sẵn bước đó ngay trong response lỗi:

1. Regex lấy cột sai từ message SQL Server (``Invalid column name 'x'``).
2. Parse câu SQL lấy bảng sau FROM/JOIN/UPDATE/INSERT INTO (bỏ #temp, subquery).
3. Query read-only ``sys.columns`` lấy cột thật của các bảng đó.
4. Gợi ý: ``difflib`` cho lỗi chính tả (``ma_khach`` → ``ma_kh``); Jev Choice cho
   sai nghĩa (``name`` → ``ten_bang``), chỉ nhận khi confidence đủ cao.

Nguyên tắc: chỉ quan sát — mọi lỗi trong recovery bị nuốt, trả ``None``; KHÔNG
đổi ``success`` hay message lỗi gốc.
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

RULE_NAME = "invalid_column"

_INVALID_COL_RE = re.compile(r"Invalid column name '([^']+)'", re.IGNORECASE)

# Bảng sau FROM/JOIN/UPDATE/INTO: [dbo].[x], dbo.x, x$202601, m81$000000...
_IDENT = r"(?:\[[^\]]+\]|[A-Za-z_#@][\w$#@]*)"
_TABLE_RE = re.compile(
    rf"\b(?:FROM|JOIN|UPDATE|INTO)\s+({_IDENT}(?:\s*\.\s*{_IDENT}){{0,2}})",
    re.IGNORECASE,
)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_RE = re.compile(r"N?'(?:[^']|'')*'")

_MAX_TABLES = 8
_MAX_COLS_LISTED = 300
_DIFFLIB_CUTOFF = 0.6
_JEV_MAX_OPTIONS = 240      # docs TypeSafe: Choice ổn định tới ~240 option
_JEV_TIMEOUT_CAP = 5        # recovery không được làm agent chờ lâu
_DIFFLIB_STRONG = 0.8       # difflib >= ngưỡng này mới đủ tin, khỏi hỏi Jev
_JEV_CONF_ACT = 0.7         # fallback khi config không có confidence_act
_JEV_CONF_REVIEW = 0.4      # fallback khi config không có confidence_review

_UNSET = object()
_jev_config_cache: Any = _UNSET


def extract_invalid_columns(error_text: str) -> list[str]:
    """Các cột SQL Server báo không tồn tại (giữ thứ tự, bỏ trùng)."""
    seen: dict[str, None] = {}
    for m in _INVALID_COL_RE.finditer(error_text or ""):
        seen.setdefault(m.group(1), None)
    return list(seen)


def _strip_noise(sql: str) -> str:
    sql = _BLOCK_COMMENT_RE.sub(" ", sql)
    sql = _LINE_COMMENT_RE.sub(" ", sql)
    return _STRING_RE.sub("''", sql)


def _last_part(name: str) -> str:
    part = re.split(r"\s*\.\s*", name.strip())[-1]
    return part.strip("[]")


def extract_tables(sql: str) -> list[str]:
    """Bảng vật lý trong câu SQL (bỏ #temp, @table var, schema prefix)."""
    out: dict[str, None] = {}
    for m in _TABLE_RE.finditer(_strip_noise(sql or "")):
        name = _last_part(m.group(1))
        if not name or name[0] in "#@":
            continue
        out.setdefault(name, None)
        if len(out) >= _MAX_TABLES:
            break
    return list(out)


def fetch_columns(parsed: dict, tables: list[str]) -> dict[str, list[str]]:
    """Cột thật theo bảng — 1 query read-only sys.columns, parameterized."""
    from .executor import execute_query

    if not tables:
        return {}
    values = ",".join("(?)" for _ in tables)
    sql = (
        "SELECT t.name_in, c.name "
        f"FROM (VALUES {values}) t(name_in) "
        "JOIN sys.columns c ON c.object_id = OBJECT_ID(t.name_in) "
        "ORDER BY t.name_in, c.column_id"
    )
    res = execute_query(parsed, sql, max_rows=5000, params=tables)
    if not res.get("success"):
        return {}
    cols: dict[str, list[str]] = {}
    for rs in res.get("result_sets") or []:
        for row in rs.get("rows") or []:
            cols.setdefault(str(row[0]), []).append(str(row[1]))
    return cols


def _difflib_matches(bad: str, table_cols: dict[str, list[str]]) -> list[dict]:
    pool = {c.lower(): (t, c) for t, cs in table_cols.items() for c in cs}
    hits = difflib.get_close_matches(
        bad.lower(), list(pool), n=3, cutoff=_DIFFLIB_CUTOFF)
    return [{"column": pool[h][1], "table": pool[h][0], "by": "difflib",
             "score": round(difflib.SequenceMatcher(
                 None, bad.lower(), h).ratio(), 2)}
            for h in hits]


def _load_jev_config() -> dict | None:
    global _jev_config_cache
    if _jev_config_cache is _UNSET:
        try:
            from jev import load_jev_config

            _jev_config_cache = load_jev_config()
        except Exception:
            _jev_config_cache = None
    return _jev_config_cache


def _jev_matches(sql: str, bad_cols: list[str],
                 table_cols: dict[str, list[str]],
                 jev_config: dict) -> dict[str, dict]:
    """1 call Jev, mỗi cột sai = 1 Choice trên cột thật + 'none'.

    Trả ``{bad: {"hit": dict|None, "none_confident": bool}}`` — hit khi
    conf >= confidence_review (``uncertain`` nếu < confidence_act);
    ``none_confident`` khi Jev chắc chắn không cột nào khớp nghĩa.
    """
    from jev import ask_jev

    multi = len(table_cols) > 1
    options: dict[str, tuple[str, str]] = {}
    for t, cs in table_cols.items():
        for c in cs:
            options[f"{t}.{c}" if multi else c] = (t, c)
    if not options or len(options) + 1 > _JEV_MAX_OPTIONS:
        return {}

    criteria: dict[str, Any] = {k: None for k in options}
    criteria["none"] = "no real column matches the intended meaning"
    questions = {
        f"col{i}": {
            "type": "choice",
            "instructions": (
                f"The SQL references column `{bad}` which does not exist. "
                "Which real column (state.table_columns) did the author "
                "most likely mean? Pick 'none' if unsure."
            ),
            "criteria": criteria,
        }
        for i, bad in enumerate(bad_cols)
    }
    state = {"sql": sql[:3000], "invalid_columns": bad_cols,
             "table_columns": table_cols}
    cfg = dict(jev_config)
    cfg["timeout_seconds"] = min(
        int(cfg.get("timeout_seconds") or _JEV_TIMEOUT_CAP), _JEV_TIMEOUT_CAP)
    res = ask_jev(cfg, state, questions)
    if not res.get("ok"):
        return {}

    act = float(jev_config.get("confidence_act") or _JEV_CONF_ACT)
    review = float(jev_config.get("confidence_review") or _JEV_CONF_REVIEW)
    out: dict[str, dict] = {}
    for i, bad in enumerate(bad_cols):
        ans = (res.get("answers") or {}).get(f"col{i}") or {}
        choice = str(ans.get("choice") or "")
        conf = float(ans.get("confidence") or 0)
        hit = None
        if choice in options and conf >= review:
            t, c = options[choice]
            hit = {"column": c, "table": t, "by": "jev",
                   "confidence": round(conf, 2)}
            if conf < act:
                hit["uncertain"] = True
        out[bad] = {"hit": hit,
                    "none_confident": choice == "none" and conf >= act}
    return out


def build_column_hint(parsed: dict, sql: str, error_text: str,
                      jev_config: Any = _UNSET) -> dict | None:
    """Khối ``recovery`` cho lỗi Invalid column, hoặc None nếu không áp dụng."""
    try:
        bad_cols = extract_invalid_columns(error_text)
        if not bad_cols:
            return None
        tables = extract_tables(sql)
        table_cols = fetch_columns(parsed, tables) if tables else {}

        # difflib bắt lỗi chính tả; chỉ hit >= _DIFFLIB_STRONG mới đủ tin để
        # khỏi hỏi Jev (hit yếu như gia_ban→ong_ba thường là nhiễu).
        did_you_mean: dict[str, list[dict]] = {}
        need_jev: list[str] = []
        for bad in bad_cols:
            hits = _difflib_matches(bad, table_cols)
            if hits:
                did_you_mean[bad] = hits
            if not any(h["score"] >= _DIFFLIB_STRONG for h in hits):
                need_jev.append(bad)

        if jev_config is _UNSET:
            jev_config = _load_jev_config()
        if need_jev and table_cols and jev_config:
            try:
                jev_out = _jev_matches(sql, need_jev, table_cols, jev_config)
            except Exception as e:  # Jev lỗi → vẫn còn difflib + cột thật
                logger.debug(f"column_hint jev error: {e}")
                jev_out = {}
            for bad, r in jev_out.items():
                weak = did_you_mean.pop(bad, [])
                if r["none_confident"]:
                    continue        # Jev chắc không cột nào khớp → bỏ nhiễu
                merged = [r["hit"]] if r["hit"] else []
                merged += [h for h in weak if not r["hit"]
                           or h["column"] != r["hit"]["column"]
                           or h["table"] != r["hit"]["table"]]
                if merged:
                    did_you_mean[bad] = merged
        did_you_mean = {b: did_you_mean[b] for b in bad_cols
                        if b in did_you_mean}

        hint: dict[str, Any] = {
            "rule": RULE_NAME,
            "kind": "fix_args",
            "invalid_columns": bad_cols,
            "table_columns": {t: cs[:_MAX_COLS_LISTED]
                              for t, cs in table_cols.items()},
        }
        if did_you_mean:
            hint["did_you_mean"] = did_you_mean
        missing = [t for t in tables if t not in table_cols]
        if missing:
            hint["unresolved_tables"] = missing
        if table_cols:
            hint["hint"] = ("Sửa query dùng cột có thật ở trên — không cần "
                            "query sys.columns nữa")
        else:
            hint["hint"] = ("Không xác định được bảng — check schema bằng "
                            "query_database query_type=0 với tên bảng")
        return hint
    except Exception as e:
        logger.debug(f"column_hint error: {e}")
        return None

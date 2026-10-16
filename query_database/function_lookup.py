"""mode='lookup': tra chức năng FBO theo mã CT / tên controller / tiêu đề menu.

Gom 1 lần các câu agent hay tự viết sai cột trên bảng hệ thống:
- DB sys: ``wcommand`` (cây menu web: wmenu_id, wmenu_id0, bar, link, sysid)
  JOIN ``command`` (menu_id, sysid = controller, syscode = ma_ct, exe).
- DB app: ``dmct`` (ma_ct, ten_ct, m_phdbf/m_ctdbf).
- Đĩa: App_Data/Controllers/<folder>/<controller>.xml|.f.

Cột được dò qua sys.columns trước khi dựng SQL — bản FBO thiếu cột/bảng
thì bỏ qua phần đó thay vì lỗi Invalid column. Tiêu đề so khớp không dấu
(COLLATE Latin1_General_CI_AI). Mọi giá trị người dùng đi qua tham số '?'.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from .connection import get_connection_config
from .executor import execute_query

_W_COLS = ("wmenu_id", "wmenu_id0", "menu_id", "bar", "bar2", "link",
           "parameter", "sysid", "type")
_C_COLS = ("menu_id", "sysid", "syscode", "bar", "bar2", "type", "exe")
_D_COLS = ("ma_ct", "ten_ct", "ten_ct2", "ma_phan_he", "ma_ct_me",
           "m_phdbf", "m_ctdbf", "status")
_CTRL_FOLDERS = ("Dir", "Grid", "Filter", "List", "Report", "View")
_TYPE_DESC = {"V": "voucher", "D": "category"}
_AI = "COLLATE Latin1_General_CI_AI"
_ROW_CAP = 200
_FILE_CHECK_CAP = 15


def _like_param(keyword: str) -> str:
    esc = keyword.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
    return f"%{esc}%"


def _rows(res: dict) -> list[dict]:
    sets = res.get("result_sets") or []
    if not sets:
        return []
    cols = sets[0].get("columns") or []
    return [dict(zip(cols, r)) for r in sets[0].get("rows") or []]


def _table_columns(parsed: dict, tables: tuple[str, ...]) -> dict[str, set]:
    placeholders = ", ".join("OBJECT_ID(?)" for _ in tables)
    res = execute_query(
        parsed,
        "SELECT OBJECT_NAME(object_id) AS t, LOWER(name) AS c FROM sys.columns "
        f"WHERE object_id IN ({placeholders})",
        max_rows=2000,
        params=tuple(f"dbo.{t}" for t in tables),
    )
    out: dict[str, set] = {}
    for r in _rows(res):
        out.setdefault(str(r["t"]).lower(), set()).add(r["c"])
    return out


def _col(alias: str, cols: set, name: str) -> str:
    return f"{alias}.{name}" if name in cols else "NULL"


def _menu_sql(wcols: set, ccols: set, keyword: str) -> tuple[str, list]:
    """SQL tra menu: wcommand (+command) và command không có trong wcommand."""
    like = _like_param(keyword)
    parts: list[str] = []
    params: list = []

    def match(alias: str, cols: set, extra_exact: tuple = (),
              extra_like: tuple = ()) -> tuple[str, list]:
        conds, ps = [], []
        for name in ("sysid", "menu_id") + extra_exact:
            if name in cols:
                conds.append(f"RTRIM({alias}.{name}) = ?")
                ps.append(keyword)
        if "sysid" in cols:
            conds.append(f"{alias}.sysid LIKE ?")
            ps.append(like)
        for name in ("bar", "bar2"):
            if name in cols:
                conds.append(f"{alias}.{name} {_AI} LIKE ?")
                ps.append(like)
        for name in extra_like:
            if name in cols:
                conds.append(f"{alias}.{name} LIKE ?")
                ps.append(like)
        return " OR ".join(conds), ps

    if wcols:
        join_c = bool(ccols) and "menu_id" in wcols and "menu_id" in ccols
        c = ccols if join_c else set()
        w_cond, w_ps = match("w", wcols, ("wmenu_id",), ("link", "parameter"))
        c_cond, c_ps = match("c", c, ("syscode",), ("exe",)) if c else ("", [])
        where = " OR ".join(x for x in (w_cond, c_cond) if x) or "1 = 0"
        has_parent = "wmenu_id0" in wcols and "wmenu_id" in wcols
        parts.append(
            f"SELECT TOP {_ROW_CAP} 'wcommand' AS src, "
            f"RTRIM({_col('w', wcols, 'wmenu_id')}) AS wmenu_id, "
            f"RTRIM({_col('w', wcols, 'menu_id')}) AS menu_id, "
            f"{_col('w', wcols, 'bar')} AS title, {_col('w', wcols, 'bar2')} AS title_e, "
            f"RTRIM(COALESCE(NULLIF(RTRIM({_col('w', wcols, 'sysid')}), ''), "
            f"{_col('c', c, 'sysid')})) AS controller, "
            f"RTRIM({_col('c', c, 'syscode')}) AS ma_ct, "
            f"RTRIM(COALESCE(NULLIF(RTRIM({_col('w', wcols, 'type')}), ''), "
            f"{_col('c', c, 'type')})) AS type, "
            f"RTRIM(COALESCE(NULLIF(RTRIM({_col('w', wcols, 'link')}), ''), "
            f"{_col('c', c, 'exe')})) AS page, "
            f"{_col('w', wcols, 'parameter')} AS parameter, "
            f"{'p.bar' if has_parent and 'bar' in wcols else 'NULL'} AS parent_title, "
            f"{'pp.bar' if has_parent and 'bar' in wcols else 'NULL'} AS grand_title "
            "FROM wcommand w "
            + ("LEFT JOIN command c ON c.menu_id = w.menu_id " if join_c else "")
            + ("LEFT JOIN wcommand p ON p.wmenu_id = w.wmenu_id0 "
               "LEFT JOIN wcommand pp ON pp.wmenu_id = p.wmenu_id0 "
               if has_parent else "")
            + f"WHERE {where}"
        )
        params += w_ps + c_ps

    if ccols:
        c_cond, c_ps = match("c", ccols, ("syscode",), ("exe",))
        not_in_w = (
            "NOT EXISTS (SELECT 1 FROM wcommand w WHERE w.menu_id = c.menu_id) AND "
            if wcols and "menu_id" in wcols and "menu_id" in ccols else ""
        )
        parts.append(
            f"SELECT TOP {_ROW_CAP} 'command' AS src, NULL AS wmenu_id, "
            f"RTRIM({_col('c', ccols, 'menu_id')}) AS menu_id, "
            f"{_col('c', ccols, 'bar')} AS title, {_col('c', ccols, 'bar2')} AS title_e, "
            f"RTRIM({_col('c', ccols, 'sysid')}) AS controller, "
            f"RTRIM({_col('c', ccols, 'syscode')}) AS ma_ct, "
            f"RTRIM({_col('c', ccols, 'type')}) AS type, "
            f"RTRIM({_col('c', ccols, 'exe')}) AS page, NULL AS parameter, "
            "NULL AS parent_title, NULL AS grand_title "
            f"FROM command c WHERE {not_in_w}({c_cond or '1 = 0'})"
        )
        params += c_ps

    return ";\n".join(parts), params


def _score(row: dict, keyword: str) -> int:
    k = keyword.lower()
    ctrl = str(row.get("controller") or "").lower()
    if k in (str(row.get("ma_ct") or "").lower(), ctrl,
             str(row.get("menu_id") or "").lower(),
             str(row.get("wmenu_id") or "").lower()):
        return 0
    if ctrl.startswith(k):
        return 1
    if k in ctrl:
        return 2
    return 3


def _controller_files(project_root: str, controllers: list[str]) -> dict:
    base = os.path.join(project_root, "App_Data", "Controllers")
    jobs = [(ctrl, folder, ext) for ctrl in controllers
            for folder in _CTRL_FOLDERS for ext in (".xml", ".f")]

    def check(job: tuple) -> tuple | None:
        ctrl, folder, ext = job
        return job if os.path.isfile(os.path.join(base, folder, ctrl + ext)) else None

    out: dict[str, dict] = {c: {"files": [], "encrypted_only": []} for c in controllers}
    with ThreadPoolExecutor(max_workers=16) as pool:
        found = {j for j in pool.map(check, jobs) if j}
    for ctrl in controllers:
        for folder in _CTRL_FOLDERS:
            if (ctrl, folder, ".xml") in found:
                out[ctrl]["files"].append(f"{folder}/{ctrl}.xml")
            elif (ctrl, folder, ".f") in found:
                out[ctrl]["encrypted_only"].append(f"{folder}/{ctrl}.f")
    return out


def lookup_function(file_path: str, keyword: str, max_results: int = 20) -> dict:
    """Tra chức năng theo mã CT | controller | menu_id | tiêu đề (không dấu OK)."""
    keyword = (keyword or "").strip()
    if not keyword:
        return {
            "success": False, "mode": "lookup", "error_code": "keyword_required",
            "error": "mode='lookup' cần query = mã CT (DDV) | controller (DDVTran) "
                     "| menu_id | cụm tiêu đề (vd 'hop dong dich vu')",
        }
    max_results = max(1, min(int(max_results or 20), 50))
    warnings: list[str] = []

    sys_conn = get_connection_config(file_path, "sys")
    if not sys_conn.get("success"):
        sys_conn["mode"] = "lookup"
        return sys_conn
    project_root = sys_conn.get("project_root") or ""

    scols = _table_columns(sys_conn["parsed"], ("wcommand", "command"))
    wcols, ccols = scols.get("wcommand", set()), scols.get("command", set())
    menu_rows: list[dict] = []
    if not wcols and not ccols:
        warnings.append("DB sys không có bảng wcommand/command — bỏ qua tra menu")
    else:
        sql, params = _menu_sql(wcols, ccols, keyword)
        res = execute_query(sys_conn["parsed"], sql, max_rows=_ROW_CAP * 2,
                            params=tuple(params))
        if not res.get("success"):
            return {"success": False, "mode": "lookup", "error": res.get("error"),
                    "project_root": project_root}
        for rs in res.get("result_sets") or []:
            cols = rs.get("columns") or []
            menu_rows += [dict(zip(cols, r)) for r in rs.get("rows") or []]

    by_key: dict = {}
    functions: list[dict] = []
    for row in sorted(menu_rows, key=lambda r: (_score(r, keyword),
                                                str(r.get("wmenu_id") or r.get("menu_id") or ""))):
        if str(row.get("title") or "").strip() in ("", "-", "."):
            continue  # dòng phân cách menu
        path = " > ".join(
            str(t).strip() for t in (row.get("grand_title"), row.get("parent_title"),
                                     row.get("title"))
            if t and str(t).strip() not in ("", ".", "-")
        )
        # 1 controller gắn nhiều menu → gộp, giữ danh sách menu_paths
        key = row.get("controller") or (row.get("title"), row.get("menu_id"))
        if key in by_key:
            paths = by_key[key]["menu_paths"]
            if path not in paths:
                paths.append(path)
            continue
        typ = (row.get("type") or "").strip()
        page = str(row.get("page") or "").strip()
        entry = {
            "controller": row.get("controller") or None,
            "ma_ct": row.get("ma_ct") or None,
            "title": row.get("title"),
            "title_e": row.get("title_e"),
            "type": _TYPE_DESC.get(typ, typ or None),
            "page": page if page not in ("", ".") else None,
            "parameter": row.get("parameter") or None,
            "menu_id": row.get("menu_id") or None,
            "wmenu_id": row.get("wmenu_id") or None,
            "menu_paths": [path],
            "source": row.get("src"),
        }
        by_key[key] = entry
        functions.append(entry)
    truncated = len(functions) > max_results
    functions = functions[:max_results]

    # dmct (DB app): mã CT khớp keyword hoặc syscode của menu tìm được
    vouchers: list[dict] = []
    app_conn = get_connection_config(file_path, "app")
    if app_conn.get("success"):
        dcols = _table_columns(app_conn["parsed"], ("dmct",)).get("dmct", set())
        if "ma_ct" in dcols:
            codes = sorted({f["ma_ct"] for f in functions if f["ma_ct"]} | {keyword})[:30]
            conds = [f"RTRIM(ma_ct) IN ({', '.join('?' for _ in codes)})"]
            params = list(codes)
            for name in ("ten_ct", "ten_ct2"):
                if name in dcols:
                    conds.append(f"{name} {_AI} LIKE ?")
                    params.append(_like_param(keyword))
            select = ", ".join(f"RTRIM({c}) AS {c}" if c in dcols else f"NULL AS {c}"
                               for c in _D_COLS)
            res = execute_query(app_conn["parsed"],
                                f"SELECT TOP 30 {select} FROM dmct WHERE {' OR '.join(conds)}",
                                max_rows=30, params=tuple(params))
            vouchers = _rows(res) if res.get("success") else []
        else:
            warnings.append("DB app không có bảng dmct — bỏ qua thông tin chứng từ")

    # File controller trên đĩa
    ctrls = list(dict.fromkeys(f["controller"] for f in functions if f["controller"]))
    if project_root and ctrls:
        files = _controller_files(project_root, ctrls[:_FILE_CHECK_CAP])
        for f in functions:
            info = files.get(f["controller"] or "")
            if info:
                f["files"] = info["files"]
                if info["encrypted_only"]:
                    f["encrypted_only"] = info["encrypted_only"]
        if len(ctrls) > _FILE_CHECK_CAP:
            warnings.append(f"Chỉ kiểm tra file cho {_FILE_CHECK_CAP} controller đầu")

    hints: list[str] = []
    if not functions and not vouchers:
        hints.append(
            "Không có trong menu/dmct — màn hình con/popup thường không đăng ký "
            "menu: search_files mode=content include_glob='*.xml' pattern='<cụm "
            "tiêu đề>' root=App_Data/Controllers"
        )
    elif any(f.get("encrypted_only") and not f.get("files") for f in functions):
        hints.append("encrypted_only = chỉ có .f (mã hóa, KHÔNG sửa) — cần .xml nguồn thì hỏi user")
    if any(f.get("files") for f in functions):
        hints.append("Đọc cấu trúc: read_local_file read_option=3 trên files[0]")

    result = {
        "success": True,
        "mode": "lookup",
        "keyword": keyword,
        "functions": functions,
        "function_count": len(functions),
        "vouchers": vouchers,
        "truncated": truncated,
        "project_root": project_root,
    }
    if hints:
        result["hints"] = hints
    if warnings:
        result["warnings"] = warnings
    return result

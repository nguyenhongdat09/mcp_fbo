"""type=6 — Save-as / copy từ chức năng có sẵn.

Grammar ``object``: ``saveas:<src>-><new_ctrl>``

  ``<src>``:
    - ``ctrl:zclctt``         → tên controller nguồn trực tiếp
    - ``title:Báo cáo ...``   → tìm theo title_v/title_e (Kuzu trước,
                              fallback quét <title v="..."> trên disk vì
                              watcher có thể chưa kịp index / bị tắt khi
                              user_multi_db_yn=0)
    - ``zclctt``              → auto: chuỗi identifier → ctrl
    - ``Báo cáo ...``         → auto: có space/ký tự đặc biệt → title
    - ``zclctt.xml`` / ``Filter/zclctt.xml`` → lấy stem làm ctrl

Flow:
  1. Resolve src → source_ctrl (trả candidates khi ambiguous, không auto-pick).
  2. Delegate clone file cho type=3: ``suite:<src>-><dst>`` (execute/overwrite
     giữ nguyên semantics type=3 — mặc định dry-run).
  3. Đọc Filter/Report/Grid/Dir/Query XML nguồn → summary_xml → sql.procs →
     export ALTER ra 1 file .sql temp (UTF-8 BOM) bằng machinery type=1.
     Proc KHÔNG tự đổi tên — agent đổi trong file .sql theo tên user gửi.
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from .file_manager import (
    resolve_output_file,
    append_script_block,
    ensure_use_db_sections,
)
from .helpers import normalize_object_name
from .open_editor import open_file_for_user
from .script_transform import transform_create_to_alter
from .type3_file_clone import (
    coerce_bool,
    resolve_project_root,
    _expand_suite_files,
    run_type3_file_clone,
    to_posix,
)

logger = logging.getLogger("clone_things.type6")

RE_IDENT = re.compile(r"^[a-zA-Z0-9_]+$")
RE_TITLE = re.compile(r'<title[^>]*\bv="([^"]*)"', re.IGNORECASE)

# Folder có khả năng chứa <title v> + proc chính của suite báo cáo/chứng từ.
TITLE_SCAN_DIRS = ("Filter", "Report", "Grid", "Dir", "Lookup", "Query", "View")
SQL_REF_FOLDERS = {"filter", "report", "grid", "dir", "query"}

# System noise — không export khi gặp trong command/query.
_SQL_SKIP_PREFIXES = ("sp_", "xp_", "dt_", "fn_help", "fsd_diag")

# Hậu tố file phụ của suite — khi ambiguous, controller KHÔNG mang hậu tố
# này thường là trang chính (ví dụ rptBalanceSheetMultiPeriod vs
# rptBalanceSheetMultiPeriodGraph).
_AUX_SUFFIX = re.compile(
    r"(Graph|Group|Detail|Files|Form|Lookup|MultiForm|MultiGrid)$",
    re.IGNORECASE,
)


def _err(code: str, message: str, warnings: list[str], elapsed, **extra) -> dict[str, Any]:
    res: dict[str, Any] = {
        "success": False,
        "spec_version": "1.0",
        "type": 6,
        "mode": "save_as",
        "error_code": code,
        "message": message,
        "warnings": warnings,
        "elapsed_ms": elapsed(),
    }
    res.update(extra)
    return res


def parse_saveas_spec(object_str: str) -> tuple[str, str, str, str | None]:
    """Parse ``saveas:<src>-><new>``.

    Returns (kind, src_val, dst_ctrl, err_code). kind ∈ {"ctrl", "title"}.
    """
    spec = (object_str or "").strip()
    if not spec.lower().startswith("saveas:"):
        return "", "", "", "invalid_object"
    body = spec[len("saveas:"):].strip()
    if "->" not in body:
        return "", "", "", "invalid_object"
    src_tok, dst_tok = (s.strip() for s in body.split("->", 1))
    if not src_tok or not dst_tok:
        return "", "", "", "invalid_object"
    if not RE_IDENT.match(dst_tok):
        return "", "", "", "invalid_rename"

    low = src_tok.lower()
    if low.startswith("ctrl:"):
        kind, val = "ctrl", src_tok[5:].strip()
    elif low.startswith("title:"):
        kind, val = "title", src_tok[6:].strip()
    elif src_tok.lower().endswith(".xml") or "/" in src_tok or "\\" in src_tok:
        kind, val = "ctrl", Path(src_tok).stem
    elif RE_IDENT.match(src_tok):
        kind, val = "ctrl", src_tok
    else:
        kind, val = "title", src_tok

    if not val:
        return "", "", "", "invalid_object"
    if kind == "ctrl" and not RE_IDENT.match(val):
        return "", "", "", "invalid_object"
    return kind, val, dst_tok, None


def _scan_titles_on_disk(root_src_path: Path, term: str) -> list[dict[str, Any]]:
    """Quét <title v="..."> trong App_Data/Controllers khi Kuzu không sẵn sàng.

    Chỉ đọc .xml trong các folder suite (TITLE_SCAN_DIRS), tối đa 64KB/file.
    """
    hits: list[dict[str, Any]] = []
    ctrl_root = root_src_path / "App_Data" / "Controllers"
    if not ctrl_root.is_dir():
        ctrl_root = root_src_path
    term_l = term.lower()
    for sub in TITLE_SCAN_DIRS:
        d = ctrl_root / sub
        if not d.is_dir():
            continue
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except Exception:
            continue
        for e in entries:
            if not e.is_file() or not e.name.lower().endswith(".xml"):
                continue
            try:
                head = Path(e.path).read_text(
                    encoding="utf-8", errors="ignore"
                )[:65536]
            except Exception:
                continue
            m = RE_TITLE.search(head)
            if m and term_l in (m.group(1) or "").lower():
                rel = to_posix(Path(e.path).relative_to(root_src_path))
                hits.append(
                    {
                        "relative_path": rel,
                        "title_v": m.group(1),
                        "folder_type": sub,
                        "via": "disk",
                    }
                )
    return hits


def _scan_titles_via_kuzu(
    root_src_path: Path, project_source: str, term: str, warnings: list[str]
) -> list[dict[str, Any]]:
    """Tìm theo title_v/title_e qua Kuzu graph. Trả [] khi DB chưa build / lỗi."""
    try:
        from xml_fbograph.utils.path_helper import ProjectPathHelper
        from xml_fbograph.utils.kuzu_build_spawn import kuzu_db_ready

        helper = ProjectPathHelper(project_source or str(root_src_path))
        if not kuzu_db_ready(helper.get_kuzu_path()):
            warnings.append(
                "kuzu_not_built: Kuzu chưa build → quét <title> trên disk. "
                "Nếu project chỉ có .f thì quét disk cũng không thấy title "
                "(file mã hóa) — cần file .xml nguồn."
            )
            return []
        from xml_fbograph.query.engine import xml_graph_query

        res = xml_graph_query(
            "search",
            term,
            str(root_src_path),
            match_type="file",
            folder_filter="filter,report,grid,dir,lookup,query,view",
            limit=50,
        )
        out = []
        term_l = term.lower()
        for m in res.get("file_matches") or []:
            rel = (m.get("relative_path") or "").replace(" [Encrypted]", "")
            tv = m.get("title_v") or ""
            te = m.get("title_e") or ""
            # Chỉ nhận match mà title thật sự chứa term (loại match qua
            # path/stem/synonym của engine)
            if term_l and (term_l in tv.lower() or term_l in te.lower()):
                out.append(
                    {
                        "relative_path": rel,
                        "title_v": tv,
                        "folder_type": m.get("folder_type") or "",
                        "is_encrypted": bool(m.get("is_encrypted")),
                        "needs_xml": bool(m.get("needs_xml")),
                        "via": "kuzu",
                    }
                )
        return out
    except Exception as e:
        warnings.append(f"kuzu_search_failed: {e} → quét <title> trên disk")
        return []


def resolve_source_by_title(
    root_src_path: Path, project_source: str, title: str, warnings: list[str]
) -> tuple[str | None, list[dict[str, Any]]]:
    """Title → controller stem. Trả (ctrl_name, candidates).

    ctrl_name=None + candidates rỗng = không tìm thấy; >1 candidate = ambiguous.
    """
    hits = _scan_titles_via_kuzu(root_src_path, project_source, title, warnings)
    if not hits:
        hits = _scan_titles_on_disk(root_src_path, title)

    # Group theo controller stem
    by_ctrl: dict[str, dict[str, Any]] = {}
    for h in hits:
        stem = Path(h["relative_path"]).stem
        slot = by_ctrl.setdefault(
            stem,
            {
                "ctrl": stem,
                "titles": set(),
                "files": [],
                "exact": False,
                "needs_xml": False,
                "is_encrypted": False,
            },
        )
        slot["files"].append(h["relative_path"])
        if h.get("title_v"):
            slot["titles"].add(h["title_v"])
        if (h.get("title_v") or "").lower() == title.lower():
            slot["exact"] = True
        slot["needs_xml"] = slot["needs_xml"] or bool(h.get("needs_xml"))
        slot["is_encrypted"] = slot["is_encrypted"] or bool(h.get("is_encrypted"))

    candidates = list(by_ctrl.values())
    exact = [c for c in candidates if c["exact"]]
    pool = exact if exact else candidates
    for c in pool:
        c["titles"] = sorted(c["titles"])
    pool.sort(key=lambda c: (not c["exact"], c["ctrl"]))

    if len(pool) == 1:
        return pool[0]["ctrl"], pool
    return None, pool


def _collect_sql_refs(root_src_path: Path, suite_files: list[str], warnings: list[str]) -> list[str]:
    """Extract proc names từ các file XML của suite qua summary_xml."""
    import clone_things.service as svc

    names: list[str] = []
    seen: set[str] = set()
    for rel in suite_files:
        if not rel.lower().endswith(".xml"):
            continue
        parts = rel.split("/")
        folder = parts[-2].lower() if len(parts) >= 2 else ""
        if folder not in SQL_REF_FOLDERS:
            continue
        f_path = root_src_path / rel
        if not f_path.is_file():
            continue
        try:
            s = svc.summary_xml(str(f_path))
        except Exception as e:
            warnings.append(f"xml_summary_failed: {rel} ({e})")
            continue
        if not s.get("success"):
            warnings.append(f"xml_summary_failed: {rel}")
            continue
        for p in (s.get("sql") or {}).get("procs") or []:
            pn = str(p).strip()
            if not pn or pn.lower().startswith(_SQL_SKIP_PREFIXES):
                continue
            if pn.lower() not in seen:
                seen.add(pn.lower())
                names.append(pn)
    return names


def _export_sql_objects(
    sql_names: list[str],
    project_source: str,
    dest_ctrl: str,
    schema: str,
    open_file: bool,
    open_editor_cmd: str,
    config: dict[str, Any],
    warnings: list[str],
) -> tuple[str | None, list[dict[str, Any]], list[str], list[str]]:
    """Export ALTER từng proc ra 1 file .sql temp. Returns
    (out_file, pasted, unresolved, encrypted)."""
    import clone_things.service as svc
    from .db_ops import DB_LOOKUP_ORDER

    pasted: list[dict[str, Any]] = []
    unresolved: list[str] = []
    encrypted: list[str] = []

    source_dbs = svc.load_project_db_connections(project_source, warnings)
    if not source_dbs:
        warnings.append(
            "db_connections_missing: không resolve được connection từ "
            "project_source — bỏ qua export proc; agent export sau bằng "
            "clone_things type=1 (object=<tên proc>)"
        )
        unresolved.extend(sql_names)
        return None, pasted, unresolved, encrypted

    out_file, ferr = resolve_output_file(
        "", dest_ctrl, config, project_source=project_source
    )
    if ferr:
        warnings.append(
            f"sql_temp_unavailable: {ferr} — bỏ qua export proc; agent tự tạo "
            "file bằng clone_things type=5 rồi type=1"
        )
        unresolved.extend(sql_names)
        return None, pasted, unresolved, encrypted

    app_db = (source_dbs.get("app") or {}).get("database") or ""
    sys_db = (source_dbs.get("sys") or {}).get("database") or ""
    ensure_use_db_sections(out_file, app_db_name=app_db, sys_db_name=sys_db)

    for name in sql_names:
        i_schema, i_clean, _ = normalize_object_name(name, schema)
        full_name = f"{i_schema}.{i_clean}"
        try:
            exists, s_type, s_desc, s_db = svc.find_object_on_side(
                source_dbs, i_clean, i_schema, order=DB_LOOKUP_ORDER
            )
        except Exception as e:
            warnings.append(f"lookup_failed: {full_name} ({e})")
            unresolved.append(full_name)
            continue
        if not exists:
            unresolved.append(full_name)
            continue

        fetch_db = s_db or "app"
        conn = source_dbs.get(fetch_db)
        try:
            if conn and svc.is_object_encrypted(conn, i_clean, i_schema):
                encrypted.append(full_name)
                continue
        except Exception:
            pass

        try:
            fetch_res = svc.fetch_object_script(
                file_path=project_source,
                clean_name=i_clean,
                schema=i_schema,
                obj_type=s_type,
                type_desc=s_desc,
                db_type=fetch_db,
                wrap_exists=False,
            )
            script = fetch_res[0] if isinstance(fetch_res, tuple) else fetch_res
        except Exception as e:
            warnings.append(f"fetch_failed: {full_name} ({e})")
            unresolved.append(full_name)
            continue
        if not script:
            unresolved.append(full_name)
            continue

        tdesc = (s_desc or s_type or "OBJECT").upper()
        if any(k in tdesc for k in ("PROCEDURE", "PROC", "FUNCTION")) or s_type.upper() in ("P", "FN", "IF", "TF"):
            out_script = transform_create_to_alter(script)
        elif "VIEW" in tdesc or s_type.upper() == "V":
            out_script = transform_create_to_alter(script)
        else:
            out_script = script
            warnings.append(f"unsupported_object_kind: {full_name} ({s_desc or s_type})")

        try:
            ls, le = append_script_block(
                out_file,
                out_script,
                full_name,
                s_desc or s_type or "OBJECT",
                db=fetch_db,
                app_db_name=app_db,
                sys_db_name=sys_db,
                header_tag="save_as",
            )
            pasted.append(
                {"name": full_name, "db": fetch_db, "line_start": ls, "line_end": le}
            )
        except Exception as e:
            warnings.append(f"append_failed: {full_name} ({e})")
            unresolved.append(full_name)

    if pasted and open_file:
        opened, warn = open_file_for_user(out_file, open_editor_cmd, True)
        if warn:
            warnings.append(warn)

    return out_file, pasted, unresolved, encrypted


def run_type6_save_as(
    object: str = "",
    project_source: str = "",
    project_target: str = "",
    execute: Any = False,
    overwrite: Any = False,
    confirm_overwrite: Any = False,
    expand_dirs: Any = False,
    max_files: int = 100,
    schema: str = "dbo",
    open_file: bool = True,
    open_editor_cmd: str = "auto",
    config: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    start_time: float | None = None,
) -> dict[str, Any]:
    """Execute type=6 save-as flow."""
    warnings = warnings if warnings is not None else []
    if start_time is None:
        start_time = time.perf_counter()
    elapsed = lambda: round((time.perf_counter() - start_time) * 1000, 1)

    kind, src_val, dst_ctrl, perr = parse_saveas_spec(object)
    if perr:
        return _err(
            perr,
            "object phải dạng 'saveas:<src>-><new_ctrl>' — src: ctrl:<tên> / "
            "title:<tiêu đề> / tên controller (vd saveas:zclctt->zcbcdt hoặc "
            "saveas:title:Báo cáo lưu chuyển tiền tệ->zcbcdt)",
            warnings,
            elapsed,
        )

    root_src = resolve_project_root(project_source)
    if not root_src or not Path(root_src).exists():
        return _err(
            "invalid_project_source",
            f"Cannot resolve or find project_source root: {project_source}",
            warnings,
            elapsed,
        )
    root_src_path = Path(root_src)

    # --- 1. Resolve source controller ---
    source_ctrl = ""
    source_title = ""
    candidates: list[dict[str, Any]] = []
    if kind == "ctrl":
        source_ctrl = src_val
    else:
        source_ctrl, candidates = resolve_source_by_title(
            root_src_path, project_source, src_val, warnings
        )
        if not source_ctrl:
            if not candidates:
                return _err(
                    "source_not_found",
                    f"Không tìm thấy chức năng nào có title chứa '{src_val}'. "
                    "Kuzu có thể chưa index kịp .xml vừa dán (watcher tắt khi "
                    "user_multi_db_yn=0) hoặc project chỉ có .f — hỏi user "
                    "xác nhận file .xml nguồn hoặc gọi lại bằng "
                    "saveas:ctrl:<tên_controller>->...",
                    warnings,
                    elapsed,
                )
            non_aux = [
                c for c in candidates if not _AUX_SUFFIX.search(c["ctrl"])
            ]
            if len(non_aux) == 1:
                non_aux[0]["suggested"] = True
            return _err(
                "ambiguous_source",
                f"Title '{src_val}' match {len(candidates)} controller — "
                "hỏi user chọn rồi gọi lại bằng saveas:ctrl:<tên>->.... "
                "Gợi ý: controller KHÔNG hậu tố Graph/Group/Detail/Form "
                "thường là trang chính (suggested=true nếu chỉ có 1); "
                'phân biệt thêm bằng search_files mode=content pattern '
                '\'Controller="<stem>"\' trên <project>\\Main — trang .aspx '
                "chính trỏ đúng controller đó",
                warnings,
                elapsed,
                candidates=candidates,
            )
        source_title = sorted(candidates[0]["titles"])[0] if candidates and candidates[0]["titles"] else src_val

    suite_files = _expand_suite_files(root_src_path, source_ctrl, warnings)
    if not suite_files:
        return _err(
            "suite_empty",
            f"suite_empty: '{source_ctrl}' — không tìm thấy file controller "
            "nào trên source (kiểm tra project chỉ có .f → cần .xml nguồn)",
            warnings,
            elapsed,
            source_ctrl=source_ctrl,
        )
    if not any(f.lower().endswith(".xml") for f in suite_files):
        warnings.append(
            f"suite_f_only: '{source_ctrl}' chỉ có .f (encrypted), không có "
            ".xml đọc được — cần xin file .xml nguồn từ user"
        )

    # --- 2. Clone suite (delegate type=3) ---
    clone_res = run_type3_file_clone(
        object=f"suite:{source_ctrl}->{dst_ctrl}",
        project_source=project_source,
        project_target=project_target,
        execute=execute,
        overwrite=overwrite,
        confirm_overwrite=confirm_overwrite,
        expand_dirs=expand_dirs,
        max_files=max_files,
        warnings=warnings,
        start_time=start_time,
    )
    if not clone_res.get("success"):
        clone_res["type"] = 6
        clone_res["mode"] = "save_as"
        clone_res["stage"] = "suite_clone"
        clone_res["source_ctrl"] = source_ctrl
        clone_res["dest_ctrl"] = dst_ctrl
        return clone_res

    # _expand_suite_files chạy 2 lần (type6 trước + bên trong type3) →
    # warning marker bị nhân đôi; dedupe giữ thứ tự.
    seen_warn: set[str] = set()
    warnings[:] = [
        w for w in warnings if not (w in seen_warn or seen_warn.add(w))
    ]

    # --- 3. SQL refs → export ALTER ra .sql temp ---
    sql_names = _collect_sql_refs(root_src_path, suite_files, warnings)
    out_file, pasted, unresolved, encrypted = (
        _export_sql_objects(
            sql_names,
            project_source,
            dst_ctrl,
            schema,
            coerce_bool(open_file),
            open_editor_cmd,
            config or {},
            warnings,
        )
        if sql_names
        else (None, [], [], [])
    )
    if not sql_names:
        warnings.append(
            "no_sql_refs: không extract được proc nào từ XML suite — kiểm tra "
            "tay command/query trong Filter/Report (dynamic SQL có thể miss)"
        )

    next_steps = [
        f"Đổi tên object trong file .sql (ALTER/CREATE ... {source_ctrl}* → "
        f"tên mới theo user, vd proc {dst_ctrl}) — export giữ nguyên tên nguồn, "
        "không auto-rename",
        f"Sửa <title v=...> trong Filter/Report XML mới ({dst_ctrl}) thành "
        "title chức năng mới theo UR",
        "Đăng ký menu/aspx cho chức năng mới nếu UR yêu cầu",
        "Áp dụng các yêu cầu chỉnh sửa còn lại của UR (cách tính, toolbar, "
        "đồ thị, ...) lên bản clone",
        "Check syntax .sql bằng query_database query_type=3 (PARSEONLY) "
        "trước khi báo user F5",
    ]
    warn_txt = " ".join(warnings)
    if "suite_aspx_detected" in warn_txt:
        next_steps.append(
            "Review file .aspx detect được trong planned[]/copied[] — "
            "same-project save-as sẽ skip same-name: copy tay + đổi tên + "
            f'sửa Controller="{source_ctrl}" → "{dst_ctrl}" trong file mới'
        )
    elif "suite_aspx_missing" in warn_txt:
        next_steps.append(
            "Không detect được trang .aspx — tìm tay bằng search_files "
            f'pattern \'Controller="{source_ctrl}"\' trên <project>\\Main '
            "rồi copy + đổi tên + sửa Controller= trỏ controller mới"
        )
    denied_xsd = [
        r for r in (clone_res.get("skipped_denied") or [])
        if r.lower().endswith(".xsd")
    ]
    if denied_xsd:
        next_steps.append(
            "File .xsd bị deny (schema dataset do Report designer sinh): "
            + ", ".join(denied_xsd)
            + " — tạo lại bằng designer hoặc copy tay nếu UR cần"
        )
    graph_files = [
        f for f in suite_files if "graph" in Path(f).stem.lower()
    ]
    if graph_files:
        next_steps.append(
            "Suite có file Graph ("
            + ", ".join(Path(f).name for f in graph_files)
            + ") — clone chỉ đổi TÊN file: nội dung vẫn trỏ "
            f"entity/Identification của {source_ctrl}, sửa tay sau clone "
            "(nút Đồ thị còn cần aspx có LoadControl Chart.ascx + entity "
            "Identification/GraphMa*)"
        )
    has_excel = any(
        "/templates/excel/" in f.replace("\\", "/").lower()
        for f in suite_files
    )
    if not has_excel:
        next_steps.append(
            "Source không có mẫu in Excel (Templates/Excel) — UR cần mẫu "
            "Excel mới thì clone/tạo tay bằng clone_things type=3 + "
            "excel-mcp (xem skill fbo-excel-pivot-template)"
        )

    result: dict[str, Any] = {
        "success": True,
        "spec_version": "1.0",
        "type": 6,
        "mode": "save_as",
        "source_ctrl": source_ctrl,
        "source_title": source_title,
        "dest_ctrl": dst_ctrl,
        "execute": clone_res.get("execute"),
        "needs_user_confirm": clone_res.get("needs_user_confirm"),
        "summary_counts": clone_res.get("summary_counts"),
        "planned": clone_res.get("planned"),
        "will_copy": clone_res.get("will_copy"),
        "copied": clone_res.get("copied"),
        "exists_on_target": clone_res.get("exists_on_target"),
        "skipped_exists": clone_res.get("skipped_exists"),
        "skipped_denied": clone_res.get("skipped_denied"),
        "skipped_same_source": clone_res.get("skipped_same_source"),
        "user_prompt": clone_res.get("user_prompt"),
        "sql_objects": sql_names,
        "sql_objects_exported": [p["name"] for p in pasted],
        "sql_objects_unresolved": unresolved,
        "sql_objects_encrypted": encrypted,
        "path_to_pasted": out_file,
        "next_steps": next_steps,
        "warnings": warnings,
        "elapsed_ms": elapsed(),
    }
    if unresolved or encrypted:
        result["agent_message"] = (
            "Một số object không export được (unresolved/encrypted) — agent "
            "kiểm tay hoặc hỏi user; các yêu cầu UR còn lại sửa trên bản clone."
        )
    return result

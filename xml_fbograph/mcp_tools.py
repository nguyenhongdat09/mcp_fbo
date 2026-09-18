import json
import threading
import sys
from pathlib import Path
from typing import Optional

# Setup paths to ensure clean execution and imports
sys.path.append(str(Path(__file__).parent.parent.resolve()))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from xml_fbograph.utils.path_helper import ProjectPathHelper
from xml_fbograph.utils.any_path import project_switch_message, resolve_any_path
from xml_fbograph.utils.kuzu_build_spawn import (
    InvalidReferenceFileError,
    NotFastBusinessProjectError,
    KuzuBuildFailedError,
    ensure_mcp_kuzu_ready,
    kuzu_db_ready,
)
from xml_fbograph.service.watcher import start_watcher
from xml_fbograph.storage.kuzu_index import KuzuIndexStore
from xml_fbograph.query.engine import xml_graph_query, _safe_log
from xml_fbograph.save_disk import touch_kuzu_access, maybe_cleanup_stale_kuzu

# Cache connections and watcher
_watched_projects = set()
_kuzu_stores = {}


def _kuzu_db_ready(db_path: Path) -> bool:
    return kuzu_db_ready(db_path)


def _ensure_graph_built(reference_file: str) -> Path:
    """
    Dam bao Kuzu san sang cho MCP.
    Thieu Kuzu -> sync-build in-process roi return db_path.
    """
    return ensure_mcp_kuzu_ready(reference_file)


def start_watcher_for_project(reference_file: str):
    """Khoi chay file watcher trong background thread neu project nay chua duoc giam sat."""
    try:
        helper = ProjectPathHelper(reference_file)
        if not helper.is_fastbusiness_customerpro_project():
            return
        project_root = str(helper.get_project_root())
        controllers_dir = helper.get_controllers_path()
        graph_dir = helper.get_graph_dir()

        from xml_fbograph.utils.path_helper import is_db_owner
        if not is_db_owner(controllers_dir, graph_dir):
            sys.stderr.write(f"[FboFBOGraph MCP] user_multi_db_yn=0: Watcher disabled for {controllers_dir} because it is not owner of Kuzu DB ({graph_dir.parent.name})\n")
            return

        _watched_projects.add(project_root)

        def watcher_thread():
            try:
                import os
                sys.stderr.write(f"[FboFBOGraph MCP] Starting file watcher thread for {controllers_dir} (PID: {os.getpid()})\n")
                sys.stderr.write(f"[FboFBOGraph MCP] WARNING: Recommend using a single MCP instance per machine for same KuzuDB to avoid lock conflicts.\n")
                start_watcher(controllers_dir, graph_dir)
            except Exception as e:
                sys.stderr.write(f"[FboFBOGraph MCP] Watcher thread failed: {e}\n")

        t = threading.Thread(target=watcher_thread, daemon=True)
        t.start()
    except Exception as e:
        sys.stderr.write(f"[FboFBOGraph MCP] Error starting watcher: {e}\n")


def get_kuzu_store(reference_file: str, progress_callback=None):
    """Lay ket noi Kuzu read-only (gate CustomerPro; thieu DB -> sync-build in-process)."""

    def _prog(done: int, total: int, msg: str) -> None:
        if progress_callback:
            try:
                progress_callback(done, total, msg)
            except Exception:
                pass

    db_path = ensure_mcp_kuzu_ready(reference_file, progress_callback=progress_callback)
    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir()
    try:
        graph_dir = graph_dir.resolve()
        db_path = db_path.resolve()
    except Exception:
        pass
    db_key = str(db_path)

    from xml_fbograph.query import engine as qe

    start_watcher_for_project(reference_file)

    _prog(60, 100, "Mo Kuzu store / load graph...")
    store = qe.ensure_fresh_readonly_store(db_path, graph_dir)
    store._bind_live_connection()
    _kuzu_stores[db_key] = store
    
    # Touch access log & try cleanup
    touch_kuzu_access(str(helper.get_project_root()))
    maybe_cleanup_stale_kuzu()
    
    return store


def _mcp_gate_error_json(exc: Exception) -> Optional[str]:
    if isinstance(exc, (InvalidReferenceFileError, NotFastBusinessProjectError, KuzuBuildFailedError)):
        return json.dumps(exc.payload, indent=2, ensure_ascii=False)
    return None



# Tool 1
def _get_radar_schema(store: KuzuIndexStore) -> dict:
    """Doc schema Kuzu live va bo sung quy tac nghiep vu de agent viet Cypher."""
    from xml_fbograph.rules.edges_rules import EDGE_DESCRIPTIONS, EdgeType

    tables = store.execute_cypher("CALL show_tables() RETURN *")
    node_info = store.execute_cypher("CALL table_info('XmlFile') RETURN *")
    rel_info = store.execute_cypher("CALL table_info('Rel') RETURN *")
    live_edge_rows = store.execute_cypher(
        """
        MATCH (:XmlFile)-[r:Rel]->(:XmlFile)
        RETURN DISTINCT r.edge_type AS edge_type
        ORDER BY edge_type
        """
    )
    live_edge_types = {row["edge_type"] for row in live_edge_rows}

    node_columns = {row["name"]: row["type"] for row in node_info}
    rel_columns = {row["name"]: row["type"] for row in rel_info}
    edge_types = {}
    for edge_type in EdgeType:
        edge_types[edge_type.value] = {
            "description": EDGE_DESCRIPTIONS.get(edge_type, ""),
            "present_in_database": edge_type.value in live_edge_types,
        }

    return {
        "mode": "schema",
        "source": "Live Kuzu schema + FBO edge semantics",
        "tables": tables,
        "node_table": {
            "name": "XmlFile",
            "primary_key": "node_id",
            "columns": node_columns,
        },
        "relationship_table": {
            "name": "Rel",
            "from": "XmlFile",
            "to": "XmlFile",
            "columns": rel_columns,
        },
        "edge_types": edge_types,
        "rules": [
            "Kuzu chi co relationship table :Rel; loai nghiep vu nam trong r.edge_type.",
            "Dung MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile), khong dung label Neo4j [:GRID_MASTER_DETAIL].",
            "Luon filter r.edge_type va them LIMIT khi query relationship (SHARED_INCLUDE phu thuoc extract_options.shared_include).",
            "relative_path dung backslash, vi du Dir\\\\CPTran.xml.",
            "Dung js_text CONTAINS 'HandlerName' de tim JavaScript; dung size(string), khong dung length(string).",
            "canonical_path/alias_of gom nhieu file vat ly ve mot logical controller.",
        ],
        "examples": [
            {
                "name": "Master voucher -> detail grid",
                "cypher": (
                    "MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile) "
                    "WHERE a.relative_path = 'Dir\\\\CPTran.xml' "
                    "AND r.edge_type = 'GRID_MASTER_DETAIL' "
                    "RETURN a.relative_path, b.relative_path, r.meta LIMIT 20"
                ),
            },
            {
                "name": "Reverse lookup: ai goi RequestFilter",
                "cypher": (
                    "MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile) "
                    "WHERE b.relative_path CONTAINS 'RequestFilter' "
                    "AND r.edge_type = 'RETRIEVE_DATA_SOURCE' "
                    "RETURN a.relative_path, b.relative_path, r.meta LIMIT 20"
                ),
            },
            {
                "name": "Chuoi 2 cap voucher -> detail -> filter",
                "cypher": (
                    "MATCH (a:XmlFile)-[r1:Rel]->(b:XmlFile)-[r2:Rel]->(c:XmlFile) "
                    "WHERE r1.edge_type = 'GRID_MASTER_DETAIL' "
                    "AND r2.edge_type = 'RETRIEVE_DATA_SOURCE' "
                    "RETURN a.relative_path, b.relative_path, c.relative_path LIMIT 20"
                ),
            },
        ],
    }


def mcp_query_radar(
    cypher_query: str,
    reference_file: str,
    mode: str = "query",
    progress_callback=None,
) -> str:
    # Sticky context visibility — detect project từ reference_file (không đổi resolve)
    ctx_root: Optional[str] = None
    ctx_via = ""
    ctx_warn: Optional[str] = None
    if (reference_file or "").strip():
        _ctx_res = resolve_any_path(reference_file)
        if _ctx_res.ok:
            ctx_root = _ctx_res.project_root
            ctx_via = _ctx_res.resolved_via
            ctx_warn = project_switch_message(_ctx_res.switched_from, _ctx_res.project_root)

    def _wrap(payload):
        """Gắn project_root/resolved_via/warnings vào response khi có context."""
        if ctx_root is None and not ctx_warn:
            return payload
        if isinstance(payload, dict):
            payload.setdefault("project_root", ctx_root)
            payload.setdefault("resolved_via", ctx_via)
            if ctx_warn:
                warns = payload.setdefault("warnings", [])
                if isinstance(warns, list):
                    warns.append(ctx_warn)
            return payload
        env = {"results": payload, "project_root": ctx_root}
        if ctx_via:
            env["resolved_via"] = ctx_via
        if ctx_warn:
            env["warnings"] = [ctx_warn]
        return env

    try:
        normalized_mode = (mode or "query").strip().lower()
        if normalized_mode not in {"query", "schema"}:
            return json.dumps(
                _wrap({"error": "mode phai la 'query' hoac 'schema'"}),
                indent=2,
                ensure_ascii=False,
            )

        # Fail-fast: validate cypher TRUOC khi get_kuzu_store (load store tốn hàng chục giây)
        if normalized_mode == "query" and not (cypher_query or "").strip():
            return json.dumps(
                _wrap({"error": "cypher_query la bat buoc khi mode='query'"}),
                indent=2,
                ensure_ascii=False,
            )

        store = get_kuzu_store(reference_file, progress_callback=progress_callback)
        if normalized_mode == "schema":
            return json.dumps(_wrap(_get_radar_schema(store)), indent=2, ensure_ascii=False)

        is_rel_query = "-" in cypher_query and "MATCH" in cypher_query.upper()
        has_limit = "LIMIT" in cypher_query.upper()
        has_edge_filter = "EDGE_TYPE" in cypher_query.upper()

        warning = None
        if is_rel_query and not has_limit and not has_edge_filter:
            cypher_query = cypher_query.rstrip().rstrip(";") + " LIMIT 50"
            warning = (
                "Warning: Query MATCHes relationships without LIMIT or edge_type filter. "
                "Automatically applied LIMIT 50 to prevent context window overflow."
            )

        if progress_callback:
            try:
                progress_callback(85, 100, "Dang thuc thi Cypher...")
            except Exception:
                pass
        results = store.execute_cypher(cypher_query)

        if warning:
            return json.dumps(_wrap({"warning": warning, "results": results}), indent=2, ensure_ascii=False)
        return json.dumps(_wrap(results), indent=2, ensure_ascii=False)
    except Exception as e:
        gate = _mcp_gate_error_json(e)
        if gate:
            if ctx_root is not None or ctx_warn:
                try:
                    data = json.loads(gate)
                    if isinstance(data, dict):
                        return json.dumps(_wrap(data), indent=2, ensure_ascii=False)
                except Exception:
                    pass
            return gate
        err_text = f"Loi thuc thi Cypher: {str(e)}"
        if ctx_warn:
            err_text = f"[WARNING] {ctx_warn}\n" + err_text
        return err_text


# Tool 2
def mcp_search_nodes(
    query: str,
    reference_file: str,
    match_type: str = "all",
    folder_filter: str = None,
    limit: int = 20,
) -> str:
    try:
        if not folder_filter:
            folder_filter = "Dir,Grid,Filter,Report,Lookup"
        res = xml_graph_query(
            "search",
            query,
            reference_file,
            match_type=match_type,
            folder_filter=folder_filter,
            limit=limit,
        )
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        gate = _mcp_gate_error_json(e)
        if gate:
            return gate
        return f"Loi search_nodes: {str(e)}"


# Tool 3
def mcp_get_related_nodes(
    target: str,
    reference_file: str,
    mode: str = "navigate",
    include_shared: bool = False,
) -> str:
    try:
        res = xml_graph_query(mode, target, reference_file)
        if not include_shared and isinstance(res, dict):
            for key in ("dependencies", "dependents", "results"):
                if key in res and isinstance(res[key], list):
                    res[key] = [
                        item
                        for item in res[key]
                        if not (isinstance(item, dict) and item.get("type") == "SHARED_INCLUDE")
                    ]
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        gate = _mcp_gate_error_json(e)
        if gate:
            return gate
        return f"Loi get_related_nodes: {str(e)}"


# Tool 4
def mcp_query_node_details(target: str, reference_file: str, view: str = "context") -> str:
    try:
        res = xml_graph_query(view, target, reference_file, compact=True)
        if isinstance(res, dict):
            if "needs_xml" not in res:
                res["needs_xml"] = []
            if "agent_hint" not in res:
                res["agent_hint"] = ""
            if "source_on_disk" not in res:
                res["source_on_disk"] = ""
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        gate = _mcp_gate_error_json(e)
        if gate:
            return gate
        return f"Loi query_node_details: {str(e)}"


def _is_controller_xml(p: Path, project_root: Optional[Path]) -> bool:
    """True khi p là .xml trực thuộc Dir/Grid/Filter dưới App_Data/Controllers."""
    if p.suffix.lower() != ".xml" or project_root is None:
        return False
    controllers_root = (project_root / "App_Data" / "Controllers").resolve()
    try:
        rel = p.resolve().relative_to(controllers_root)
    except ValueError:
        return False
    return len(rel.parts) == 2 and rel.parts[0].lower() in {"dir", "grid", "filter"}


def _display_path(p: Path, project_root: Optional[Path]) -> str:
    """Path hiển thị trong response: rel tới Controllers hoặc project root."""
    if project_root is not None:
        controllers_root = (project_root / "App_Data" / "Controllers").resolve()
        for base in (controllers_root, project_root.resolve()):
            try:
                return str(p.resolve().relative_to(base))
            except ValueError:
                continue
    return str(p)


def _snippet_origin(p: Path, symbol: str) -> str:
    """'file' nếu symbol định nghĩa trong file gốc; 'entity:<name>'/'entity' nếu trong include."""
    import re as _re

    from xml_fbograph.parsers.xml_parser import read_file_content

    raw = read_file_content(p) or ""
    esc = _re.escape(symbol)
    if _re.search(r"(?<![\w$])function\s+" + esc + r"\s*\(", raw) or _re.search(
        r"(?<![\w$])" + esc + r"\s*=\s*", raw
    ):
        return "file"

    # Thử locate entity chứa định nghĩa (v1: best-effort, fallback 'entity')
    try:
        from find_entity_by_xml.entity_resolver import (
            get_entities_for_file,
            read_file_content as read_ent_file,
        )

        general, _param, _mtimes = get_entities_for_file(p)
        func_re = _re.compile(r"(?<![\w$])function\s+" + esc + r"\s*\(")
        for name, ent in (general or {}).items():
            src = (ent or {}).get("sourceFile") or (ent or {}).get("resolvedPath")
            if not src:
                continue
            content = read_ent_file(src) or ""
            if func_re.search(content):
                return f"entity:{name}"
    except Exception:
        pass
    return "entity"


def _snippet_response(p: Path, project_root: Optional[Path], view: str,
                      snippets: list, warnings: list) -> str:
    return json.dumps(
        {
            "success": True,
            "mode": "snippet",
            "file": _display_path(p, project_root),
            "view": view,
            "snippets": snippets,
            "warnings": warnings,
        },
        indent=2,
        ensure_ascii=False,
    )


def _snippet_error(code: str, p: Path, project_root: Optional[Path], **extra) -> str:
    payload = {
        "success": False,
        "mode": "snippet",
        "error_code": code,
        "file": _display_path(p, project_root),
    }
    payload.update(extra)
    return json.dumps(payload, indent=2, ensure_ascii=False)


_PLAIN_SCRIPT_EXTS = {".aspx", ".html", ".htm", ".cshtml"}
_MAX_LINE_CHARS_DEFAULT = 2000
_DUMP_CAP_CHARS = 80_000
_MINIFIED_WINDOW = 500


def _symbol_snippet_plain(p: Path, project_root: Optional[Path], source_text: str,
                          chunks: list, symbol: str, context_lines: int,
                          line_numbers: bool, max_line_chars: int,
                          warnings: list) -> str:
    """Symbol trên file thường (.js/.aspx/...) qua generic JS extractor.

    chunks: list (content_start_offset, chunk_text) — offset map về raw file.
    """
    from xml_controller_summary.snippet import (
        find_js_function_generic,
        format_snippet_lines,
        format_snippet_text,
        line_of,
        list_js_function_names_generic,
    )

    lines = source_text.split("\n")
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln) + 1)

    max_line_chars = max_line_chars or _MAX_LINE_CHARS_DEFAULT
    minified = any(len(l) > max_line_chars for l in lines)

    found: list = []  # (abs_start, abs_end|None, name)
    available: list = []
    for base, chunk in chunks:
        for m in find_js_function_generic(chunk, symbol):
            abs_s = base + m.start
            abs_e = base + m.end if m.end is not None and m.end >= 0 else None
            found.append((abs_s, abs_e, m.name))
        for nm in list_js_function_names_generic(chunk):
            if nm not in available:
                available.append(nm)

    if not found:
        extra = {"symbol": symbol, "available_functions": available[:50]}
        if minified:
            extra["note"] = "file minified — tên có thể không đầy đủ"
        return _snippet_error("symbol_not_found", p, project_root, **extra)

    snippets = []
    for abs_s, abs_e, name in found:
        line_no = line_of(source_text, abs_s)
        line_text = lines[line_no - 1] if 0 < line_no <= len(lines) else ""
        item = {"kind": "js_function", "name": name, "origin": "file"}
        if len(line_text) > max_line_chars:
            # Minified: cửa sổ ±_MINIFIED_WINDOW ký tự quanh match, không dump cả dòng
            col = abs_s - offsets[line_no - 1]
            win_lo = max(0, col - _MINIFIED_WINDOW)
            win_hi = min(len(line_text), col + _MINIFIED_WINDOW)
            text = line_text[win_lo:win_hi]
            if line_numbers:
                text = (
                    f"{line_no}|"
                    + ("…" if win_lo > 0 else "")
                    + text
                    + ("…" if win_hi < len(line_text) else "")
                )
            item.update(
                line_start=line_no,
                line_end=line_no,
                text=text,
                line_truncated=True,
                line_total_chars=len(line_text),
            )
        elif abs_e is None:
            # Fallback: không brace-match được → dòng match ± context_lines
            ls, le, text = format_snippet_lines(
                source_text, line_no, line_no, context_lines, line_numbers
            )
            item.update(line_start=ls, line_end=le, text=text, brace_fallback=True)
        else:
            ls, le, text = format_snippet_text(
                source_text, abs_s, abs_e, context_lines, line_numbers
            )
            item.update(line_start=ls, line_end=le, text=text)
        snippets.append(item)
    return _snippet_response(p, project_root, "raw", snippets, warnings)


def _read_snippet(p: Path, project_root: Optional[Path], *, symbol: str, block: str,
                  start_line: int, end_line: int, context_lines: int,
                  line_numbers: bool, max_line_chars: int = _MAX_LINE_CHARS_DEFAULT) -> str:
    """Snippet mode của read_local_file — trả JSON {mode:'snippet', snippets[]}."""
    from xml_fbograph.parsers.xml_parser import read_file_content
    from xml_controller_summary.snippet import (
        extract_script_blocks,
        find_block,
        find_js_function_in_text,
        format_snippet_lines,
        format_snippet_text,
        line_of,
        list_js_function_names,
    )

    warnings: list = []
    is_controller = _is_controller_xml(p, project_root)

    if symbol and (start_line or end_line):
        warnings.append("symbol_overrides_lines")
        start_line = 0
        end_line = 0

    # --- symbol: trích function JS ---
    if symbol:
        suffix = p.suffix.lower()
        if not is_controller and suffix in _PLAIN_SCRIPT_EXTS | {".js"}:
            source_text = read_file_content(p) or ""
            chunks = (
                extract_script_blocks(source_text)
                if suffix in _PLAIN_SCRIPT_EXTS
                else [(0, source_text)]
            )
            return _symbol_snippet_plain(
                p, project_root, source_text, chunks, symbol,
                context_lines, line_numbers, max_line_chars, warnings,
            )

        if is_controller:
            view = "flat"
            try:
                from find_entity_by_xml.facade import flat_xml

                source_text = flat_xml(str(p))
            except Exception as e:
                return _snippet_error("flat_failed", p, project_root, message=str(e))
        else:
            view = "raw"
            source_text = read_file_content(p) or ""

        matches = find_js_function_in_text(source_text, symbol)
        if not matches:
            return _snippet_error(
                "symbol_not_found",
                p,
                project_root,
                symbol=symbol,
                available_functions=list_js_function_names(source_text),
            )

        origin = "file" if view == "raw" else _snippet_origin(p, symbol)
        if origin != "file":
            warnings.append(
                "symbol nằm trong entity/include — số dòng là của flat view; "
                "xem get_xml_entities(mode='path') để biết file vật lý, "
                "không str_replace theo số dòng này."
            )

        snippets = []
        for m in matches:
            ls, le, text = format_snippet_text(
                source_text, m.start, m.end, context_lines, line_numbers
            )
            snippets.append(
                {
                    "kind": "js_function",
                    "name": m.name,
                    "line_start": ls,
                    "line_end": le,
                    "origin": origin,
                    "text": text,
                }
            )
        return _snippet_response(p, project_root, view, snippets, warnings)

    # --- block: action:<id> / command:<event> / field:<name> / query:<n> ---
    if block:
        if not is_controller:
            return _snippet_error(
                "block_not_supported_for_plain_file",
                p,
                project_root,
                message="block chi ho tro .xml truc thuoc Dir/Grid/Filter; dung start_line/end_line hoac symbol cho file khac",
            )
        try:
            from find_entity_by_xml.facade import flat_xml
            from xml_controller_summary.extract import extract_controller_blocks

            flat = flat_xml(str(p))
        except Exception as e:
            return _snippet_error("flat_failed", p, project_root, message=str(e))

        blocks = extract_controller_blocks(flat)
        matches, available = find_block(blocks, block)
        if not matches:
            return _snippet_error(
                "block_not_found",
                p,
                project_root,
                block=block,
                available=available,
            )

        origin = "file" if block.split(":", 1)[-1] in (read_file_content(p) or "") else "entity"
        if origin != "file":
            warnings.append(
                "block nằm trong entity/include — số dòng là của flat view; "
                "xem get_xml_entities(mode='path') để biết file vật lý."
            )

        snippets = []
        for m in matches:
            raw_block = m.raw or ""
            start_pos = flat.find(raw_block) if raw_block else -1
            if raw_block and start_pos >= 0:
                ls, le, text = format_snippet_text(
                    flat, start_pos, start_pos + len(raw_block), context_lines, line_numbers
                )
            else:
                ls, le, text = m.line, m.line, raw_block
            snippets.append(
                {
                    "kind": m.kind,
                    "name": m.name,
                    "line_start": ls,
                    "line_end": le,
                    "origin": origin,
                    "text": text,
                }
            )
        return _snippet_response(p, project_root, "flat", snippets, warnings)

    # --- lines: cắt khoảng dòng trên raw ---
    if start_line > 0 and end_line > 0 and start_line > end_line:
        return _snippet_error(
            "invalid_range",
            p,
            project_root,
            start_line=start_line,
            end_line=end_line,
            message=f"start_line ({start_line}) > end_line ({end_line})",
        )
    raw_text = read_file_content(p) or ""
    total_lines = len(raw_text.split("\n")) if raw_text else 0
    s = start_line if start_line and start_line > 0 else 1
    e = end_line if end_line and end_line > 0 else total_lines
    if total_lines == 0 or s > total_lines:
        return _snippet_error(
            "line_out_of_range",
            p,
            project_root,
            start_line=start_line,
            end_line=end_line,
            total_lines=total_lines,
        )
    if e > total_lines:
        e = total_lines
    if e < s:
        e = s
    ls, le, text = format_snippet_lines(raw_text, s, e, context_lines, line_numbers)
    return _snippet_response(
        p,
        project_root,
        "raw",
        [
            {
                "kind": "lines",
                "name": f"lines:{s}-{e}",
                "line_start": ls,
                "line_end": le,
                "origin": "file",
                "text": text,
            }
        ],
        warnings,
    )


def mcp_read_local_file(file_path: str, reference_file: str = "", read_option: int = 3,
                        start_line: int = 0, end_line: int = 0, symbol: str = "",
                        block: str = "", context_lines: int = 0,
                        line_numbers: bool = True, old_string: str = "",
                        new_string: str = "", edits: Optional[list] = None,
                        max_expand: int = 10,
                        max_line_chars: int = _MAX_LINE_CHARS_DEFAULT) -> str:

    try:
        if not file_path or not str(file_path).strip():
            return "Loi: file_path khong duoc de trong"

        # read_option=4 — suggest_edit (READ-ONLY: gợi ý str_replace, không ghi file)
        if read_option == 4:
            from suggest_edit import suggest_edit as _suggest_edit

            return json.dumps(
                _suggest_edit(
                    file_path=file_path,
                    reference_file=reference_file,
                    symbol=symbol or "",
                    block=block or "",
                    start_line=start_line or 0,
                    end_line=end_line or 0,
                    old_string=old_string or "",
                    new_string=new_string or "",
                    max_expand=max_expand if max_expand is not None else 10,
                    edits=edits,
                ),
                indent=2,
                ensure_ascii=False,
            )

        resolved = resolve_any_path(file_path, reference_file)
        if not resolved.ok:
            err = dict(resolved.error or {"success": False})
            err.setdefault("project_root", resolved.project_root)
            err.setdefault("resolved_via", resolved.resolved_via)
            return json.dumps(err, indent=2, ensure_ascii=False)

        # Sticky context visibility — lộ project đã resolve + cảnh báo khi context trôi
        switch_warn = project_switch_message(resolved.switched_from, resolved.project_root)

        def _ctx_header() -> str:
            lines = [
                f"Project root: {resolved.project_root or 'null'}",
                f"Resolved via: {resolved.resolved_via}",
            ]
            if switch_warn:
                lines.append(f"[WARNING] {switch_warn}")
            return "\n".join(lines) + "\n\n"

        p = Path(resolved.abs_path)
        project_root = Path(resolved.project_root).resolve() if resolved.project_root else None

        # Sandbox check: khi detect được project thì file phải nằm trong project
        if project_root is not None:
            try:
                p.resolve().relative_to(project_root)
            except ValueError:
                return f"Loi: Duong dan nam ngoai thu muc du an: {file_path}"

        if symbol or block or start_line or end_line:
            snippet_out = _read_snippet(
                p,
                project_root,
                symbol=symbol or "",
                block=block or "",
                start_line=start_line or 0,
                end_line=end_line or 0,
                context_lines=context_lines or 0,
                line_numbers=bool(line_numbers),
                max_line_chars=max_line_chars or _MAX_LINE_CHARS_DEFAULT,
            )
            try:
                data = json.loads(snippet_out)
            except Exception:
                data = None
            if isinstance(data, dict):
                data["project_root"] = resolved.project_root
                data["resolved_via"] = resolved.resolved_via
                if switch_warn:
                    warns = data.setdefault("warnings", [])
                    if isinstance(warns, list):
                        warns.append(switch_warn)
                return json.dumps(data, indent=2, ensure_ascii=False)
            return _ctx_header() + snippet_out

        if resolved.project_root:
            helper = ProjectPathHelper(
                str(Path(resolved.project_root) / "App_Data" / "Controllers" / "Dir" / "dummy.xml")
            )
        else:
            helper = ProjectPathHelper(str(p))

        if read_option == 3:
            is_valid_summary_xml = False
            if p.suffix.lower() == ".xml":
                controllers_root = helper.get_controllers_path().resolve()
                try:
                    rel = p.relative_to(controllers_root)
                except ValueError:
                    p_str = str(p).replace("\\", "/")
                    c_str = str(controllers_root).replace("\\", "/")
                    if p_str.lower().startswith(c_str.lower().rstrip("/") + "/"):
                        rel_str = p_str[len(c_str.rstrip("/")) + 1:]
                        rel = Path(rel_str)
                    else:
                        rel = None

                if rel and len(rel.parts) == 2 and rel.parts[0].lower() in {"dir", "grid", "filter"}:
                    is_valid_summary_xml = True

            if not is_valid_summary_xml:
                read_option = 1
            else:
                from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml
                from find_entity_by_xml.bridges.summary_xml_format import format_summary_xml_result
                try:
                    result = summary_xml(str(p))
                    if isinstance(result, dict):
                        result["project_root"] = resolved.project_root
                        result["resolved_via"] = resolved.resolved_via
                        if switch_warn:
                            warns = result.setdefault("warnings", [])
                            if isinstance(warns, list):
                                warns.append(switch_warn)
                    out = format_summary_xml_result(result)
                    if switch_warn:
                        out = f"[WARNING] {switch_warn}\n" + out
                    return out
                except Exception as e:
                    return f"[ERROR] read_local_file summary_xml\nLoi khi summary XML: {str(e)}"

        from xml_fbograph.parsers.xml_parser import read_file_content
        from find_entity_by_xml.facade import flat_xml

        if read_option == 2:
            try:
                content = flat_xml(str(p))
            except Exception as e:
                # Fallback to original content or display error
                return f"Loi khi doc flat XML: {str(e)}\n\nNoidung goc:\n{read_file_content(p)}"
        else:
            content = read_file_content(p)
        content = content or ""
        if len(content) > _DUMP_CAP_CHARS:
            # Full-dump cap: head + footer JSON structured — agent dùng
            # start_line/end_line hoặc symbol/block để đọc tiếp đúng vùng.
            footer = {
                "truncated": True,
                "total_chars": len(content),
                "total_lines": content.count("\n") + 1,
                "returned_chars": _DUMP_CAP_CHARS,
                "hint": (
                    "File quá dài — dùng start_line/end_line (đọc tiếp từ "
                    "dòng tiếp theo) hoặc symbol/block để lấy đúng vùng."
                ),
            }
            return (
                _ctx_header()
                + content[:_DUMP_CAP_CHARS]
                + "\n\n[TRUNCATED] "
                + json.dumps(footer, ensure_ascii=False)
            )
        return _ctx_header() + content
    except Exception as e:
        return f"Loi doc file: {str(e)}"


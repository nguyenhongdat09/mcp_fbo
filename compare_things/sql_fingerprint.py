"""SQL definition normalization, fingerprinting, and signal extraction."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional, Set, Tuple

from .text_normalize import normalize_text_lines


def strip_sql_noise_header(definition: str) -> str:
    """
    Strip leading clone_things / paste-for-edit header comments before CREATE/ALTER:
    e.g.:
    -- clone_things type=1: dbo.FastBusiness$App$GetApprovalMailList | ... paste-for-edit ...
    -- ====================
    /* ==================================== */
    """
    if not definition:
        return ""
    lines = definition.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if (
            line.startswith("-- clone_things")
            or line.startswith("-- paste-for-edit")
            or re.match(r"^--\s*[=\-_*]{3,}", line)
            or re.match(r"^/\*\s*[=\-_*]{3,}", line)
            or re.match(r"^/\*.*clone_things.*\*/$", line, re.IGNORECASE)
        ):
            idx += 1
            continue
        break

    return "\n".join(lines[idx:]).strip()



def normalize_sql_definition(
    definition: str,
    ignore_line_endings: bool = True,
    ignore_whitespace: bool = False,
) -> Tuple[str, List[str]]:
    """
    Normalize SQL definition into canonical string and list of lines.
    Strips clone_things header noise before comparison.
    """
    cleaned = strip_sql_noise_header(definition)
    lines = normalize_text_lines(
        cleaned,
        ignore_line_endings=ignore_line_endings,
        ignore_whitespace=ignore_whitespace,
    )
    canonical_text = "\n".join(lines)
    return canonical_text, lines


def compute_sql_fingerprint(canonical_text: str) -> str:
    """Compute sha256 hash string for normalized SQL definition."""
    h = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
    return f"sha256:{h}"


FBO_COLUMN_AND_KEYWORD_DENYLIST: Set[str] = {
    # System / audit columns
    "datetime0",
    "datetime2",
    "date0",
    "date2",
    "user_id0",
    "user_id2",
    "user_id3",
    "user_id4",
    "status",
    "stt_rec",
    "stt_rec0",
    "ma_dvcs",
    "u_status",
    "kieu_duyet",
    "parallel_yn",
    "deny_mail_yn",
    "xtype",
    "reset",
    # SQL keywords / clauses
    "select",
    "insert",
    "update",
    "delete",
    "output",
    "into",
    "from",
    "join",
    "set",
    "values",
    "where",
    "and",
    "or",
    "on",
    "as",
    "with",
    "group",
    "by",
    "order",
    "having",
    "exec",
    "execute",
    "declare",
    "return",
    "table",
    "distinct",
    "top",
    "null",
    "not",
    "exists",
    "case",
    "when",
    "then",
    "else",
    "end",
    "apply",
    "cross",
    "outer",
}


def strip_sql_string_literals(text: str) -> str:
    """
    Remove or blank out string literals '...' and N'...' from SQL text.
    Handles escaped quotes '' properly to avoid parsing dynamic SQL content.
    """
    if not text:
        return ""
    return re.sub(r"(?:N)?'(?:''|[^'])*'", " ", text)


def extract_sql_refs(
    text: str,
    dbs: Optional[Any] = None,
    type_cache: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, List[str]]:
    """
    Extract referenced tables, views, funcs, and procs from SQL definition.
    Queries SQL Server sys.objects (via dbs / type_cache) to accurately determine object types:
      - 'V' / VIEW -> views
      - 'U', 'S' / TABLE -> tables
      - 'FN', 'IF', 'TF', 'FS', 'FT' / FUNC -> funcs
      - 'P', 'PC' / PROC -> procs
    Returns {"views": [...], "tables": [...], "funcs": [...], "procs": [...]} (sorted unique).
    """
    views: Set[str] = set()
    tables: Set[str] = set()
    funcs: Set[str] = set()
    procs: Set[str] = set()

    # Preprocess: strip string literals (tránh dynamic SQL lọt cột như datetime2)
    cleaned_text = strip_sql_string_literals(text)

    # 1. Regex tìm sau FROM / JOIN / INTO
    from_join_into_matches = re.findall(
        r"\b(?:FROM|JOIN|INTO)\s+(?:\[?dbo\]?\.)?\[?([a-zA-Z0-9_#$]+)\]?",
        cleaned_text,
        re.IGNORECASE,
    )
    # 2. Regex riêng cho UPDATE: dừng trước SET
    update_matches = re.findall(
        r"\bUPDATE\s+(?:\[?dbo\]?\.)?\[?([a-zA-Z0-9_#$]+)\]?(?:\s+SET\b|\s+FROM\b|\s+WITH\b|\s+AS\b|\s|$)",
        cleaned_text,
        re.IGNORECASE,
    )
    # 3. Regex EXEC / EXECUTE (procs)
    exec_matches = re.findall(
        r"\b(?:EXEC|EXECUTE)\s+(?:\[?dbo\]?\.)?\[?([a-zA-Z0-9_#$]+)\]?",
        cleaned_text,
        re.IGNORECASE,
    )
    # 4. Regex function call dbo.fn(...)
    fn_matches = re.findall(
        r"\b(?:\[?dbo\]?\.)\[?([a-zA-Z0-9_#$]+)\]?\s*\(",
        cleaned_text,
        re.IGNORECASE,
    )

    def _is_valid_candidate(name: str) -> bool:
        n = name.strip().lower()
        if not n or n.startswith("#") or n.startswith("@"):
            return False
        if n in FBO_COLUMN_AND_KEYWORD_DENYLIST:
            return False
        return True

    relational_cands = {m.strip().lower() for m in from_join_into_matches if _is_valid_candidate(m)}
    relational_cands.update({m.strip().lower() for m in update_matches if _is_valid_candidate(m)})
    proc_cands = {m.strip().lower() for m in exec_matches if _is_valid_candidate(m)}
    func_cands = {m.strip().lower() for m in fn_matches if _is_valid_candidate(m)}

    # Check known approval / delegation objects phổ biến FBO
    known_views = ["vdmduyetuq", "vgndmduyetuq", "vsodmduyetuq", "vsysuserinfo", "vsysuser"]
    for kv in known_views:
        if re.search(rf"\b{re.escape(kv)}\b", cleaned_text, re.IGNORECASE):
            relational_cands.add(kv)

    known_tables = ["dmduyet", "dmuqduyet", "gndmuqduyet", "sodmuqduyet", "dmquyen", "dmxn", "dmnttduyet"]
    for kt in known_tables:
        if re.search(rf"\b{re.escape(kt)}\b", cleaned_text, re.IGNORECASE):
            relational_cands.add(kt)

    all_cands = relational_cands | proc_cands | func_cands

    # 5. Tra cứu sys.objects từ SQL Server nếu có kết nối DB
    if dbs is not None:
        uncached = [c for c in all_cands if not type_cache or c.lower() not in type_cache]
        if uncached:
            try:
                from .db_access import resolve_objects_types_from_db
                resolved = resolve_objects_types_from_db(dbs, uncached)
                if type_cache is not None:
                    type_cache.update(resolved)
                    for c in uncached:
                        if c.lower() not in type_cache:
                            type_cache[c.lower()] = {
                                "name": c,
                                "schema": "dbo",
                                "type": "",
                                "type_desc": "",
                                "category": "unknown",
                            }
                else:
                    type_cache = dict(resolved)
            except Exception:
                pass

    # 6. Phân loại theo kết quả sys.objects hoặc fallback offline
    for c in sorted(all_cands):
        info = type_cache.get(c.lower()) if type_cache else None
        cat = info.get("category") if info else None
        sch = (info.get("schema") or "dbo") if info else "dbo"
        real_name = (info.get("name") or c) if info else c
        full_name = f"{sch}.{real_name}"

        if cat == "view":
            views.add(full_name)
        elif cat == "table":
            tables.add(full_name)
        elif cat == "func":
            funcs.add(full_name)
        elif cat == "proc":
            procs.add(full_name)
        else:
            # Đối tượng không tìm thấy trong sys.objects hoặc chế độ offline không có DB
            if c in proc_cands:
                procs.add(full_name)
            elif c in func_cands:
                funcs.add(full_name)
            elif dbs is None and (c.startswith(("vdm", "vgn", "vso", "vsys")) or c in known_views):
                # Fallback offline cho unit test khi không kết nối DB
                views.add(full_name)
            else:
                tables.add(full_name)

    return {
        "views": sorted(list(views)),
        "tables": sorted(list(tables)),
        "funcs": sorted(list(funcs)),
        "procs": sorted(list(procs)),
    }


def extract_sql_signals(
    text_source: str,
    text_target: str,
    seed_keywords: List[str] = None,
    refs_source: Optional[Dict[str, List[str]]] = None,
    refs_target: Optional[Dict[str, List[str]]] = None,
) -> List[str]:
    """
    Extract high-level business signals between source and target routines.
    Emits signals for BOTH source and target sides.
    Only emits refs_match_body_diff when full refs (views + tables) are identical.
    """
    signals: List[str] = []
    src_lower = text_source.lower()
    tgt_lower = text_target.lower()

    # 1. Source signals
    src_has_view_uq = bool(re.search(r"\b(vdmduyetuq|vgndmduyetuq|vsodmduyetuq)\b", src_lower))
    if src_has_view_uq:
        signals.append("source_refs_vdmduyetuq")
    if re.search(r"\bdmduyet\b", src_lower):
        signals.append("source_refs_dmduyet")
    if re.search(r"\b(dmuqduyet|gndmuqduyet|sodmuqduyet)\b", src_lower):
        signals.append("source_refs_dmuqduyet")

    # 2. Target signals
    tgt_has_view_uq = bool(re.search(r"\b(vdmduyetuq|vgndmduyetuq|vsodmduyetuq)\b", tgt_lower))
    if tgt_has_view_uq:
        signals.append("target_refs_vdmduyetuq")
    if re.search(r"\bdmduyet\b", tgt_lower):
        signals.append("target_refs_dmduyet")
    if re.search(r"\b(dmuqduyet|gndmuqduyet|sodmuqduyet)\b", tgt_lower):
        signals.append("target_refs_dmuqduyet")

    # 3. Correlation signals between source & target
    if (src_has_view_uq and re.search(r"\bdmduyet\b", tgt_lower)) or (
        tgt_has_view_uq and re.search(r"\bdmduyet\b", src_lower)
    ):
        signals.append("delegation_view_mismatch")

    # refs_match_body_diff: CHỈ emit khi refs của 2 phía bằng nhau
    r_src = refs_source if refs_source is not None else extract_sql_refs(text_source)
    r_tgt = refs_target if refs_target is not None else extract_sql_refs(text_target)

    same_views = set(r_src.get("views", [])) == set(r_tgt.get("views", []))
    same_tables = set(r_src.get("tables", [])) == set(r_tgt.get("tables", []))
    same_funcs = set(r_src.get("funcs", [])) == set(r_tgt.get("funcs", []))
    same_procs = set(r_src.get("procs", [])) == set(r_tgt.get("procs", []))
    if same_views and same_tables and same_funcs and same_procs:
        signals.append("refs_match_body_diff")

    # Check for seed keywords with exact word boundary
    if seed_keywords:
        for kw in seed_keywords:
            kw_clean = kw.strip().lower()
            if not kw_clean:
                continue
            pattern = rf"\b{re.escape(kw_clean)}\b"
            in_src = bool(re.search(pattern, src_lower))
            in_tgt = bool(re.search(pattern, tgt_lower))
            if in_src and not in_tgt:
                signals.append(f"source_only_refs_{kw_clean}")
            elif in_tgt and not in_src:
                signals.append(f"target_only_refs_{kw_clean}")

    return signals


def extract_hunk_signals(preview_lines: List[str]) -> List[str]:
    """Extract signals specifically from a hunk's preview lines."""
    signals: List[str] = []
    joined = " ".join(preview_lines).lower()

    if ("dmduyet" in joined) and ("vdmduyetuq" in joined):
        signals.append("dmduyet_vs_vdmduyetuq")

    return signals

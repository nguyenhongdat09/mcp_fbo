"""Check legacy cho file controller XML FastBusiness (Dir/Filter/Grid).

Port từ CheckLegacyWorker.js + CheckLegacyFields/Structure/Grid/Utils/Message.js
trong extension fbo-autocomplete.

Pipeline: expand &entity; trong <fields>/<views> -> chạy rules -> diagnostics
[{line, severity, message}].
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

SEV_ERROR = "error"
SEV_WARNING = "warning"
SEV_INFORMATION = "information"
SEV_HINT = "hint"


# ---------------------------------------------------------------------------
# Helpers (port CheckLegacyUtils.js)
# ---------------------------------------------------------------------------


def _escape_re(s: str) -> str:
    return re.sub(r"[.*+?^${}()|[\]\\]", r"\\\g<0>", s)


def _make_line_index(content: str):
    """Trả về hàm map char-index -> số dòng (1-based)."""
    starts = [0]
    for i, ch in enumerate(content):
        if ch == "\n":
            starts.append(i + 1)

    def line_at(idx: int) -> int:
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) >> 1
            if starts[mid] <= idx:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    return line_at


def _set_diag(line: int, message: str, line_count: int, severity: str = SEV_ERROR) -> dict:
    _line = max(1, line)
    if _line > line_count:
        _line = line_count
    return {"line": _line, "severity": severity, "message": message}


def get_field_tags(content: str) -> List[Dict[str, Any]]:
    """Tất cả <field> trong các block <fields> (kể cả self-closing)."""
    results = []
    fields_block_re = re.compile(r"<fields>([\s\S]*?)</fields>", re.IGNORECASE)
    field_re = re.compile(r"<field\b[^>]*?(?:/>|>[\s\S]*?</field>)")
    for bm in fields_block_re.finditer(content):
        block, base = bm.group(0), bm.start()
        for fm in field_re.finditer(block):
            m = re.match(r"^<field\b[^>]*?(?:/)?>", fm.group(0))
            open_tag = m.group(0) if m else fm.group(0)
            name_m = re.search(r'\bname\s*=\s*"([^"]+)"', open_tag)
            results.append(
                {
                    "name": name_m.group(1) if name_m else "",
                    "tag": open_tag,
                    "block": fm.group(0),
                    "index": base + fm.start(),
                }
            )
    return results


_NUMERIC_FIELD_TYPES = re.compile(r"^(decimal|int|int16|int32|int64)$", re.IGNORECASE)
_ENTITY_LEFT_RE = re.compile(r"&(?!gt;|lt;|amp;|quot;|apos;)[\w.]+;")


def _check_numeric_items_style(fields, line_count: int, diagnostics: list) -> None:
    """Field numeric (Decimal/Int*) phải có <items style="Numeric">."""
    for f in fields:
        block = str(f.get("block") or "")
        m = re.match(r"^<field\b[^>]*>", block)
        open_tag = m.group(0) if m else ""
        type_m = re.search(r'\btype\s*=\s*["\']([^"\']+)["\']', open_tag, re.IGNORECASE)
        if not type_m or not _NUMERIC_FIELD_TYPES.match(type_m.group(1).strip()):
            continue

        if not re.search(r"/>\s*$", open_tag):
            end_idx = block.find("</field>")
            body = block if end_idx == -1 else block[:end_idx]
            if re.search(r'<items\b[^>]*\bstyle\s*=\s*["\']\s*Numeric\s*["\']', body, re.IGNORECASE):
                continue
            if _ENTITY_LEFT_RE.search(body):
                continue
        diagnostics.append(
            _set_diag(
                f.get("line") or 1,
                f'Field "{f["name"]}" type="{type_m.group(1)}" là numeric nhưng thiếu <items style="Numeric"></items>',
                line_count,
            )
        )


# ---------------------------------------------------------------------------
# Entity expand (port CheckLegacyWorker.runCheck)
# ---------------------------------------------------------------------------

_ENT_REF_RE = re.compile(r"&[^;\s]+;")
_PREDEFINED_ENT_RE = re.compile(r"^&(?:gt|lt|amp|quot|apos|#\d+);$")


def _replace_entity(content: str, entity_contents: Dict[str, str]) -> List[Dict[str, str]]:
    """Tìm &entity; trong content, map sang nội dung đã resolve."""
    entities = list(dict.fromkeys(_ENT_REF_RE.findall(content)))
    parsed = [
        {"entity": e, "entity_variable": e.strip("&;")}
        for e in entities
        if not _PREDEFINED_ENT_RE.match(e)
    ]
    return [
        {"entity": item["entity"], "content": entity_contents.get(item["entity_variable"], "")}
        for item in parsed
    ]


def expand_fields_views(content: str, entity_contents: Dict[str, str]) -> str:
    """Expand &entity; chỉ trong <fields>/<views>, tối đa 5 vòng (giống worker)."""
    fields_block_re = re.compile(r"<fields>([\s\S]*?)</fields>", re.IGNORECASE)
    views_block_re = re.compile(r"<views>[\s\S]*?</views>", re.IGNORECASE)

    iterations = 0
    has_replaced = True
    while has_replaced and iterations < 5:
        has_replaced = False
        iterations += 1
        target_sections = "".join(m.group(0) + "\n" for m in fields_block_re.finditer(content))
        target_sections += "".join(m.group(0) + "\n" for m in views_block_re.finditer(content))
        if not target_sections:
            break

        ent_content = _replace_entity(target_sections, entity_contents)
        if not ent_content:
            break

        entity_map = {
            e["entity"]: e["content"].replace("\r\n", " ").replace("\n", " ")
            for e in ent_content
            if e["content"] != ""
        }
        if not entity_map:
            break

        entity_re = re.compile("|".join(_escape_re(k) for k in entity_map))
        next_content = entity_re.sub(lambda m: entity_map.get(m.group(0), m.group(0)), content)
        if next_content != content:
            content = next_content
            has_replaced = True
    return content


# ---------------------------------------------------------------------------
# Field extractors (port CheckLegacyFields.js)
# ---------------------------------------------------------------------------


def get_field_on_fields(content: str) -> List[Dict[str, Any]]:
    """<field name="x">...</field> trong block <fields> ĐẦU TIÊN (bỏ filterSource="Vacant")."""
    fields_re = re.compile(r"<fields>([\s\S]*?)</fields>")
    fields_match = fields_re.search(content)
    if not fields_match:
        return []
    xml_fields = fields_match.group(0)
    field_re = re.compile(r'<field[^>]*name="([^"]+)"[^>]*>[\s\S]*?</field>')

    base_line = 1 + content[: fields_match.start()].count("\n")
    results = []
    last_idx = 0
    current_line = base_line
    for match in field_re.finditer(xml_fields):
        value_t = match.group(0)
        if 'filterSource="Vacant"' in value_t:
            continue
        current_line += xml_fields[last_idx : match.start()].count("\n")
        last_idx = match.start()
        results.append({"key": match.group(1), "value": value_t, "line": current_line})
    return results


def get_field_on_view(content: str) -> List[Dict[str, Any]]:
    """<item value="pattern: [f1] [f2]"> trên toàn file."""
    item_re = re.compile(r'<item value="([^"]+):\s*([^"]+)"')
    results = []
    last_idx = 0
    current_line = 1
    for match in item_re.finditer(content):
        key = re.sub(r"[0-]", "", match.group(1).strip())
        fields = [
            re.sub(r"\[|\]", "", f).strip()
            for f in re.findall(r"\[([^\]]+)\]", match.group(2))
        ]
        current_line += content[last_idx : match.start()].count("\n")
        last_idx = match.start()
        results.append({"key": key, "fields": fields, "line": current_line})
    return results


# ---------------------------------------------------------------------------
# Rules (port CheckLegacyFields/Structure/Grid)
# ---------------------------------------------------------------------------


def check_legacy_item(
    field_item,
    fields_declare,
    diagnostics,
    line_count: int,
    has_unresolved_view_entities: bool,
    has_unresolved_fields_entities: bool,
    field_not_on_view: bool = False,
) -> None:
    # thừa/thiếu phần tử 1
    error_item = [item for item in field_item if len(item["key"]) != len(item["fields"])]
    for item in error_item:
        line = item["line"] or 1
        if len(item["key"]) > len(item["fields"]):
            msg = (
                f'Lỗi "thừa" phần tử 1: \n - Số phần tử 1 là "{len(item["key"])}" '
                f'\n - Số field là "{len(item["fields"])}" '
            )
        else:
            msg = (
                f'Lỗi "thiếu" phần tử 1: \n - Số phần tử 1 là "{len(item["key"])}" '
                f'\n - Số field là "{len(item["fields"])}"'
            )
        diagnostics.append(_set_diag(line, msg, line_count))

    field_distinct = [
        {"fields": list(dict.fromkeys(item["fields"])), "line": item["line"]}
        for item in field_item
    ]

    _check_numeric_items_style(
        [{"name": f["key"], "block": f["value"], "line": f["line"]} for f in fields_declare],
        line_count,
        diagnostics,
    )

    if not has_unresolved_fields_entities:
        field_decl_set = {f["key"] for f in fields_declare}
        for item in field_distinct:
            for field in item["fields"]:
                if field not in field_decl_set:
                    diagnostics.append(
                        _set_diag(
                            item["line"] or 1,
                            f"Field: {field} chưa khai báo ở Fields.",
                            line_count,
                        )
                    )

    if not has_unresolved_view_entities and field_not_on_view:
        all_view_fields = {f for item in field_distinct for f in item["fields"]}
        for item_field in fields_declare:
            if item_field["key"] not in all_view_fields:
                diagnostics.append(
                    _set_diag(
                        item_field["line"] or 1,
                        f"Chưa khai báo Field: {item_field['key']} xuống thẻ view",
                        line_count,
                    )
                )


def check_structure_rules(content: str, diagnostics: list, line_count: int, include_view_rules: bool) -> None:
    line_at = _make_line_index(content)
    fields = get_field_tags(content)

    # ---- Khóa chính: isPrimaryKey phải khớp code="..." ----
    pk_fields = [f for f in fields if re.search(r'\bisPrimaryKey\s*=\s*"true"', f["tag"], re.IGNORECASE)]
    root_m = re.search(r"<(dir|grid|filter)\b[^>]*>", content, re.IGNORECASE)
    code_m = re.search(r'\bcode\s*=\s*"([^"]*)"', root_m.group(0), re.IGNORECASE) if root_m else None
    if code_m and not re.search(r"[&;]", code_m.group(1)):
        code_cols = [c.strip() for c in code_m.group(1).split(",") if c.strip()]
        field_names = {f["name"] for f in fields}
        pk_names = {f["name"] for f in pk_fields}
        for c in code_cols:
            if c not in pk_names and c in field_names:
                f = next(x for x in fields if x["name"] == c)
                diagnostics.append(
                    _set_diag(
                        line_at(f["index"]),
                        f'Cột "{c}" nằm trong code="{code_m.group(1)}" nhưng field chưa khai báo isPrimaryKey="true"',
                        line_count,
                    )
                )
    elif pk_fields and not code_m:
        diagnostics.append(
            _set_diag(
                1,
                f'Có {len(pk_fields)} field isPrimaryKey="true" nhưng thẻ gốc thiếu code="..."',
                line_count,
                SEV_WARNING,
            )
        )

    # ---- categoryIndex phải khớp <category index="N"> ----
    cat_blocks = re.findall(r"<categories>[\s\S]*?</categories>", content, re.IGNORECASE)
    has_unresolved_cat = any(_ENTITY_LEFT_RE.search(b) for b in cat_blocks)
    cat_indexes = {
        m.group(1)
        for m in re.finditer(r'<category\b[^>]*?\bindex\s*=\s*"(-?\d+)"', content, re.IGNORECASE)
    }
    if not has_unresolved_cat:
        for f in fields:
            ci = re.search(r'\bcategoryIndex\s*=\s*"(-?\d+)"', f["tag"], re.IGNORECASE)
            if ci and ci.group(1) not in cat_indexes:
                diagnostics.append(
                    _set_diag(
                        line_at(f["index"]),
                        f'Field "{f["name"]}" categoryIndex="{ci.group(1)}" không khớp <category index> nào trong view',
                        line_count,
                    )
                )

    if not include_view_rules:
        return

    # ---- anchor / split trên <view> và pattern từng <item> ----
    view_re = re.compile(r"<view\b[^>]*>[\s\S]*?</view>", re.IGNORECASE)
    item_re = re.compile(r'<item\b[^>]*?\bvalue\s*=\s*"([^"]*)"[^>]*>')
    for vm in view_re.finditer(content):
        body = vm.group(0)
        m = re.match(r"^<view\b[^>]*>", body)
        view_tag = m.group(0) if m else ""
        view_line = line_at(vm.start())

        item_vals = [
            {"v": im.group(1), "index": vm.start() + im.start()} for im in item_re.finditer(body)
        ]
        master_cols = 0
        for it in item_vals:
            if ":" not in it["v"] and re.match(r"^[\d,\s]+$", it["v"].strip()):
                master_cols = len([s for s in it["v"].split(",") if s.strip() != ""])
                break

        if master_cols > 0:
            anchor_m = re.search(r'\banchor\s*=\s*"(-?\d+)"', view_tag)
            if anchor_m:
                a = int(anchor_m.group(1))
                if a < 1 or a > master_cols:
                    diagnostics.append(
                        _set_diag(view_line, f'<view> anchor="{a}" vượt số cột master ({master_cols})', line_count)
                    )
            split_m = re.search(r'\bsplit\s*=\s*"(-?\d+)"', view_tag)
            if split_m:
                s = int(split_m.group(1))
                if s < 1 or s > master_cols:
                    diagnostics.append(
                        _set_diag(view_line, f'<view> split="{s}" vượt số cột master ({master_cols})', line_count)
                    )

        for it in item_vals:
            if ":" not in it["v"]:
                continue
            pattern = it["v"].split(":")[0].strip()
            if not re.match(r"^[01-]+$", pattern):
                continue
            item_line = line_at(it["index"])
            if master_cols > 0 and len(pattern) > master_cols:
                diagnostics.append(
                    _set_diag(
                        item_line,
                        f'Pattern "{pattern}" dài {len(pattern)} vượt số cột master ({master_cols})',
                        line_count,
                    )
                )
            if re.search(r"110{3,}11", pattern):
                diagnostics.append(
                    _set_diag(
                        item_line,
                        f'Pattern "{pattern}" dùng chuỗi "0" dài làm gap giữa 2 nhóm field — nên dùng "-"',
                        line_count,
                        SEV_WARNING,
                    )
                )

    # ---- anchor / split trên <category columns="..."> ----
    for cm in re.finditer(r"<category\b[^>]*>", content, re.IGNORECASE):
        tag = cm.group(0)
        cols_m = re.search(r'\bcolumns\s*=\s*"([^"]*)"', tag)
        if not cols_m or not re.match(r"^[\d,\s]+$", cols_m.group(1).strip()):
            continue
        n = len([s for s in cols_m.group(1).split(",") if s.strip() != ""])
        a_m = re.search(r'\banchor\s*=\s*"(-?\d+)"', tag)
        if a_m:
            a = int(a_m.group(1))
            if a < 1 or a > n:
                diagnostics.append(
                    _set_diag(line_at(cm.start()), f'<category> anchor="{a}" vượt số cột ({n})', line_count)
                )
        s_m = re.search(r'\bsplit\s*=\s*"(-?\d+)"', tag)
        if s_m:
            s = int(s_m.group(1))
            if s < 1 or s > n:
                diagnostics.append(
                    _set_diag(line_at(cm.start()), f'<category> split="{s}" vượt số cột ({n})', line_count)
                )


def check_grid_rules(content: str, raw_content: str, diagnostics: list, line_count: int) -> None:
    line_at = _make_line_index(content)
    line_at_raw = _make_line_index(raw_content)

    check_structure_rules(content, diagnostics, line_count, include_view_rules=False)

    fields = get_field_tags(content)
    _check_numeric_items_style(
        [{"name": f["name"], "block": f["block"], "line": line_at(f["index"])} for f in fields],
        line_count,
        diagnostics,
    )

    has_allow_filter = False
    for f in fields:
        af = re.search(r'\ballowFilter\s*=\s*"([^"]*)"', f["tag"], re.IGNORECASE)
        if not af:
            continue
        v = af.group(1).strip().lower()
        if v in ("", "false", "0"):
            continue
        has_allow_filter = True
        qm = re.search(r"<query\b[^>]*>([\s\S]*?)</query>", f["block"])
        if not qm or qm.group(1).strip() == "":
            diagnostics.append(
                _set_diag(
                    line_at(f["index"]),
                    f'Field "{f["name"]}" bật allowFilter nhưng thiếu <query>&InsertCommandFilter;</query>',
                    line_count,
                )
            )
        if f["name"] == "tag" or re.search(r'\bhidden\s*=\s*"true"', f["tag"], re.IGNORECASE):
            diagnostics.append(
                _set_diag(
                    line_at(f["index"]),
                    f'Field "{f["name"]}" là cột tag/hidden — không nên gắn allowFilter',
                    line_count,
                    SEV_WARNING,
                )
            )

    if has_allow_filter:
        dq = re.search(
            r'<query\b[^>]*?\bevent\s*=\s*"Declare"[^>]*>[\s\S]*?</query>', raw_content, re.IGNORECASE
        )
        if not dq:
            diagnostics.append(
                _set_diag(
                    1,
                    'Grid dùng allowFilter nhưng thiếu <query event="Declare">&DeclareCommandFilter;</query> (tạo #filter)',
                    line_count,
                )
            )
        elif not re.search(r"DeclareCommandFilter", dq.group(0), re.IGNORECASE):
            diagnostics.append(
                _set_diag(
                    line_at_raw(dq.start()),
                    '<query event="Declare"> không gọi &DeclareCommandFilter; — dòng lọc sẽ không hoạt động',
                    line_count,
                    SEV_WARNING,
                )
            )
        m = re.search(r"<!DOCTYPE[\s\S]*?\]>", raw_content, re.IGNORECASE)
        doctype = m.group(0) if m else ""
        if not re.search(r"Filter\.\w*ent", doctype, re.IGNORECASE):
            diagnostics.append(
                _set_diag(
                    1,
                    "Grid dùng allowFilter nhưng DOCTYPE chưa include Filter.ent (entity &GridVoucherAllowFilter;)",
                    line_count,
                    SEV_WARNING,
                )
            )


# ---------------------------------------------------------------------------
# Options/Message.xml duplicate check (port CheckLagacyMessage.js)
# ---------------------------------------------------------------------------


def check_message_duplicates(content: str) -> List[dict]:
    diagnostics = []
    lines = content.split("\n")
    line_count = len(lines)
    inside_fields = False
    seen: dict[str, int] = {}
    for idx, line in enumerate(lines):
        if "<fields" in line:
            inside_fields = True
            seen = {}
        if inside_fields:
            m = re.search(r'<field\s+name="([^"]+)"', line)
            if m:
                name = m.group(1)
                if name in seen:
                    diagnostics.append(
                        _set_diag(idx + 1, f'Duplicate field name "{name}"', line_count)
                    )
                else:
                    seen[name] = idx
        if "</fields>" in line:
            inside_fields = False
    return diagnostics


# ---------------------------------------------------------------------------
# Entry point (port CheckLegacyWorker.runCheck)
# ---------------------------------------------------------------------------


def classify_path(file_path: str) -> str:
    """'grid' | 'dir_filter' | 'other' theo thư mục chứa file (giống extension)."""
    from pathlib import PurePath

    dir_path = str(PurePath(file_path).parent).replace("\\", "/").lower()
    if "controllers/grid" in dir_path:
        return "grid"
    if "controllers/dir" in dir_path or "controllers/filter" in dir_path:
        return "dir_filter"
    return "other"


def check_legacy(file_path: str, content: str, entity_contents: Dict[str, str]) -> List[dict]:
    """Chạy check legacy full trên content (đã đọc từ file, có thể đã format).

    Trả list diagnostic [{line, severity, message}]. isGrid quyết theo path.
    """
    kind = classify_path(file_path)
    if kind == "other":
        # Options/Message.xml vẫn có rule riêng (duplicate field)
        norm = file_path.replace("\\", "/")
        if norm.lower().endswith("/options/message.xml"):
            return check_message_duplicates(content)
        return []

    expanded = expand_fields_views(content, entity_contents)
    line_count = len(expanded.split("\n"))
    diagnostics: List[dict] = []

    if kind == "grid":
        check_grid_rules(expanded, content, diagnostics, line_count)
    else:
        field_item = get_field_on_view(expanded)
        fields_declare = get_field_on_fields(expanded)
        views_content = "\n".join(
            re.findall(r"<views>[\s\S]*?</views>", expanded, re.IGNORECASE)
        )
        fields_content = "\n".join(
            re.findall(r"<fields>[\s\S]*?</fields>", expanded, re.IGNORECASE)
        )
        has_unresolved_view = bool(_ENTITY_LEFT_RE.search(views_content))
        has_unresolved_fields = bool(_ENTITY_LEFT_RE.search(fields_content))
        check_legacy_item(
            field_item,
            fields_declare,
            diagnostics,
            line_count,
            has_unresolved_view,
            has_unresolved_fields,
            field_not_on_view=True,
        )
        check_structure_rules(expanded, diagnostics, line_count, include_view_rules=True)

    return diagnostics

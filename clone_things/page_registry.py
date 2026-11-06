"""Khai báo trang của program mới (SP30+): dòng ``<page .../>``.

Bản cũ mỗi trang là 1 file ``Main/<id>.aspx``; bản mới là 1 dòng ``<page id=".."
controller=".." template="Page.0xx"/>``. Dòng ``<page>`` nằm ở 2 nơi:

- ``App_Data/Metadata/Page*.xml`` — file được entity-include vào
  ``PageMetadata.xml``, thường gom theo template (``Page.001``..``Page.022``,
  ``Page.Flow``, ``Page.Query``).
- ``App_Data/PageMetadata.xml`` — page inline: named templates (Item,
  Customer...), Page.023/024 (không có file riêng) và block
  ``<!--Customize--> ... <!--End Customize-->`` dành cho dòng thêm tay/tool.

``template`` = khuôn HTML ở ``Metadata/Fragments/<template>.xml``. Menu
(``wcommand.link``) vẫn là ``<id>.aspx``.

Mọi dòng ``<page>`` do tool thêm đều ghi vào block ``<!--Customize-->`` của
``PageMetadata.xml`` (tự tạo block trước ``</pages>`` nếu chưa có) — không đụng
file ``Page.0xx.xml`` lớn của hệ thống.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_BOM = b"\xef\xbb\xbf"
_RE_PAGE_LINE = re.compile(r"^\s*<page\s", re.IGNORECASE)
_RE_ID = re.compile(r'\bid\s*=\s*"([^"]*)"')
_RE_TEMPLATE = re.compile(r'\btemplate\s*=\s*"([^"]*)"')
_RE_CTRL_ATTR = re.compile(r'\bcontroller\s*=\s*"([^"]*)"', re.IGNORECASE)
_RE_FILE = re.compile(r"^Page.*\.xml$", re.IGNORECASE)
_SIMPLE_TEMPLATE = "Page.001"
# Khuôn theo control mà trang .aspx bản cũ nạp bằng LoadControl (khảo sát 1.626 trang
# TA_VN đối chiếu khuôn SP30): Chart.ascx -> Page.004, TreeView.ascx -> Page.005.
_CONTROL_TEMPLATE = {"chart.ascx": "Page.004", "treeview.ascx": "Page.005"}

_PAGE_META = Path("App_Data") / "PageMetadata.xml"
_RE_CUSTOMIZE = re.compile(r"<!--\s*Customize\s*-->", re.IGNORECASE)
_RE_END_CUSTOMIZE = re.compile(r"<!--\s*End\s+Customize\s*-->", re.IGNORECASE)
_RE_END_SHORT = re.compile(r"<!--\s*End\s*-->", re.IGNORECASE)
_RE_PAGES_CLOSE = re.compile(r"</\s*pages\s*>", re.IGNORECASE)
# Entity khai trong DOCTYPE của PageMetadata.xml (<!ENTITY X SYSTEM "path">).
# Flat entity = mọi file chứa dòng <page>, kể cả file tên lệch Page*.xml.
_RE_ENTITY_DECL = re.compile(
    r'<!ENTITY\s+\S+\s+SYSTEM\s+"([^"]+)"', re.IGNORECASE
)


def metadata_dir(root: Path) -> Path:
    return Path(root) / "App_Data" / "Metadata"


def page_metadata_path(root: Path) -> Path:
    return Path(root) / _PAGE_META


def _page_files(root: Path) -> list[tuple[str, Path]]:
    """(display_name, path) của mọi file chứa dòng ``<page>``:
    ``Metadata/Page*.xml`` + mọi file ``PageMetadata.xml`` khai entity
    (``<!ENTITY X SYSTEM "..">`` — flat entity ra) + chính
    ``PageMetadata.xml`` (page inline: named templates, Page.023/024,
    block Customize)."""
    out: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    d = metadata_dir(root)
    if d.is_dir():
        try:
            for e in sorted(os.scandir(d), key=lambda e: e.name):
                if e.is_file() and _RE_FILE.match(e.name):
                    p = Path(e.path)
                    out.append((e.name, p))
                    seen.add(p.resolve())
        except Exception:
            pass
    pm = page_metadata_path(root)
    if pm.is_file():
        try:
            text = pm.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            text = ""
        root_res = Path(root).resolve()
        for m in _RE_ENTITY_DECL.finditer(text):
            ref = m.group(1).strip().replace("\\", "/")
            cand = (pm.parent / ref).resolve()
            try:
                rel = cand.relative_to(root_res)
            except Exception:
                continue
            if not cand.is_file() or cand in seen:
                continue
            seen.add(cand)
            name = (
                cand.name
                if cand.parent == metadata_dir(root).resolve()
                else f"../{rel.as_posix()}"
            )
            out.append((name, cand))
        out.append(("../PageMetadata.xml", pm))
    return out


def _read_lines(path: str | Path) -> list[str]:
    return Path(path).read_text(encoding="utf-8-sig", errors="ignore").splitlines()


def _parse_page_line(file: str, no: int, line: str) -> dict[str, Any] | None:
    m_ctrl = _RE_CTRL_ATTR.search(line)
    m_id = _RE_ID.search(line)
    m_tpl = _RE_TEMPLATE.search(line)
    return {
        "file": file,
        "line_no": no,
        "id": m_id.group(1) if m_id else "",
        "controller": m_ctrl.group(1) if m_ctrl else "",
        "template": m_tpl.group(1) if m_tpl else "",
        "text": line,
    }


def find_page_entries(root: Path, ctrl: str) -> list[dict[str, Any]]:
    """Mọi dòng ``<page controller="<ctrl>">`` trong Metadata/Page*.xml và
    App_Data/PageMetadata.xml (page inline)."""
    pat = re.compile(r'controller\s*=\s*"' + re.escape(ctrl) + r'"', re.IGNORECASE)
    out: list[dict[str, Any]] = []
    for fname, fpath in _page_files(root):
        try:
            lines = _read_lines(fpath)
        except Exception:
            continue
        for no, line in enumerate(lines, 1):
            if not _RE_PAGE_LINE.match(line) or not pat.search(line):
                continue
            entry = _parse_page_line(fname, no, line)
            if entry:
                out.append(entry)
    return out


def all_page_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for _fname, fpath in _page_files(root):
        try:
            for line in _read_lines(fpath):
                if _RE_PAGE_LINE.match(line):
                    m = _RE_ID.search(line)
                    if m:
                        ids.add(m.group(1).lower())
        except Exception:
            continue
    return ids


def find_entry_by_id(root: Path, page_id: str) -> dict[str, Any] | None:
    """Dòng ``<page id="...">`` đầu tiên có id trùng (bất kể hoa thường) —
    để báo agent chỗ đang trùng khi cần nhắn user."""
    want = page_id.lower()
    for fname, fpath in _page_files(root):
        try:
            for no, line in enumerate(_read_lines(fpath)):
                if not _RE_PAGE_LINE.match(line):
                    continue
                m = _RE_ID.search(line)
                if m and m.group(1).lower() == want:
                    return _parse_page_line(fname, no, line)
        except Exception:
            continue
    return None


def _id_exists_entry(info: dict[str, Any], ex: dict[str, Any] | None) -> dict:
    loc = f'{ex["file"]}:{ex["line_no"]}' if ex else "?"
    return {
        **info,
        "status": "id_exists",
        "existing": loc,
        "message": (
            f'id "{info.get("id")}" đã tồn tại ở {loc} — báo user page id '
            "bị trùng, đổi id khác hoặc xóa dòng cũ"
        ),
    }


def _xml_attr(val: str) -> str:
    return (
        val.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# Thuộc tính ngoài v/e mà một số khuôn Fragments đòi (placeholder ``@@tinyv`` ...).
# Thiếu thì tiêu đề trang hiện nguyên chữ ``@@tinyv`` và trang trắng.
_TEMPLATE_ATTR_SOURCE = {"tinyv": "v", "tinye": "e"}
_RE_PLACEHOLDER = re.compile(r"@@(\w+)")


def template_needs(root: Path, template: str) -> set[str]:
    """Các thuộc tính (``tinyv``/``tinye``) mà khuôn ``Fragments/<template>.xml`` đòi
    trên dòng ``<page>`` — đọc từ placeholder ``@@name`` trong khuôn."""
    frag = metadata_dir(root) / "Fragments" / f"{template}.xml"
    try:
        text = frag.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return set()
    return {m for m in _RE_PLACEHOLDER.findall(text) if m in _TEMPLATE_ATTR_SOURCE}


def ensure_template_attrs(line: str, needs: set[str]) -> str:
    """Bổ sung các thuộc tính khuôn đòi mà dòng ``<page>`` còn thiếu (``tinyv`` lấy
    từ ``v``, ``tinye`` lấy từ ``e``), đặt ngay sau ``e=``."""
    for attr in sorted(needs):
        if re.search(r"\b" + attr + r'\s*=\s*"', line):
            continue
        m_src = re.search(
            r"\b" + _TEMPLATE_ATTR_SOURCE[attr] + r'\s*=\s*"([^"]*)"', line
        )
        if not m_src:
            continue
        m_e = re.search(r'\be\s*=\s*"[^"]*"', line)
        pos = m_e.end() if m_e else line.index("controller")
        line = line[:pos] + f' {attr}="{m_src.group(1)}"' + line[pos:]
    return line


def build_page_line(
    page_id: str,
    controller: str,
    v: str,
    e: str,
    read_only: bool,
    filter_mode: bool,
    template: str,
    needs: set[str] | None = None,
) -> str:
    """Dòng ``<page>`` theo thứ tự thuộc tính của file chuẩn."""
    parts = [
        f'id="{page_id}"',
        f'v="{_xml_attr(v)}"',
        f'e="{_xml_attr(e)}"',
        *[
            f'{a}="{_xml_attr(v if _TEMPLATE_ATTR_SOURCE[a] == "v" else e)}"'
            for a in sorted(needs or ())
        ],
        f'controller="{controller}"',
    ]
    if read_only:
        parts.append('readOnly="true"')
    if filter_mode:
        parts.append('filterMode="true"')
    parts.append(f'template="{template}"')
    return "<page " + " ".join(parts) + "/>"


def clone_page_line(src_line: str, new_id: str, new_ctrl: str) -> str:
    """Nhân bản dòng nguồn, chỉ đổi ``id`` và ``controller``."""
    line = re.sub(
        r'(<page\s+id=")[^"]*(")',
        lambda m: m.group(1) + new_id + m.group(2),
        src_line,
        count=1,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r'(\bcontroller\s*=\s*")[^"]*(")',
        lambda m: m.group(1) + new_ctrl + m.group(2),
        line,
        count=1,
        flags=re.IGNORECASE,
    )


def insert_page_line(
    path: Path, new_line: str, new_id: str, execute: bool
) -> dict[str, Any]:
    """Chèn 1 dòng ``<page>`` vào ``path``. File đang sắp theo id thì chèn đúng
    thứ tự, không thì thêm cuối danh sách. Giữ BOM và kiểu xuống dòng."""
    raw = path.read_bytes()
    has_bom = raw.startswith(_BOM)
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)

    idx = [i for i, ln in enumerate(lines) if _RE_PAGE_LINE.match(ln)]
    ids = []
    for i in idx:
        m = _RE_ID.search(lines[i])
        ids.append((m.group(1).lower() if m else "", i))

    keys = [k for k, _ in ids]
    is_sorted = bool(keys) and keys == sorted(keys)
    insert_at = (idx[-1] + 1) if idx else len(lines)
    position = "append"
    if is_sorted:
        for k, i in ids:
            if k > new_id.lower():
                insert_at = i
                position = "sorted"
                break

    if insert_at > 0 and insert_at == len(lines) and lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] = lines[-1] + nl
    lines.insert(insert_at, new_line + nl)

    if execute:
        out = "".join(lines).encode("utf-8")
        path.write_bytes((_BOM if has_bom else b"") + out)
    return {
        "file": f"App_Data/Metadata/{path.name}",
        "line_no": insert_at + 1,
        "position": position,
        "line": new_line,
    }


def insert_customize_page(
    root: Path, new_lines: list[str], execute: bool
) -> dict[str, Any]:
    """Chèn các dòng ``<page>`` vào block ``<!--Customize--> ... <!--End
    Customize-->`` của ``App_Data/PageMetadata.xml`` (chèn ngay TRÊN dòng
    ``<!--End Customize-->``; chấp nhận cả marker ``<!--End-->``). Chưa có
    block thì tạo mới ngay trước ``</pages>``. Giữ BOM và kiểu xuống dòng."""
    path = page_metadata_path(root)
    if not path.is_file():
        return {"status": "file_missing", "file": _PAGE_META.as_posix()}
    raw = path.read_bytes()
    has_bom = raw.startswith(_BOM)
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)

    # indent theo dòng <page> gần nhất, mặc định 2 spaces
    indent = "  "
    for ln in reversed(lines):
        if _RE_PAGE_LINE.match(ln):
            indent = ln[: len(ln) - len(ln.lstrip())] or "  "
            break

    ins = [indent + l.strip() + nl for l in new_lines]

    end_i = next(
        (i for i, ln in enumerate(lines) if _RE_END_CUSTOMIZE.search(ln)),
        None,
    )
    if end_i is None and any(_RE_CUSTOMIZE.search(ln) for ln in lines):
        end_i = next(
            (i for i, ln in enumerate(lines) if _RE_END_SHORT.search(ln)),
            None,
        )

    if end_i is not None:
        lines[end_i:end_i] = ins
        line_no = end_i + 1
    else:
        close_i = next(
            (i for i, ln in enumerate(lines) if _RE_PAGES_CLOSE.search(ln)),
            len(lines),
        )
        if close_i > 0 and not lines[close_i - 1].endswith(("\n", "\r")):
            lines[close_i - 1] += nl
        block = [
            indent + "<!--Customize-->" + nl,
            *ins,
            indent + "<!--End Customize-->" + nl,
        ]
        lines[close_i:close_i] = block
        line_no = close_i + 2

    if execute:
        out = "".join(lines).encode("utf-8")
        path.write_bytes((_BOM if has_bom else b"") + out)
    return {
        "status": "added" if execute else "planned",
        "file": _PAGE_META.as_posix(),
        "line_no": line_no,
        "position": "customize",
    }


def find_entries_by_controllers(
    root: Path, ctrls: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """Quét page files 1 lần, gom dòng ``<page>`` theo controller thuộc ``ctrls``."""
    out: dict[str, list[dict[str, Any]]] = {}
    for fname, fpath in _page_files(root):
        try:
            lines = _read_lines(fpath)
        except Exception:
            continue
        for no, line in enumerate(lines, 1):
            if not _RE_PAGE_LINE.match(line):
                continue
            m = _RE_CTRL_ATTR.search(line)
            if not m or m.group(1) not in ctrls:
                continue
            entry = _parse_page_line(fname, no, line)
            if entry:
                out.setdefault(m.group(1), []).append(entry)
    return out


# ------------------------------------------------------ template suggestion

# Feature flags trích từ nội dung khuôn Fragments/<template>.xml.
_FEATURE_PATTERNS = [
    ("crypto", re.compile(r"Script\.Cryptography", re.IGNORECASE)),
    ("query", re.compile(r"queryInitGrid|CommonScripts,\s*query", re.IGNORECASE)),
    ("chart", re.compile(r"t=Chart|Chart\.ascx", re.IGNORECASE)),
    ("pdf", re.compile(r"t=PDF", re.IGNORECASE)),
    ("calendar", re.compile(r"t=Calendar", re.IGNORECASE)),
    ("treeview", re.compile(r"TreeView", re.IGNORECASE)),
    ("voucher", re.compile(r"[/\\~]Extender\.txt", re.IGNORECASE)),
    ("sign", re.compile(r"VoucherSign\.txt", re.IGNORECASE)),
    ("apv_sign", re.compile(r"APVSign\.txt", re.IGNORECASE)),
    ("splitter", re.compile(r"HTML\.MainSplitter", re.IGNORECASE)),
    ("grid", re.compile(r"HTML\.Grid", re.IGNORECASE)),
    ("tiny", re.compile(r"@@tinyv", re.IGNORECASE)),
]
_RE_RENDER_GROUP = re.compile(
    r"@render\([^)]*?,\s*(flow|f|query)\s*\)", re.IGNORECASE
)
# flow render → flow; f render → attach (đính kèm); query render → query.
_RENDER_GROUP_MAP = {"f": "attach", "flow": "flow", "query": "query"}

_LAYOUT_FEATURES = {"grid", "splitter", "tiny"}
_RE_QUERY_CTRL_NAME = re.compile(r"(?:^|_)query|QRT", re.IGNORECASE)


def fragment_features(root: Path) -> dict[str, set[str]]:
    """Feature flags của từng khuôn ``Metadata/Fragments/<template>.xml``."""
    out: dict[str, set[str]] = {}
    fdir = metadata_dir(root) / "Fragments"
    if not fdir.is_dir():
        return out
    try:
        entries = sorted(os.scandir(fdir), key=lambda e: e.name)
    except Exception:
        return out
    for e in entries:
        if not e.is_file() or not e.name.lower().endswith(".xml"):
            continue
        try:
            text = Path(e.path).read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue
        feats = {
            name for name, pat in _FEATURE_PATTERNS if pat.search(text)
        }
        if re.search(r"Init\.Flow", text, re.IGNORECASE):
            feats.add("flow")
        for g in _RE_RENDER_GROUP.findall(text):
            feats.add(_RENDER_GROUP_MAP.get(g.lower(), g.lower()))
        out[e.name[:-4]] = feats
    return out


def _ctrl_family(controller: str) -> str:
    """Họ controller: *Tran / *Approval / *Query* / *Request / other."""
    c = controller or ""
    if c.endswith("Approval"):
        return "approval"
    if _RE_QUERY_CTRL_NAME.search(c):
        return "query"
    if c.endswith("Tran"):
        return "tran"
    if c.endswith("Request"):
        return "request"
    return "other"


def page_needed_features(
    controller: str, texts: list[str] | None = None
) -> set[str]:
    """Feature trang cần, từ tên controller + nội dung file nguồn
    (aspx bản cũ hoặc XML suite)."""
    need: set[str] = set()
    fam = _ctrl_family(controller)
    if fam == "approval":
        need.update({"approval", "flow", "apv_sign"})
    elif fam == "query":
        need.add("query_page")
    elif fam in ("tran", "request"):
        need.add("voucher")
    for t in texts or []:
        if (
            "ExtenderControls" in t
            or "&Extender;" in t
            or "Extender.txt" in t
        ):
            need.add("voucher")
        if "VoucherSign" in t:
            need.add("sign")
        if "APVSign" in t:
            need.add("apv_sign")
        if (
            'Assembly="Flow"' in t
            or "FlowMulti" in t
            or "Init.Flow" in t
            or "Approval" in t
        ):
            need.add("flow")
        if "QueryExtender" in t or "queryInitGrid" in t:
            need.add("query")
        if "Chart.ascx" in t or "&Graph" in t or "t=Chart" in t:
            need.add("chart")
        if "TreeView" in t:
            need.add("treeview")
        if "MultiViewer" in t:
            need.add("attach")
    return need


def _template_freq(root: Path, family: str) -> dict[str, int]:
    """Tần suất template trong các ``<page>`` hiện có cùng họ controller."""
    freq: dict[str, int] = {}
    for _fname, fpath in _page_files(root):
        try:
            lines = _read_lines(fpath)
        except Exception:
            continue
        for line in lines:
            if not _RE_PAGE_LINE.match(line):
                continue
            m = _RE_CTRL_ATTR.search(line)
            t = _RE_TEMPLATE.search(line)
            if m and t and _ctrl_family(m.group(1)) == family:
                freq[t.group(1)] = freq.get(t.group(1), 0) + 1
    return freq


def suggest_template(
    root: Path, needed: set[str], controller: str = ""
) -> list[dict[str, Any]]:
    """Xếp hạng template khuôn phù hợp. Trả ``[{'template','matched','missing',
    'extra','score'}]`` giảm dần theo score. ``query_page`` → khuôn ``Query``;
    ``approval`` → ưu tiên khuôn có ``apv_sign``+``flow`` (Page.011)."""
    frags = fragment_features(root)
    if not frags:
        return []
    core = needed - {"approval", "query_page"}
    if "query_page" in needed:
        if "Query" in frags:
            return [
                {"template": "Query", "matched": ["query_page"],
                 "missing": [], "extra": [], "score": 999}
            ]
    freq = _template_freq(root, _ctrl_family(controller))

    scored: list[tuple[float, str, set, set, set]] = []
    for tpl, feats in frags.items():
        missing = core - feats
        extra = (feats - core) - _LAYOUT_FEATURES
        matched = core & feats
        score = (
            len(matched) * 10
            - len(missing) * 20
            - len(extra)
            + freq.get(tpl, 0) * 2
        )
        if "approval" in needed and not ({"apv_sign", "flow"} & feats):
            score -= 40
        scored.append((score, tpl, matched, missing, extra))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [
        {
            "template": tpl,
            "matched": sorted(matched),
            "missing": sorted(missing),
            "extra": sorted(extra),
            "score": round(score, 1),
        }
        for score, tpl, matched, missing, extra in scored
    ]


def _set_template(line: str, tpl: str) -> str:
    """Ghi/ghi đè thuộc tính ``template=`` trên dòng ``<page>``."""
    if _RE_TEMPLATE.search(line):
        return re.sub(
            r'\btemplate\s*=\s*"[^"]*"',
            f'template="{tpl}"',
            line,
            flags=re.IGNORECASE,
        )
    return re.sub(r"\s*/?\s*>\s*$", f' template="{tpl}"/>', line)


def _extract_page_lines(page_lines: str | list[str]) -> list[str]:
    if isinstance(page_lines, str):
        return [
            l.strip()
            for l in page_lines.splitlines()
            if _RE_PAGE_LINE.match(l)
        ]
    return [
        l.strip()
        for l in (str(x) for x in page_lines)
        if _RE_PAGE_LINE.match(l.strip())
    ]


def register_page_line(
    root: Path,
    page_lines: str | list[str],
    execute: bool,
    texts: list[str] | None = None,
) -> dict[str, Any]:
    """Nhét dòng ``<page>`` do agent truyền (param ``page``) vào block
    ``<!--Customize-->`` của ``App_Data/PageMetadata.xml``.

    Thiếu ``template`` → gợi ý bằng ``suggest_template`` theo feature controller
    rồi điền vào (``suggested_template`` trong kết quả). Trả ``entries`` per-line
    + ``status`` tổng: added | planned | invalid_page_line | file_missing |
    error (status per-line: id_exists | controller_exists | template_missing
    cũng chặn dòng đó khỏi chèn)."""
    raw_lines = _extract_page_lines(page_lines)
    if not raw_lines:
        return {
            "status": "invalid_page_line",
            "message": "không thấy dòng <page .../> trong param page",
            "entries": [],
        }
    if not page_metadata_path(root).is_file():
        return {
            "status": "file_missing",
            "file": _PAGE_META.as_posix(),
            "entries": [],
        }

    ids_now = all_page_ids(root)
    entries: list[dict[str, Any]] = []
    good: list[str] = []
    for line in raw_lines:
        m_id = _RE_ID.search(line)
        m_ctrl = _RE_CTRL_ATTR.search(line)
        if not m_id or not m_ctrl:
            entries.append(
                {"status": "invalid_page_line", "line": line,
                 "message": "dòng <page> thiếu id= hoặc controller="}
            )
            continue
        pid, ctrl = m_id.group(1), m_ctrl.group(1)
        info: dict[str, Any] = {"id": pid, "controller": ctrl}
        if pid.lower() in ids_now:
            entries.append(
                _id_exists_entry(info, find_entry_by_id(root, pid))
            )
            continue
        if find_page_entries(root, ctrl):
            entries.append({**info, "status": "controller_exists"})
            continue
        m_tpl = _RE_TEMPLATE.search(line)
        tpl = m_tpl.group(1) if m_tpl else ""
        if not tpl:
            needed = page_needed_features(ctrl, texts)
            cands = suggest_template(root, needed, ctrl)
            if cands:
                tpl = cands[0]["template"]
                line = _set_template(line, tpl)
                info["suggested_template"] = tpl
                info["candidates"] = [
                    c["template"] for c in cands[:3]
                ]
            else:
                entries.append(
                    {**info, "status": "template_missing",
                     "message": "không gợi ý được template — truyền template="}
                )
                continue
        if not (
            metadata_dir(root) / "Fragments" / f"{tpl}.xml"
        ).is_file():
            entries.append(
                {**info, "status": "template_missing",
                 "template": tpl,
                 "message": f"thiếu Metadata/Fragments/{tpl}.xml trên project đích"}
            )
            continue
        entries.append({**info, "status": "ok", "template": tpl, "line": line})
        good.append(line)
        ids_now.add(pid.lower())

    if good:
        ins = insert_customize_page(root, good, execute)
        if ins.get("status") in ("added", "planned"):
            status = ins["status"]
            for e in entries:
                if e["status"] == "ok":
                    e["status"] = status
                    e["file"] = ins["file"]
                    e["line_no"] = ins["line_no"]
        else:
            status = ins.get("status", "error")
            for e in entries:
                if e["status"] == "ok":
                    e["status"] = status
        out_status = status if all(
            e["status"] in ("added", "planned") for e in entries
        ) else "partial"
    else:
        out_status = (
            entries[0]["status"] if len(entries) == 1 else "nothing_added"
        )
    return {"status": out_status, "entries": entries,
            "file": _PAGE_META.as_posix()}


# ------------------------------------------------------------- clone flows

def register_saveas_page(
    root_src: Path,
    root_tgt: Path,
    src_ctrl: str,
    dst_ctrl: str,
    execute: bool,
) -> dict[str, Any]:
    """Nhân bản dòng ``<page>`` của ``src_ctrl`` cho ``dst_ctrl`` (id mới =
    ``dst_ctrl`` viết thường), ghi vào block ``<!--Customize-->`` của
    ``PageMetadata.xml`` đích. Trả ``status``: added | planned |
    no_source_page | ambiguous_source_page | id_exists | controller_exists |
    template_missing | file_missing | error."""
    entries = find_page_entries(root_src, src_ctrl)
    if not entries:
        return {"status": "no_source_page"}
    if len(entries) > 1:
        return {
            "status": "ambiguous_source_page",
            "entries": [f'{x["file"]}:{x["line_no"]} id={x["id"]}' for x in entries],
        }
    return register_page_clone(root_tgt, entries[0], dst_ctrl, execute)


def register_suite_pages(
    root_src: Path,
    root_tgt: Path,
    src_ctrl: str,
    controllers: set[str],
    rename: Any,
    execute: bool,
) -> list[dict[str, Any]]:
    """Suite clone: đăng ký trang cho mọi controller của suite có dòng ``<page>``.

    ``controllers`` = tên controller có file Dir/Grid/Filter/Report trong suite
    (vd ``APTran``, ``APApproval``); ``rename(c)`` trả tên controller đích. Controller
    không đổi tên (dùng chung, không thuộc suite) bị bỏ qua. Trang của ``src_ctrl``
    luôn có mặt trong kết quả (``no_source_page`` nếu nguồn không có dòng nào)."""
    found = find_entries_by_controllers(root_src, controllers | {src_ctrl})
    out: list[dict[str, Any]] = []
    for ctrl in sorted(found.keys() | {src_ctrl}):
        dst = rename(ctrl)
        if dst == ctrl:
            continue
        entries = found.get(ctrl) or []
        if not entries:
            res = {"status": "no_source_page"}
        elif len(entries) > 1:
            res = {
                "status": "ambiguous_source_page",
                "entries": [f'{x["file"]}:{x["line_no"]} id={x["id"]}' for x in entries],
            }
        else:
            res = register_page_clone(root_tgt, entries[0], dst, execute)
        out.append({**res, "src_controller": ctrl, "dst_controller": dst})
    return out


def register_page_clone(
    root_tgt: Path, src: dict[str, Any], dst_ctrl: str, execute: bool
) -> dict[str, Any]:
    """Nhân bản 1 dòng ``<page>`` nguồn (``src`` từ ``find_page_entries``) cho
    ``dst_ctrl`` — ghi vào block ``<!--Customize-->`` của PageMetadata.xml đích."""
    new_id = dst_ctrl.lower()
    info: dict[str, Any] = {"id": new_id, "template": src["template"]}

    if new_id in all_page_ids(root_tgt):
        return _id_exists_entry(info, find_entry_by_id(root_tgt, new_id))
    if find_page_entries(root_tgt, dst_ctrl):
        return {**info, "status": "controller_exists"}
    if src["template"] and not (
        metadata_dir(root_tgt) / "Fragments" / f'{src["template"]}.xml'
    ).is_file():
        return {**info, "status": "template_missing"}

    indent = src["text"][: len(src["text"]) - len(src["text"].lstrip())]
    new_line = indent + ensure_template_attrs(
        clone_page_line(src["text"].strip(), new_id, dst_ctrl),
        template_needs(root_tgt, src["template"]),
    )
    try:
        ins = insert_customize_page(root_tgt, [new_line.strip()], execute)
    except Exception as ex:
        return {**info, "status": "error", "message": f"{type(ex).__name__}: {ex}"}
    return {**info, **ins, "line": new_line.strip()}


# ---------------------------------------------------------------- type4 (template)

_RE_ASPX_V = re.compile(r'<%@\s*Page\b[^>]*?\bv="([^"]*)"', re.IGNORECASE)
_RE_ASPX_E = re.compile(r'<%@\s*Page\b[^>]*?\be="([^"]*)"', re.IGNORECASE)
_RE_ASPX_CTRL = re.compile(r'\bController="([^"]*)"', re.IGNORECASE)
_RE_ASPX_RO = re.compile(r'\bReadOnly="true"', re.IGNORECASE)
_RE_ASPX_FM = re.compile(r'\bFilterMode="true"', re.IGNORECASE)


def page_base_attrs_from_aspx(content: str) -> dict[str, Any] | None:
    """Attrs cơ bản của trang aspx bản cũ — kể cả trang có code riêng
    (chứng từ/duyệt): ``controller``/``v``/``e``/``read_only``/``filter_mode``.
    ``None`` nếu không thấy ``Controller="..."``."""
    m_ctrl = _RE_ASPX_CTRL.search(content)
    if not m_ctrl:
        return None
    m_v = _RE_ASPX_V.search(content)
    m_e = _RE_ASPX_E.search(content)
    return {
        "controller": m_ctrl.group(1),
        "v": m_v.group(1) if m_v else "",
        "e": m_e.group(1) if m_e else "",
        "read_only": bool(_RE_ASPX_RO.search(content)),
        "filter_mode": bool(_RE_ASPX_FM.search(content)),
    }


def page_attrs_from_aspx(content: str) -> dict[str, Any] | None:
    """Trang aspx 'trơn' (chỉ ``ReportExtender``: báo cáo, danh mục) → thuộc tính
    của dòng ``<page>`` tương ứng (template ``Page.001``). Trang có code VB /
    Register (chứng từ, duyệt...) trả None — dùng ``suggest_template`` để chọn
    khuôn theo feature."""
    ctls = {c.lower() for c in re.findall(r'LoadControl\("([^"]+)"\)', content)}
    if (
        ctls - set(_CONTROL_TEMPLATE)
        or len(ctls) > 1
        or ("<script runat=" in content and not ctls)
        or re.search(r"<%@\s*Register", content, re.I)
    ):
        return None
    base = page_base_attrs_from_aspx(content)
    if base is None:
        return None
    base["template"] = (
        _CONTROL_TEMPLATE[next(iter(ctls))] if ctls else _SIMPLE_TEMPLATE
    )
    return base


def register_template_page(
    root_tgt: Path, page_id: str, attrs: dict[str, Any], execute: bool
) -> dict[str, Any]:
    """Type4: thêm dòng ``<page>`` cho trang trơn vào block ``<!--Customize-->``
    của PageMetadata.xml."""
    info: dict[str, Any] = {"id": page_id, "template": attrs["template"]}
    if page_id.lower() in all_page_ids(root_tgt):
        return _id_exists_entry(
            info, find_entry_by_id(root_tgt, page_id)
        )
    if not (metadata_dir(root_tgt) / "Fragments" / f'{attrs["template"]}.xml').is_file():
        return {**info, "status": "template_missing"}
    if not page_metadata_path(root_tgt).is_file():
        return {**info, "status": "file_missing", "file": _PAGE_META.as_posix()}
    line = build_page_line(
        page_id,
        attrs["controller"],
        attrs["v"],
        attrs["e"],
        attrs["read_only"],
        attrs["filter_mode"],
        attrs["template"],
        template_needs(root_tgt, attrs["template"]),
    )
    try:
        ins = insert_customize_page(root_tgt, [line], execute)
    except Exception as ex:
        return {**info, "status": "error", "message": f"{type(ex).__name__}: {ex}"}
    return {**info, **ins, "line": line}

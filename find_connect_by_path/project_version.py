"""Nhận diện thế hệ program của project FBO theo tên thư mục.

Tên thư mục project kết thúc bằng ``SP<số>`` (``FBISP2422``, ``FBISP30``,
``FBISP3012``...). Lấy 2 chữ số đầu của số sau ``SP``: >= 30 là program mới
(trang khai báo trong ``App_Data/Metadata/Page*.xml``, không còn ``Main/*.aspx``).
Không nhận ra ``SP<số>`` thì coi là bản cũ để giữ xử lý hiện có.

Lời nhắc cho agent chọn theo bản: bản cũ chỉ nhắc ``.aspx``, SP30+ chỉ nhắc dòng
``<page>`` (xem ``render_by_generation``).
"""

from __future__ import annotations

import re
from pathlib import Path

METADATA_MIN_SP = 30

_RE_SP = re.compile(r"SP(\d+)", re.IGNORECASE)


def parse_sp_major(project_root: str | Path) -> int | None:
    """Trả 2 chữ số đầu của số sau ``SP`` cuối cùng trong tên thư mục, hoặc None."""
    name = Path(str(project_root).rstrip("\\/")).name
    found = _RE_SP.findall(name)
    if not found:
        return None
    return int(found[-1][:2])


def is_metadata_project(project_root: str | Path) -> bool:
    """True nếu project là program mới (SP30 trở lên)."""
    major = parse_sp_major(project_root)
    return major is not None and major >= METADATA_MIN_SP


LEGACY = "legacy"
METADATA = "metadata"

_CONTEXT_PATH_KEYS = ("path", "project", "project_root", "project_source",
                      "project_target", "file_path")


def generation_of(project_root: str | Path | None) -> str | None:
    """``metadata`` (SP30+), ``legacy`` (có ``SP<số>`` < 30), None nếu không rõ."""
    if not project_root:
        return None
    major = parse_sp_major(project_root)
    if major is None:
        return None
    return METADATA if major >= METADATA_MIN_SP else LEGACY


def _project_of_path(path: str) -> str | None:
    """Phần tên project trong path bất kỳ: tìm thư mục có ``SP<số>``."""
    for part in reversed(re.split(r"[\\/]+", str(path))):
        if _RE_SP.search(part):
            return part
    return None


def resolve_generation(context: dict | None = None) -> str | None:
    """Bản đang làm: ưu tiên path trong ``context``, sau đó sticky project."""
    for key in _CONTEXT_PATH_KEYS:
        val = (context or {}).get(key)
        if isinstance(val, str) and val.strip():
            part = _project_of_path(val)
            gen = generation_of(part) if part else None
            if gen:
                return gen
    try:
        from xml_fbograph.utils.any_path import last_project_root

        return generation_of(last_project_root())
    except Exception:
        return None


# Văn bản chọn theo bản: ``⟪L:chỉ bản cũ⟫`` và ``⟪N:chỉ SP30+⟫``. Bản rõ → chỉ giữ
# phần của bản đó (không nhắc phần kia); bản chưa rõ → giữ cả hai, gắn nhãn.
_RE_RUN = re.compile(r"(?:⟪[LN]:.*?⟫)+", re.DOTALL)
_RE_SEG = re.compile(r"⟪([LN]):(.*?)⟫", re.DOTALL)


def render_by_generation(text: str, gen: str | None) -> str:
    if "⟪" not in text:
        return text

    def run(m: re.Match) -> str:
        segs = _RE_SEG.findall(m.group(0))
        if gen == LEGACY:
            return "".join(t for k, t in segs if k == "L")
        if gen == METADATA:
            return "".join(t for k, t in segs if k == "N")
        label = {"L": "SP<30: ", "N": "SP30+: "}
        return "; ".join(label[k] + t for k, t in segs)

    return _RE_RUN.sub(run, text)


def render_tree(obj, gen: str | None):
    """Áp ``render_by_generation`` cho mọi chuỗi trong dict/list lồng nhau."""
    if isinstance(obj, str):
        return render_by_generation(obj, gen)
    if isinstance(obj, list):
        return [render_tree(x, gen) for x in obj]
    if isinstance(obj, dict):
        return {k: render_tree(v, gen) for k, v in obj.items()}
    return obj


_RE_MAIN_ASPX = re.compile(r"Main[/\\]([^\s,;:)\"']+?)\.aspx", re.IGNORECASE)
_RE_NAME_ASPX = re.compile(r"\b([A-Za-z0-9_{}]+)\.aspx\b", re.IGNORECASE)


def to_page_wording(text: str) -> str:
    """Hướng dẫn viết cho bản cũ (``Main/<x>.aspx``) → cách nói của SP30+ (dòng
    ``<page>``), để project mới không bị nhắc tới aspx."""
    t = _RE_MAIN_ASPX.sub(r'dòng <page id="\1"> (Metadata/Page*.xml)', text)
    t = _RE_NAME_ASPX.sub(r'trang "\1"', t)
    t = re.sub(r"ASPX ATTR", "PAGE ATTR", t)
    t = re.sub(r"Main aspx", "trang (dòng <page>)", t, flags=re.IGNORECASE)
    t = re.sub(r"\baspx\b", "trang", t, flags=re.IGNORECASE)
    return t

"""Đọc entity DOCTYPE trong XML FastBusiness bằng lxml (thay ReadXML.exe)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree


@dataclass
class EntityDeclaration:
    file: str
    line: int
    text: str


@dataclass
class EntityRecord:
    name: str
    found: bool = True
    content: str = ""
    external_file: str | None = None
    source_file: str = ""
    line: int = -1
    declarations: list[EntityDeclaration] = field(default_factory=list)


_parse_cache: dict[str, tuple[float, dict[str, EntityRecord]]] = {}


def clear_parse_cache() -> None:
    _parse_cache.clear()


def read_file_content(path: Path) -> str:
    """Đọc file với UTF-8 / UTF-16 (có hoặc không BOM)."""
    raw_bytes = path.read_bytes()

    if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
        return raw_bytes.decode("utf-16", errors="ignore")
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return raw_bytes.decode("utf-8-sig", errors="ignore")

    try:
        content = raw_bytes.decode("utf-8")
        if "\x00" in content:
            return raw_bytes.decode("utf-16", errors="ignore")
        return content
    except UnicodeDecodeError:
        try:
            return raw_bytes.decode("utf-16", errors="ignore")
        except Exception:
            return raw_bytes.decode("utf-8", errors="ignore")


def preprocess_xml(xml_text: str) -> str:
    """Chuẩn hóa path SYSTEM trong DTD: \\ -> /."""
    pattern = re.compile(r'(SYSTEM\s+["\'])([^"\']+)(["\'])')

    def repl(match: re.Match[str]) -> str:
        prefix = match.group(1)
        path = match.group(2)
        suffix = match.group(3)
        return f"{prefix}{path.replace(chr(92), '/')}{suffix}"

    return pattern.sub(repl, xml_text)


class FboResolver(etree.Resolver):
    def __init__(self, main_xml_dir: Path):
        super().__init__()
        self.main_xml_dir = main_xml_dir
        self.loaded_files: list[tuple[Path, str]] = []

    def resolve(self, url, pubid, context):
        clean_url = url.replace("\\", "/")

        is_absolute = False
        if clean_url.startswith("file:///"):
            clean_url = clean_url[8:]
            is_absolute = True
        elif clean_url.startswith("file:/"):
            clean_url = clean_url[6:]
            is_absolute = True
        elif len(clean_url) > 1 and clean_url[1] == ":":
            is_absolute = True

        if is_absolute:
            target_path = Path(clean_url).resolve()
        else:
            target_path = (self.main_xml_dir / clean_url).resolve()

        if not target_path.exists():
            return None

        try:
            raw_content = read_file_content(target_path)
            clean_content = preprocess_xml(raw_content)
            self.loaded_files.append((target_path, raw_content))
            base_url_posix = str(target_path).replace("\\", "/")
            return self.resolve_string(
                clean_content.encode("utf-8"),
                context,
                base_url=base_url_posix,
            )
        except Exception:
            return None


def find_entity_declarations(entity_name: str, loaded_files: list) -> list[EntityDeclaration]:
    pattern = re.compile(rf"<!ENTITY\s+(%\s+)?{re.escape(entity_name)}\b")
    matches: list[EntityDeclaration] = []

    for file_path, content in loaded_files:
        for line_num, line in enumerate(content.splitlines(), 1):
            if pattern.search(line):
                matches.append(
                    EntityDeclaration(
                        file=str(file_path),
                        line=line_num,
                        text=line.strip(),
                    )
                )
    return matches


def resolve_entity_file_path(system_url: str, main_xml_dir: Path) -> Path:
    clean_path_str = system_url.replace("file:///", "").replace("file:/", "")
    target = Path(clean_path_str)
    if not target.is_absolute() or not target.exists():
        target = (main_xml_dir / clean_path_str).resolve()
    return target


def get_entity_content(ent, main_xml_dir: Path) -> tuple[str, Path | None]:
    system_url = getattr(ent, "system_url", None)
    if system_url:
        target_file_path = resolve_entity_file_path(system_url, main_xml_dir)
        if target_file_path.exists():
            return read_file_content(target_file_path), target_file_path
        return "", target_file_path

    content = ent.content
    if content is None:
        return "", None
    return content, None


def parse_fbo_xml(xml_file_path: Path) -> tuple[etree._Element, FboResolver]:
    main_xml_dir = xml_file_path.parent
    resolver = FboResolver(main_xml_dir)

    parser = etree.XMLParser(
        load_dtd=True,
        resolve_entities=True,
        no_network=True,
    )
    parser.resolvers.add(resolver)

    raw_text = read_file_content(xml_file_path)
    clean_text = preprocess_xml(raw_text)
    resolver.loaded_files.append((xml_file_path, raw_text))

    base_url_posix = str(xml_file_path.resolve()).replace("\\", "/")
    root = etree.fromstring(
        clean_text.encode("utf-8"),
        parser=parser,
        base_url=base_url_posix,
    )
    return root, resolver


def _build_entity_record(
    entity_name: str,
    ent,
    main_xml_dir: Path,
    loaded_files: list,
) -> EntityRecord:
    content, external_file = get_entity_content(ent, main_xml_dir)
    declarations = find_entity_declarations(entity_name, loaded_files)
    active = declarations[0] if declarations else None

    return EntityRecord(
        name=entity_name,
        found=True,
        content=content,
        external_file=str(external_file) if external_file else None,
        source_file=active.file if active else "",
        line=active.line if active else -1,
        declarations=declarations,
    )


def parse_xml_entities_uncached(xml_file_path: Path) -> dict[str, EntityRecord]:
    """Parse toàn bộ entity trong DTD của file XML."""
    root, resolver = parse_fbo_xml(xml_file_path)
    dtd = root.getroottree().docinfo.internalDTD
    if dtd is None:
        return {}

    main_xml_dir = xml_file_path.parent
    entities: dict[str, EntityRecord] = {}
    for ent in dtd.entities():
        entity_name = getattr(ent, "name", "") or ""
        if not entity_name:
            continue
        entities[entity_name] = _build_entity_record(
            entity_name,
            ent,
            main_xml_dir,
            resolver.loaded_files,
        )
    return entities


def parse_xml_entities(xml_file_path: Path, *, force_reload: bool = False) -> dict[str, EntityRecord]:
    """Parse entity với cache theo mtime file."""
    key = str(xml_file_path.resolve())
    try:
        mtime = xml_file_path.stat().st_mtime
    except OSError as exc:
        raise FileNotFoundError(f"Không đọc được file: {xml_file_path}") from exc

    if not force_reload:
        cached = _parse_cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1]

    entities = parse_xml_entities_uncached(xml_file_path)
    _parse_cache[key] = (mtime, entities)
    return entities


def read_entity(xml_file_path: Path, entity_name: str) -> dict[str, Any]:
    """API tương thích read_entity.py — đọc một entity."""
    entities = parse_xml_entities(xml_file_path)
    record = entities.get(entity_name)
    if record is None:
        return {
            "entity_name": entity_name,
            "found": False,
            "content": "",
            "external_file": None,
            "declarations": [],
        }

    return {
        "entity_name": entity_name,
        "found": True,
        "content": record.content,
        "external_file": record.external_file,
        "declarations": [
            {"file": item.file, "line": item.line, "text": item.text}
            for item in record.declarations
        ],
    }

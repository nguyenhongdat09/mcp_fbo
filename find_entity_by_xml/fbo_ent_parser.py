"""
FboEntParser - Bộ phân tích file .ent của FastBusiness
Ported from FboEntParser.js

Quy tắc cốt lõi:
- INCLUDE -> Chỉ đọc bên trong khối. Mọi entity bên ngoài là vô hình.
- IGNORE -> Bỏ qua bên trong khối. Đọc phần ELSE (entity bên ngoài) bình thường.
"""

from __future__ import annotations

import re
from typing import Callable, Any, Dict, List, Optional, Tuple


class FboEntParser:
    def __init__(
        self,
        read_file_fn: Callable[[str], str | None],
        resolve_path_fn: Callable[[str, str], str],
        record_file_mtime_fn: Optional[Callable[[str], None]] = None,
    ):
        """
        :param read_file_fn: function(filePath: str) -> str | None
        :param resolve_path_fn: function(currentFile: str, relativeUrl: str) -> str
        :param record_file_mtime_fn: function(filePath: str) -> None
        """
        self._read_file = read_file_fn
        self._resolve_path = resolve_path_fn
        self._record_file_mtime = record_file_mtime_fn

    def parse_content(
        self,
        content: str,
        current_file_path: str,
        line_offset: int = 0,
        seed_params: Dict[str, Any] | None = None,
        seed_general: Dict[str, Any] | None = None,
        seed_overridden: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        param_entities = dict(seed_params) if seed_params else {}
        general_entities = dict(seed_general) if seed_general else {}
        overridden_entities = list(seed_overridden) if seed_overridden else []

        self._parse_block(
            content,
            current_file_path,
            line_offset,
            param_entities,
            general_entities,
            overridden_entities,
            False,
        )

        return {
            "paramEntities": param_entities,
            "generalEntities": general_entities,
            "overriddenEntities": overridden_entities,
        }

    def _build_line_index(self, content: str) -> List[int]:
        line_index = [0]
        i = -1
        while True:
            i = content.find("\n", i + 1)
            if i == -1:
                break
            line_index.append(i + 1)
        return line_index

    def _get_line_number(self, line_index: List[int], char_index: int) -> int:
        low = 0
        high = len(line_index) - 1
        while low <= high:
            mid = (low + high) >> 1
            if line_index[mid] <= char_index:
                if mid == len(line_index) - 1 or line_index[mid + 1] > char_index:
                    return mid + 1
                low = mid + 1
            else:
                high = mid - 1
        return 1

    def _parse_block(
        self,
        content: str,
        current_file_path: str,
        line_offset: int,
        param_entities: Dict[str, Any],
        general_entities: Dict[str, Any],
        overridden_entities: List[Dict[str, Any]],
        inside_include_block: bool,
    ) -> None:
        line_index = self._build_line_index(content)
        i = 0
        length = len(content)

        # Precompile some regex for `%Name;` matching within loop
        # We only need to check if the current position starts with `%`
        param_ref_re = re.compile(r"^%([\w.]+);")

        while i < length:
            ch = content[i]

            # 0. Skip comment <!-- ... -->
            if ch == "<" and content.startswith("<!--", i):
                end = content.find("-->", i + 4)
                i = (end + 3) if end != -1 else length
                continue

            # 1. Khai báo <!ENTITY ...>
            if ch == "<" and content.startswith("<!ENTITY", i):
                end = self._find_entity_end(content, i)
                decl = content[i : end + 1]
                line_number = self._get_line_number(line_index, i) + line_offset

                self._process_entity_decl(
                    decl,
                    current_file_path,
                    line_number,
                    param_entities,
                    general_entities,
                    overridden_entities,
                )

                i = end + 1
                continue

            # 2. Khối điều kiện <![%Condition;[ ... ]]>
            if ch == "<" and content.startswith("<![", i):
                end, section = self._extract_conditional_section(content, i)

                match_cond = re.match(r"^<!\[\s*([^\[]+)\[", section)
                prefix_lines = match_cond.group(0).count("\n") if match_cond else 0
                parent_lines_before = self._get_line_number(line_index, i) - 1
                inner_line_offset = line_offset + parent_lines_before + prefix_lines

                self._process_conditional_section(
                    section,
                    current_file_path,
                    inner_line_offset,
                    param_entities,
                    general_entities,
                    overridden_entities,
                )

                i = end + 3  # Bước qua ]]>
                continue

            # 3. Tham chiếu % entity tự do: %Name;
            if ch == "%":
                # Check next char is word char
                if i + 1 < length and re.match(r"\w", content[i + 1]):
                    match = param_ref_re.match(content[i:])
                    if match:
                        name = match.group(1)
                        if name in param_entities:
                            ent = param_entities[name]
                            parent_lines_before = self._get_line_number(line_index, i) - 1
                            inner_line_offset = 0 if ent.get("systemUrl") else (line_offset + parent_lines_before)

                            if ent.get("systemUrl") and not ent.get("_parsed"):
                                ent["_parsed"] = True
                                ext_content = self._safe_read(ent["resolvedPath"])
                                if ext_content is not None:
                                    self._parse_block(
                                        ext_content,
                                        ent["resolvedPath"],
                                        0,
                                        param_entities,
                                        general_entities,
                                        overridden_entities,
                                        False,
                                    )
                            elif not ent.get("systemUrl") and ent.get("value"):
                                self._parse_block(
                                    ent["value"],
                                    ent.get("sourceFile") or current_file_path,
                                    inner_line_offset,
                                    param_entities,
                                    general_entities,
                                    overridden_entities,
                                    False,
                                )
                        i += len(match.group(0))
                        continue

            i += 1

    def _process_entity_decl(
        self,
        decl: str,
        current_file_path: str,
        line_number: int,
        param_entities: Dict[str, Any],
        general_entities: Dict[str, Any],
        overridden_entities: List[Dict[str, Any]],
    ) -> None:
        # TRƯỜNG HỢP 1: <!ENTITY % Name SYSTEM "path">
        m1 = re.match(r"^<!ENTITY\s+%\s+([\w.]+)\s+SYSTEM\s+([\"'])([^\"'\r\n]+)\2\s*>", decl, re.IGNORECASE)
        if m1:
            name = m1.group(1)
            system_url = m1.group(3)
            resolved_path = self._resolve_path(current_file_path, system_url)

            if name not in param_entities:
                param_entities[name] = {
                    "value": None,
                    "systemUrl": system_url,
                    "sourceFile": resolved_path,
                    "resolvedPath": resolved_path,
                    "line": 1,
                    "text": decl,
                    "_parsed": False,  # Chưa parse — sẽ parse khi %name; được gọi
                }
            else:
                overridden_entities.append(
                    {
                        "name": name,
                        "systemUrl": system_url,
                        "sourceFile": resolved_path,
                        "line": line_number,
                        "text": decl,
                        "is_parameter": True,
                        "declaredInFile": current_file_path,
                    }
                )
            return

        # TRƯỜNG HỢP 2: <!ENTITY % Name "value">
        m2 = re.match(r"^<!ENTITY\s+%\s+([\w.]+)\s+([\"'])([\s\S]*?)\2\s*>", decl, re.IGNORECASE)
        if m2:
            name = m2.group(1)
            if name not in param_entities:
                param_entities[name] = {
                    "value": m2.group(3),
                    "systemUrl": None,
                    "sourceFile": current_file_path,
                    "resolvedPath": None,
                    "line": line_number,
                    "text": decl,
                }
            return

        # TRƯỜNG HỢP 3: <!ENTITY Name SYSTEM "path">
        m3 = re.match(r"^<!ENTITY\s+([\w.]+)\s+SYSTEM\s+([\"'])([^\"'\r\n]+)\2\s*>", decl, re.IGNORECASE)
        if m3:
            name = m3.group(1)
            system_url = m3.group(3)
            resolved_path = self._resolve_path(current_file_path, system_url)

            if name not in general_entities:
                if self._record_file_mtime:
                    self._record_file_mtime(resolved_path)
                general_entities[name] = {
                    "name": name,
                    "value": None,
                    "systemUrl": system_url,
                    "sourceFile": resolved_path,
                    "line": 1,  # External files start at 1
                    "declaredInFile": current_file_path,
                    "text": decl,
                }
            else:
                overridden_entities.append(
                    {
                        "name": name,
                        "previousValue": general_entities[name],
                        "overridingFile": resolved_path,
                        "overridingLine": line_number,
                    }
                )
            return

        # TRƯỜNG HỢP 4: <!ENTITY Name "value">
        m4 = re.match(r"^<!ENTITY\s+([\w.]+)\s+([\"'])([\s\S]*?)\2\s*>", decl, re.IGNORECASE)
        if m4:
            name = m4.group(1)
            if name not in general_entities:
                general_entities[name] = {
                    "name": name,
                    "value": m4.group(3),
                    "systemUrl": None,
                    "sourceFile": current_file_path,
                    "line": line_number,
                    "declaredInFile": current_file_path,
                    "text": decl,
                }

    def _process_conditional_section(
        self,
        section: str,
        current_file_path: str,
        inner_line_offset: int,
        param_entities: Dict[str, Any],
        general_entities: Dict[str, Any],
        overridden_entities: List[Dict[str, Any]],
    ) -> bool | None:
        head_match = re.match(r"^<!\[\s*(.+?)\s*\[", section)
        if not head_match:
            return None

        inner_content = section[len(head_match.group(0)) : -3]
        resolved_condition = self._resolve_condition(head_match.group(1).strip(), param_entities)

        if resolved_condition == "INCLUDE":
            self._parse_block(
                inner_content,
                current_file_path,
                inner_line_offset,
                param_entities,
                general_entities,
                overridden_entities,
                True,
            )
            return True
        elif resolved_condition == "IGNORE":
            return False

        return None

    def _resolve_condition(self, raw_condition: str, param_entities: Dict[str, Any]) -> str | None:
        condition = raw_condition
        depth = 0

        while condition.startswith("%") and depth < 10:
            name = re.sub(r"^%|;$", "", condition).strip()
            if name not in param_entities:
                return None
            ent = param_entities[name]

            if ent.get("systemUrl") and ent.get("resolvedPath"):
                if ent.get("value") is None:
                    file_content = self._safe_read(ent["resolvedPath"])
                    if file_content is not None:
                        ent["value"] = file_content.strip()
                condition = (ent.get("value") or "").strip()
            else:
                condition = (ent.get("value") or "").strip()

            depth += 1

        res = re.sub(r"[\"']", "", condition).strip().upper()
        return res if res else None

    def _find_entity_end(self, content: str, start_index: int) -> int:
        i = start_index + 8
        in_quote = False
        quote_char = ""
        length = len(content)

        while i < length:
            ch = content[i]
            if (ch == '"' or ch == "'") and not in_quote:
                in_quote = True
                quote_char = ch
            elif ch == quote_char and in_quote:
                in_quote = False
            elif ch == ">" and not in_quote:
                break
            i += 1

        return i

    def _extract_conditional_section(self, content: str, start_index: int) -> Tuple[int, str]:
        depth = 1
        i = start_index + 3
        length = len(content)

        while i < length - 2:
            if content.startswith("<![", i):
                depth += 1
                i += 3
            elif content.startswith("]]>", i):
                depth -= 1
                if depth == 0:
                    break
                i += 3
            else:
                i += 1

        return i, content[start_index : i + 3]

    def _safe_read(self, file_path: str) -> str | None:
        try:
            return self._read_file(file_path)
        except Exception:
            return None

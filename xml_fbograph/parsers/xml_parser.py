import os
import re
from pathlib import Path
from lxml import etree
from typing import Dict, List, Tuple, Any
import functools

@functools.lru_cache(maxsize=512)
def _read_file_cached(path_str: str) -> bytes:
    """Cache bytes thô — key là path string, share được giữa tất cả XMLParser instance."""
    try:
        return Path(path_str).read_bytes()
    except Exception:
        return b""

def read_file_content(path: Path) -> str:
    """Đọc file xử lý mã hóa UTF-8, Windows-1258 hoặc UTF-16 (có/không BOM) một cách an sau."""
    if path.suffix.lower() == ".ent":
        raw_bytes = _read_file_cached(str(path.resolve()))
    else:
        try:
            raw_bytes = path.read_bytes()
        except Exception:
            return ""

    if not raw_bytes:
        return ""

    if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
        return raw_bytes.decode("utf-16", errors="ignore")
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return raw_bytes.decode("utf-8-sig", errors="ignore")

    # Kiểm tra khai báo encoding trong XML header
    match = re.search(b'encoding\\s*=\\s*["\']([^"\']+)["\']', raw_bytes[:200])
    if match:
        enc = match.group(1).decode("ascii", errors="ignore").lower()
        try:
            if enc in ("windows-1258", "win-1258", "1258"):
                return raw_bytes.decode("windows-1258", errors="ignore")
            elif enc in ("utf-8", "utf8"):
                return raw_bytes.decode("utf-8", errors="ignore")
            elif enc in ("utf-16", "utf16"):
                return raw_bytes.decode("utf-16", errors="ignore")
        except Exception:
            pass

    try:
        content = raw_bytes.decode("utf-8")
        if "\x00" in content:
            return raw_bytes.decode("utf-16", errors="ignore")
        return content
    except UnicodeDecodeError:
        try:
            # Fallback sang windows-1258 cho các file Việt hóa cũ
            return raw_bytes.decode("windows-1258", errors="ignore")
        except Exception:
            try:
                return raw_bytes.decode("utf-16", errors="ignore")
            except Exception:
                return raw_bytes.decode("utf-8", errors="ignore")


def preprocess_xml(xml_text: str) -> str:
    """Chuẩn hóa đường dẫn SYSTEM trong DTD: \\ -> / để libxml2 không báo lỗi URI."""
    pattern = re.compile(r'(SYSTEM\s+["\'])([^"\']+)(["\'])')
    def repl(match: re.Match) -> str:
        prefix = match.group(1)
        path = match.group(2)
        suffix = match.group(3)
        return f"{prefix}{path.replace(chr(92), '/')}{suffix}"
    return pattern.sub(repl, xml_text)

def is_encrypted_file(raw_bytes: bytes) -> bool:
    """
    Nhận diện file XML bị mã hóa của FBO (binary .f hoặc nội dung không đọc được).
    Lưu ý: <!--C--> là marker file flat đã giải mã, KHÔNG phải encrypted.
    """
    has_bom = raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff")
    if not has_bom:
        null_ratio = raw_bytes.count(0) / max(len(raw_bytes), 1)
        if null_ratio > 0.3:
            return True
    return False


_SCRIPT_BLOCK_RE = re.compile(
    r"<(script|clientScript)\b[^>]*>(.*?)</\1>",
    re.DOTALL | re.IGNORECASE,
)
_SPLIT_CDATA_RE = re.compile(r"\]\]>\s*(?:&[a-zA-Z0-9_]+;)?\s*<!\[CDATA\[", re.DOTALL)


def extract_js_blocks_from_raw(raw_content: str) -> List[Dict[str, Any]]:
    """
    Trích JS từ XML thô khi lxml không parse được (CDATA bị tách bởi entity include).
    """
    blocks: List[Dict[str, Any]] = []
    if not raw_content:
        return blocks

    for match in _SCRIPT_BLOCK_RE.finditer(raw_content):
        tag = match.group(1).lower()
        inner = match.group(2)
        inner = re.sub(r"<!\[CDATA\[", "", inner)
        inner = re.sub(r"\]\]>", "", inner)
        inner = _SPLIT_CDATA_RE.sub("\n", inner)
        inner = re.sub(r"&[a-zA-Z0-9_]+;", "\n", inner)
        content = inner.strip()
        if not content:
            continue
        line_num = raw_content[: match.start()].count("\n") + 1
        blocks.append({"content": content, "line": line_num, "tag": tag})
    return blocks

class XmlControllerParser:
    def __init__(self, controllers_root: Path):
        self.controllers_root = Path(controllers_root).resolve()

    def parse(self, file_path: Path) -> Dict[str, Any]:
        """Phân tích cấu trúc file XML."""
        file_path = Path(file_path).resolve()
        
        try:
            raw_bytes = file_path.read_bytes()
            if is_encrypted_file(raw_bytes):
                # File nhị phân mã hóa hoàn toàn -> Trả về node rỗng ngay, không cố parse
                return self._build_empty_result(file_path, "", [], [], "File is encrypted")
        except Exception:
            pass
            
        raw_content = read_file_content(file_path)
        
        from find_entity_by_xml.facade import extract_expanded_blocks
        
        blocks_data = extract_expanded_blocks(str(file_path))
        flat_text = blocks_data.get('flat_text', "")
        sql_blocks = blocks_data.get('sql_blocks', [])
        js_blocks = blocks_data.get('js_blocks', [])
        
        system_entities = blocks_data.get('system_entities', [])
        param_entities_dicts = blocks_data.get('param_entities', [])
        
        # Combine system and param entities that have files into `node.entities`
        all_entities = system_entities + param_entities_dicts
        for ent in all_entities:
            src_file = ent.get('sourceFile')
            if src_file:
                try:
                    ent['relative_path'] = os.path.relpath(src_file, self.controllers_root)
                except Exception:
                    ent['relative_path'] = src_file
            else:
                ent['relative_path'] = ""
                
        param_entity_names = [e.get('name') for e in param_entities_dicts if e.get('name')]
        
        if all_entities:
            entity_markers = []
            for ent in all_entities:
                name = ent.get('name')
                src_file = ent.get('relative_path') or ent.get('sourceFile')
                if name or src_file:
                    entity_markers.append(f"{name or ''} | {src_file or ''}")
            if entity_markers:
                marker_text = "/* FBO_ENTITIES: " + " ; ".join(entity_markers) + " */"
                if sql_blocks:
                    sql_blocks[-1]["content"] += "\n" + marker_text
                else:
                    sql_blocks.append({"content": marker_text, "line": 1, "tag": "query"})
        
        parser = etree.XMLParser(recover=True, strip_cdata=False)
        try:
            root = etree.fromstring(flat_text.encode('utf-8'), parser=parser)
        except Exception as e:
            return self._build_empty_result(file_path, raw_content, param_entity_names, all_entities, str(e))

        if root is None:
            return self._build_empty_result(file_path, raw_content, param_entity_names, all_entities, "XML root is None")

        # Trích xuất metadata từ root element
        xmlns = root.nsmap.get(None, '')
        xml_root_tag = etree.QName(root.tag).localname
        
        # Xác định folder_type & folder_subtype
        rel_parts = file_path.relative_to(self.controllers_root).parts
        folder_type = rel_parts[0] if len(rel_parts) > 0 else ''
        folder_subtype = rel_parts[1] if len(rel_parts) > 1 else ''

        # Lấy thuộc tính table và code
        table = root.get('table')
        code_field = root.get('code')

        # Lấy tiêu đề
        title_v = ''
        title_e = ''
        for elem in root.iter():
            if not isinstance(elem.tag, str):
                continue
            if etree.QName(elem.tag).localname == 'title':
                title_v = elem.get('v') or ''
                title_e = elem.get('e') or ''
                break

        # Quét các fields khai báo
        fields = []
        grid_refs = []
        lookup_refs = []
        
        for elem in root.xpath(".//*[local-name()='field']"):
            name = elem.get('name')
            if not name:
                continue
            
            header_elems = elem.xpath(".//*[local-name()='header']")
            header_elem = header_elems[0] if header_elems else None
            header_v = header_elem.get('v') if header_elem is not None else ''
            header_e = header_elem.get('e') if header_elem is not None else ''
            if not header_v:
                label_elems = elem.xpath(".//*[local-name()='label']")
                if label_elems:
                    header_v = label_elems[0].get('v') or ''
                    header_e = label_elems[0].get('e') or ''

            line_start = elem.sourceline or 1
            line_end = line_start
            
            try:
                snippet_bytes = etree.tostring(elem, encoding='utf-8', pretty_print=True)
                snippet = snippet_bytes.decode('utf-8').strip()
            except Exception:
                snippet = ''

            is_external = elem.get('external') == 'true'
            filter_source = elem.get('filterSource')

            if not is_external or filter_source == 'Tidy':
                fields.append({
                    'name': name,
                    'line_start': line_start,
                    'line_end': line_end,
                    'snippet': snippet,
                    'header_v': header_v,
                    'header_e': header_e,
                    'type': elem.get('type'),
                    'external': is_external
                })

            items_list = elem.xpath(".//*[local-name()='items']")
            items_elem = items_list[0] if items_list else None
            
            style = None
            controller = None
            
            if items_elem is not None:
                style = items_elem.get('style')
                controller = items_elem.get('controller')
            
            raw_elem_str = ''
            if not controller:
                try:
                    raw_elem_str = etree.tostring(elem, encoding='utf-8').decode('utf-8')
                except Exception:
                    raw_elem_str = ''
                match_ctrl = re.search(r'controller\s*=\s*[\"\']([^\"\']+)[\"\']', raw_elem_str)
                match_style = re.search(r'style\s*=\s*[\"\']([^\"\']+)[\"\']', raw_elem_str)
                if match_ctrl:
                    controller = match_ctrl.group(1)
                    style = match_style.group(1) if match_style else None

            if controller:
                if style == 'Grid':
                    foreign_key = None
                    if items_elem is not None:
                        fk_items = items_elem.xpath(".//*[local-name()='item' and @value='ForeignKey']")
                        fk_item = fk_items[0] if fk_items else None
                        if fk_item is not None:
                            text_elems = fk_item.xpath(".//*[local-name()='text']")
                            text_elem = text_elems[0] if text_elems else None
                            if text_elem is not None:
                                v_val = text_elem.get('v') or ''
                                match = re.search(r'String:\s*([a-zA-Z0-9_]+)', v_val)
                                if match:
                                    foreign_key = match.group(1)
                    else:
                        if not raw_elem_str:
                            try:
                                raw_elem_str = etree.tostring(elem, encoding='utf-8').decode('utf-8')
                            except Exception:
                                raw_elem_str = ''
                        match_fk = re.search(r'String:\s*([a-zA-Z0-9_]+)', raw_elem_str)
                        if match_fk:
                            foreign_key = match_fk.group(1)
                            
                    grid_refs.append({
                        'field_name': name,
                        'controller': controller,
                        'foreign_key': foreign_key
                    })
                elif style in {'AutoComplete', 'Lookup'}:
                    lookup_refs.append({
                        'field_name': name,
                        'controller': controller
                    })

        return {
            'file_path': str(file_path),
            'relative_path': os.path.relpath(file_path, self.controllers_root),
            'folder_type': folder_type,
            'folder_subtype': folder_subtype,
            'xml_root_tag': xml_root_tag,
            'xml_namespace': xmlns,
            'table': table,
            'code_field': code_field,
            'title_v': title_v,
            'title_e': title_e,
            'entities': all_entities,
            'param_entities': param_entity_names,
            'fields': fields,
            'grid_refs': grid_refs,
            'lookup_refs': lookup_refs,
            'sql_blocks': sql_blocks,
            'js_blocks': js_blocks,
            'file_size': len(raw_content) if raw_content else 0,
            'error': None
        }

    def _build_empty_result(self, file_path: Path, raw_content: str, param_entities: List[str], system_entities: List[Dict], error_msg: str) -> Dict[str, Any]:
        """Tạo kết quả rỗng hoặc fallback regex khi XML parser gặp lỗi (thường là file .ent, .txt hoặc XML lỗi cấu trúc)."""
        rel_parts = file_path.relative_to(self.controllers_root).parts
        folder_type = rel_parts[0]
        folder_subtype = rel_parts[1] if len(rel_parts) > 2 else ""
        
        sql_blocks = []
        js_blocks = []
        grid_refs = []
        lookup_refs = []
        fields = []
        table = None
        code_field = None
        
        # Chỉ chạy fallback regex cho các file XML hoặc các file nằm trong folder chính
        if file_path.suffix.lower() in {".xml", ".f"} and folder_type.lower() in {"dir", "grid", "filter", "report", "lookup", "form"}:
            js_blocks = extract_js_blocks_from_raw(raw_content)

            # 1. Trích xuất SQL blocks
            import re
            pattern = re.compile(r'<(\w+)(?:\s+[^>]*)?>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</\1>', re.DOTALL | re.IGNORECASE)
            for match in pattern.finditer(raw_content):
                tag = match.group(1).lower()
                content = match.group(2)
                line_num = raw_content[:match.start()].count('\n') + 1
                
                if tag in {"query", "command", "action"}:
                    sql_blocks.append({
                        "content": content,
                        "line": line_num,
                        "tag": tag
                    })
            
            # 2. Trích xuất grid_refs và lookup_refs
            field_matches = re.finditer(r'<field\s+name\s*=\s*["\']([a-zA-Z0-9_\$]+%?[a-zA-Z0-9_\$]*)["\'][^>]*>(.*?)</field>', raw_content, re.DOTALL | re.IGNORECASE)
            for fm in field_matches:
                fname = fm.group(1)
                fcontent = fm.group(2)
                
                ctrl_m = re.search(r'controller\s*=\s*["\']([a-zA-Z0-9_\$]+)["\']', fcontent, re.IGNORECASE)
                style_m = re.search(r'style\s*=\s*["\']([a-zA-Z0-9_\$]+)["\']', fcontent, re.IGNORECASE)
                
                if ctrl_m:
                    ctrl = ctrl_m.group(1)
                    style = style_m.group(1) if style_m else None
                    if style == "Grid":
                        fk = None
                        fk_m = re.search(r'String:\s*([a-zA-Z0-9_]+)', fcontent, re.IGNORECASE)
                        if fk_m:
                            fk = fk_m.group(1)
                        grid_refs.append({
                            "field_name": fname,
                            "controller": ctrl,
                            "foreign_key": fk
                        })
                    elif style in {"AutoComplete", "Lookup"}:
                        lookup_refs.append({
                            "field_name": fname,
                            "controller": ctrl
                        })
                
                # Trích xuất fields thô
                fields.append({
                    "name": fname,
                    "line_start": raw_content[:fm.start()].count('\n') + 1,
                    "line_end": raw_content[:fm.end()].count('\n') + 1,
                    "snippet": fm.group(0),
                    "header_v": "",
                    "header_e": "",
                    "type": None,
                    "external": False
                })
                
            # Trích xuất table và code từ root tag thô
            root_match = re.search(r'<dir\s+[^>]*table\s*=\s*["\']([^"\']+)["\']', raw_content, re.IGNORECASE)
            if not root_match:
                root_match = re.search(r'<grid\s+[^>]*table\s*=\s*["\']([^"\']+)["\']', raw_content, re.IGNORECASE)
            if root_match:
                table = root_match.group(1)
                
            code_match = re.search(r'code\s*=\s*["\']([^"\']+)["\']', raw_content, re.IGNORECASE)
            if code_match:
                code_field = code_match.group(1)
        
        return {
            "file_path": str(file_path),
            "relative_path": os.path.relpath(file_path, self.controllers_root),
            "folder_type": folder_type,
            "folder_subtype": folder_subtype,
            "xml_root_tag": folder_type.lower() if folder_type.lower() in {"dir", "grid", "filter", "report", "lookup", "form"} else "",
            "xml_namespace": "",
            "table": table,
            "code_field": code_field,
            "title_v": "",
            "title_e": "",
            "entities": system_entities,
            "param_entities": list(set(param_entities)),
            "fields": fields,
            "grid_refs": grid_refs,
            "lookup_refs": lookup_refs,
            "sql_blocks": sql_blocks,
            "js_blocks": js_blocks,
            "file_size": len(raw_content),
            "error": error_msg
        }


import os
import re
from pathlib import Path
from lxml import etree
from typing import Dict, List, Tuple, Any

def read_file_content(path: Path) -> str:
    """Đọc file xử lý mã hóa UTF-8, Windows-1258 hoặc UTF-16 (có/không BOM) một cách an sau."""
    try:
        raw_bytes = path.read_bytes()
    except Exception:
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
    Nhận diện file XML bị mã hóa của FBO.
    File mã hóa thường:
      - Không có UTF-16 BOM mà chứa nhiều byte NULL (\x00) bài bản
      - Hoặc có comment đặc biệt <!--C--> hoặc Encrypted block
      - Hoặc không có tag XML hợp lệ nào sau khi decode
    """
    # Giải mã thử UTF-16 trước
    has_bom = raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff")
    if has_bom:
        try:
            text = raw_bytes.decode("utf-16", errors="ignore")
        except Exception:
            text = ""
    else:
        text = raw_bytes.decode("utf-8", errors="ignore")
    # Kiểm tra có comment <!--C--> (đặc trưng của file flat/encrypted trong FBO)
    if "<!--C-->" in text:
        return True
    # Kiểm tra bài toàn nội dung thường bị mã hóa: tỷ lệ bít NULL cao
    if not has_bom:
        null_ratio = raw_bytes.count(0) / max(len(raw_bytes), 1)
        if null_ratio > 0.3:
            return True
    return False

def uri_to_path(url: str) -> Path:
    """Convert a file:/// or file:// URI/path to a pathlib.Path object, handling UNC paths."""
    if url.startswith("file:"):
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc:
            return Path(f"\\\\{parsed.netloc}{parsed.path}").resolve()
        else:
            path = parsed.path
            if path.startswith('/') and len(path) > 2 and path[2] == ':':
                path = path[1:]
            return Path(path).resolve()

    clean_url = url.replace("\\", "/")
    if len(clean_url) > 1 and clean_url[1] == ":":
        return Path(clean_url).resolve()
    return Path(url)


class FboResolver(etree.Resolver):
    """Bộ giải quyết thực thể động của FBO để tự động nạp các file thực thể phụ thuộc."""
    def __init__(self, main_xml_dir: Path):
        super().__init__()
        self.main_xml_dir = main_xml_dir
        self.loaded_files: List[Tuple[Path, str]] = []

    def resolve(self, url, pubid, context):
        if url.startswith("file:"):
            target_path = uri_to_path(url)
            is_absolute = True
        else:
            clean_url = url.replace("\\", "/")
            if len(clean_url) > 1 and clean_url[1] == ":":
                target_path = Path(clean_url).resolve()
                is_absolute = True
            else:
                target_path = (self.main_xml_dir / clean_url).resolve()
                is_absolute = False

        # Flatten include fallback: nếu file không tồn tại, tìm trong Config/Fields/
        if not target_path.exists() and not is_absolute:
            filename = Path(clean_url).name
            # Thử các subdirectory thường chứa config fields trong FBO
            fallback_paths = [
                self.main_xml_dir / "Config" / "Fields" / filename,
                self.main_xml_dir / "Config" / filename,
                self.main_xml_dir.parent / "Config" / "Fields" / filename,
                self.main_xml_dir.parent / "Config" / filename,
            ]
            for fb in fallback_paths:
                if fb.exists():
                    target_path = fb.resolve()
                    break

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

def flatten_cdata_nodes(root: etree._Element) -> None:
    """
    Gộp nội dung các thẻ text/query/clientScript/script thành 1 khối CDATA
    trong bộ nhớ. Tránh phân mảnh CDATA hoặc escape ký tự đặc biệt.
    """
    for elem in root.iter():
        local_name = etree.QName(elem.tag).localname
        if local_name not in {"text", "query", "clientScript", "script"}:
            continue

        full_text = "".join(elem.itertext())
        attributes = dict(elem.attrib)
        elem.clear()

        for key, value in attributes.items():
            elem.set(key, value)

        elem.text = etree.CDATA(full_text)

class XmlControllerParser:
    def __init__(self, controllers_root: Path):
        self.controllers_root = Path(controllers_root).resolve()

    def parse(self, file_path: Path) -> Dict[str, Any]:
        """Phân tích cấu trúc file XML."""
        file_path = Path(file_path).resolve()
        main_xml_dir = file_path.parent
        
        # Đọc file thô để quét các parameter entities và SYSTEM entities
        raw_content = read_file_content(file_path)
        
        # Tìm parameter entities được gọi trong DTD (ví dụ: %Invoice;)
        param_entities = re.findall(r"%([a-zA-Z0-9_\.]+);", raw_content)
        
        # Quét khai báo SYSTEM entity để lập dependency
        system_entities = []
        entity_decl_pattern = re.compile(
            r'<!ENTITY\s+(?:%\s+)?([a-zA-Z0-9_\.]+)\s+SYSTEM\s+["\']([^"\']+)["\']',
            re.IGNORECASE
        )
        for name, system_path in entity_decl_pattern.findall(raw_content):
            # Tính toán đường dẫn thực tế của entity file
            clean_sys_path = system_path.replace("\\", "/")
            target_ent_path = (main_xml_dir / clean_sys_path).resolve()
            system_entities.append({
                "name": name,
                "path": str(target_ent_path),
                "relative_path": os.path.relpath(target_ent_path, self.controllers_root) if target_ent_path.exists() else clean_sys_path
            })

        # Bắt đầu parse XML bằng lxml
        resolver = FboResolver(main_xml_dir)
        parser = etree.XMLParser(
            load_dtd=True,
            resolve_entities=True,
            no_network=True,
            strip_cdata=False
        )
        parser.resolvers.add(resolver)

        clean_text = preprocess_xml(raw_content)
        resolver.loaded_files.append((file_path, raw_content))
        
        try:
            base_url_posix = str(file_path).replace("\\", "/")
            root = etree.fromstring(
                clean_text.encode("utf-8"),
                parser=parser,
                base_url=base_url_posix,
            )
            # Làm phẳng CDATA ngay trên cây DOM trong bộ nhớ
            flatten_cdata_nodes(root)
        except Exception as e:
            # Fallback nếu parse XML lỗi (ví dụ file .ent thô không có root tag)
            return self._build_empty_result(file_path, raw_content, param_entities, system_entities, str(e))

        # Trích xuất metadata từ root element
        xmlns = root.nsmap.get(None, "")
        xml_root_tag = etree.QName(root.tag).localname
        
        # Xác định folder_type & folder_subtype
        rel_parts = file_path.relative_to(self.controllers_root).parts
        folder_type = rel_parts[0]
        folder_subtype = rel_parts[1] if len(rel_parts) > 2 else ""

        # Lấy thuộc tính table và code
        table = root.get("table")
        code_field = root.get("code")

        # Lấy tiêu đề
        title_v = ""
        title_e = ""
        for elem in root.iter():
            if not isinstance(elem.tag, str):
                continue
            if etree.QName(elem.tag).localname == "title":
                title_v = elem.get("v") or ""
                title_e = elem.get("e") or ""
                break

        # Quét các fields khai báo
        fields = []
        grid_refs = []
        lookup_refs = []
        
        # Duyệt qua các thẻ field (hỗ trợ cả các field có namespace và không có namespace)
        for elem in root.xpath(".//*[local-name()='field']"):
            name = elem.get("name")
            if not name:
                continue
            
            header_elems = elem.xpath(".//*[local-name()='header']")
            header_elem = header_elems[0] if header_elems else None
            header_v = header_elem.get("v") if header_elem is not None else ""
            header_e = header_elem.get("e") if header_elem is not None else ""
            if not header_v:
                label_elems = elem.xpath(".//*[local-name()='label']")
                if label_elems:
                    header_v = label_elems[0].get("v") or ""
                    header_e = label_elems[0].get("e") or ""

            line_start = elem.sourceline or 1
            line_end = line_start
            
            # Sử dụng etree.tostring để lấy chính xác thẻ XML thô của field
            try:
                snippet_bytes = etree.tostring(elem, encoding="utf-8", pretty_print=True)
                snippet = snippet_bytes.decode("utf-8").strip()
            except Exception:
                snippet = ""

            is_external = elem.get("external") == "true"
            filter_source = elem.get("filterSource")

            if not is_external or filter_source == "Tidy":
                fields.append({
                    "name": name,
                    "line_start": line_start,
                    "line_end": line_end,
                    "snippet": snippet,
                    "header_v": header_v,
                    "header_e": header_e,
                    "type": elem.get("type"),
                    "external": is_external
                })

            # Phân tích tag <items> con để lấy grid_refs và lookup_refs
            items_list = elem.xpath(".//*[local-name()='items']")
            items_elem = items_list[0] if items_list else None
            
            style = None
            controller = None
            
            if items_elem is not None:
                style = items_elem.get("style")
                controller = items_elem.get("controller")
            
            # Fallback regex check nếu items_elem rỗng hoặc thiếu controller
            raw_elem_str = ""
            if not controller:
                try:
                    raw_elem_str = etree.tostring(elem, encoding="utf-8").decode("utf-8")
                except Exception:
                    raw_elem_str = ""
                # Tìm <items style="..." controller="..." /> hoặc style/controller ngược lại
                match_ctrl = re.search(r'controller\s*=\s*["\']([^"\']+)["\']', raw_elem_str)
                match_style = re.search(r'style\s*=\s*["\']([^"\']+)["\']', raw_elem_str)
                if match_ctrl:
                    controller = match_ctrl.group(1)
                    style = match_style.group(1) if match_style else None

            if controller:
                if style == "Grid":
                    foreign_key = None
                    if items_elem is not None:
                        # Dùng xpath local-name() cho ForeignKey item
                        fk_items = items_elem.xpath(".//*[local-name()='item' and @value='ForeignKey']")
                        fk_item = fk_items[0] if fk_items else None
                        if fk_item is not None:
                            text_elems = fk_item.xpath(".//*[local-name()='text']")
                            text_elem = text_elems[0] if text_elems else None
                            if text_elem is not None:
                                v_val = text_elem.get("v") or ""
                                match = re.search(r"String:\s*([a-zA-Z0-9_]+)", v_val)
                                if match:
                                    foreign_key = match.group(1)
                    else:
                        # Regex fallback cho ForeignKey
                        if not raw_elem_str:
                            try:
                                raw_elem_str = etree.tostring(elem, encoding="utf-8").decode("utf-8")
                            except Exception:
                                raw_elem_str = ""
                        match_fk = re.search(r'String:\s*([a-zA-Z0-9_]+)', raw_elem_str)
                        if match_fk:
                            foreign_key = match_fk.group(1)
                            
                    grid_refs.append({
                        "field_name": name,
                        "controller": controller,
                        "foreign_key": foreign_key
                    })
                elif style in {"AutoComplete", "Lookup"}:
                    lookup_refs.append({
                        "field_name": name,
                        "controller": controller
                    })

        # Trích xuất SQL & JS CDATA blocks
        sql_blocks = []
        js_blocks = []

        for elem in root.iter():
            if not isinstance(elem.tag, str):
                continue
            local_name = etree.QName(elem.tag).localname
            if elem.text:
                line_num = elem.sourceline or 1
                if local_name in {"query", "command", "action"}:
                    sql_blocks.append({
                        "content": elem.text,
                        "line": line_num,
                        "tag": local_name
                    })
                elif local_name in {"clientScript", "script"}:
                    js_blocks.append({
                        "content": elem.text,
                        "line": line_num,
                        "tag": local_name
                    })

        return {
            "file_path": str(file_path),
            "relative_path": os.path.relpath(file_path, self.controllers_root),
            "folder_type": folder_type,
            "folder_subtype": folder_subtype,
            "xml_root_tag": xml_root_tag,
            "xml_namespace": xmlns,
            "table": table,
            "code_field": code_field,
            "title_v": title_v,
            "title_e": title_e,
            "entities": system_entities,
            "param_entities": list(set(param_entities)),
            "fields": fields,
            "grid_refs": grid_refs,
            "lookup_refs": lookup_refs,
            "sql_blocks": sql_blocks,
            "js_blocks": js_blocks,
            "file_size": len(raw_content),
            "error": None
        }

    def _build_empty_result(self, file_path: Path, raw_content: str, param_entities: List[str], system_entities: List[Dict], error_msg: str) -> Dict[str, Any]:
        """Tạo kết quả rỗng khi XML parser gặp lỗi (thường là file .ent, .txt hoặc XML lỗi cấu trúc)."""
        rel_parts = file_path.relative_to(self.controllers_root).parts
        folder_type = rel_parts[0]
        folder_subtype = rel_parts[1] if len(rel_parts) > 2 else ""
        
        return {
            "file_path": str(file_path),
            "relative_path": os.path.relpath(file_path, self.controllers_root),
            "folder_type": folder_type,
            "folder_subtype": folder_subtype,
            "xml_root_tag": "",
            "xml_namespace": "",
            "table": None,
            "code_field": None,
            "title_v": "",
            "title_e": "",
            "entities": system_entities,
            "param_entities": list(set(param_entities)),
            "fields": [],
            "grid_refs": [],
            "lookup_refs": [],
            "sql_blocks": [],
            "js_blocks": [],
            "file_size": len(raw_content),
            "error": error_msg
        }


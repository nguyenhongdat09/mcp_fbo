import re
from typing import Dict, List, Set, Any
from xml_codegraph.rules.regex_rules import JS_PATTERNS

class JsBlockParser:
    @staticmethod
    def parse(js_content: str) -> Dict[str, Any]:
        """
        Phân tích Javascript thô để tìm các hàm tự định nghĩa,
        các hàm helper của FBO (g.something) và các biến trường UI (g.$a.field).
        """
        if not js_content:
            return {"functions": [], "helper_calls": [], "client_fields": []}

        # Loại bỏ các dòng comment trong JS trước khi quét
        # Loại bỏ comment // ...
        clean_js = re.sub(r"//.*$", "", js_content, flags=re.MULTILINE)
        # Loại bỏ comment /* ... */
        clean_js = re.sub(r"/\*.*?\*/", "", clean_js, flags=re.DOTALL)

        # 1. Quét định nghĩa functions
        functions: Set[str] = set()
        for match in JS_PATTERNS["functions"].finditer(clean_js):
            functions.add(match.group(1).strip())

        # 2. Quét cuộc gọi hàm helper g.*
        helper_calls: Set[str] = set()
        for match in JS_PATTERNS["fbo_helper_calls"].finditer(clean_js):
            helper_name = match.group(1).strip()
            if helper_name not in {"$a"}: # bỏ qua ký hiệu $a đặc biệt đại diện cho client fields
                helper_calls.add(helper_name)

        # 3. Quét các trường client g.$a.field
        client_fields: Set[str] = set()
        for match in JS_PATTERNS["client_fields"].finditer(clean_js):
            client_fields.add(match.group(1).strip())

        # 4. Quét các cuộc gọi g.showForm('FormName')
        show_form_calls: Set[str] = set()
        show_form_pattern = re.compile(r"\bg\s*\.\s*showForm\s*\(\s*['\"]([a-zA-Z0-9_\$]+)['\"]\s*\)")
        for match in show_form_pattern.finditer(clean_js):
            show_form_calls.add(match.group(1).strip())

        return {
            "functions": sorted(list(functions)),
            "helper_calls": sorted(list(helper_calls)),
            "client_fields": sorted(list(client_fields)),
            "show_form_calls": sorted(list(show_form_calls))
        }

import re
from typing import Dict, List, Set, Any
from xml_fbograph.rules.regex_rules import SQL_PATTERNS

class SqlBlockParser:
    @staticmethod
    def parse(sql_content: str) -> Dict[str, Any]:
        """
        Phân tích cú pháp SQL thô để trích xuất các stored procedure,
        các bảng dữ liệu và các biến được dùng.
        """
        if not sql_content:
            return {"tables": [], "stored_procedures": [], "variables": []}
            
        # Loại bỏ comment trong SQL trước khi scan regex
        # Loại bỏ comment dạng -- ...
        clean_sql = re.sub(r"--.*$", "", sql_content, flags=re.MULTILINE)
        # Loại bỏ comment dạng /* ... */
        clean_sql = re.sub(r"/\*.*?\*/", "", clean_sql, flags=re.DOTALL)

        # 1. Quét Stored Procedures
        procedures: Set[str] = set()
        for match in SQL_PATTERNS["stored_procedures"].finditer(clean_sql):
            proc_name = match.group(1).strip()
            # Loại bỏ các từ khóa nhiễu nếu regex bắt nhầm
            if proc_name.lower() not in {"select", "insert", "update", "delete", "begin", "end"}:
                procedures.add(proc_name)

        # 2. Quét các bảng DB tác động
        tables: Set[str] = set()
        for match in SQL_PATTERNS["tables"].finditer(clean_sql):
            table_name = match.group(1).strip()
            # Loại bỏ các từ khóa giả
            if table_name.lower() not in {"select", "insert", "update", "delete", "begin", "end", "values", "set", "where", "into"}:
                # Loại bỏ các biến bảng như #t, #in, #inquiry
                if not table_name.startswith("#") and not table_name.startswith("@"):
                    tables.add(table_name)

        # 3. Quét các biến
        variables: Set[str] = set()
        for match in SQL_PATTERNS["variables"].finditer(clean_sql):
            variables.add(match.group(1).strip())

        return {
            "tables": sorted(list(tables)),
            "stored_procedures": sorted(list(procedures)),
            "variables": sorted(list(variables))
        }

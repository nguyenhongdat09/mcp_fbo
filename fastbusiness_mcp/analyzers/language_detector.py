"""Language detection in CDATA blocks."""

import re
from ..core.constants import LanguageType, SQL_KEYWORDS, JS_KEYWORDS


class LanguageDetector:
    """Detects programming language in CDATA blocks."""

    def detect(self, code: str, parent_tag: str = "") -> LanguageType:
        """
        Detect language type from code content.

        Args:
            code: Code content
            parent_tag: Parent XML tag name (command, script, action, query)

        Returns:
            Detected language type
        """
        # Quick detection based on parent tag
        if parent_tag in ["command", "action", "query"]:
            return LanguageType.SQL
        elif parent_tag in ["script", "clientScript"]:
            return LanguageType.JAVASCRIPT

        # Content-based detection
        code_lower = code.lower().strip()

        # Check SQL indicators
        sql_score = self._score_sql(code_lower)
        js_score = self._score_javascript(code_lower)

        if sql_score > js_score:
            return LanguageType.SQL
        elif js_score > sql_score:
            return LanguageType.JAVASCRIPT

        return LanguageType.UNKNOWN

    def _score_sql(self, code: str) -> int:
        """Score code as SQL."""
        score = 0

        # Check SQL keywords
        for keyword in SQL_KEYWORDS:
            if re.search(rf"\b{keyword}\b", code):
                score += 2

        # Check SQL-specific patterns
        if re.search(r"@\w+", code):  # @variable
            score += 3
        if re.search(r"@@\w+", code):  # @@system_var
            score += 3
        if "dbo." in code:
            score += 2
        if "exec " in code or "execute " in code:
            score += 3

        return score

    def _score_javascript(self, code: str) -> int:
        """Score code as JavaScript."""
        score = 0

        # Check JS keywords
        for keyword in JS_KEYWORDS:
            if re.search(rf"\b{keyword}\b", code):
                score += 2

        # Check JS-specific patterns
        if re.search(r"\.getItemValue\(", code):
            score += 5
        if re.search(r"\.setItemValue\(", code):
            score += 5
        if re.search(r"\bsender\b", code):
            score += 3
        if re.search(r"\be\.type\b", code):
            score += 3
        if "function " in code:
            score += 3

        return score

"""Phân loại Page.0xx cho menu mới ở dự án SP30+ (2 lần gọi Jev)."""

from tool_help.classify_page.directive import kind_of
from tool_help.classify_page.directive import resolve as directive
from tool_help.classify_page.questions import build_questions, page_questions

__all__ = ["build_questions", "directive", "kind_of", "page_questions"]

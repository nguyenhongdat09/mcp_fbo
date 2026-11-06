"""Gom đáp án 2 lần gọi Jev → chỉ thị bắt buộc cho PageMetadata.xml."""

from typing import Callable

from tool_help.classify_page.catalog import CATEGORY_PAGE, PAGE_TEMPLATES
from tool_help.classify_page.questions import (
    IS_NEW_MENU, KIND_CATEGORY, KIND_REPORT, KIND_VOUCHER, MENU_KIND,
    PAGE_TEMPLATE)

NEW_MENU_MIN = 0.8
PAGE_MIN = 0.8

_DIRECTIVE = (
    "Sau khi xem xét kĩ yêu cầu tôi nhận thấy đây là yêu cầu tạo mới 1 "
    "menu nên hãy thêm menu vào App_Data/PageMetadata.xml loại là "
    "{page_id}. Đây là bắt buộc của user. Nếu xem xét lại thấy không đúng "
    "và quyết định không khai báo {page_id} vào App_Data/PageMetadata.xml "
    "thì phải hỏi user trước khi làm")

_NO_PAGE = (
    "Tôi đã xem xét rất kỹ và không thấy Page ID nào hợp lý để thêm vào "
    "App_data/PageMetadata.xml. Đây là lệnh của user. Hãy hỏi user rằng "
    "Page nào là hợp lý để làm cho chức năng này và không được tự ý bịa ra "
    "Page và tự thêm và App_data/PageMetadata.xml")

_KINDS = (KIND_REPORT, KIND_VOUCHER, KIND_CATEGORY)


def _new_menu_prob(answers: dict) -> float:
    a = answers.get(IS_NEW_MENU) or {}
    try:
        return float(a.get("noul") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _kind(answers: dict) -> str | None:
    ans = answers.get(MENU_KIND) or {}
    probs = {k: float(v) for k, v in (ans.get("probabilities") or {}).items()
             if k in _KINDS and isinstance(v, (int, float))}
    if probs:
        return max(probs, key=probs.get)
    return ans.get("choice") if ans.get("choice") in _KINDS else None


def kind_of(answers: dict) -> str | None:
    """Loại menu nếu Jev xác định đây là tạo mới menu (> 80%), ngược lại None."""
    if not answers or _new_menu_prob(answers) <= NEW_MENU_MIN:
        return None
    return _kind(answers)


def _page_probs(page_answers: dict, allowed) -> dict[str, float]:
    ans = (page_answers or {}).get(PAGE_TEMPLATE) or {}
    return {k: float(v) for k, v in (ans.get("probabilities") or {}).items()
            if k in allowed and isinstance(v, (int, float))}


def resolve(answers: dict,
            ask_pages: Callable[[str], dict | None] | None = None
            ) -> dict | None:
    """answers: đáp án lần gọi 1. ask_pages(kind) → đáp án lần gọi 2 (hoặc
    None nếu lỗi). Danh mục → Page.001 thẳng; báo cáo/chứng từ → Page có
    xác suất > 80%, không có thì yêu cầu hỏi user."""
    kind = kind_of(answers)
    if kind is None:
        return None
    base = {"kind": kind,
            "new_menu_probability": round(_new_menu_prob(answers), 3)}
    if kind == KIND_CATEGORY:
        return {"page_directive": _DIRECTIVE.format(page_id=CATEGORY_PAGE),
                "page_template": {**base, "choice": CATEGORY_PAGE,
                                  "probability": 1.0}}
    if ask_pages is None:
        return None
    from tool_help.classify_page.catalog import REPORT_PAGES, VOUCHER_PAGES
    allowed = REPORT_PAGES if kind == KIND_REPORT else VOUCHER_PAGES
    page_answers = ask_pages(kind)
    if page_answers is None:
        return None
    probs = _page_probs(page_answers, allowed)
    top = sorted(probs.items(), key=lambda kv: -kv[1])
    top = {k: round(v, 3) for k, v in top if v >= 0.05}
    choice = max(probs, key=probs.get) if probs else None
    if choice in PAGE_TEMPLATES and probs[choice] > PAGE_MIN:
        return {"page_directive": _DIRECTIVE.format(page_id=choice),
                "page_template": {**base, "choice": choice,
                                  "probability": round(probs[choice], 3),
                                  "candidates": top}}
    return {"page_directive": _NO_PAGE,
            "page_template": {**base, "choice": None, "candidates": top}}

"""classify_page: câu hỏi Jev SP30+ + chỉ thị khai báo PageMetadata.xml."""

import json

import pytest

from tool_help import classify_page, service
from tool_help.classify_page.catalog import PAGE_TEMPLATES
from tool_help.service import tool_help

FAKE_CFG = {"api_key": "k", "base_url": "http://x",
            "confidence_act": 0.7, "confidence_review": 0.4}
SP30 = {"path": r"\\srv\FBI\DIVN\FBISP30\App_Data\Controllers\Filter\x.xml"}
LEGACY = {"path": r"\\srv\FBO\TA_VN\SP2261\App_Data\Controllers\Filter\x.xml"}
UR = "Gen menu Bảng cân đối VAS - USGAAP sang menu Bảng cân đối VAS - IFRS"


@pytest.fixture(autouse=True)
def _clear_cache():
    service._RESULT_CACHE.clear()
    yield
    service._RESULT_CACHE.clear()


def _choice(probs):
    return {"type": "choice", "choice": max(probs, key=probs.get),
            "probabilities": probs}


def _run(monkeypatch, new_menu, kind, pages, ctx, fail_pages=False):
    calls = []

    def fake(cfg, state, questions):
        calls.append((state, questions))
        if "page_template" in questions:
            if fail_pages:
                return {"ok": False, "error": "x"}
            return {"ok": True, "answers": {"page_template": _choice(pages)},
                    "usage": {"input_tokens": 2, "output_tokens": 2}}
        return {"ok": True, "usage": {"input_tokens": 1, "output_tokens": 1},
                "answers": {
                    "step1_tool": _choice({"save_as_existing": 0.9}),
                    "is_new_menu": {"noul": new_menu},
                    "menu_kind": _choice({kind: 0.95})}}

    import jev
    monkeypatch.setattr(jev, "ask_jev", fake)
    out = json.loads(tool_help("Clone báo cáo", jev_config=FAKE_CFG,
                               context={"task_requirement": UR, **ctx}))
    return out, calls


def test_catalog_range():
    assert "Page.020" in PAGE_TEMPLATES and "Page.024" in PAGE_TEMPLATES
    assert "Page.025" not in PAGE_TEMPLATES


def test_report_page020_two_calls(monkeypatch):
    out, calls = _run(monkeypatch, 0.94, "report",
                      {"Page.020": 0.96, "Page.004": 0.04}, SP30)
    assert len(calls) == 2
    assert "is_new_menu" in calls[0][1] and "menu_kind" in calls[0][1]
    assert "page_template" not in calls[0][1]
    assert set(calls[1][0]) == {"task_requirement"}
    assert set(calls[1][1]["page_template"]["criteria"]) == {
        "Page.003", "Page.004", "Page.017", "Page.020", "Query"}
    assert "Page.020" in out["page_directive"]
    assert "App_Data/PageMetadata.xml" in out["page_directive"]
    assert out["page_template"]["choice"] == "Page.020"
    assert out["page_template"]["kind"] == "report"


def test_voucher_uses_voucher_pages(monkeypatch):
    out, calls = _run(monkeypatch, 0.94, "voucher",
                      {"Page.013": 0.9, "Page.012": 0.1}, SP30)
    assert "Page.012" in calls[1][1]["page_template"]["criteria"]
    assert "Page.020" not in calls[1][1]["page_template"]["criteria"]
    assert out["page_template"]["choice"] == "Page.013"


def test_category_is_page001_no_second_call(monkeypatch):
    out, calls = _run(monkeypatch, 0.94, "category", {}, SP30)
    assert len(calls) == 1
    assert out["page_template"]["choice"] == "Page.001"
    assert "Page.001" in out["page_directive"]


def test_no_page_above_80_asks_user(monkeypatch):
    out, _ = _run(monkeypatch, 0.94, "report",
                  {"Page.004": 0.5, "Page.020": 0.4, "Page.017": 0.1}, SP30)
    assert "không thấy Page ID nào hợp lý" in out["page_directive"]
    assert out["page_template"]["choice"] is None


def test_page_call_failure_no_directive(monkeypatch):
    out, _ = _run(monkeypatch, 0.94, "report", {}, SP30, fail_pages=True)
    assert "page_directive" not in out


def test_no_directive_when_not_new_menu(monkeypatch):
    out, calls = _run(monkeypatch, 0.5, "report", {"Page.020": 0.9}, SP30)
    assert len(calls) == 1 and "page_directive" not in out


def test_legacy_project_untouched(monkeypatch):
    out, calls = _run(monkeypatch, 0.99, "report", {"Page.020": 0.9}, LEGACY)
    assert "is_new_menu" not in calls[0][1] and "menu_kind" not in calls[0][1]
    assert len(calls) == 1 and "page_directive" not in out


def test_directive_ignores_unknown_page():
    ans = {"is_new_menu": {"noul": 0.99}, "menu_kind": _choice({"report": 1.0})}
    assert classify_page.directive(
        ans, lambda k: {"page_template": {"probabilities": {"Page.099": 1.0}}}
    )["page_template"]["choice"] is None

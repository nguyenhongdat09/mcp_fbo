"""Lời nhắc cho agent theo bản: bản cũ chỉ nói .aspx, SP30+ chỉ nói dòng <page>."""

import pytest

from clone_things.type4_template import run_type4_template, template_root
from find_connect_by_path.project_version import (
    generation_of,
    render_by_generation,
    render_tree,
    resolve_generation,
    to_page_wording,
)
from tool_help import cards
from tool_help.notices import NOTICE_RULES

# Chỉ báo "đang nói về bản mới" / "đang nói về bản cũ" trong văn bản gửi agent.
NEW_MARKERS = ("<page", "Page.0", "Metadata/Page", "page_entries")
OLD_MARKERS = ("Main/", "LoadControl", 'Controller="', "Main aspx", "aspx")


def test_generation_of():
    assert generation_of(r"z:\FBI\DIVN\FBISP30") == "metadata"
    assert generation_of("//srv/x/FBISP2422") == "legacy"
    assert generation_of("//srv/x/proj") is None
    assert generation_of(None) is None


def test_render_by_generation_each_side():
    t = "Trang: ⟪L:file .aspx⟫⟪N:dòng <page>⟫ xong; ⟪L:chỉ cũ⟫."
    assert render_by_generation(t, "legacy") == "Trang: file .aspx xong; chỉ cũ."
    assert render_by_generation(t, "metadata") == "Trang: dòng <page> xong; ."
    both = render_by_generation(t, None)
    assert "SP<30: file .aspx; SP30+: dòng <page>" in both and "chỉ cũ" in both
    assert "⟪" not in both and "⟫" not in both
    assert render_by_generation("không markup", "legacy") == "không markup"


def test_render_tree_nested():
    obj = {"a": ["x ⟪L:cũ⟫⟪N:mới⟫"], "b": {"c": "⟪N:mới⟫"}, "n": 3}
    assert render_tree(obj, "metadata") == {"a": ["x mới"], "b": {"c": "mới"}, "n": 3}


def test_resolve_generation_from_context_path():
    assert resolve_generation({"path": r"z:\FBI\DIVN\FBISP30\App_Data\Controllers\Dir\x.xml"}) == "metadata"
    assert resolve_generation({"path": "//srv/FBI/TTI/FBISP2422/Main/a.aspx"}) == "legacy"
    assert resolve_generation({"file_path": r"\\srv\FBO\TA_VN\SP2261\Web.config"}) == "legacy"


def _agent_texts():
    """Mọi chuỗi gửi cho agent từ lớp tool_help (pitfalls, workflow, notices, files)."""
    out = []
    for card in cards.TASK_TYPES.values():
        out.extend(card.get("pitfalls") or [])
    for req in cards.REQUIREMENT_TYPES.values():
        out.extend(req.get("workflow") or [])
    out.extend(r["text"] for r in NOTICE_RULES)
    for name in cards.REQUIREMENT_TYPES:
        blk = cards.template_block(name)
        if blk:
            out.extend(blk["files"])
    return out


def test_agent_texts_clean_per_generation():
    texts = _agent_texts()
    assert texts
    for t in texts:
        legacy = render_by_generation(t, "legacy")
        new = render_by_generation(t, "metadata")
        assert "⟪" not in legacy and "⟫" not in legacy
        assert "⟪" not in new and "⟫" not in new
        for m in NEW_MARKERS:
            assert m not in legacy, f"bản cũ bị nhắc page: {m!r} trong {t[:80]!r}"
        for m in OLD_MARKERS:
            # link menu '<id>.aspx' là link thật, không phải file aspx
            cleaned = new.replace(".aspx')", "").replace(".aspx'", "")
            assert m not in cleaned, f"SP30 bị nhắc aspx: {m!r} trong {t[:80]!r}"


@pytest.mark.parametrize(
    "tpl",
    sorted(p.parent.name for p in template_root().glob("*/manifest.yaml")),
)
def test_type4_edit_guide_wording_per_generation(tmp_path, tpl):
    legacy = tmp_path / "FBISP2422"
    legacy.mkdir()
    new = tmp_path / "FBISP30"
    (new / "App_Data" / "Metadata" / "Fragments").mkdir(parents=True)
    (new / "App_Data" / "Metadata" / "Fragments" / "Page.001.xml").write_text("<r/>", encoding="utf-8")
    (new / "App_Data" / "Metadata" / "Page.001.xml").write_text("", encoding="utf-8")

    r_old = run_type4_template(object=tpl, new_name="zcx", project_target=str(legacy), execute=False)
    r_new = run_type4_template(object=tpl, new_name="zcx", project_target=str(new), execute=False)
    for m in NEW_MARKERS:
        assert m not in r_old["edit_guide"], f"{tpl}: bản cũ bị nhắc {m}"
    guide = r_new["edit_guide"].replace(".aspx'", "")
    assert "aspx" not in guide.lower(), f"{tpl}: SP30 vẫn nhắc aspx"
    assert "Main/" not in guide


def test_to_page_wording_examples():
    s = "v=/e= ở Main/zcx.aspx. ASPX ATTR: ReadOnly. Main aspx zcPLHd.aspx"
    out = to_page_wording(s)
    assert "aspx" not in out.lower()
    assert 'dòng <page id="zcx">' in out

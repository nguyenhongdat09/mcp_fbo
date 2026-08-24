"""Probe 3 FBO screen types: report, category, voucher — collect $find _type _fields."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URLS = [
    ("report", "http://172.168.5.14/BinhDienMK/Main/rpt_bkctsstt.aspx?id=15.02.39"),
    ("category", "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"),
    ("voucher", "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"),
]

CLASSIFY_JS = """
() => {
  function findComponents() {
    var out = { mainReport: null, searchExtender: null, dirExtender: null, allIds: [] };
    if (typeof Sys === 'undefined' || !Sys.Application) return out;
    var comps = Sys.Application.getComponents ? Sys.Application.getComponents() : [];
    for (var i = 0; i < comps.length; i++) {
      var c = comps[i];
      var id = c.get_id ? c.get_id() : '';
      if (!id) continue;
      if (id.indexOf('MainReport') >= 0 && id.indexOf('searchExtender') < 0 && id.indexOf('dirExtender') < 0) {
        if (!out.mainReport || id.length < out.mainReport.id.length) out.mainReport = { id: id, type: c._type };
      }
      if (id.indexOf('MainReport') >= 0 && id.indexOf('searchExtender') >= 0) {
        out.searchExtender = { id: id, type: c._type };
      }
      if (id.indexOf('dirExtender') >= 0 && id.indexOf('FormLookup') < 0) {
        if (!out.dirExtender) out.dirExtender = { id: id, type: c._type };
      }
    }
    return out;
  }

  function summarizeFields(fields) {
    if (!fields || !fields.length) return [];
    var res = [];
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i];
      res.push({
        name: f.Name || f.AliasName || '',
        alias: f.AliasName || '',
        header: f.HeaderText || f.Label || '',
        type: f.Type || '',
        allowNulls: f.AllowNulls,
        readOnly: f.ReadOnly,
        hidden: f.Hidden,
        visible: f.Visible,
      });
    }
    return res;
  }

  function getComp(id) {
    try { return $find(id); } catch (e) { return null; }
  }

  var comps = findComponents();
  var result = {
    url: location.href,
    title: document.title,
    components: comps,
    mainReport_type: null,
    searchExtender_type: null,
    dirExtender_type: null,
    mainReport_fields: [],
    searchExtender_fields: [],
    dirExtender_fields: [],
    toolbar_buttons: [],
    modal_visible: !!document.querySelector('.ModalBackground, [id*=ModalPopupBehavior_backgroundElement]'),
    has_f: typeof f !== 'undefined' && f && typeof f !== 'boolean' && typeof f.setItemValue === 'function',
    g_type: typeof g,
  };

  if (comps.mainReport) {
    var mr = getComp(comps.mainReport.id);
    if (mr) {
      result.mainReport_type = mr._type;
      result.mainReport_fields = summarizeFields(mr._fields);
    }
  }
  if (comps.searchExtender) {
    var se = getComp(comps.searchExtender.id);
    if (se) {
      result.searchExtender_type = se._type;
      result.searchExtender_fields = summarizeFields(se._fields);
    }
  }
  if (comps.dirExtender) {
    var de = getComp(comps.dirExtender.id);
    if (de) {
      result.dirExtender_type = de._type;
      result.dirExtender_fields = summarizeFields(de._fields);
    }
  }

  var btns = document.querySelectorAll('[id*=ToolbarButton_]');
  for (var b of btns) {
    var t = (b.innerText || b.textContent || '').trim();
    if (t) result.toolbar_buttons.push({ id: b.id, text: t, onclick: (b.getAttribute('onclick') || '').substring(0, 120) });
  }

  return result;
}
"""

TOOLBAR_PROBE_JS = """
(btnText) => {
  var btns = document.querySelectorAll('[id*=ToolbarButton_], button, .ToolbarTextButton');
  for (var b of btns) {
    var t = (b.innerText || b.textContent || '').trim();
    if (t === btnText || t.indexOf(btnText) >= 0) {
      return { found: true, id: b.id, text: t, onclick: b.getAttribute('onclick') };
    }
  }
  return { found: false };
}
"""


def probe_url(session: ChromeSession, cfg: dict, label: str, url: str) -> dict:
    browser = session.connect(cfg.get("cdp_url", "http://localhost:9222"))
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    record: dict = {"label": label, "url": url, "stages": []}

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
        base = page.evaluate(CLASSIFY_JS)
        record["stages"].append({"stage": "initial_load", "data": base})

        # Report: try Nhận if searchExtender + required fields
        if label == "report" and base.get("searchExtender_fields"):
            required = [f for f in base["searchExtender_fields"] if f.get("allowNulls") is False and f.get("name")]
            record["required_filter_fields"] = required
            # Fill sample ma_vt if present
            fill_js = """
            (fieldName, val) => {
              var comps = Sys.Application.getComponents();
              for (var i = 0; i < comps.length; i++) {
                var c = comps[i];
                var id = c.get_id ? c.get_id() : '';
                if (id.indexOf('searchExtender') >= 0 && c._fields) {
                  for (var j = 0; j < c._fields.length; j++) {
                    if (c._fields[j].Name === fieldName || c._fields[j].AliasName === fieldName) {
                      try {
                        if (typeof c.setItemValue === 'function') { c.setItemValue(fieldName, val); return { ok: true, via: 'setItemValue' }; }
                      } catch(e) {}
                    }
                  }
                }
              }
              var inp = document.querySelector('[id*="' + fieldName + '"]');
              if (inp) { inp.value = val; if (inp.onchange) inp.onchange(); return { ok: true, via: 'dom' }; }
              return { ok: false };
            }
            """
            for fname in ["ma_vt", "ma_kho", "fromDate", "toDate"]:
                if any(f.get("name") == fname or f.get("alias") == fname for f in base["searchExtender_fields"]):
                    r = page.evaluate(fill_js, fname, "TEST" if "ma_" in fname else "2025-01-01")
                    record.setdefault("fill_attempts", []).append({fname: r})

            nhận = page.evaluate(TOOLBAR_PROBE_JS, "Nhận")
            record["nhan_button"] = nhận
            if nhận.get("found"):
                try:
                    page.locator(f"#{nhận['id']}").first.click(timeout=5000)
                    time.sleep(4)
                    after = page.evaluate(CLASSIFY_JS)
                    record["stages"].append({"stage": "after_nhan", "data": after})
                except Exception as ex:
                    record["after_nhan_error"] = str(ex)

        # Category: probe grid fields
        if label == "category":
            record["classification_note"] = "mainReport._type empty => danh muc"

        # Voucher: click Moi if no modal
        if label == "voucher" and not base.get("modal_visible"):
            moi = page.evaluate(TOOLBAR_PROBE_JS, "Mới")
            record["moi_button"] = moi
            if moi.get("found"):
                try:
                    page.locator(f"#{moi['id']}").first.click(timeout=10000)
                    time.sleep(3)
                    after = page.evaluate(CLASSIFY_JS)
                    record["stages"].append({"stage": "after_moi", "data": after})
                    # sample ma_kh in dirExtender
                    ma_kh_inp = page.evaluate(
                        """() => {
                      var el = document.querySelector('[id*="dirExtender_form_ma_kh"]');
                      if (!el) return { found: false };
                      el.value = 'TKH001';
                      if (el.onchange) el.onchange();
                      return { found: true, id: el.id, value: el.value };
                    }"""
                    )
                    record["ma_kh_fill"] = ma_kh_inp
                    ten = page.evaluate(
                        """() => {
                      var el = document.querySelector('[id*="dirExtender_form_ten_kh"]');
                      return el ? el.value : null;
                    }"""
                    )
                    record["ten_kh_after"] = ten
                except Exception as ex:
                    record["after_moi_error"] = str(ex)
        elif label == "voucher" and base.get("modal_visible"):
            ma_kh_inp = page.evaluate(
                """() => {
              var el = document.querySelector('[id*="dirExtender_form_ma_kh"]');
              if (!el) return { found: false };
              el.value = 'TKH001';
              if (el.onchange) el.onchange();
              return { found: true, id: el.id, value: el.value };
            }"""
            )
            record["ma_kh_fill_existing_modal"] = ma_kh_inp

    except Exception as ex:
        record["error"] = str(ex)
    finally:
        try:
            page.close()
        except Exception:
            pass

    return record


def main():
    cfg = load_chrome_debug_config()
    session = ChromeSession.get_instance()
    session.disconnect()
    session.set_config(cfg)

    results = []
    for label, url in URLS:
        print(f"\n========== PROBE {label}: {url} ==========")
        rec = probe_url(session, cfg, label, url)
        results.append(rec)
        print(json.dumps(rec, ensure_ascii=False, indent=2)[:8000])

    out_path = Path(__file__).parent.parent / "docs" / "doc_fix" / "_probe_three_screens_raw.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    print(f"\nSaved raw: {out_path}")


if __name__ == "__main__":
    main()

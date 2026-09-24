"""Crawl toàn bộ màn hình FBO: login → từng leaf URL → snapshot → JeV
classify → probe an toàn theo loại màn → report JSON incremental.

Probe (read-only / tự rollback):
  - list      : row_count, select_row(1), New→cancel (nếu toolbar có New)
  - voucher   : (form tự mở) → cancel
  - report_*  : toolbar/fields only; Retrieve chỉ khi là nút hiển nhiên
  - dialog_only: classify_dialog + message
  - unknown   : clickables có sẵn trong state

KHÔNG BAO GIỜ: Save, Delete, Post, Duyệt, Tính, Nhận, Chấp nhận — mutating.
Resume: skip url đã có trong crawl_report.json.
"""
import json
import sys
import time
import traceback
from urllib.parse import urljoin

sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from browser_fbo import session as S
from browser_fbo import smart as SM
from browser_fbo.state import capture_state
from fastbusiness_mcp.mcp_app import get_config

BASE = "http://172.168.5.14/HAOHOA/Main/"
MAP = r"E:\PythonProject\mcp_fbo\scratch\menu_map.json"
OUT = r"E:\PythonProject\mcp_fbo\scratch\crawl_report.json"
FP = (r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421"
      r"\App_Data\Controllers\Report\Config\MRTran.ent")

cfg = get_config()
items = json.load(open(MAP, encoding="utf-8"))
try:
    done = json.load(open(OUT, encoding="utf-8"))
except Exception:
    done = {}
# map mới lưu theo url key; migrate cũ nếu cần
results = done if isinstance(done, dict) else {}


def save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


def snap(page, label=""):
    try:
        st = capture_state(S.current_page() or page)
        return st
    except Exception as e:
        return {"error": f"snapshot: {e}", "url": getattr(page, "url", "?")}


def jev(st, intent):
    try:
        return SM.dispatch("classify_screen", st, intent, cfg)
    except Exception as e:
        return {"error": f"jev: {e}"}


def jev_dialog(st, intent):
    try:
        return SM.dispatch("classify_dialog", st, intent, cfg)
    except Exception as e:
        return {"error": f"jev: {e}"}


def probe_list(rec):
    """row_count + select_row(1) + New→cancel."""
    page = S.current_page()
    rc = BS.browser_fbo(action="row_count", config=cfg)
    rec["row_count"] = rc.get("result")
    rows = ((rc.get("result") or {}).get("rows")
            or (rc.get("state") or {}).get("grid", {}).get("row_count") or 0)
    rec["rows"] = rows
    if rows:
        r = BS.browser_fbo(action="select_row", row=1, config=cfg)
        rec["select_row"] = {"ok": r["success"], "err": r.get("error")}
        if r["success"]:
            g = BS.browser_fbo(action="grid_get", row=1, col="1", config=cfg)
            rec["grid_get_1_1"] = g.get("result")
    # New → cancel: mở form rồi hủy — đo coverage nút New + dialog open/close
    tb = [t.lower() for t in (rec["state"].get("toolbar") or [])]
    if any("new" in t or "thêm" in t or "them" in t for t in tb):
        r = BS.browser_fbo(action="command", command_name="New",
                           command_argument="0", config=cfg)
        time.sleep(1.5)
        rec["new_open"] = {"ok": r["success"], "err": r.get("error")}
        st2 = snap(page, "after_new")
        rec["new_dialog"] = {"dialogs": len(st2.get("dialogs") or []),
                             "fields": len(st2.get("form_fields") or []),
                             "screen": st2.get("screen")}
        c = BS.browser_fbo(action="cancel", config=cfg)
        time.sleep(0.8)
        rec["new_cancel"] = {"ok": c["success"], "err": c.get("error"),
                             "res": c.get("result")}


def probe_dialog(rec, st_full):
    rec["dialog_jev"] = jev_dialog(st_full, rec["text"])
    # dismiss an toàn — đọc message (không confirm yes)
    r = BS.browser_fbo(action="message", dismiss=True, config=cfg)
    rec["message"] = {"ok": r["success"], "res": r.get("result")}


def probe_report(rec):
    """Report screens: chỉ ghi nhận filter fields + toolbar, KHÔNG run."""
    st = rec["state"]
    rec["filter_fields"] = len(st.get("form_fields") or [])


# ---- main loop ----
r = BS.browser_fbo(action="login", file_path=FP, user="ADMIN",
                   password="2222222222", config=cfg)
print("login:", r["success"], str(r.get("error"))[:120], flush=True)
if not r["success"]:
    sys.exit(1)
time.sleep(2)

n = 0
for it in items:
    url = urljoin(BASE, it["url"])
    key = it["url"]
    if key in results:
        v = results[key]
        clean = (
            v.get("state")
            and not v.get("errors")
            and (v.get("new_open") or {}).get("ok") is not False
            and (v.get("new_cancel") or {}).get("ok") is not False
            and (v.get("select_row") or {}).get("ok") is not False
        )
        if clean:
            continue  # resume — chỉ re-run màn có lỗi/probe fail
    n += 1
    rec = {"text": it["text"], "url": url, "probes": {}, "errors": []}
    t0 = time.time()
    try:
        page = S.current_page()
        if page is None or page.is_closed():
            raise RuntimeError("page dead — cần relaunch")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2.2)
        st = snap(page)
        rec["state"] = {
            "screen": st.get("screen"), "url": st.get("url"),
            "title": st.get("title"),
            "toolbar": st.get("toolbar"),
            "dialogs": len(st.get("dialogs") or []),
            "fields": len(st.get("form_fields") or []),
            "grid_rows": (st.get("grid") or {}).get("row_count"),
            "clickables": (st.get("clickables") or [])[:15],
            "frames": st.get("frames"),
            "menu_links": len(st.get("menu_links") or []),
        }
        # redirect về login = session hết
        if "login.aspx" in (st.get("url") or "").lower():
            rec["errors"].append("redirected_to_login")
            results[key] = rec
            save()
            r = BS.browser_fbo(action="login", file_path=FP, user="ADMIN",
                               password="2222222222", config=cfg)
            rec["relogin"] = r["success"]
            continue
        # JeV classify luôn — user yêu cầu tận dụng
        rec["jev_screen"] = jev(st, it["text"])
        screen = (rec["jev_screen"].get("screen")
                  if isinstance(rec["jev_screen"], dict) else None) \
            or st.get("screen")
        rec["screen_final"] = screen
        if screen == "list":
            probe_list(rec)
        elif screen == "voucher":
            # form đang mở sẵn → cancel về list rồi probe list
            c = BS.browser_fbo(action="cancel", config=cfg)
            rec["voucher_cancel"] = {"ok": c["success"],
                                     "err": c.get("error")}
            st2 = snap(page)
            rec["state"]["screen_after_cancel"] = st2.get("screen")
            if st2.get("screen") == "list" or (st2.get("grid") or {}):
                rec["state"]["toolbar"] = st2.get("toolbar") or \
                    rec["state"]["toolbar"]
                probe_list(rec)
        elif screen == "dialog_only":
            probe_dialog(rec, st)
        elif screen in ("report_view", "report_filter", "report"):
            probe_report(rec)
    except Exception as e:
        rec["errors"].append(f"{type(e).__name__}: {str(e)[:200]}")
        # page chết → thử relaunch + login lại
        try:
            if S.current_page() is None or S.current_page().is_closed():
                S.close()
                r = BS.browser_fbo(action="login", file_path=FP,
                                   user="ADMIN", password="2222222222",
                                   config=cfg)
                rec["relaunch"] = r["success"]
                time.sleep(2)
        except Exception:
            pass
    rec["elapsed_s"] = round(time.time() - t0, 1)
    results[key] = rec
    save()
    stt = rec["state"].get("screen") if rec.get("state") else "?"
    err = "; ".join(rec["errors"])[:60] if rec["errors"] else ""
    print(f"[{len(results)}/{len(items)}] {it['url']:<42} "
          f"{stt:<12} {err}", flush=True)

# ---- summary ----
from collections import Counter
screens = Counter(v.get("screen_final") or
                  (v.get("state") or {}).get("screen") or "?"
                  for v in results.values())
errs = [k for k, v in results.items() if v.get("errors")]
new_fail = [k for k, v in results.items()
            if (v.get("new_open") or {}).get("ok") is False]
cancel_fail = [k for k, v in results.items()
               if (v.get("new_cancel") or {}).get("ok") is False]
sel_fail = [k for k, v in results.items()
            if (v.get("select_row") or {}).get("ok") is False]
print("\n===== SUMMARY =====")
print("screens:", dict(screens))
print(f"total={len(results)} errors={len(errs)} "
      f"new_fail={len(new_fail)} cancel_fail={len(cancel_fail)} "
      f"select_fail={len(sel_fail)}")
for k in errs[:30]:
    print("  ERR", k, "→", "; ".join(results[k]["errors"])[:100])
BS.browser_fbo(action="close", config=cfg)

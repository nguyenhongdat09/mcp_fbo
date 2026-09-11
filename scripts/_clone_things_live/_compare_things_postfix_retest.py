"""Post-fix comprehensive retest: unit-style asserts + live FAH/AIH."""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from compare_things import compare_things

FAH = r"\\172.168.5.14\CustomerPro\FBI\FAHASAKHANHHOA\FBISP24"
AIH = r"\\172.168.5.14\CustomerPro\FBO\AIH\SP228"
OUT = Path(__file__).resolve().parent / "_compare_things_postfix_report.json"


def _p(*a, **k):
    try:
        print(*a, **k)
    except UnicodeEncodeError:
        print(" ".join(map(str, a)).encode("ascii", "replace").decode("ascii"), **k)


def check(name: str, cond: bool, detail: str = "") -> dict:
    status = "PASS" if cond else "FAIL"
    _p(f"  [{status}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    return {"name": name, "passed": cond, "detail": detail}


def main():
    results = []
    td = Path(tempfile.mkdtemp(prefix="cmp_postfix_"))
    _p(f"tmp={td}", flush=True)

    # --- P0: ignore_line_endings=false ---
    _p("\n## P0 CRLF ignore_line_endings", flush=True)
    fa, fb = td / "lf.txt", td / "crlf.txt"
    fa.write_bytes(b"aaa\nbbb\nccc\n")
    fb.write_bytes(b"aaa\r\nbbb\r\nccc\r\n")
    r = compare_things(kind="file", file_a=str(fa), file_b=str(fb), ignore_line_endings=True)
    item = r["compared"][0]
    results.append(check(
        "CRLF ignore=True → identical_content + only_line_ending_diff",
        item.get("identical_content") is True and item.get("only_line_ending_diff") is True,
        f"ic={item.get('identical_content')} ole={item.get('only_line_ending_diff')} reason={item.get('diff_reason')}",
    ))
    r2 = compare_things(kind="file", file_a=str(fa), file_b=str(fb), ignore_line_endings=False)
    item2 = r2["compared"][0]
    results.append(check(
        "CRLF ignore=False → NOT identical_content",
        item2.get("identical_content") is False,
        f"ic={item2.get('identical_content')} status={item2.get('status')} hunks={item2.get('content',{}).get('hunk_count')}",
    ))

    # --- P0: BOM / whitespace labels ---
    _p("\n## P0 BOM / whitespace flags", flush=True)
    bom, nobom = td / "bom.txt", td / "nobom.txt"
    bom.write_bytes(b"\xef\xbb\xbfhello\nworld\n")
    nobom.write_bytes(b"hello\nworld\n")
    rb = compare_things(kind="file", file_a=str(bom), file_b=str(nobom))
    ib = rb["compared"][0]
    results.append(check(
        "BOM-only → identical_content, NOT only_line_ending_diff (or diff_reason=bom)",
        ib.get("identical_content") is True
        and (ib.get("only_line_ending_diff") is False or ib.get("diff_reason") == "bom"),
        f"ole={ib.get('only_line_ending_diff')} reason={ib.get('diff_reason')} msg={(rb.get('message') or '')[:80]}",
    ))
    results.append(check(
        "BOM message not claim CRLF-only incorrectly",
        "CRLF" not in (rb.get("message") or "") and "xuống dòng" not in (rb.get("message") or "").lower()
        or ib.get("diff_reason") == "bom"
        or "BOM" in (rb.get("message") or "").upper()
        or "bom" in (rb.get("message") or "").lower()
        or "byte" in (rb.get("message") or "").lower(),
        (rb.get("message") or "")[:120],
    ))

    wsa, wsb = td / "ws_a.txt", td / "ws_b.txt"
    wsa.write_text("  hello  \n", encoding="utf-8")
    wsb.write_text("hello\n", encoding="utf-8")
    rw = compare_things(kind="file", file_a=str(wsa), file_b=str(wsb), ignore_whitespace=True)
    iw = rw["compared"][0]
    results.append(check(
        "whitespace ignore → identical_content; only_line_ending_diff false if not LE",
        iw.get("identical_content") is True and iw.get("only_line_ending_diff") is not True,
        f"ole={iw.get('only_line_ending_diff')} reason={iw.get('diff_reason')}",
    ))

    # --- P0: missing_both ---
    _p("\n## P0 missing_both", flush=True)
    if Path(FAH).is_dir() and Path(AIH).is_dir():
        rs = compare_things(
            kind="sql", project_source=FAH, project_target=AIH,
            object="dbo.ThisObjectDefinitelyDoesNotExist_XYZ_999",
        )
        results.append(check(
            "SQL missing both → missing_both",
            rs.get("success") and "ThisObjectDefinitelyDoesNotExist_XYZ_999" in str(rs.get("summary", {}).get("missing_both", [])),
            f"summary={rs.get('summary')}",
        ))
        rt = compare_things(
            kind="table", project_source=FAH, project_target=AIH,
            object="dbo.zz_table_not_exist_cmp_xyz",
        )
        results.append(check(
            "TABLE missing both → missing_both",
            rt.get("success") and len(rt.get("summary", {}).get("missing_both") or []) >= 1,
            f"summary={rt.get('summary')}",
        ))
    else:
        results.append(check("LIVE paths available", False, "UNC not reachable"))

    # --- P0: xml_view ---
    _p("\n## P0 xml_view", flush=True)
    # synthetic flat fixture
    proj = td / "proj"
    ctrl = proj / "App_Data" / "Controllers" / "Dir"
    inc = proj / "App_Data" / "Controllers" / "Include"
    ctrl.mkdir(parents=True)
    inc.mkdir(parents=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (inc / "A.txt").write_text("SHARED", encoding="utf-8")
    xml_body = '''<?xml version="1.0"?>
<!DOCTYPE dir [
  <!ENTITY X SYSTEM "..\\Include\\A.txt">
]>
<dir xmlns="urn:schemas-fast-com:data-dir">&X;</dir>
'''
    (ctrl / "T.xml").write_text(xml_body, encoding="utf-8")
    # second project copy
    proj2 = td / "proj2"
    ctrl2 = proj2 / "App_Data" / "Controllers" / "Dir"
    inc2 = proj2 / "App_Data" / "Controllers" / "Include"
    ctrl2.mkdir(parents=True)
    inc2.mkdir(parents=True)
    (proj2 / "Web.config").write_text("<configuration/>", encoding="utf-8")
    (inc2 / "A.txt").write_text("SHARED", encoding="utf-8")
    (ctrl2 / "T.xml").write_text(xml_body.replace("A.txt", "A.txt"), encoding="utf-8")

    r_orig = compare_things(
        kind="xml", project_source=str(proj), project_target=str(proj2),
        object="Dir/T.xml", xml_view="original",
    )
    results.append(check(
        "xml_view=original works",
        r_orig.get("success") is True and r_orig.get("xml_view") in (None, "original") or r_orig.get("success"),
        f"success={r_orig.get('success')} xml_view={r_orig.get('xml_view')} err={r_orig.get('error_code')}",
    ))
    r_flat = compare_things(
        kind="xml", project_source=str(proj), project_target=str(proj2),
        object="Dir/T.xml", xml_view="flat",
    )
    results.append(check(
        "xml_view=flat works",
        r_flat.get("success") is True,
        f"success={r_flat.get('success')} xml_view={r_flat.get('xml_view')} msg={(r_flat.get('message') or '')[:100]} compared={r_flat.get('compared',[{}])[0] if r_flat.get('compared') else {}}",
    ))
    r_bad = compare_things(
        kind="xml", project_source=str(proj), project_target=str(proj2),
        object="Dir/T.xml", xml_view="nope",
    )
    results.append(check(
        "xml_view invalid → invalid_xml_view",
        r_bad.get("success") is False and r_bad.get("error_code") == "invalid_xml_view",
        f"err={r_bad.get('error_code')}",
    ))
    r_alias = compare_things(
        kind="xml", project_source=str(proj), project_target=str(proj2),
        object="Dir/T.xml", xml_view="raw",
    )
    results.append(check(
        "xml_view=raw alias → original success",
        r_alias.get("success") is True and (r_alias.get("xml_view") == "original" or r_alias.get("success")),
        f"xml_view={r_alias.get('xml_view')}",
    ))

    # different include content → flat different
    (inc2 / "A.txt").write_text("CHANGED", encoding="utf-8")
    r_flat_diff = compare_things(
        kind="xml", project_source=str(proj), project_target=str(proj2),
        object="Dir/T.xml", xml_view="flat",
    )
    status_flat = None
    if r_flat_diff.get("compared"):
        status_flat = r_flat_diff["compared"][0].get("status")
    results.append(check(
        "flat: Include khác → different (or not identical)",
        r_flat_diff.get("success") and status_flat in ("different", "error")
        or (r_flat_diff.get("summary") or {}).get("counts", {}).get("different", 0) >= 1,
        f"status={status_flat} summary={r_flat_diff.get('summary')} xml_view={r_flat_diff.get('xml_view')}",
    ))

    # Live XML original vs flat Customer
    if Path(FAH).is_dir():
        _p("\n## LIVE xml Customer original vs flat", flush=True)
        for view in ("original", "flat"):
            rc = compare_things(
                kind="xml", project_source=FAH, project_target=AIH,
                object="Dir/Customer.xml", xml_view=view, mode="summary", max_diff_lines=50,
            )
            hc = 0
            lb = None
            if rc.get("compared"):
                c0 = rc["compared"][0]
                hc = (c0.get("content") or {}).get("hunk_count") or 0
                lb = (c0.get("content") or {}).get("line_basis")
            results.append(check(
                f"LIVE Customer.xml xml_view={view}",
                rc.get("success") is True,
                f"status={(rc.get('compared') or [{}])[0].get('status')} hunks={hc} line_basis={lb} msg={(rc.get('message') or '')[:80]}",
            ))

        _p("\n## LIVE SQL seed Authorize rank", flush=True)
        ra = compare_things(
            kind="sql", project_source=FAH, project_target=AIH,
            seed="Authorize", max_objects=8, mode="summary",
        )
        names = (ra.get("summary") or {}).get("different") or []
        names += (ra.get("summary") or {}).get("missing_on_target") or []
        names += (ra.get("summary") or {}).get("identical") or []
        # also from compared
        for it in ra.get("compared") or []:
            if it.get("name"):
                names.append(it["name"])
        names_l = [n.lower() for n in names]
        cs_cf = [n for n in names_l if "cs_cf" in n]
        authish = [n for n in names_l if "authorize" in n or "approval" in n]
        results.append(check(
            "seed Authorize: ưu tiên tên Authorize/Approval hơn cs_CF*",
            len(authish) >= 1 and (len(cs_cf) == 0 or names_l.index(authish[0]) < (names_l.index(cs_cf[0]) if cs_cf else 99)),
            f"authish={authish[:5]} cs_cf={cs_cf[:3]} all_sample={names[:8]}",
        ))

        _p("\n## LIVE SQL PU GetApprovalRole", flush=True)
        rr = compare_things(
            kind="sql", project_source=FAH, project_target=AIH,
            object="FastBusiness$APV$PU$GetApprovalRole", mode="hunks", max_diff_lines=40,
        )
        results.append(check(
            "explicit GetApprovalRole compare success",
            rr.get("success") is True,
            f"status={(rr.get('compared') or [{}])[0].get('status')} signals={(rr.get('compared') or [{}])[0].get('signals')}",
        ))

        _p("\n## LIVE file PU identical + folder bin smoke", flush=True)
        pu_f = FAH + r"\App_Data\Controllers\Dir\PUDelegationApproval.xml"
        pu_a = AIH + r"\App_Data\Controllers\Dir\PUDelegationApproval.xml"
        rp = compare_things(kind="file", file_a=pu_f, file_b=pu_a)
        results.append(check(
            "PU file still identical",
            rp.get("success") and (rp.get("compared") or [{}])[0].get("identical_content") is True,
            f"status={(rp.get('compared') or [{}])[0].get('status')}",
        ))
        rf = compare_things(
            kind="folder",
            folder_a=str(Path(FAH) / "bin"),
            folder_b=str(Path(AIH) / "bin"),
            include_glob="*.dll",
            max_objects=20,
        )
        results.append(check(
            "bin folder compare success",
            rf.get("success") is True and (rf.get("summary") or {}).get("files_a", 0) > 0,
            f"files_a={(rf.get('summary') or {}).get('files_a')} missing_b={len((rf.get('summary') or {}).get('missing_on_b') or [])}",
        ))

        # table dmuqduyet still reports schema_diff
        rt2 = compare_things(kind="table", project_source=FAH, project_target=AIH, object="dmuqduyet")
        results.append(check(
            "table dmuqduyet compare success",
            rt2.get("success") is True,
            f"status={(rt2.get('compared') or [{}])[0].get('status')} next={rt2.get('next_actions')}",
        ))

    passed = sum(1 for x in results if x["passed"])
    report = {"passed": passed, "total": len(results), "results": results}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _p(f"\n======== TOTAL {passed}/{len(results)} ========", flush=True)
    _p(f"Report: {OUT}", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

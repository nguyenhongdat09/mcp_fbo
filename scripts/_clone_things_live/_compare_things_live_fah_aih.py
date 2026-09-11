"""Live acceptance: compare_things FAHASA FBISP24 vs AIH SP228 — all kinds."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

# Windows console often cp1252 — force utf-8 for live report prints
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from compare_things import compare_things

FAH = r"\\172.168.5.14\CustomerPro\FBI\FAHASAKHANHHOA\FBISP24"
AIH = r"\\172.168.5.14\CustomerPro\FBO\AIH\SP228"

FAH_PU = FAH + r"\App_Data\Controllers\Dir\PUDelegationApproval.xml"
AIH_PU = AIH + r"\App_Data\Controllers\Dir\PUDelegationApproval.xml"
FAH_PO = FAH + r"\App_Data\Controllers\Grid\POTran.xml"
AIH_PO = AIH + r"\App_Data\Controllers\Grid\POTran.xml"
USER_A = FAH_PU
USER_B = AIH + r"\App_Data\Controllers\Grid\POTran.xml"

OUT = Path(__file__).resolve().parent / "_compare_things_live_report.json"


def brief(r: dict, max_compared: int = 5) -> dict:
    """Shrink result for report readability."""
    if not r:
        return {}
    out = {
        "success": r.get("success"),
        "kind": r.get("kind"),
        "mode": r.get("mode"),
        "error_code": r.get("error_code"),
        "error": r.get("error"),
        "message": r.get("message"),
        "next_actions": r.get("next_actions"),
        "warnings": (r.get("warnings") or [])[:10],
        "summary": r.get("summary"),
    }
    compared = r.get("compared") or []
    slim = []
    for item in compared[:max_compared]:
        c = dict(item)
        content = c.get("content")
        if isinstance(content, dict):
            hunks = content.get("hunks") or []
            content = {
                **{k: content.get(k) for k in (
                    "lines_a", "lines_b", "lines_source", "lines_target",
                    "lines_added", "lines_removed", "hunk_count", "diff_truncated",
                ) if k in content},
                "hunks_preview": [
                    {
                        "id": h.get("id"),
                        "change_type": h.get("change_type"),
                        "a_line_start": h.get("a_line_start"),
                        "a_line_end": h.get("a_line_end"),
                        "b_line_start": h.get("b_line_start"),
                        "b_line_end": h.get("b_line_end"),
                        "source_line_start": h.get("source_line_start"),
                        "source_line_end": h.get("source_line_end"),
                        "target_line_start": h.get("target_line_start"),
                        "target_line_end": h.get("target_line_end"),
                        "preview": (h.get("preview") or [])[:6],
                        "signals_in_hunk": h.get("signals_in_hunk"),
                    }
                    for h in hunks[:5]
                ],
                "unified_diff_head": ((content.get("unified_diff") or "")[:500]),
            }
            c["content"] = content
        # trim huge schema
        if "schema_diff" in c and c["schema_diff"]:
            sd = c["schema_diff"]
            c["schema_diff"] = {k: (v if not isinstance(v, list) or len(v) <= 20 else v[:20] + ["..."]) for k, v in sd.items()}
        slim.append(c)
    out["compared_count"] = len(compared)
    out["compared_sample"] = slim
    return out


def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        print(text.encode("ascii", "replace").decode("ascii"), **kwargs)


def run_case(name: str, **kwargs) -> dict:
    _safe_print(f"\n=== {name} ===", flush=True)
    try:
        r = compare_things(**kwargs)
        ok = bool(r.get("success"))
        msg = (r.get("message") or "")[:120]
        _safe_print(
            f"  success={ok} kind={r.get('kind')} err={r.get('error_code')} msg={msg}",
            flush=True,
        )
        if r.get("summary"):
            s = r["summary"]
            keys = [
                "status", "identical_content", "only_line_ending_diff",
                "missing_on_target", "missing_on_source", "identical", "different",
                "encrypted_skip", "files_a", "files_b", "missing_on_a", "missing_on_b",
                "different_meta", "different_content", "omitted_identical_count", "truncated",
                "counts",
            ]
            show = {k: s.get(k) for k in keys if k in s and s.get(k) not in (None, [], {})}
            for k, v in list(show.items()):
                if isinstance(v, list) and len(v) > 8:
                    show[k] = v[:8] + [f"...(+{len(v)-8})"]
            _safe_print(f"  summary={show}", flush=True)
        _safe_print(f"  next_actions={r.get('next_actions')}", flush=True)
        return {"name": name, "ok": ok, "result": brief(r)}
    except Exception as e:
        _safe_print(f"  EXCEPTION: {e}", flush=True)
        traceback.print_exc()
        return {"name": name, "ok": False, "exception": str(e)}


def main():
    report = {"projects": {"FAHASA": FAH, "AIH": AIH}, "path_checks": {}, "cases": []}

    checks = {
        "FAH_root": Path(FAH).is_dir(),
        "AIH_root": Path(AIH).is_dir(),
        "FAH_PU": Path(FAH_PU).is_file(),
        "AIH_PU": Path(AIH_PU).is_file(),
        "FAH_PO": Path(FAH_PO).is_file(),
        "AIH_PO": Path(AIH_PO).is_file(),
        "FAH_bin": Path(FAH, "bin").is_dir(),
        "AIH_bin": Path(AIH, "bin").is_dir(),
    }
    report["path_checks"] = checks
    _safe_print("PATH CHECKS:", json.dumps(checks, indent=2), flush=True)

    # --- FILE ---
    report["cases"].append(run_case(
        "FILE-01 user paths (PU Dir FAH vs PO Grid AIH) — expect different",
        kind="file", file_a=USER_A, file_b=USER_B, mode="summary",
    ))
    if checks["FAH_PU"] and checks["AIH_PU"]:
        report["cases"].append(run_case(
            "FILE-02 same relative PUDelegationApproval.xml FAH vs AIH",
            kind="file", file_a=FAH_PU, file_b=AIH_PU, mode="hunks", max_diff_lines=80,
        ))
        report["cases"].append(run_case(
            "FILE-03 PU CRLF ignore + body mode sample",
            kind="file", file_a=FAH_PU, file_b=AIH_PU, mode="body", max_diff_lines=40,
        ))
    if checks["FAH_PO"] and checks["AIH_PO"]:
        report["cases"].append(run_case(
            "FILE-04 POTran.xml FAH vs AIH",
            kind="file", file_a=FAH_PO, file_b=AIH_PO, mode="summary",
        ))

    # --- XML ---
    report["cases"].append(run_case(
        "XML-01 Dir/PUDelegationApproval.xml (project roots)",
        kind="xml",
        project_source=FAH, project_target=AIH,
        object="Dir/PUDelegationApproval.xml",
        mode="summary",
    ))
    report["cases"].append(run_case(
        "XML-02 Grid/POTran.xml",
        kind="xml",
        project_source=FAH, project_target=AIH,
        object="Grid/POTran.xml",
        mode="summary",
    ))
    report["cases"].append(run_case(
        "XML-03 multi object list",
        kind="xml",
        project_source=FAH, project_target=AIH,
        object="Dir/PUDelegationApproval.xml,Grid/POTran.xml",
        mode="summary",
    ))
    report["cases"].append(run_case(
        "XML-04 path traversal reject",
        kind="xml",
        project_source=FAH, project_target=AIH,
        object="Dir/../Web.config",
        mode="summary",
    ))

    # --- FOLDER bin ---
    if checks["FAH_bin"] and checks["AIH_bin"]:
        report["cases"].append(run_case(
            "FOLDER-01 bin meta-only (*.dll)",
            kind="folder",
            folder_a=str(Path(FAH) / "bin"),
            folder_b=str(Path(AIH) / "bin"),
            include_glob="*.dll",
            compare_content=False,
            max_objects=50,
            mode="summary",
        ))
        report["cases"].append(run_case(
            "FOLDER-02 bin *.dll max_objects=15 truncation",
            kind="folder",
            folder_a=str(Path(FAH) / "bin"),
            folder_b=str(Path(AIH) / "bin"),
            include_glob="*.dll",
            max_objects=15,
        ))

    # Controllers Dir folder (smaller than full Controllers)
    fah_dir = Path(FAH) / "App_Data" / "Controllers" / "Dir"
    aih_dir = Path(AIH) / "App_Data" / "Controllers" / "Dir"
    if fah_dir.is_dir() and aih_dir.is_dir():
        report["cases"].append(run_case(
            "FOLDER-03 Controllers/Dir *.xml meta",
            kind="folder",
            folder_a=str(fah_dir),
            folder_b=str(aih_dir),
            include_glob="*.xml",
            recursive=False,
            max_objects=40,
        ))

    # --- SQL ---
    report["cases"].append(run_case(
        "SQL-01 seed dmuqduyet,vdmduyetuq (acceptance)",
        kind="sql",
        project_source=FAH,
        project_target=AIH,
        seed="dmuqduyet,vdmduyetuq",
        db_type="app",
        mode="summary",
        max_objects=30,
    ))
    report["cases"].append(run_case(
        "SQL-02 seed with mode=hunks",
        kind="sql",
        project_source=FAH,
        project_target=AIH,
        seed="vdmduyetuq",
        mode="hunks",
        max_objects=10,
        max_diff_lines=60,
    ))
    # try a common object name if any from seed - also explicit empty validation
    report["cases"].append(run_case(
        "SQL-03 invalid empty object+seed",
        kind="sql",
        project_source=FAH,
        project_target=AIH,
        object="",
        seed="",
    ))

    # --- TABLE ---
    for tbl in ("dmuqduyet", "vdmduyetuq", "dmkh"):
        report["cases"].append(run_case(
            f"TABLE-{tbl}",
            kind="table",
            project_source=FAH,
            project_target=AIH,
            object=tbl,
            db_type="app",
            mode="summary",
        ))

    # --- validation ---
    report["cases"].append(run_case(
        "API invalid kind",
        kind="nope",
        project_source=FAH,
        project_target=AIH,
    ))

    passed = sum(1 for c in report["cases"] if c.get("ok") or (
        # validation cases expected success=false
        c.get("name", "").startswith("API") or "invalid" in c.get("name", "").lower() or "traversal" in c.get("name", "").lower()
    ) and c.get("result", {}).get("success") is False or c.get("ok"))
    # Better scoring:
    expected_fail = {"API invalid kind", "SQL-03 invalid empty object+seed", "XML-04 path traversal reject"}
    score = []
    for c in report["cases"]:
        name = c["name"]
        if name in expected_fail:
            ok = c.get("result", {}).get("success") is False or c.get("ok") is False
            # success False is pass for these
            if c.get("exception"):
                ok = False
            elif c.get("result") is not None:
                ok = c["result"].get("success") is False
            else:
                ok = False
        else:
            ok = bool(c.get("ok"))
        score.append({"name": name, "pass": ok})
    report["scorecard"] = score
    report["pass_count"] = sum(1 for s in score if s["pass"])
    report["total"] = len(score)

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _safe_print("\n======== SCORECARD ========", flush=True)
    for s in score:
        _safe_print(f"  [{'PASS' if s['pass'] else 'FAIL'}] {s['name']}", flush=True)
    _safe_print(f"\nTOTAL {report['pass_count']}/{report['total']}", flush=True)
    _safe_print(f"Report: {OUT}", flush=True)


if __name__ == "__main__":
    main()

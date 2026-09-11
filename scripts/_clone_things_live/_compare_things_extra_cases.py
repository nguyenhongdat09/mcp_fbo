"""Extra diverse live cases for compare_things — FAHASA vs AIH + synthetic fixtures."""
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
OUT = Path(__file__).resolve().parent / "_compare_things_extra_cases_report.json"


def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        print(" ".join(str(a) for a in args).encode("ascii", "replace").decode("ascii"), **kwargs)


def brief(r: dict, n: int = 3) -> dict:
    if not r:
        return {}
    compared = r.get("compared") or []
    samples = []
    for item in compared[:n]:
        row = {
            "status": item.get("status"),
            "name": item.get("name") or item.get("relative_path"),
            "next_actions": item.get("next_actions"),
            "signals": item.get("signals"),
            "only_line_ending_diff": item.get("only_line_ending_diff"),
            "identical_content": item.get("identical_content"),
            "meta_diff": item.get("meta_diff"),
            "schema_diff_nonzero": None,
        }
        sd = item.get("schema_diff")
        if sd:
            row["schema_diff_nonzero"] = {k: v for k, v in sd.items() if v not in (None, [], False, "")}
        content = item.get("content") or {}
        hunks = content.get("hunks") or []
        if hunks:
            h = hunks[0]
            row["hunk0"] = {
                k: h.get(k)
                for k in (
                    "change_type",
                    "a_line_start", "a_line_end", "b_line_start", "b_line_end",
                    "source_line_start", "source_line_end", "target_line_start", "target_line_end",
                )
                if h.get(k) is not None
            }
            row["hunk0_preview"] = (h.get("preview") or [])[:4]
        samples.append(row)
    return {
        "success": r.get("success"),
        "kind": r.get("kind"),
        "error_code": r.get("error_code"),
        "message": (r.get("message") or "")[:200],
        "next_actions": r.get("next_actions"),
        "warnings": (r.get("warnings") or [])[:5],
        "summary": r.get("summary"),
        "compared_count": len(compared),
        "samples": samples,
    }


def run(name: str, expect_success: bool | None = True, **kwargs) -> dict:
    _safe_print(f"\n=== {name} ===", flush=True)
    try:
        r = compare_things(**kwargs)
        ok_tool = bool(r.get("success"))
        if expect_success is None:
            passed = True  # observational
        elif expect_success:
            passed = ok_tool
        else:
            passed = not ok_tool
        _safe_print(
            f"  tool_success={ok_tool} expect_success={expect_success} "
            f"CASE={'PASS' if passed else 'FAIL'} err={r.get('error_code')}",
            flush=True,
        )
        _safe_print(f"  msg={(r.get('message') or '')[:140]}", flush=True)
        s = r.get("summary") or {}
        interesting = {
            k: s.get(k)
            for k in (
                "status", "identical_content", "only_line_ending_diff",
                "counts", "files_a", "files_b", "truncated",
                "missing_on_target", "missing_on_source", "missing_on_a", "missing_on_b",
                "different", "identical", "different_meta", "encrypted_skip",
            )
            if k in s and s.get(k) not in (None, [], {})
        }
        for k, v in list(interesting.items()):
            if isinstance(v, list) and len(v) > 6:
                interesting[k] = v[:6] + [f"...(+{len(v)-6})"]
        if interesting:
            _safe_print(f"  summary={interesting}", flush=True)
        return {"name": name, "passed": passed, "expect_success": expect_success, "result": brief(r)}
    except Exception as e:
        _safe_print(f"  EXCEPTION: {e}", flush=True)
        traceback.print_exc()
        return {"name": name, "passed": False, "exception": str(e)}


def main():
    cases = []
    td = Path(tempfile.mkdtemp(prefix="cmp_extra_"))
    _safe_print(f"Synthetic dir: {td}", flush=True)

    # --- Synthetic file fixtures ---
    f_lf = td / "same_lf.txt"
    f_crlf = td / "same_crlf.txt"
    f_lf.write_bytes(b"aaa\nbbb\nccc\n")
    f_crlf.write_bytes(b"aaa\r\nbbb\r\nccc\r\n")
    f_bom = td / "bom.txt"
    f_nobom = td / "nobom.txt"
    f_bom.write_bytes(b"\xef\xbb\xbfhello\nworld\n")
    f_nobom.write_bytes(b"hello\nworld\n")
    f_diff_a = td / "diff_a.txt"
    f_diff_b = td / "diff_b.txt"
    f_diff_a.write_text("L1\nOLD\nL3\nL4\n", encoding="utf-8")
    f_diff_b.write_text("L1\nNEW\nL3\nL4\nEXTRA\n", encoding="utf-8")
    f_bin_a = td / "a.bin"
    f_bin_b = td / "b.bin"
    f_bin_a.write_bytes(b"MZ\x00\x01ABC")
    f_bin_b.write_bytes(b"MZ\x00\x01XYZ")
    f_empty_a = td / "empty_a.txt"
    f_empty_b = td / "empty_b.txt"
    f_empty_a.write_bytes(b"")
    f_empty_b.write_bytes(b"")

    # folder trees
    fa = td / "fold_a"
    fb = td / "fold_b"
    (fa / "sub").mkdir(parents=True)
    (fb / "sub").mkdir(parents=True)
    (fa / "keep.txt").write_text("same", encoding="utf-8")
    (fb / "keep.txt").write_text("same", encoding="utf-8")
    (fa / "only_a.txt").write_text("a", encoding="utf-8")
    (fb / "only_b.txt").write_text("b", encoding="utf-8")
    (fa / "sub" / "x.txt").write_text("v1\n", encoding="utf-8")
    (fb / "sub" / "x.txt").write_text("v2\n", encoding="utf-8")
    (fa / "skip.pdb").write_text("pdb", encoding="utf-8")
    (fb / "skip.pdb").write_text("pdb2", encoding="utf-8")
    (fa / "bigish.txt").write_text("x" * 100, encoding="utf-8")
    (fb / "bigish.txt").write_text("y" * 120, encoding="utf-8")

    # ========== SYNTHETIC ==========
    cases.append(run("S-FILE self compare identical", kind="file", file_a=str(f_lf), file_b=str(f_lf)))
    cases.append(run("S-FILE CRLF vs LF only_line_ending", kind="file", file_a=str(f_lf), file_b=str(f_crlf)))
    cases.append(run(
        "S-FILE CRLF vs LF ignore_line_endings=false → different",
        kind="file", file_a=str(f_lf), file_b=str(f_crlf), ignore_line_endings=False,
    ))
    cases.append(run("S-FILE BOM vs no BOM", kind="file", file_a=str(f_bom), file_b=str(f_nobom)))
    cases.append(run("S-FILE content diff hunks", kind="file", file_a=str(f_diff_a), file_b=str(f_diff_b), mode="hunks"))
    cases.append(run("S-FILE mode=body window", kind="file", file_a=str(f_diff_a), file_b=str(f_diff_b), mode="body", max_diff_lines=30))
    cases.append(run("S-FILE binary different", kind="file", file_a=str(f_bin_a), file_b=str(f_bin_b)))
    cases.append(run("S-FILE empty vs empty", kind="file", file_a=str(f_empty_a), file_b=str(f_empty_b)))
    (td / "ws_a.txt").write_text("  hello  \n", encoding="utf-8")
    (td / "ws_b.txt").write_text("hello\n", encoding="utf-8")
    cases.append(run(
        "S-FILE ignore_whitespace true",
        kind="file",
        file_a=str(td / "ws_a.txt"),
        file_b=str(td / "ws_b.txt"),
        ignore_whitespace=True,
    ))
    cases.append(run(
        "S-FILE ignore_whitespace false → likely different",
        kind="file",
        file_a=str(td / "ws_a.txt"),
        file_b=str(td / "ws_b.txt"),
        ignore_whitespace=False,
    ))
    cases.append(run(
        "S-FILE missing path", expect_success=False,
        kind="file", file_a=str(td / "nope.txt"), file_b=str(f_lf),
    ))

    cases.append(run(
        "S-FOLDER missing + meta + recursive",
        kind="folder", folder_a=str(fa), folder_b=str(fb), recursive=True, max_objects=20,
    ))
    cases.append(run(
        "S-FOLDER exclude *.pdb",
        kind="folder", folder_a=str(fa), folder_b=str(fb),
        exclude_glob="*.pdb", include_glob="*", max_objects=20,
    ))
    cases.append(run(
        "S-FOLDER include only *.txt recursive false",
        kind="folder", folder_a=str(fa), folder_b=str(fb),
        include_glob="*.txt", recursive=False, max_objects=20,
    ))
    cases.append(run(
        "S-FOLDER compare_content text hunks",
        kind="folder", folder_a=str(fa), folder_b=str(fb),
        compare_content=True, include_glob="*.txt", recursive=True, max_objects=20, mode="hunks",
    ))
    cases.append(run(
        "S-FOLDER hash_max_bytes tiny skip large",
        kind="folder", folder_a=str(fa), folder_b=str(fb),
        compare_content=True, hash_max_bytes=10, include_glob="bigish.txt",
    ))

    # ========== LIVE UNC ==========
    pu_fah = FAH + r"\App_Data\Controllers\Dir\PUDelegationApproval.xml"
    pu_aih = AIH + r"\App_Data\Controllers\Dir\PUDelegationApproval.xml"
    customer_fah = FAH + r"\App_Data\Controllers\Dir\Customer.xml"
    customer_aih = AIH + r"\App_Data\Controllers\Dir\Customer.xml"

    cases.append(run(
        "L-FILE PU self FAH",
        kind="file", file_a=pu_fah, file_b=pu_fah,
    ))
    cases.append(run(
        "L-FILE Customer.xml FAH vs AIH (often different projects)",
        kind="file", file_a=customer_fah, file_b=customer_aih, mode="summary",
        expect_success=None,  # may missing
    ))
    # If missing, tool returns success false — mark observational by checking exists
    if Path(customer_fah).is_file() and Path(customer_aih).is_file():
        cases[-1] = run(
            "L-FILE Customer.xml FAH vs AIH",
            kind="file", file_a=customer_fah, file_b=customer_aih, mode="hunks", max_diff_lines=50,
        )
    else:
        cases[-1] = {
            "name": "L-FILE Customer.xml FAH vs AIH",
            "passed": True,
            "skipped": True,
            "reason": f"exists FAH={Path(customer_fah).is_file()} AIH={Path(customer_aih).is_file()}",
        }
        _safe_print(f"\n=== SKIP L-FILE Customer.xml ({cases[-1]['reason']}) ===", flush=True)

    cases.append(run(
        "L-XML Filter list if any — try common Filter name",
        kind="xml", project_source=FAH, project_target=AIH,
        object="Filter/PUDelegationApprovalFilter.xml,Dir/Customer.xml,Dir/PUDelegationApproval.xml",
        mode="summary", max_objects=10,
    ))
    cases.append(run(
        "L-XML absolute-like relative App_Data prefix normalize",
        kind="xml", project_source=FAH, project_target=AIH,
        object="App_Data/Controllers/Dir/PUDelegationApproval.xml",
    ))
    cases.append(run(
        "L-XML project path as controller file (resolve root)",
        kind="xml",
        project_source=pu_fah,
        project_target=pu_aih,
        object="Dir/PUDelegationApproval.xml",
    ))

    cases.append(run(
        "L-FOLDER bin exclude FastBusiness.* glob pattern",
        kind="folder",
        folder_a=str(Path(FAH) / "bin"),
        folder_b=str(Path(AIH) / "bin"),
        include_glob="*.dll",
        exclude_glob="FastBusiness.*.dll",
        max_objects=25,
    ))
    cases.append(run(
        "L-FOLDER Grid xml only non-recursive",
        kind="folder",
        folder_a=str(Path(FAH) / "App_Data" / "Controllers" / "Grid"),
        folder_b=str(Path(AIH) / "App_Data" / "Controllers" / "Grid"),
        include_glob="*.xml",
        recursive=False,
        max_objects=30,
    ))
    cases.append(run(
        "L-FOLDER Filter compare_content small sample",
        kind="folder",
        folder_a=str(Path(FAH) / "App_Data" / "Controllers" / "Filter"),
        folder_b=str(Path(AIH) / "App_Data" / "Controllers" / "Filter"),
        include_glob="*Approval*.xml",
        compare_content=True,
        hash_max_bytes=2_000_000,
        max_objects=15,
        mode="summary",
    ))

    cases.append(run(
        "L-SQL object explicit GetApprovalRole",
        kind="sql",
        project_source=FAH, project_target=AIH,
        object="FastBusiness$APV$PU$GetApprovalRole,FastBusiness$App$GetApprovalRole",
        mode="hunks", max_diff_lines=40,
    ))
    cases.append(run(
        "L-SQL seed Authorize only max_objects=5",
        kind="sql",
        project_source=FAH, project_target=AIH,
        seed="Authorize",
        max_objects=5,
        mode="summary",
    ))
    cases.append(run(
        "L-SQL db_type=both seed vdmduyetuq max 8",
        kind="sql",
        project_source=FAH, project_target=AIH,
        seed="vdmduyetuq",
        db_type="both",
        max_objects=8,
    ))
    cases.append(run(
        "L-SQL missing object name",
        kind="sql",
        project_source=FAH, project_target=AIH,
        object="dbo.ThisObjectDefinitelyDoesNotExist_XYZ_999",
        expect_success=None,
    ))

    cases.append(run(
        "L-TABLE multi dmkh,dmvt,dmdvkd",
        kind="table",
        project_source=FAH, project_target=AIH,
        object="dmkh, dmvt, dmdvkd",
        mode="summary",
    ))
    cases.append(run(
        "L-TABLE missing table",
        kind="table",
        project_source=FAH, project_target=AIH,
        object="dbo.zz_table_not_exist_cmp_things",
        expect_success=None,
    ))
    cases.append(run(
        "L-TABLE db_type=sys try sys table syschecks or options",
        kind="table",
        project_source=FAH, project_target=AIH,
        object="options",
        db_type="sys",
        expect_success=None,
    ))

    # validation matrix
    cases.append(run("V-invalid mode", expect_success=False, kind="file", file_a=str(f_lf), file_b=str(f_lf), mode="full"))
    cases.append(run("V-sql missing project", expect_success=False, kind="sql", object="dbo.x", project_source="", project_target=""))
    cases.append(run("V-folder not dir", expect_success=False, kind="folder", folder_a=str(f_lf), folder_b=str(fb)))
    cases.append(run("V-max_objects 0", expect_success=False, kind="file", file_a=str(f_lf), file_b=str(f_lf), max_objects=0))
    cases.append(run(
        "V-xml empty object", expect_success=False,
        kind="xml", project_source=FAH, project_target=AIH, object="",
    ))

    # swap source/target direction for sql seed (AIH → FAH)
    cases.append(run(
        "L-SQL reverse AIH→FAH seed dmduyet",
        kind="sql",
        project_source=AIH, project_target=FAH,
        seed="dmduyet",
        max_objects=12,
        mode="summary",
    ))

    report = {
        "synthetic_dir": str(td),
        "pass_count": sum(1 for c in cases if c.get("passed")),
        "total": len(cases),
        "cases": cases,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _safe_print("\n======== EXTRA SCORECARD ========", flush=True)
    for c in cases:
        flag = "PASS" if c.get("passed") else "FAIL"
        skip = " SKIP" if c.get("skipped") else ""
        _safe_print(f"  [{flag}{skip}] {c.get('name')}", flush=True)
    _safe_print(f"\nTOTAL {report['pass_count']}/{report['total']}", flush=True)
    _safe_print(f"Report: {OUT}", flush=True)


if __name__ == "__main__":
    main()

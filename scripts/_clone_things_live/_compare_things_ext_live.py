"""Live smoke: compare_things all extensions except .f (FAH vs AIH)."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from compare_things import compare_things

FAH = r"\\172.168.5.14\CustomerPro\FBI\FAHASAKHANHHOA\FBISP24"
AIH = r"\\172.168.5.14\CustomerPro\FBO\AIH\SP228"


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    return cond


def _status(r: dict) -> str:
    summary = r.get("summary") or {}
    if isinstance(summary, dict) and summary.get("status"):
        return str(summary.get("status"))
    compared = r.get("compared") or []
    if compared:
        return str(compared[0].get("status"))
    return str(r.get("status") or "")


def _first_pair(root_a: Path, root_b: Path, pattern: str):
    for ea in root_a.rglob(pattern):
        rel = ea.relative_to(root_a)
        eb = root_b / rel
        if eb.exists():
            return ea, eb
    return None


def main() -> int:
    results: list[bool] = []
    print("## LIVE extension rules FAH/AIH", flush=True)

    include_a = Path(FAH) / "App_Data" / "Controllers" / "Include"
    include_b = Path(AIH) / "App_Data" / "Controllers" / "Include"

    # LIVE-TXT: first .txt present on both sides
    txt_pair = _first_pair(include_a, include_b, "*.txt")
    print(f"txt_pair={txt_pair}", flush=True)
    if txt_pair:
        fa, fb = txt_pair
        r = compare_things(kind="file", file_a=str(fa), file_b=str(fb), mode="summary")
        msg = (r.get("message") or "")[:100]
        results.append(
            check(
                f"LIVE-TXT {fa.name}",
                r.get("success") is True,
                f"status={_status(r)} msg={msg}",
            )
        )
    else:
        results.append(check("LIVE-TXT pair found", False, "no matching .txt on both sides"))

    # LIVE-ENT: first .ent present on both sides
    ent_pair = _first_pair(include_a, include_b, "*.ent")
    print(f"ent_pair={ent_pair}", flush=True)
    if ent_pair:
        ea, eb = ent_pair
        r2 = compare_things(kind="file", file_a=str(ea), file_b=str(eb), mode="summary")
        results.append(
            check(
                f"LIVE-ENT {ea.name}",
                r2.get("success") is True,
                f"status={_status(r2)}",
            )
        )
    else:
        results.append(check("LIVE-ENT pair found", False, "no matching .ent on both sides"))

    # LIVE-F reject
    fs = list(Path(FAH).joinpath("App_Data", "Controllers").rglob("*.f"))[:1]
    print(f"sample .f={fs}", flush=True)
    if fs:
        rf = compare_things(kind="file", file_a=str(fs[0]), file_b=str(fs[0]), mode="summary")
    else:
        rf = compare_things(
            kind="file",
            file_a=FAH + r"\App_Data\Controllers\Dir\Fake.f",
            file_b=AIH + r"\App_Data\Controllers\Dir\Fake.f",
        )
    results.append(
        check(
            "LIVE-F reject",
            rf.get("success") is False and rf.get("error_code") == "unsupported_extension_f",
            f"code={rf.get('error_code')} msg={(rf.get('message') or '')[:120]}",
        )
    )

    # LIVE-FOLDER: include .f in glob but must skip
    folder_a = FAH + r"\App_Data\Controllers\Include\Command"
    folder_b = AIH + r"\App_Data\Controllers\Include\Command"
    r3 = compare_things(
        kind="folder",
        folder_a=folder_a,
        folder_b=folder_b,
        include_glob="*.txt,*.ent,*.f",
        recursive=True,
        compare_content=False,
        mode="summary",
    )
    sum3 = r3.get("summary") or {}
    miss_diff = (
        (sum3.get("missing_on_a") or [])
        + (sum3.get("missing_on_b") or [])
        + (sum3.get("different_meta") or [])
        + (sum3.get("different_content") or [])
    )
    has_f = any(str(x).lower().endswith(".f") for x in miss_diff)
    results.append(
        check(
            "LIVE-FOLDER no .f in results",
            r3.get("success") is True and not has_f,
            f"skipped_f={sum3.get('skipped_f_count')} files_a={sum3.get('files_a')} "
            f"files_b={sum3.get('files_b')} status={sum3.get('status')}",
        )
    )

    # LIVE-XML: .txt via kind=xml must reject
    r4 = compare_things(
        kind="xml",
        project_source=FAH,
        project_target=AIH,
        object="Include/Command/WhenVoucherInit.txt",
    )
    results.append(
        check(
            "LIVE-XML txt via kind=xml reject",
            r4.get("success") is False and r4.get("error_code") == "invalid_object",
            f"code={r4.get('error_code')} msg={(r4.get('message') or '')[:120]}",
        )
    )

    passed = sum(1 for x in results if x)
    print(f"\n{passed}/{len(results)} passed", flush=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

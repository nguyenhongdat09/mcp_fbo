"""Resolve danh sách file cần check — port CheckingFileResolver.js (v1).

- .xml giữ; .xml thiếu → thử .f cùng tên (FBO encrypted).
- .aspx → skipped_files + warning (v1 không port AnalystASPX).
- Extension khác → skipped_files.
- Dedupe theo normpath().lower().
"""

from __future__ import annotations

import os


def resolve_checking_files(file_paths: list[str] | None) -> dict:
    xml_files: list[str] = []
    skipped_files: list[str] = []
    warnings: list[str] = []

    for fp in file_paths or []:
        if not fp:
            continue
        cand = str(fp)
        ext = os.path.splitext(cand)[1].lower()
        if ext == ".xml":
            if not os.path.exists(cand):
                f_path = cand[: -len(".xml")] + ".f"
                if os.path.exists(f_path):
                    cand = f_path
            xml_files.append(cand)
        elif ext == ".aspx":
            skipped_files.append(cand)
            warnings.append(
                f"aspx_resolution_not_supported: '{cand}' — v1 không resolve "
                ".aspx→.xml (MCP thiếu AnalystASPX); truyền file .xml trực tiếp."
            )
        else:
            skipped_files.append(cand)

    seen: set[str] = set()
    unique: list[str] = []
    for x in xml_files:
        norm = os.path.normpath(x).lower()
        if norm not in seen:
            seen.add(norm)
            unique.append(os.path.normpath(x))

    return {
        "xml_files": unique,
        "skipped_files": skipped_files,
        "warnings": warnings,
    }

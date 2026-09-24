"""Module handling clone_things type=3 (file clone between projects).

Copies files (relative, list, glob, presets) from project_source to project_target.
Defaults to dry-run (execute=False).
Defaults to no overwrite (overwrite=False) for existing files, prompting user confirmation.
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from find_connect_by_path.path_resolver import get_project_root_from_path

logger = logging.getLogger("clone_things.type3")

# Whitelist preset definitions
PRESETS: dict[str, list[str]] = {
    "mail": [
        "bin/fsdMail.dll",
        "bin/callMailXS.dll",
        "bin/clsFileUpload.dll",
        "bin/zcCallMail.dll",
        "Main/Uploads/AjaxWeb.aspx",
        "Main/Uploads/AjaxWeb_Core.aspx",
        "ClientScript/jAjax.js",
    ],
    "ajax": [
        "Main/Uploads/AjaxWeb.aspx",
        "ClientScript/jAjax.js",
    ],
}

HASH_MAX_BYTES = 32 * 1024 * 1024  # 32 MB


def coerce_bool(val: Any) -> bool:
    """Coerce boolean from string, int, or bool."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False


def to_posix(path_str: str | Path) -> str:
    """Convert path to forward slash POSIX style."""
    return str(path_str).replace("\\", "/")


def resolve_project_root(path_str: str) -> str | None:
    """
    Resolve project root using get_project_root_from_path with fallback.

    Fallback: if get_project_root_from_path returns None and path is an existing
    directory, return resolved directory path (essential for pytest tmp_path).
    """
    if not path_str or not str(path_str).strip():
        return None

    try:
        resolved_root = get_project_root_from_path(path_str)
        if resolved_root:
            return to_posix(Path(resolved_root).resolve())

        p = Path(path_str).resolve()
        if p.is_dir():
            return to_posix(p)
    except Exception as e:
        logger.warning("Error resolving project root for %s: %e", path_str, e)

    return None


def calculate_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


RE_RL_SE = re.compile(r"^rl\((s|e),\s*(\d+),\s*([^)]+)\)$", re.IGNORECASE)
RE_RL_REPLACE = re.compile(r"^rl\(([^,]+),\s*([^)]+)\)$", re.IGNORECASE)
RE_RLX_SE = re.compile(r"^rlx\((s|e),\s*(\d+),\s*([^)]+)\)$", re.IGNORECASE)
RE_RLX_REPLACE = re.compile(r"^rlx\(([^,]+),\s*([^)]+)\)$", re.IGNORECASE)


def get_suite_candidates(ctrl_name: str) -> list[str]:
    """Return standard candidate file paths for a controller suite."""
    return [
        f"App_Data/Controllers/Filter/{ctrl_name}.xml",
        f"App_Data/Controllers/Filter/{ctrl_name}Form.xml",
        f"App_Data/Controllers/Grid/{ctrl_name}.xml",
        f"App_Data/Controllers/Grid/{ctrl_name}Grid.xml",
        f"App_Data/Controllers/Dir/{ctrl_name}.xml",
        f"App_Data/Controllers/Dir/{ctrl_name}Form.xml",
        f"App_Data/Controllers/Lookup/{ctrl_name}.xml",
        f"App_Data/Controllers/Query/{ctrl_name}.xml",
        f"App_Data/Controllers/Notify/{ctrl_name}.xml",
        f"App_Data/Controllers/Report/{ctrl_name}.xml",
        f"App_Data/Controllers/Report/Config/{ctrl_name}.ent",
        f"App_Data/Controllers/Templates/Rpt/{ctrl_name}.xsd",
        f"App_Data/Controllers/Templates/Upload/{ctrl_name}.xml",
        f"App_Data/Controllers/Templates/Upload/{ctrl_name}ImportXml.xml",
        f"App_Data/Controllers/Include/{ctrl_name}.xml",
        f"App_Data/Controllers/Include/{ctrl_name}.ent",
        f"App_Data/Controllers/Include/{ctrl_name}.txt",
        f"App_Data/Controllers/Include/{ctrl_name}.Nested",
        f"App_Data/Controllers/Include/{ctrl_name}.Nested.txt",
        f"App_Data/Controllers/Include/{ctrl_name}Grid.ent",
        f"App_Data/Controllers/Include/Extender.{ctrl_name}",
        f"App_Data/Controllers/Include/BIMode.{ctrl_name}",
        f"App_Data/Controllers/Include/ImportOverWriteVoucher.{ctrl_name}",
        f"App_Data/Controllers/Include/Revert.{ctrl_name}.ent",
        f"App_Data/Controllers/Include/Tiny.External.{ctrl_name}",
        f"App_Data/Controllers/Include/Unit.{ctrl_name}",
        f"App_Data/Controllers/Include/Command/GNEditCheckTable{ctrl_name}.txt",
        f"Main/{ctrl_name}.aspx",
        f"App_Data/Controllers/Templates/Mail/{ctrl_name}.html",
        f"App_Data/Controllers/Templates/Mail/zmail{ctrl_name}.html",
    ]


def suite_prefix(ctrl_name: str) -> str:
    """Prefix-family của suite: strip đuôi 'Tran' (MRTran→MR;
    InputInvoice→InputInvoice nguyên)."""
    return ctrl_name[:-4] if ctrl_name.endswith("Tran") else ctrl_name


# Whitelist dirs cho prefix-scan — KHÔNG quét Main/, ClientScript/, bin/
# (tên trang .aspx bất quy tắc: inctpx0.aspx / zchddv.aspx).
SUITE_SCAN_DIRS = [
    "App_Data/Controllers/Filter",
    "App_Data/Controllers/Grid",
    "App_Data/Controllers/Dir",
    "App_Data/Controllers/Lookup",
    "App_Data/Controllers/Query",
    "App_Data/Controllers/Notify",
    "App_Data/Controllers/Report",
    "App_Data/Controllers/Report/Config",
    "App_Data/Controllers/View",
    "App_Data/Controllers/Templates/Rpt",
    "App_Data/Controllers/Templates/Upload",
    "App_Data/Controllers/Templates/Mail",
    "App_Data/Controllers/Include",
    "App_Data/Controllers/Include/XML",
    "App_Data/Controllers/Include/XML/Config/Fields",
    "App_Data/Controllers/Include/Command",
]


def expand_suite_prefix_files(
    root_src_path: Path, ctrl_name: str, src_prefix: str
) -> list[str]:
    """Scan whitelist ``SUITE_SCAN_DIRS`` cho file prefix-family:
    - basename startswith ``src_prefix`` (case-SENSITIVE: 'MR' ≠ 'hrRMRequest')
    - basename startswith ``GNEditCheckTable`` + ctrl_name
    - basename startswith ``Extra.`` + src_prefix

    Skip ``*.f``, ``*.xsd``. Trả rel path POSIX theo thứ tự scan, đã dedupe."""
    out: list[str] = []
    seen: set[str] = set()
    for rel_dir in SUITE_SCAN_DIRS:
        d = root_src_path / rel_dir
        if not d.is_dir():
            continue
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except Exception:
            continue
        for e in entries:
            if not e.is_file():
                continue
            name = e.name
            if name.lower().endswith((".f", ".xsd")):
                continue
            hit = (
                (bool(src_prefix) and name.startswith(src_prefix))
                or name.startswith("GNEditCheckTable" + ctrl_name)
                or (bool(src_prefix) and name.startswith("Extra." + src_prefix))
            )
            if not hit:
                continue
            rel = to_posix(Path(rel_dir) / name).lstrip("/")
            if rel not in seen:
                seen.add(rel)
                out.append(rel)
    return out


def rename_suite_basename(
    old_base: str,
    src_prefix: str,
    dst_prefix: str,
    ctrl_name: str,
    dst_tok: str,
) -> str:
    """Rename basename cho suite:X -> Y.

    - ``Extra.{p}Detail`` → ``Extra.{dst_prefix}Detail`` (pattern lệch prefix)
    - ``{p}Approval.xml`` → ``{dst_prefix}Approval.xml`` (startswith src_prefix)
    - ``{c}...``/``GNEditCheckTable{c}.txt`` → replace ctrl_name → dst_tok
    - còn lại → giữ nguyên
    """
    if src_prefix and old_base.startswith(f"Extra.{src_prefix}"):
        return f"Extra.{dst_prefix}" + old_base[len(f"Extra.{src_prefix}"):]
    if src_prefix and old_base.startswith(src_prefix):
        return dst_prefix + old_base[len(src_prefix):]
    if ctrl_name in old_base:
        return old_base.replace(ctrl_name, dst_tok, 1)
    return old_base


def _expand_suite_files(
    root_src_path: Path, ctrl_name: str, warnings: list[str]
) -> list[str]:
    """Templated candidates tồn tại trên source + prefix-family scan
    (dedupe với templated, giữ thứ tự). Append warning
    ``suite_prefix_expanded`` / ``suite_aspx_missing`` khi cần."""
    found = [
        c for c in get_suite_candidates(ctrl_name) if (root_src_path / c).is_file()
    ]
    src_prefix = suite_prefix(ctrl_name)
    known = set(found)
    extra = [
        rel
        for rel in expand_suite_prefix_files(root_src_path, ctrl_name, src_prefix)
        if rel not in known
    ]
    if extra:
        warnings.append(
            f"suite_prefix_expanded: +{len(extra)} file theo prefix "
            f"'{src_prefix}*' — review planned[] trước khi execute"
        )
        found.extend(extra)
    if not (root_src_path / f"Main/{ctrl_name}.aspx").is_file():
        warnings.append(
            "suite_aspx_missing: trang .aspx của voucher thường tên riêng "
            "(zc*/inct*) — copy tay nếu cần"
        )
    return found


def apply_pattern(pattern_str: str, target_name: str) -> str:
    """Apply rl/rlx pattern to target_name."""
    m_se = RE_RLX_SE.match(pattern_str) or RE_RL_SE.match(pattern_str)
    if m_se:
        pos = m_se.group(1).lower()
        count = int(m_se.group(2))
        replacement = m_se.group(3)
        if pos == "s":
            return replacement + target_name[count:]
        else:
            end_idx = max(0, len(target_name) - count)
            return target_name[:end_idx] + replacement

    m_rep = RE_RLX_REPLACE.match(pattern_str) or RE_RL_REPLACE.match(pattern_str)
    if m_rep:
        from_str = m_rep.group(1)
        to_str = m_rep.group(2)
        return target_name.replace(from_str, to_str, 1)

    return pattern_str


def resolve_dst(
    dst_token: str,
    src_rel: str,
    root_tgt_path: Path,
) -> tuple[str | None, str | None, str | None]:
    """
    Resolve dst_token against src_rel and root_tgt_path.

    Returns:
        (dst_rel, error_code, error_message)
    """
    dst_token = dst_token.strip()
    if not dst_token:
        return None, "invalid_rename", "invalid_rename: dst rỗng"

    is_dir_dst = dst_token.endswith(("/", "\\"))
    src_basename = Path(src_rel).name

    if is_dir_dst:
        # 1. dst_token endswith '/' or '\' -> folder đích, giữ nguyên src_basename
        folder_str = dst_token.replace("\\", "/").rstrip("/")
        if ".." in folder_str.split("/"):
            return None, "path_outside_project", f"path_outside_project: '{dst_token}' contains '..' segment"

        folder_path = Path(dst_token)
        if folder_path.is_absolute():
            try:
                rel_folder = folder_path.resolve().relative_to(root_tgt_path).as_posix()
            except ValueError:
                return None, "path_outside_project", f"path_outside_project: '{dst_token}' is outside target root"
        else:
            rel_folder = folder_str.lstrip("/")

        dst_rel = f"{rel_folder}/{src_basename}" if rel_folder else src_basename
        return to_posix(dst_rel).lstrip("/"), None, None

    # 2. Tách dst = (dir_part, last_seg) theo dấu '/' hoặc '\' CUỐI
    norm_dst = dst_token.replace("\\", "/")
    if "/" in norm_dst:
        dir_part, last_seg = norm_dst.rsplit("/", 1)
    else:
        dir_part = None
        last_seg = norm_dst

    suffix = Path(src_basename).suffix
    stem = src_basename[:-len(suffix)] if suffix else src_basename

    if RE_RLX_SE.match(last_seg) or RE_RLX_REPLACE.match(last_seg):
        new_basename = apply_pattern(last_seg, src_basename)
    elif RE_RL_SE.match(last_seg) or RE_RL_REPLACE.match(last_seg):
        new_basename = apply_pattern(last_seg, stem) + suffix
    else:
        new_basename = last_seg

    if not new_basename or not new_basename.strip():
        return None, "invalid_rename", f"invalid_rename: kết quả rename rỗng từ '{dst_token}'"

    if ".." in new_basename.split("/") or new_basename in ("..", "."):
        return None, "path_outside_project", f"path_outside_project: '{new_basename}'"

    if dir_part is None:
        # SIBLING: cùng folder với src_rel
        src_parent = Path(src_rel).parent.as_posix()
        if src_parent and src_parent != ".":
            dst_rel = f"{src_parent}/{new_basename}"
        else:
            dst_rel = new_basename
    else:
        # Có dir_part: relative từ root_target
        if ".." in dir_part.split("/"):
            return None, "path_outside_project", f"path_outside_project: '{dst_token}' contains '..' segment"

        dp_path = Path(dir_part)
        if dp_path.is_absolute():
            try:
                rel_dir = dp_path.resolve().relative_to(root_tgt_path).as_posix()
            except ValueError:
                return None, "path_outside_project", f"path_outside_project: '{dst_token}' is outside target root"
        else:
            rel_dir = dir_part.lstrip("/")

        dst_rel = f"{rel_dir}/{new_basename}" if rel_dir else new_basename

    dst_rel_clean = to_posix(dst_rel).lstrip("/")
    if not dst_rel_clean:
        return None, "invalid_rename", "invalid_rename: dst_rel rỗng sau khi xử lý"

    return dst_rel_clean, None, None


def expand_object_tokens(
    object_str: str,
    root_source: str,
    root_target: str | None = None,
    expand_dirs: bool = False,
) -> tuple[list[tuple[str, str]] | None, str | None, list[str], dict[str, Any] | None]:
    """
    Parse and expand object tokens token-first.

    Returns:
        (unique_relative_pairs, error_code, warnings, error_detail)
        where each pair is (src_rel, dst_rel)
    """
    warnings: list[str] = []
    if not object_str or not str(object_str).strip():
        return None, "invalid_object", warnings, {"token": object_str, "message": "invalid_object"}

    # 1. Split tokens by ',', ';', or '\n' (ignoring delimiters inside parentheses for rl(...))
    raw_tokens = []
    for line in str(object_str).splitlines():
        current: list[str] = []
        paren_depth = 0
        for char in line:
            if char == "(":
                paren_depth += 1
                current.append(char)
            elif char == ")":
                paren_depth = max(0, paren_depth - 1)
                current.append(char)
            elif (char in (",", ";")) and paren_depth == 0:
                t = "".join(current).strip()
                if t:
                    raw_tokens.append(t)
                current = []
            else:
                current.append(char)
        t = "".join(current).strip()
        if t:
            raw_tokens.append(t)

    if not raw_tokens:
        return None, "invalid_object", warnings, {"token": object_str, "message": "invalid_object"}

    pairs: list[tuple[str, str]] = []
    root_src_path = Path(root_source).resolve()
    root_tgt_path = (
        Path(root_target).resolve()
        if (root_target and str(root_target).strip())
        else root_src_path
    )

    single_token_candidate_unknown: str | None = None
    has_any_valid_path = False

    for token in raw_tokens:
        if "->" in token:
            if token.count("->") > 1:
                return (
                    None,
                    "invalid_rename",
                    warnings,
                    {
                        "token": token,
                        "message": f"invalid_rename: token '{token}' chứa nhiều hơn 1 dấu '->'",
                    },
                )
            src_tok, dst_tok = token.split("->", 1)
            src_tok = src_tok.strip()
            dst_tok = dst_tok.strip()
            if not dst_tok:
                return (
                    None,
                    "invalid_rename",
                    warnings,
                    {
                        "token": token,
                        "message": f"invalid_rename: dst rỗng trong token '{token}'",
                    },
                )
            if not src_tok:
                return (
                    None,
                    "invalid_rename",
                    warnings,
                    {
                        "token": token,
                        "message": f"invalid_rename: src rỗng trong token '{token}'",
                    },
                )

            # Classify src_tok:
            # a. Preset
            if src_tok.lower().startswith("preset:") or src_tok.lower() in PRESETS:
                return (
                    None,
                    "rename_not_supported",
                    warnings,
                    {
                        "token": token,
                        "message": f"rename_not_supported: preset '{src_tok}' không hỗ trợ rename",
                    },
                )

            # b. Suite
            if src_tok.lower().startswith("suite:"):
                ctrl_name = src_tok[len("suite:") :].strip()
                if not ctrl_name or not re.match(r"^[a-zA-Z0-9_]+$", ctrl_name):
                    return (
                        None,
                        "invalid_object",
                        warnings,
                        {
                            "token": token,
                            "message": f"invalid_object: suite name '{ctrl_name}' không hợp lệ. Chỉ chấp nhận ký tự an toàn [a-zA-Z0-9_].",
                        },
                    )

                if "/" in dst_tok or "\\" in dst_tok:
                    return (
                        None,
                        "invalid_rename",
                        warnings,
                        {
                            "token": token,
                            "message": f"invalid_rename: suite không được kèm dir_part trong dst: '{dst_tok}'",
                        },
                    )

                is_rl = bool(RE_RL_SE.match(dst_tok) or RE_RL_REPLACE.match(dst_tok))
                is_rlx = bool(RE_RLX_SE.match(dst_tok) or RE_RLX_REPLACE.match(dst_tok))
                if is_rl:
                    warnings.append(f"suite_rename_full_basename: '{dst_tok}'")
                elif not is_rlx:
                    if not re.match(r"^[a-zA-Z0-9_]+$", dst_tok):
                        return (
                            None,
                            "invalid_object",
                            warnings,
                            {
                                "token": token,
                                "message": f"invalid_object: tên mới '{dst_tok}' cho suite không hợp lệ. Chỉ chấp nhận ký tự an toàn [a-zA-Z0-9_].",
                            },
                        )

                found_suite_files = _expand_suite_files(
                    root_src_path, ctrl_name, warnings
                )
                if found_suite_files:
                    src_prefix = suite_prefix(ctrl_name)
                    dst_prefix = suite_prefix(dst_tok)
                    for cand in found_suite_files:
                        old_base = Path(cand).name
                        if is_rl or is_rlx:
                            new_base = apply_pattern(dst_tok, old_base)
                        else:
                            new_base = rename_suite_basename(
                                old_base, src_prefix, dst_prefix, ctrl_name, dst_tok
                            )

                        cand_parent = Path(cand).parent.as_posix()
                        d_rel = (
                            f"{cand_parent}/{new_base}"
                            if cand_parent and cand_parent != "."
                            else new_base
                        )
                        pairs.append((cand, to_posix(d_rel).lstrip("/")))
                        has_any_valid_path = True
                else:
                    warnings.append(f"suite_empty: '{ctrl_name}' (không tìm thấy file controller nào trên source)")
                continue

            # c. Glob
            if "*" in src_tok or "?" in src_tok:
                norm_pat = src_tok.replace("\\", "/").lstrip("/")
                if ".." in norm_pat.split("/"):
                    return None, "path_outside_project", warnings, {"token": token, "message": "path_outside_project"}

                is_folder_dst = dst_tok.endswith(("/", "\\"))
                last_seg = dst_tok.replace("\\", "/").rsplit("/", 1)[-1]
                has_rl = bool(
                    RE_RL_SE.match(last_seg)
                    or RE_RL_REPLACE.match(last_seg)
                    or RE_RLX_SE.match(last_seg)
                    or RE_RLX_REPLACE.match(last_seg)
                )
                if not is_folder_dst and not has_rl:
                    return (
                        None,
                        "invalid_rename",
                        warnings,
                        {
                            "token": token,
                            "message": f"invalid_rename: glob source '{src_tok}' yêu cầu dst phải là folder (kết thúc '/') hoặc chứa pattern rl()/rlx()",
                        },
                    )

                try:
                    matched_files = [f for f in root_src_path.glob(norm_pat) if f.is_file()]
                    if not matched_files:
                        warnings.append(f"no_files_matched_glob: {src_tok}")
                    for mf in matched_files:
                        try:
                            s_rel = mf.relative_to(root_src_path).as_posix()
                            d_rel, err_code, err_msg = resolve_dst(dst_tok, s_rel, root_tgt_path)
                            if err_code:
                                return None, err_code, warnings, {"token": token, "message": err_msg}
                            pairs.append((s_rel, d_rel))
                            has_any_valid_path = True
                        except ValueError:
                            return None, "path_outside_project", warnings, {"token": token, "message": "path_outside_project"}
                except Exception as e:
                    warnings.append(f"glob_error for '{src_tok}': {e}")
                continue

            # d. Directory & Single file
            norm_token = src_tok.replace("\\", "/").strip().lstrip("/")
            parts = norm_token.split("/")
            if ".." in parts:
                return None, "path_outside_project", warnings, {"token": token, "message": "path_outside_project"}

            token_path = Path(src_tok)
            if token_path.is_absolute():
                try:
                    candidate_target = token_path.resolve()
                    s_rel = candidate_target.relative_to(root_src_path).as_posix()
                except ValueError:
                    return None, "path_outside_project", warnings, {"token": token, "message": "path_outside_project"}
            else:
                candidate_target = (root_src_path / norm_token).resolve()
                s_rel = norm_token

            if candidate_target.is_dir():
                if expand_dirs:
                    is_folder_dst = dst_tok.endswith(("/", "\\"))
                    last_seg = dst_tok.replace("\\", "/").rsplit("/", 1)[-1]
                    has_rl = bool(
                        RE_RL_SE.match(last_seg)
                        or RE_RL_REPLACE.match(last_seg)
                        or RE_RLX_SE.match(last_seg)
                        or RE_RLX_REPLACE.match(last_seg)
                    )
                    if not is_folder_dst and not has_rl:
                        return (
                            None,
                            "invalid_rename",
                            warnings,
                            {
                                "token": token,
                                "message": f"invalid_rename: directory source '{src_tok}' yêu cầu dst phải là folder (kết thúc '/') hoặc chứa pattern rl()/rlx()",
                            },
                        )

                    matched_dir_files = []
                    for dirpath, _, filenames in os.walk(str(candidate_target)):
                        for fname in sorted(filenames):
                            if fname.lower().endswith((".f", ".xsd")):
                                continue
                            f_abs = Path(dirpath) / fname
                            try:
                                f_rel = f_abs.relative_to(root_src_path).as_posix()
                                matched_dir_files.append(f_rel)
                            except ValueError:
                                pass
                    if not matched_dir_files:
                        warnings.append(f"no_files_found_in_dir: {src_tok}")
                    for f_rel in matched_dir_files:
                        d_rel, err_code, err_msg = resolve_dst(dst_tok, f_rel, root_tgt_path)
                        if err_code:
                            return None, err_code, warnings, {"token": token, "message": err_msg}
                        pairs.append((f_rel, d_rel))
                        has_any_valid_path = True
                    continue
                else:
                    return (
                        None,
                        "is_directory",
                        warnings,
                        {
                            "token": token,
                            "message": f"Token '{src_tok}' là thư mục trên source. Hãy dùng '{src_tok}/*' hoặc '{src_tok}/**/*' hoặc đặt expand_dirs=true để quét danh sách file con.",
                        },
                    )

            # Single file
            d_rel, err_code, err_msg = resolve_dst(dst_tok, s_rel, root_tgt_path)
            if err_code:
                return None, err_code, warnings, {"token": token, "message": err_msg}
            pairs.append((s_rel, d_rel))
            has_any_valid_path = True

        else:
            # Token không có '->': giữ nguyên luồng cũ
            if token.lower().startswith("suite:"):
                ctrl_name = token[len("suite:") :].strip()
                if not ctrl_name or not re.match(r"^[a-zA-Z0-9_]+$", ctrl_name):
                    return (
                        None,
                        "invalid_object",
                        warnings,
                        {
                            "token": token,
                            "message": f"invalid_object: suite name '{ctrl_name}' không hợp lệ. Chỉ chấp nhận ký tự an toàn [a-zA-Z0-9_].",
                        },
                    )
                found_suite_files = _expand_suite_files(
                    root_src_path, ctrl_name, warnings
                )
                if found_suite_files:
                    pairs.extend((cand, cand) for cand in found_suite_files)
                    has_any_valid_path = True
                else:
                    warnings.append(f"suite_empty: '{ctrl_name}' (không tìm thấy file controller nào trên source)")
                continue

            if token.lower().startswith("preset:"):
                preset_name = token[len("preset:") :].strip().lower()
                if preset_name in PRESETS:
                    pairs.extend((p, p) for p in PRESETS[preset_name])
                    has_any_valid_path = True
                else:
                    return (
                        None,
                        "unknown_preset",
                        warnings,
                        {
                            "token": token,
                            "message": f"unknown_preset: token '{preset_name}' (from '{token}')",
                        },
                    )
                continue

            if token.lower() in PRESETS:
                pairs.extend((p, p) for p in PRESETS[token.lower()])
                has_any_valid_path = True
                continue

            if "*" in token or "?" in token:
                norm_pat = token.replace("\\", "/").lstrip("/")
                if ".." in norm_pat.split("/"):
                    return None, "path_outside_project", warnings, {"token": token, "message": "path_outside_project"}

                try:
                    matched_files = [f for f in root_src_path.glob(norm_pat) if f.is_file()]
                    if not matched_files:
                        warnings.append(f"no_files_matched_glob: {token}")
                    for mf in matched_files:
                        try:
                            rel = mf.relative_to(root_src_path).as_posix()
                            pairs.append((rel, rel))
                            has_any_valid_path = True
                        except ValueError:
                            return None, "path_outside_project", warnings, {"token": token, "message": "path_outside_project"}
                except Exception as e:
                    warnings.append(f"glob_error for '{token}': {e}")
                continue

            norm_token = token.replace("\\", "/").strip().lstrip("/")
            parts = norm_token.split("/")
            if ".." in parts:
                return None, "path_outside_project", warnings, {"token": token, "message": "path_outside_project"}

            token_path = Path(token)
            if token_path.is_absolute():
                try:
                    candidate_target = token_path.resolve()
                    rel = candidate_target.relative_to(root_src_path).as_posix()
                except ValueError:
                    return None, "path_outside_project", warnings, {"token": token, "message": "path_outside_project"}
            else:
                candidate_target = (root_src_path / norm_token).resolve()
                rel = norm_token

            if candidate_target.is_dir():
                if expand_dirs:
                    matched_dir_files = []
                    for dirpath, _, filenames in os.walk(str(candidate_target)):
                        for fname in sorted(filenames):
                            if fname.lower().endswith((".f", ".xsd")):
                                continue
                            f_abs = Path(dirpath) / fname
                            try:
                                f_rel = f_abs.relative_to(root_src_path).as_posix()
                                matched_dir_files.append(f_rel)
                            except ValueError:
                                pass
                    if not matched_dir_files:
                        warnings.append(f"no_files_found_in_dir: {token}")
                    for f_rel in matched_dir_files:
                        pairs.append((f_rel, f_rel))
                    has_any_valid_path = True
                    continue
                else:
                    return (
                        None,
                        "is_directory",
                        warnings,
                        {
                            "token": token,
                            "message": f"Token '{token}' là thư mục trên source. Hãy dùng '{token}/*' hoặc '{token}/**/*' hoặc đặt expand_dirs=true để quét danh sách file con.",
                        },
                    )

            has_slash = "/" in norm_token
            has_ext = bool(token_path.suffix)
            if not has_slash and not has_ext:
                if candidate_target.exists():
                    pairs.append((rel, rel))
                    has_any_valid_path = True
                else:
                    single_token_candidate_unknown = token
                continue

            pairs.append((rel, rel))
            has_any_valid_path = True

    if single_token_candidate_unknown and not has_any_valid_path:
        return (
            None,
            "unknown_preset",
            warnings,
            {
                "token": single_token_candidate_unknown,
                "message": f"unknown_preset: token '{single_token_candidate_unknown}' (from '{single_token_candidate_unknown}')",
            },
        )

    # Deduplicate preserving order
    seen: set[tuple[str, str]] = set()
    unique_pairs: list[tuple[str, str]] = []
    for s_rel, d_rel in pairs:
        s_norm = to_posix(s_rel).lstrip("/")
        d_norm = to_posix(d_rel).lstrip("/")
        key = (s_norm, d_norm)
        if s_norm and d_norm and key not in seen:
            seen.add(key)
            unique_pairs.append(key)

    if not unique_pairs:
        if single_token_candidate_unknown:
            return (
                None,
                "unknown_preset",
                warnings,
                {
                    "token": single_token_candidate_unknown,
                    "message": f"unknown_preset: token '{single_token_candidate_unknown}'",
                },
            )
        if any(w.startswith("suite_empty:") for w in warnings):
            return (
                None,
                "suite_empty",
                warnings,
                {
                    "token": object_str,
                    "message": f"suite_empty: không tìm thấy file nào trên source cho suite '{object_str}'",
                },
            )
        return None, "invalid_object", warnings, {"token": object_str, "message": "invalid_object"}

    return unique_pairs, None, warnings, None


def run_type3_file_clone(
    object: str = "",
    project_source: str = "",
    project_target: str = "",
    execute: Any = False,
    overwrite: Any = False,
    confirm_overwrite: Any = False,
    expand_dirs: Any = False,
    max_files: int = 100,
    copy_filter: str = "missing",
    list_presets: Any = False,
    planned_sample_size: int = 10,
    warnings: list[str] | None = None,
    start_time: float | None = None,
) -> dict[str, Any]:
    """Execute type=3 file clone flow."""
    if warnings is None:
        warnings = []
    if start_time is None:
        start_time = time.perf_counter()

    exec_coerced = coerce_bool(execute)
    overwrite_coerced = coerce_bool(overwrite)
    confirm_ow_coerced = coerce_bool(confirm_overwrite)
    expand_dirs_coerced = coerce_bool(expand_dirs)
    list_presets_coerced = coerce_bool(list_presets)

    # 0. Check list_presets
    if list_presets_coerced or (isinstance(object, str) and object.strip().lower() == "preset:?"):
        return {
            "success": True,
            "spec_version": "1.0",
            "type": 3,
            "mode": "list_presets",
            "presets": [{"name": k, "paths": v} for k, v in PRESETS.items()],
            "warnings": warnings,
        }

    # 1. Validation
    if not object or not str(object).strip():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_object",
            "message": "object is required",
            "warnings": warnings,
        }

    if not project_source or not str(project_source).strip():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_source",
            "message": "project_source is required",
            "warnings": warnings,
        }

    has_target = bool(project_target and str(project_target).strip())
    if has_target:
        if not Path(project_target).is_absolute():
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 3,
                "error_code": "invalid_project_target",
                "message": "project_target must be an absolute path",
                "warnings": warnings,
            }

    # Verify project paths are absolute
    if not Path(project_source).is_absolute():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_source",
            "message": "project_source must be an absolute path",
            "warnings": warnings,
        }

    # 2. Resolve roots
    root_src = resolve_project_root(project_source)
    if not root_src or not Path(root_src).exists():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_source",
            "message": f"Cannot resolve or find project_source root: {project_source}",
            "warnings": warnings,
        }

    if has_target:
        root_tgt = resolve_project_root(project_target)
        if not root_tgt or not Path(root_tgt).exists():
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 3,
                "error_code": "invalid_project_target",
                "message": f"Cannot resolve or find project_target root: {project_target}",
                "warnings": warnings,
            }
    else:
        root_tgt = root_src

    root_src_path = Path(root_src)
    root_tgt_path = Path(root_tgt)

    # 3. Expand object tokens
    pairs, err_code, exp_warnings, err_detail = expand_object_tokens(
        object, root_src, root_target=root_tgt, expand_dirs=expand_dirs_coerced
    )
    warnings.extend(exp_warnings)

    if err_code:
        msg = err_detail.get("message") if err_detail else f"Failed to expand object: {err_code}"
        res_err: dict[str, Any] = {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": err_code,
            "message": msg,
            "warnings": warnings,
        }
        if err_detail:
            res_err["detail"] = err_detail
        return res_err

    assert pairs is not None

    # 3b. Giới hạn max_files
    limit_files = int(max_files) if (isinstance(max_files, (int, str)) and str(max_files).isdigit() and int(max_files) > 0) else 100
    truncated_max_files = False
    total_expanded_count = len(pairs)

    if total_expanded_count > limit_files:
        if exec_coerced:
            return {
                "success": False,
                "spec_version": "1.0",
                "type": 3,
                "error_code": "too_many_files",
                "message": f"Số lượng file ({total_expanded_count}) vượt quá max_files ({limit_files}). Hãy lọc bớt hoặc tăng max_files.",
                "file_count": total_expanded_count,
                "sample_paths": [p[0] for p in pairs[:20]],
                "truncated": True,
                "warnings": warnings,
            }
        else:
            truncated_max_files = True
            warnings.append("truncated_max_files")
            pairs = pairs[:limit_files]

    if not copy_filter or str(copy_filter).strip().lower() in ("", "default"):
        filter_norm = "all" if overwrite_coerced else "missing"
    else:
        raw_filter = str(copy_filter).strip().lower()
        if raw_filter in ("missing", "different", "all"):
            filter_norm = raw_filter
        else:
            filter_norm = "all" if overwrite_coerced else "missing"

    planned: list[dict[str, Any]] = []
    will_copy: list[str] = []
    exists_on_target: list[dict[str, Any]] = []
    skipped_exists: list[str] = []
    skipped_denied: list[str] = []
    skipped_same_source: list[str] = []
    missing_on_source: list[str] = []
    copied: list[str] = []
    failed: list[dict[str, Any]] = []
    path_suggestions: list[str] = []
    blocked_different: list[str] = []

    # 4. Plan and inspect each file
    for src_rel, dst_rel in pairs:
        src_file = root_src_path / src_rel
        tgt_file = root_tgt_path / dst_rel

        # Check deny rule (*.f, *.xsd) on both src and dst
        if (
            src_rel.lower().endswith((".f", ".xsd"))
            or fnmatch.fnmatch(src_rel.lower(), "*.f")
            or fnmatch.fnmatch(src_rel.lower(), "*.xsd")
            or dst_rel.lower().endswith((".f", ".xsd"))
            or fnmatch.fnmatch(dst_rel.lower(), "*.f")
            or fnmatch.fnmatch(dst_rel.lower(), "*.xsd")
        ):
            planned_item = {
                "relative": src_rel,
                "target_relative": dst_rel,
                "status": "denied",
                "size_source": src_file.stat().st_size if src_file.is_file() else None,
                "size_target": tgt_file.stat().st_size if tgt_file.is_file() else None,
                "hash_source": None,
                "hash_target": None,
            }
            planned.append(planned_item)
            skipped_denied.append(src_rel)
            continue

        # Guard: Same file (src_file.resolve() == tgt_file.resolve())
        try:
            is_same_file = src_file.resolve() == tgt_file.resolve()
        except Exception:
            is_same_file = False

        if is_same_file:
            planned_item = {
                "relative": src_rel,
                "target_relative": dst_rel,
                "status": "same_source_target",
                "size_source": src_file.stat().st_size if src_file.is_file() else None,
                "size_target": tgt_file.stat().st_size if tgt_file.is_file() else None,
                "hash_source": None,
                "hash_target": None,
            }
            planned.append(planned_item)
            skipped_same_source.append(src_rel)
            warnings.append(f"same_source_target: '{src_rel}'")
            continue

        # Check source existence
        if not src_file.is_file():
            planned_item = {
                "relative": src_rel,
                "target_relative": dst_rel,
                "status": "missing_on_source",
                "size_source": None,
                "size_target": tgt_file.stat().st_size if tgt_file.is_file() else None,
                "hash_source": None,
                "hash_target": None,
            }
            # Path hint suggestion for missing file
            candidate_prefixes = ["App_Data/Controllers/", "App_Data/"]
            for cp in candidate_prefixes:
                if not src_rel.startswith(cp):
                    probe_rel = f"{cp}{src_rel}".replace("//", "/")
                    if (root_src_path / probe_rel).is_file():
                        planned_item["suggestion"] = probe_rel
                        if probe_rel not in path_suggestions:
                            path_suggestions.append(probe_rel)
                        warnings.append(
                            f"path_suggestion: '{src_rel}' không tồn tại trên source, nhưng tìm thấy '{probe_rel}'. "
                            f"Hãy kiểm tra và gọi lại với '{probe_rel}' nếu đúng."
                        )
                        break

            planned.append(planned_item)
            missing_on_source.append(src_rel)
            continue

        # Source exists
        src_stat = src_file.stat()
        size_src = src_stat.st_size
        mtime_src = src_stat.st_mtime
        hash_src: str | None = None

        if size_src <= HASH_MAX_BYTES:
            try:
                hash_src = calculate_sha256(src_file)
            except Exception as e:
                warnings.append(f"hash_source_error for {src_rel}: {e}")
        else:
            warnings.append(
                f"hash_skipped_large_file: {src_rel} ({size_src} bytes > {HASH_MAX_BYTES})"
            )

        # Check target existence
        if not tgt_file.is_file():
            planned_item = {
                "relative": src_rel,
                "target_relative": dst_rel,
                "status": "missing_on_target",
                "size_source": size_src,
                "size_target": None,
                "hash_source": hash_src,
                "hash_target": None,
            }
            planned.append(planned_item)

            if filter_norm in ("missing", "all"):
                will_copy.append(src_rel)
                # Copy missing_on_target if execute=True
                if exec_coerced:
                    try:
                        tgt_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, tgt_file)
                        copied.append(src_rel)
                    except Exception as e:
                        failed.append({"relative": src_rel, "error": str(e)})
            continue

        # Target exists: determine content same vs different
        tgt_stat = tgt_file.stat()
        size_tgt = tgt_stat.st_size
        mtime_tgt = tgt_stat.st_mtime
        hash_tgt: str | None = None
        content_diff: str = "different"

        if size_src <= HASH_MAX_BYTES and size_tgt <= HASH_MAX_BYTES:
            try:
                hash_tgt = calculate_sha256(tgt_file)
                content_diff = "same" if (hash_src and hash_tgt and hash_src == hash_tgt) else "different"
            except Exception as e:
                warnings.append(f"hash_target_error for {dst_rel}: {e}")
        else:
            # Large file (>32MB): compare size and mtime difference < 1s
            if size_src == size_tgt and abs(mtime_src - mtime_tgt) < 1.0:
                content_diff = "same"
            else:
                content_diff = "different"

        planned_item = {
            "relative": src_rel,
            "target_relative": dst_rel,
            "status": "exists_on_target",
            "content": content_diff,
            "size_source": size_src,
            "size_target": size_tgt,
            "hash_source": hash_src,
            "hash_target": hash_tgt,
        }
        planned.append(planned_item)

        exist_info = {
            "relative": src_rel,
            "target_relative": dst_rel,
            "content": content_diff,
            "size_source": size_src,
            "size_target": size_tgt,
        }
        exists_on_target.append(exist_info)

        # Check candidate for overwrite
        is_candidate_for_copy = (filter_norm == "all") or (filter_norm == "different" and content_diff == "different")

        if is_candidate_for_copy and overwrite_coerced:
            if confirm_ow_coerced:
                will_copy.append(src_rel)
                if exec_coerced:
                    try:
                        tgt_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, tgt_file)
                        copied.append(src_rel)
                    except Exception as e:
                        failed.append({"relative": src_rel, "error": str(e)})
            else:
                # Soft-gate: overwrite=True but confirm_overwrite=False
                skipped_exists.append(src_rel)
                if content_diff == "different":
                    blocked_different.append(src_rel)
        else:
            skipped_exists.append(src_rel)
            if is_candidate_for_copy and content_diff == "different" and not overwrite_coerced:
                blocked_different.append(src_rel)

    # Empty batch guard for same_source_target
    if planned and len(skipped_same_source) == len(planned):
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_object",
            "message": f"invalid_object: same_source_target: mọi file nguồn và đích trùng nhau ({', '.join(skipped_same_source)})",
            "warnings": warnings,
            "skipped_same_source": skipped_same_source,
        }

    # 5. Summary counts (always calculated on full processed batch <= max_files)
    summary_counts = {
        "missing_on_target": len([p for p in planned if p["status"] == "missing_on_target"]),
        "missing_on_source": len([p for p in planned if p["status"] == "missing_on_source"]),
        "exists_same": len([p for p in planned if p["status"] == "exists_on_target" and p.get("content") == "same"]),
        "exists_different": len([p for p in planned if p["status"] == "exists_on_target" and p.get("content") == "different"]),
        "same_source_target": len([p for p in planned if p["status"] == "same_source_target"]),
        "denied": len([p for p in planned if p["status"] == "denied"]),
        "will_copy": len(will_copy),
    }

    # Warning for blocked_different
    if filter_norm in ("different", "all") and blocked_different:
        n_blocked = len(blocked_different)
        sample_blocked = ", ".join(blocked_different[:10])
        if not overwrite_coerced:
            warnings.append(
                f"copy_filter_different_blocked: {n_blocked} file khác nội dung ({sample_blocked}) "
                f"nhưng chưa nằm trong will_copy vì overwrite=false. "
                f"Muốn copy các file different -> dry-run/execute với overwrite=true và confirm_overwrite=true (sau khi hỏi user)."
            )
        elif not confirm_ow_coerced:
            warnings.append(
                f"copy_filter_different_blocked: {n_blocked} file khác nội dung ({sample_blocked}) "
                f"nhưng chưa nằm trong will_copy vì confirm_overwrite=false. "
                f"Muốn copy các file different -> gọi lại với confirm_overwrite=true (sau khi hỏi user)."
            )

    # Warning for sensitive_path in will_copy
    for wc in will_copy:
        wc_lower = wc.lower().replace("\\", "/")
        if wc_lower == "web.config" or wc_lower.endswith("/web.config") or "emailconfig.xml" in wc_lower:
            warnings.append(
                f"sensitive_path: '{wc}' nằm trong will_copy (copy_filter={filter_norm}). "
                "Xác nhận với user trước khi execute."
            )

    processed_planned_count = len(planned)
    processed_exists_count = len(exists_on_target)
    planned_omitted = 0

    if truncated_max_files:
        sample_size = (
            int(planned_sample_size)
            if (isinstance(planned_sample_size, (int, str)) and str(planned_sample_size).isdigit() and int(planned_sample_size) > 0)
            else 10
        )
        if len(planned) > sample_size:
            b_missing = [p for p in planned if p["status"] == "missing_on_target"]
            b_diff = [p for p in planned if p["status"] == "exists_on_target" and p.get("content") == "different"]
            b_same = [p for p in planned if p["status"] == "exists_on_target" and p.get("content") == "same"]
            b_same_src = [p for p in planned if p["status"] == "same_source_target"]
            b_other = [p for p in planned if p not in b_missing and p not in b_diff and p not in b_same and p not in b_same_src]

            buckets = [b_missing, b_diff, b_same, b_same_src, b_other]
            sampled_items: list[dict[str, Any]] = []
            sampled_ids: set[int] = set()

            b_idx = 0
            while len(sampled_items) < sample_size and any(b_idx < len(b) for b in buckets):
                for b in buckets:
                    if b_idx < len(b) and len(sampled_items) < sample_size:
                        item = b[b_idx]
                        sampled_items.append(item)
                        sampled_ids.add(id(item))
                b_idx += 1

            sampled_planned = [p for p in planned if id(p) in sampled_ids]
            planned_omitted = len(planned) - len(sampled_planned)
            planned = sampled_planned

            sampled_rels = {p["relative"] for p in planned}
            will_copy = [r for r in will_copy if r in sampled_rels]
            exists_on_target = [it for it in exists_on_target if it["relative"] in sampled_rels]
            skipped_exists = [r for r in skipped_exists if r in sampled_rels]
            skipped_denied = [r for r in skipped_denied if r in sampled_rels]
            skipped_same_source = [r for r in skipped_same_source if r in sampled_rels]
            missing_on_source = [r for r in missing_on_source if r in sampled_rels]

        warnings.append(
            f"planned_truncated: showing {len(planned)} of {processed_planned_count} processed (total_expanded={total_expanded_count})"
        )

    # 6. User prompt and Agent messages
    needs_user_confirm = bool(
        (summary_counts["exists_same"] > 0 or summary_counts["exists_different"] > 0)
        and not (overwrite_coerced and confirm_ow_coerced)
    )

    if needs_user_confirm:
        diff_summaries = [f"{it['target_relative']} (content={it['content']})" for it in exists_on_target]
        omitted_exists = processed_exists_count - len(exists_on_target)
        if (truncated_max_files or planned_omitted > 0) and omitted_exists > 0:
            extra_msg = (
                f" … và {omitted_exists} file exists khác đã ẩn (truncated). "
                f"Xem summary_counts / gọi lại với object hẹp hoặc tăng planned_sample_size nếu cần xem đủ tên."
            )
        else:
            extra_msg = ""

        extra_msg_clean = extra_msg.rstrip(".")
        user_prompt = (
            f"Các file sau ĐÃ CÓ trên project đích (không tự ghi đè): "
            f"{', '.join(diff_summaries)}{extra_msg_clean}. Bạn có muốn ghi đè không? Nếu có, Agent gọi lại "
            f"clone_things type=3 với execute=true, overwrite=true và confirm_overwrite=true."
        )
        if filter_norm in ("different", "all") and blocked_different and not overwrite_coerced:
            agent_message = (
                f"copy_filter={filter_norm}: {len(blocked_different)} file khác nội dung chưa nằm trong will_copy vì overwrite=false. "
                f"Cần xác nhận của user trước khi đặt overwrite=true + confirm_overwrite=true. Không tự đè."
            )
        else:
            agent_message = (
                "Có file đã tồn tại trên đích → Cần xác nhận của user trước khi đặt confirm_overwrite=true. Không tự đè."
            )
    else:
        user_prompt = ""
        if not exec_coerced:
            agent_message = (
                f"Dry-run type=3: {summary_counts['will_copy']} file planned. Gọi lại execute=true sau khi user xác nhận."
            )
        else:
            agent_message = (
                f"Execute type=3 hoàn tất: {len(copied)} file copied, {len(failed)} failed."
            )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    return {
        "success": True,
        "spec_version": "1.0",
        "type": 3,
        "mode": "file_clone",
        "project_source": root_src,
        "project_target": root_tgt,
        "object": object,
        "execute": exec_coerced,
        "overwrite": overwrite_coerced,
        "confirm_overwrite": confirm_ow_coerced,
        "copy_filter": filter_norm,
        "needs_user_confirm": needs_user_confirm,
        "summary_counts": summary_counts,
        "truncated": truncated_max_files,
        "planned": planned,
        "will_copy": will_copy,
        "blocked_different": blocked_different[:20],
        "suggestions": path_suggestions,
        "exists_on_target": exists_on_target,
        "copied": copied,
        "skipped_exists": skipped_exists,
        "skipped_denied": skipped_denied,
        "skipped_same_source": skipped_same_source,
        "missing_on_source": missing_on_source,
        "failed": failed,
        "warnings": warnings,
        "user_prompt": user_prompt,
        "agent_message": agent_message,
        "meta": {
            "execute": exec_coerced,
            "overwrite": overwrite_coerced,
            "confirm_overwrite": confirm_ow_coerced,
            "file_count": len(planned),
            "total_expanded": total_expanded_count,
            "planned_omitted": planned_omitted,
            "hash_max_bytes": HASH_MAX_BYTES,
            "elapsed_ms": elapsed_ms,
        },
    }

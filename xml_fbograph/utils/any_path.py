"""Universal path resolver — agent truyền path bất kỳ, MCP tự resolve.

Chấp nhận: absolute file/dir (local hoặc UNC), relative path
("Dir/SOTran.xml", "ClientScript", "Main/x.aspx"...).
Relative resolve theo thứ tự base: reference_file -> sticky context
(_LAST_PROJECT_ROOT) -> các project đã biết (LRU); mỗi base thử
``<root>/App_Data/Controllers/<rel>`` rồi ``<root>/<rel>``.
"""

from __future__ import annotations

import difflib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from xml_fbograph.utils.path_helper import _normalize_path_str, ProjectPathHelper

_MAX_KNOWN_PROJECTS = 8

# Sticky project context — set mỗi khi resolve thành công 1 path thuộc project.
_LAST_PROJECT_ROOT: Optional[str] = None
_PROJECT_ROOTS: list[str] = []


def reset_sticky_context() -> None:
    """Xóa sticky context (dùng cho testing / server reload)."""
    global _LAST_PROJECT_ROOT, _PROJECT_ROOTS
    _LAST_PROJECT_ROOT = None
    _PROJECT_ROOTS = []


def _is_project_marker_dir(path: Path) -> bool:
    """True khi dir có marker project FBO: App_Data/Controllers hoặc Web.config."""
    try:
        return (path / "App_Data" / "Controllers").is_dir() or (
            path / "Web.config"
        ).is_file()
    except OSError:
        return False


def _known_project_containing(norm_path: str) -> Optional[str]:
    """Root trong _PROJECT_ROOTS là CHA strict của norm_path.

    None khi norm_path trùng 1 known root hoặc không thuộc project nào.
    """
    try:
        p = Path(norm_path).resolve()
    except Exception:
        p = Path(norm_path)
    candidates = ([_LAST_PROJECT_ROOT] if _LAST_PROJECT_ROOT else []) + list(
        _PROJECT_ROOTS
    )
    seen: set[str] = set()
    for root in candidates:
        if not root or root.lower() in seen:
            continue
        seen.add(root.lower())
        try:
            rp = Path(root).resolve()
        except Exception:
            rp = Path(root)
        try:
            p.relative_to(rp)
        except ValueError:
            continue
        return None if p == rp else str(rp)
    return None


def _nearest_controllers_root(path: Path) -> Optional[str]:
    """Ancestor gần nhất (kể cả chính nó) có App_Data/Controllers — marker mạnh."""
    cur = path
    while True:
        try:
            if (cur / "App_Data" / "Controllers").is_dir():
                return os.path.normpath(str(cur)).rstrip("\\/")
        except OSError:
            return None
        if cur.parent == cur:
            return None
        cur = cur.parent


def _canonical_project_root(project_root: str | Path | None) -> Optional[str]:
    """Chuẩn hóa detected root về project root thật.

    - Subfolder của project đã biết -> root cha (không tính project mới).
    - Marker mạnh App_Data/Controllers ở ancestor gần nhất -> root đó
      (subfolder có Web.config riêng không được tính project).
    - Chỉ Web.config (không Controllers ở ancestors) -> chấp nhận.
    - Không marker nào -> None.
    """
    if not project_root:
        return None
    norm = os.path.normpath(str(project_root)).rstrip("\\/")
    if not norm:
        return None
    if norm.lower() in {r.lower() for r in _PROJECT_ROOTS}:
        return norm
    strong = _nearest_controllers_root(Path(norm))
    if strong is not None:
        return strong
    parent = _known_project_containing(norm)
    if parent is not None:
        return parent
    return norm if _is_project_marker_dir(Path(norm)) else None


def set_project_root(project_root: str | Path | None) -> Optional[str]:
    """Nuôi sticky context khi detect được project root.

    Chỉ set khi root thật sự là project root (có marker) hoặc quy về project
    cha đã biết — subfolder của project không tính project mới.
    Trả về root cũ khi sticky chuyển từ project khác (root cũ non-null và khác
    root mới); None khi lần đầu set hoặc set lại cùng project.
    """
    global _LAST_PROJECT_ROOT
    norm = _canonical_project_root(project_root)
    if not norm:
        return None
    low = norm.lower()
    switched_from: Optional[str] = None
    if _LAST_PROJECT_ROOT and _LAST_PROJECT_ROOT.lower() != low:
        switched_from = _LAST_PROJECT_ROOT
    for existing in list(_PROJECT_ROOTS):
        if existing.lower() == low:
            _PROJECT_ROOTS.remove(existing)
            break
    _PROJECT_ROOTS.insert(0, norm)
    del _PROJECT_ROOTS[_MAX_KNOWN_PROJECTS:]
    _LAST_PROJECT_ROOT = norm
    return switched_from


def known_projects() -> list[str]:
    """Danh sách project root đã biết (LRU, mới nhất trước)."""
    return list(_PROJECT_ROOTS)


def project_switch_message(
    switched_from: Optional[str], new_root: Optional[str]
) -> Optional[str]:
    """Warning text khi sticky context vừa đổi project (None nếu không đổi)."""
    if not switched_from or not new_root or switched_from == new_root:
        return None
    return (
        f"project_root switched: {switched_from} → {new_root} "
        "(sticky context — nếu đang làm 2 project, truyền abs path/reference_file để pin)"
    )


@dataclass
class ResolvedPath:
    ok: bool
    abs_path: str = ""
    kind: str = ""  # "file" | "dir"
    project_root: Optional[str] = None
    resolved_via: str = ""  # "absolute" | "project_root" | "controllers_root" | "sticky_context"
    switched_from: Optional[str] = None  # root cũ khi sticky vừa đổi project
    error: Optional[dict] = None


def _detect_project_root(path: Path) -> Optional[str]:
    """Detect project root FBO chứa path (cắt tại App_Data hoặc walk tìm Web.config)."""
    try:
        from find_connect_by_path.path_resolver import get_project_root_from_path

        root = get_project_root_from_path(str(path))
        if root:
            return os.path.normpath(str(root)).rstrip("\\/")
    except Exception:
        pass
    return None


def _fuzzy_hint(path: Path) -> Optional[str]:
    """Gợi ý 1 entry gần giống trong folder cha (gõ sai chính tả?)."""
    try:
        parent = path.parent
        if not parent.is_dir():
            return None
        names = [e.name for e in os.scandir(str(parent))]
        close = difflib.get_close_matches(path.name, names, n=1, cutoff=0.6)
        if close:
            return f"Gần giống: {close[0]} (gõ sai chính tả?)"
    except Exception:
        pass
    return None


def _path_not_found(raw: str, tried: list[str], hint_path: Optional[Path] = None) -> ResolvedPath:
    error = {
        "success": False,
        "error_code": "path_not_found",
        "input": raw,
        "tried": tried,
        "known_projects": known_projects(),
    }
    hint = _fuzzy_hint(hint_path) if hint_path is not None else None
    if hint:
        error["hint"] = hint
    return ResolvedPath(ok=False, error=error)


def _strip_quotes(s: str) -> str:
    return s.strip().strip('"').strip("'").strip()


def resolve_any_path(path_str: str, reference_file: str = "") -> ResolvedPath:
    """Resolve path bất kỳ (abs file/dir, relative) thành absolute path trên disk.

    - Abs + tồn tại: xong; detect project_root, nuôi sticky context.
    - Relative: thử ``<root>/App_Data/Controllers/<rel>`` rồi ``<root>/<rel>``
      với root lấy từ reference_file -> sticky context -> known projects.
    - Không resolve được: error ``path_not_found`` kèm ``tried[]`` + ``hint``;
      chưa có context nào: error ``no_project_context``.
    """
    raw = _strip_quotes(str(path_str or ""))
    if not raw:
        return ResolvedPath(
            ok=False,
            error={
                "success": False,
                "error_code": "invalid_path",
                "input": str(path_str or ""),
                "message": "path is required",
            },
        )

    norm = _normalize_path_str(raw)
    p = Path(norm)

    if p.is_absolute():
        if p.exists():
            try:
                p = p.resolve()
            except Exception:
                pass
            kind = "file" if p.is_file() else "dir"
            project_root = _canonical_project_root(_detect_project_root(p))
            switched_from = set_project_root(project_root) if project_root else None
            return ResolvedPath(
                ok=True,
                abs_path=str(p),
                kind=kind,
                project_root=project_root,
                resolved_via="absolute",
                switched_from=switched_from,
            )
        return _path_not_found(raw, [norm], p)

    # --- Relative path ---
    bases: list[tuple[str, bool]] = []  # (project_root, from_sticky)
    seen_bases: set[str] = set()

    ref = _strip_quotes(str(reference_file or ""))
    if ref:
        ref_root: Optional[str] = _detect_project_root(Path(_normalize_path_str(ref)))
        if not ref_root:
            try:
                ref_root = str(ProjectPathHelper(ref).get_project_root())
            except Exception:
                ref_root = None
        if ref_root:
            ref_norm = _canonical_project_root(ref_root) or ""
            if ref_norm and ref_norm.lower() not in seen_bases:
                seen_bases.add(ref_norm.lower())
                bases.append((ref_norm, False))

    sticky = _LAST_PROJECT_ROOT
    if sticky and sticky.lower() not in seen_bases:
        seen_bases.add(sticky.lower())
        bases.append((sticky, True))
    for proj in _PROJECT_ROOTS:
        if proj.lower() not in seen_bases:
            seen_bases.add(proj.lower())
            bases.append((proj, True))

    if not bases:
        return ResolvedPath(
            ok=False,
            error={
                "success": False,
                "error_code": "no_project_context",
                "input": raw,
                "message": (
                    "no_project_context: truyền 1 path abs bất kỳ trong project 1 lần, "
                    "hoặc kèm reference_file"
                ),
                "known_projects": [],
            },
        )

    tried: list[str] = []
    last_candidate: Optional[Path] = None
    for base, from_sticky in bases:
        base_path = Path(base)
        controllers = base_path / "App_Data" / "Controllers"
        for candidate, via in (
            (controllers / norm, "controllers_root"),
            (base_path / norm, "project_root"),
        ):
            tried.append(str(candidate))
            last_candidate = candidate
            if candidate.exists():
                resolved = candidate.resolve()
                try:
                    resolved.relative_to(base_path.resolve())
                except ValueError:
                    continue  # vượt ra ngoài project (../) — bỏ qua
                kind = "file" if resolved.is_file() else "dir"
                project_root = _canonical_project_root(_detect_project_root(resolved)) or base
                switched_from = set_project_root(project_root)
                return ResolvedPath(
                    ok=True,
                    abs_path=str(resolved),
                    kind=kind,
                    project_root=project_root,
                    resolved_via="sticky_context" if from_sticky else via,
                    switched_from=switched_from,
                )

    return _path_not_found(raw, tried, last_candidate)

"""Idempotent redirect of stdout print to stderr for MCP stdio protocol compatibility."""

import builtins
import sys

_PATCHED = False


def ensure_stdio_safe_print() -> None:
    """Đảm bảo print() mặc định ghi ra stderr thay vì stdout."""
    global _PATCHED
    if _PATCHED:
        return
    _orig = builtins.print

    def _safe(*args, **kwargs):
        if kwargs.get("file") in (None, sys.stdout):
            kwargs["file"] = sys.stderr
        try:
            _orig(*args, **kwargs)
        except Exception:
            try:
                text = " ".join(str(a) for a in args) + "\n"
                sys.stderr.buffer.write(text.encode("utf-8", errors="replace"))
                sys.stderr.flush()
            except Exception:
                pass

    builtins.print = _safe
    _PATCHED = True

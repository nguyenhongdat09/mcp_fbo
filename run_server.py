"""
FastBusiness MCP Server - Entry Point
This file serves as the entry point for PyInstaller build
"""

import builtins
import sys
from pathlib import Path

# Windows/cp1252 console + PyInstaller: ep UTF-8 som de CodeGraph/log khong crash charmap
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# CRITICAL (MCP stdio): stdout chi duoc JSON-RPC. Moi print() → stderr.
_orig_print = builtins.print


def _mcp_safe_print(*args, **kwargs):
    file = kwargs.get("file", None)
    if file is None or file is sys.stdout:
        kwargs["file"] = sys.stderr
    try:
        _orig_print(*args, **kwargs)
    except Exception:
        try:
            text = " ".join(str(a) for a in args) + "\n"
            sys.stderr.buffer.write(text.encode("utf-8", errors="replace"))
            sys.stderr.flush()
        except Exception:
            pass


builtins.print = _mcp_safe_print

# Add the parent directory to Python path
# This allows imports to work correctly when frozen by PyInstaller
if getattr(sys, "frozen", False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).parent

sys.path.insert(0, str(application_path))

from fastbusiness_mcp.config_paths import ensure_frozen_working_directory

ensure_frozen_working_directory()

# Now import and run the main server
from fastbusiness_mcp.server import main

if __name__ == "__main__":
    main()

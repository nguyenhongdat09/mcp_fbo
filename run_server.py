"""
FastBusiness MCP Server - Entry Point
This file serves as the entry point for PyInstaller build
"""

import builtins
import sys
from pathlib import Path

# Windows/cp1252 console + PyInstaller: ep UTF-8 som de FBOGraph/log khong crash charmap
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

# Add the parent directory to Python path
# This allows imports to work correctly when frozen by PyInstaller
if getattr(sys, "frozen", False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).parent

sys.path.insert(0, str(application_path))

from fastbusiness_mcp.stdio_safe import ensure_stdio_safe_print

ensure_stdio_safe_print()

from fastbusiness_mcp.config_paths import ensure_frozen_working_directory

ensure_frozen_working_directory()


if __name__ == "__main__":
    from fastbusiness_mcp.server import main

    main()

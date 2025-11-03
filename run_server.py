"""
FastBusiness MCP Server - Entry Point
This file serves as the entry point for PyInstaller build
"""

import sys
from pathlib import Path

# Add the parent directory to Python path
# This allows imports to work correctly when frozen by PyInstaller
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    application_path = Path(sys.executable).parent
else:
    # Running as script
    application_path = Path(__file__).parent

sys.path.insert(0, str(application_path))

# Now import and run the main server
from fastbusiness_mcp.server import main

if __name__ == "__main__":
    main()

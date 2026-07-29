@echo off
echo ===============================================================
echo FastBusiness MCP - Tu dong Rebuild tat ca Kuzu DB (config.yaml)
echo ===============================================================
echo.

cd /d "%~dp0"

if exist fastbusiness_mcp.exe (
    fastbusiness_mcp.exe rebuild
) else (
    echo [INFO] fastbusiness_mcp.exe khong ton tai. Dang chay qua Python...
    python xml_graph_cli.py rebuild
)

echo.
echo [DONE] Hoan tat qua trinh rebuild.
pause

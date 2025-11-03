@echo off
echo ========================================
echo Testing FastBusiness MCP Executable
echo ========================================
echo.

if not exist dist\fastbusiness_mcp.exe (
    echo ERROR: Executable not found!
    echo Please build first with: build_and_package.bat
    pause
    exit /b 1
)

echo Testing executable...
echo.
echo Expected: Server should start and show stdio protocol messages
echo Press Ctrl+C to stop after verifying it works
echo.
echo ----------------------------------------

dist\fastbusiness_mcp.exe

echo.
echo ----------------------------------------
echo.
if errorlevel 1 (
    echo Test FAILED - Check errors above
) else (
    echo Test completed
)

pause

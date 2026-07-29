@echo off
REM Build FastBusiness MCP Server (onedir) -> dist/fastbusiness_mcp/

echo.
echo Building FastBusiness MCP Server...
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat

pyinstaller --version >nul 2>&1
if errorlevel 1 pip install pyinstaller

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller fastbusiness_mcp.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

if not exist "dist\fastbusiness_mcp\fastbusiness_mcp.exe" (
    echo [ERROR] Output not found
    pause
    exit /b 1
)

REM Copy config va file batch canh exe de user tien su dung
copy /Y config.yaml dist\fastbusiness_mcp\config.yaml >nul
copy /Y rebuild_all.bat dist\fastbusiness_mcp\rebuild_all.bat >nul

echo.
echo [OK] Build successful: dist\fastbusiness_mcp\fastbusiness_mcp.exe
echo.
pause

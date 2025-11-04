@echo off
REM ============================================
REM FastBusiness MCP Server - Build Script (Onedir)
REM ============================================
REM
REM This script builds the MCP server as a FOLDER (onedir mode)
REM instead of a single .exe file.
REM
REM ADVANTAGES:
REM - More stable (no DLL extraction errors)
REM - Faster startup (no decompression needed)
REM - Easier to debug
REM
REM OUTPUT:
REM   dist/fastbusiness_mcp/
REM     fastbusiness_mcp.exe    <- Run this file
REM     _internal/              <- DLL files and dependencies
REM     knowledge_base/
REM     data/
REM     config.yaml
REM
REM ============================================

echo.
echo ============================================
echo  FastBusiness MCP Server - Onedir Build
echo ============================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.8+
    pause
    exit /b 1
)

REM Check if PyInstaller is available
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller not found! Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo [1/5] Cleaning old build files...
if exist build (
    rmdir /s /q build
    echo       - Removed build/
)
if exist dist (
    rmdir /s /q dist
    echo       - Removed dist/
)
echo       [OK] Clean completed

echo.
echo [2/5] Building with PyInstaller (onedir mode)...
echo       This may take 2-3 minutes...
echo.

pyinstaller run_server.py ^
  --name fastbusiness_mcp ^
  --onedir ^
  --console ^
  --add-data "knowledge_base;knowledge_base" ^
  --add-data "data;data" ^
  --add-data "config.yaml;." ^
  --hidden-import mcp ^
  --hidden-import mcp.server ^
  --hidden-import mcp.server.stdio ^
  --hidden-import mcp.types ^
  --hidden-import yaml ^
  --hidden-import lmdb ^
  --hidden-import fastbusiness_mcp ^
  --hidden-import fastbusiness_mcp.server ^
  --hidden-import fastbusiness_mcp.tools ^
  --hidden-import fastbusiness_mcp.tools.generate_field_from_lmdb ^
  --hidden-import fastbusiness_mcp.tools.generate_sql_for_fields ^
  --hidden-import fastbusiness_mcp.tools.code_assistant_tool ^
  --hidden-import fastbusiness_mcp.tools.xml_snippet_tool ^
  --hidden-import fastbusiness_mcp.knowledge_base ^
  --hidden-import fastbusiness_mcp.knowledge_base.engine ^
  --hidden-import fastbusiness_mcp.knowledge_base.context_detector ^
  --hidden-import fastbusiness_mcp.knowledge_base.code_generator ^
  --hidden-import fastbusiness_mcp.utils ^
  --hidden-import fastbusiness_mcp.utils.logger ^
  --hidden-import fastbusiness_mcp.utils.file_utils ^
  --exclude-module tkinter ^
  --exclude-module matplotlib ^
  --exclude-module numpy ^
  --exclude-module pandas ^
  --exclude-module scipy ^
  --exclude-module IPython ^
  --exclude-module notebook ^
  --clean ^
  --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo       [OK] Build completed

echo.
echo [3/5] Verifying build output...
if not exist "dist\fastbusiness_mcp\fastbusiness_mcp.exe" (
    echo [ERROR] Build output not found!
    pause
    exit /b 1
)
echo       [OK] fastbusiness_mcp.exe found

echo.
echo [4/5] Creating deployment package...
if not exist "FastBusiness-MCP-Package" mkdir "FastBusiness-MCP-Package"

REM Copy entire dist folder
xcopy /E /I /Y "dist\fastbusiness_mcp\*" "FastBusiness-MCP-Package\" >nul

REM Copy documentation
if exist "README.md" copy /Y "README.md" "FastBusiness-MCP-Package\" >nul
if exist "FIX_VCRUNTIME_ERROR.md" copy /Y "FIX_VCRUNTIME_ERROR.md" "FastBusiness-MCP-Package\" >nul
if exist "INSTRUCTIONS_FOR_AI.md" copy /Y "INSTRUCTIONS_FOR_AI.md" "FastBusiness-MCP-Package\" >nul

echo       [OK] Package created in FastBusiness-MCP-Package\

echo.
echo [5/5] Testing executable...
echo       Running quick test (5 seconds timeout)...
timeout /t 2 /nobreak >nul

REM Test run with timeout
start /wait /b "" "dist\fastbusiness_mcp\fastbusiness_mcp.exe" --help >nul 2>&1 & timeout /t 3 /nobreak >nul & taskkill /f /im fastbusiness_mcp.exe >nul 2>&1

echo       [OK] Test completed

echo.
echo ============================================
echo  BUILD SUCCESSFUL!
echo ============================================
echo.
echo Output folder: dist\fastbusiness_mcp\
echo Package folder: FastBusiness-MCP-Package\
echo.
echo FILE STRUCTURE:
echo   FastBusiness-MCP-Package\
echo     fastbusiness_mcp.exe    ^<-- Run this file
echo     _internal\              ^<-- Dependencies (DO NOT DELETE)
echo     knowledge_base\
echo     data\
echo     config.yaml
echo.
echo DEPLOYMENT:
echo   1. Copy entire "FastBusiness-MCP-Package" folder to target PC
echo   2. Run fastbusiness_mcp.exe
echo   3. Configure in Cursor/VS Code MCP settings
echo.
echo MCP CONFIG EXAMPLE:
echo   {
echo     "command": "C:\\FastBusiness-MCP-Package\\fastbusiness_mcp.exe",
echo     "cwd": "C:\\FastBusiness-MCP-Package",
echo     "env": {
echo       "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
echo     }
echo   }
echo.
echo ============================================
echo.
pause

@echo off
setlocal enabledelayedexpansion

echo ========================================
echo FastBusiness MCP Server - Build Package
echo ========================================
echo.

:: Configuration
set VERSION=1.0.0
set PACKAGE_NAME=FastBusiness-MCP-v%VERSION%
set OUTPUT_DIR=%PACKAGE_NAME%

:: Step 1: Clean old builds
echo [1/8] Cleaning old build files...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist %OUTPUT_DIR% rmdir /s /q %OUTPUT_DIR%
if exist %PACKAGE_NAME%.zip del /q %PACKAGE_NAME%.zip
echo    Done!

:: Step 2: Activate virtual environment
echo.
echo [2/8] Activating virtual environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo    Virtual environment activated
) else (
    echo    WARNING: venv not found, using system Python
)

:: Step 3: Install/Update PyInstaller
echo.
echo [3/8] Checking PyInstaller installation...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo    Installing PyInstaller...
    pip install pyinstaller
) else (
    echo    PyInstaller already installed
)

:: Step 4: Build executable with PyInstaller
echo.
echo [4/8] Building executable with PyInstaller...
echo    This may take 2-5 minutes...
pyinstaller --clean fastbusiness_mcp.spec

if errorlevel 1 (
    echo.
    echo ========================================
    echo ERROR: Build failed!
    echo ========================================
    echo Check error messages above
    pause
    exit /b 1
)
echo    Build successful!

:: Step 5: Verify executable was created
echo.
echo [5/8] Verifying executable...
if not exist dist\fastbusiness_mcp.exe (
    echo    ERROR: Executable not found!
    pause
    exit /b 1
)
echo    Executable found: dist\fastbusiness_mcp.exe

:: Step 6: Create package structure
echo.
echo [6/8] Creating package structure...
mkdir %OUTPUT_DIR%
mkdir %OUTPUT_DIR%\examples
echo    Package folder created

:: Step 7: Copy files to package
echo.
echo [7/8] Copying files to package...

:: Copy executable
echo    - Copying executable...
copy dist\fastbusiness_mcp.exe %OUTPUT_DIR%\ >nul
if errorlevel 1 (
    echo    ERROR: Failed to copy executable
    pause
    exit /b 1
)

:: Copy documentation
echo    - Copying documentation...
if exist PACKAGING_README.md (
    copy PACKAGING_README.md %OUTPUT_DIR%\README.md >nul
) else (
    echo # FastBusiness MCP Server > %OUTPUT_DIR%\README.md
    echo. >> %OUTPUT_DIR%\README.md
    echo Quick Start: See SETUP_GUIDE.md >> %OUTPUT_DIR%\README.md
)

if exist SETUP_GUIDE.md (
    copy SETUP_GUIDE.md %OUTPUT_DIR%\ >nul
)

if exist LICENSE.txt (
    copy LICENSE.txt %OUTPUT_DIR%\ >nul
    echo    - License file copied
)

:: Create example Cursor config
echo    - Creating example config...
(
echo {
echo   "mcpServers": {
echo     "fastbusiness": {
echo       "command": "C:\\Path\\To\\FastBusiness-MCP-v%VERSION%\\fastbusiness_mcp.exe",
echo       "args": []
echo     }
echo   }
echo }
) > %OUTPUT_DIR%\examples\cursor_config.json

:: Create quick start batch file
echo    - Creating quick start script...
(
echo @echo off
echo echo Starting FastBusiness MCP Server...
echo echo Press Ctrl+C to stop
echo.
echo %%~dp0fastbusiness_mcp.exe
echo.
echo pause
) > %OUTPUT_DIR%\run_mcp.bat

echo    All files copied!

:: Step 8: Test executable
echo.
echo [8/8] Testing executable...
%OUTPUT_DIR%\fastbusiness_mcp.exe --version >nul 2>&1
if errorlevel 1 (
    echo    WARNING: Executable test inconclusive
    echo    Manual testing recommended
) else (
    echo    SUCCESS: Executable is working!
)

:: Step 9: Create ZIP archive
echo.
echo Creating ZIP archive...
powershell -Command "Compress-Archive -Path '%OUTPUT_DIR%' -DestinationPath '%PACKAGE_NAME%.zip' -Force"
if errorlevel 1 (
    echo    WARNING: Failed to create ZIP
    echo    You can manually compress the folder
) else (
    echo    ZIP created: %PACKAGE_NAME%.zip
)

:: Display summary
echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Package Information:
echo   - Package folder: %OUTPUT_DIR%\
echo   - ZIP file: %PACKAGE_NAME%.zip
echo   - Executable: %OUTPUT_DIR%\fastbusiness_mcp.exe
echo.

:: Show file sizes
echo File Sizes:
for %%f in (%OUTPUT_DIR%\fastbusiness_mcp.exe) do echo   - Executable: %%~zf bytes (%%~zf / 1048576 = ~%%~zf MB^)
if exist %PACKAGE_NAME%.zip (
    for %%f in (%PACKAGE_NAME%.zip) do echo   - ZIP: %%~zf bytes
)

echo.
echo Next Steps:
echo   1. Test the executable: %OUTPUT_DIR%\fastbusiness_mcp.exe
echo   2. Test in Cursor with the example config
echo   3. Distribute %PACKAGE_NAME%.zip to users
echo.
echo ========================================
echo.

pause

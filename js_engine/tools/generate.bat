@echo off
setlocal
cd /d "%~dp0"

set GRAMMAR_DIR=%~dp0..\grammar
set OUT_DIR=%~dp0..\generated
set JAR=%~dp0..\..\tsql_engine\tools\antlr-4.13.2-complete.jar

if not exist "%JAR%" (
    echo [ERROR] Missing %JAR%
    exit /b 1
)

rem Find suitable Java 11+ (class version 55+)
set JAVA_EXE=java
if exist "%USERPROFILE%\.jdk\jdk-17.0.20+8\bin\java.exe" (
    set "JAVA_EXE=%USERPROFILE%\.jdk\jdk-17.0.20+8\bin\java.exe"
)

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

rem Copy Base helper classes to OUT_DIR so generated code can import them
copy /y "%GRAMMAR_DIR%\JavaScriptLexerBase.py" "%OUT_DIR%\" >nul
copy /y "%GRAMMAR_DIR%\JavaScriptParserBase.py" "%OUT_DIR%\" >nul

"%JAVA_EXE%" -jar "%JAR%" -Dlanguage=Python3 -visitor -no-listener -o "%OUT_DIR%" ^
  "%GRAMMAR_DIR%\JavaScriptLexer.g4" ^
  "%GRAMMAR_DIR%\JavaScriptParser.g4"

if errorlevel 1 (
    echo [ERROR] ANTLR generate failed
    exit /b 1
)

echo [OK] Generated Python parser in %OUT_DIR%
endlocal

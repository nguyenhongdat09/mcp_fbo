@echo off
setlocal
cd /d "%~dp0"

set GRAMMAR_DIR=%~dp0..\grammar
set OUT_DIR=%~dp0..\generated
set JAR=%~dp0antlr-4.13.2-complete.jar

if not exist "%JAR%" (
    echo [ERROR] Missing %JAR%
    echo Download: https://www.antlr.org/download/antlr-4.13.2-complete.jar
    echo Place jar in tsql_engine\tools\
    exit /b 1
)

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

java -jar "%JAR%" -Dlanguage=Python3 -visitor -no-listener -o "%OUT_DIR%" ^
  "%GRAMMAR_DIR%\TSqlLexer.g4" ^
  "%GRAMMAR_DIR%\TSqlParser.g4"

if errorlevel 1 (
    echo [ERROR] ANTLR generate failed
    exit /b 1
)

echo [OK] Generated Python parser in %OUT_DIR%
endlocal

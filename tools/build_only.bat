@echo off
setlocal enableextensions


REM Nur Build, kein Publish
mkdocs build --clean
if errorlevel 1 (
    echo Build fehlgeschlagen
    exit /b 1
)


echo Build OK
exit /b 0
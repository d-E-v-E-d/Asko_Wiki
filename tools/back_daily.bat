@echo off
setlocal

set "SRC=C:\arbeitsanweisung_app"
set "BACKUP_ROOT=C:\arbeitsanweisung_backups\daily"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "DATESTAMP=%%i"
set "DST=%BACKUP_ROOT%\%DATESTAMP%"

if not exist "%SRC%" (
  echo [ERROR] Source path not found: %SRC%
  exit /b 1
)

if not exist "%DST%" mkdir "%DST%"

robocopy "%SRC%\docs" "%DST%\docs" /MIR /R:2 /W:5
if errorlevel 8 exit /b %errorlevel%

robocopy "%SRC%\review" "%DST%\review" /MIR /R:2 /W:5
if errorlevel 8 exit /b %errorlevel%

robocopy "%SRC%\pdf_history" "%DST%\pdf_history" /MIR /R:2 /W:5
if errorlevel 8 exit /b %errorlevel%

echo [OK] Daily backup completed: %DST%
exit /b 0

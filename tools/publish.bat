@echo off
setlocal enableextensions enabledelayedexpansion


REM Parameter: buildonly|publish
if "%1"=="buildonly" goto :BUILD
if "%1"=="publish" goto :PUBLISH


:BUILD
echo [MKDOCS] Build startet
mkdocs build --clean
if errorlevel 1 (
    echo Build fehlgeschlagen
    exit /b 1
)
echo Build OK
exit /b 0


:PUBLISH
call :BUILD || exit /b 1


REM Zielverzeichnis leeren und kopieren
set SITE=%~dp0..\site
set WWW=C:\inetpub\wwwroot_arbeitsanweisung


if not exist "%WWW%" mkdir "%WWW%"
robocopy "%SITE%" "%WWW%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo Robocopy Fehler
    exit /b 1
)


echo Publish OK
exit /b 0
@echo off
rem Starts Jarvis. The desktop shortcut and "Start Jarvis.cmd" call this.
rem   run_jarvis.cmd            Jarvis as an app: his own window, this console minimized (the default)
rem   run_jarvis.cmd voice      the same (what older shortcuts pass)
rem   run_jarvis.cmd console    voice, with this console in front (to watch what he hears)
rem   run_jarvis.cmd text       text chat in the console
rem If Jarvis is already running, starting him again just brings up his window.
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=voice"

rem As an app: run again, minimized, so only Jarvis's window shows.
if /i "%MODE%"=="voice" (
    start "Jarvis" /min cmd /c ""%~f0" app"
    exit /b 0
)

rem Sinhala and Tamil text in the console needs Windows Terminal; the old console
rem shows boxes. Reopen there once if it's installed (set JARVIS_NO_WT=1 to skip).
rem Not for the app: its window shows Sinhala and Tamil itself.
if /i not "%MODE%"=="app" if not defined WT_SESSION if not defined JARVIS_NO_WT (
    where wt >nul 2>nul
    if not errorlevel 1 (
        start "" wt -d "%ROOT%" --title Jarvis cmd /c scripts\run_jarvis.cmd %MODE%
        exit /b 0
    )
)

cd /d "%ROOT%"
title Jarvis
set "PYTHONUTF8=1"
where uv >nul 2>nul || set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul || (
    echo uv isn't installed yet. Double-click "Setup Jarvis.cmd" in the Jarvis folder first.
    if /i "%MODE%"=="app" call :popup "Jarvis is not set up on this computer yet. Double-click Setup Jarvis.cmd in the Jarvis folder."
    pause
    exit /b 1
)

if /i "%MODE%"=="text" (
    uv run jarvis
) else (
    uv run jarvis --voice
)
if errorlevel 1 (
    echo.
    echo Jarvis stopped with an error; the message above says why.
    echo If it's about a missing package or model, run "Setup Jarvis.cmd" again.
    if /i "%MODE%"=="app" call :popup "Jarvis stopped with an error. The Jarvis console window on the taskbar says why."
    pause
)
exit /b %ERRORLEVEL%

:popup
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show('%~1', 'Jarvis')" >nul 2>nul
exit /b 0

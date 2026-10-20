@echo off
rem Starts Jarvis. The desktop shortcut and "Start Jarvis.cmd" call this.
rem   run_jarvis.cmd voice    talk to Jarvis (push-to-talk), the default
rem   run_jarvis.cmd text     text chat
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=voice"

rem Sinhala and Tamil text needs Windows Terminal; the old console shows boxes.
rem Reopen there once if it's installed (set JARVIS_NO_WT=1 to skip this).
if not defined WT_SESSION if not defined JARVIS_NO_WT (
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
    pause
)
exit /b %ERRORLEVEL%

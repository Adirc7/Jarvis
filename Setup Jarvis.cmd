@echo off
rem Double-click to set up Jarvis. Run it again after an update, or to repair.
rem Options are passed on, e.g.:  "Setup Jarvis.cmd" -NoTamil
title Jarvis setup
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1" %*
set "CODE=%ERRORLEVEL%"
echo.
pause
exit /b %CODE%

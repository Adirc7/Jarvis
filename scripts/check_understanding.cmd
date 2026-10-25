@echo off
rem How well does Jarvis understand commands in English, Singlish and Sinhala?
rem Runs scripts/command_check.py on both test sets with your settings and API
rem keys. Nothing opens and no key is pressed (a pretend browser). Takes a few
rem minutes; the results go to logs\command_check-*.json for Claude to read.
setlocal
cd /d "%~dp0.."
set "PYTHONUTF8=1"
where uv >nul 2>nul || set "PATH=%USERPROFILE%\.local\bin;%PATH%"

echo === The first set (eval\commands.jsonl)
uv run python scripts/command_check.py
echo.
echo === The held-out set (eval\commands_heldout.jsonl)
uv run python scripts/command_check.py --file eval/commands_heldout.jsonl
echo.
echo Done. Tell Claude "done": it reads the results from the logs folder.
pause

@echo off
rem Train your stand-in model on Kaggle's free GPU, test it, use it only if it's better
rem (docs/TRAINING_STANDIN.md). Options: --check (only check the pipeline).
setlocal
cd /d "%~dp0.."
set "PYTHONUTF8=1"
where uv >nul 2>nul || set "PATH=%USERPROFILE%\.local\bin;%PATH%"
uv run python scripts\train_standin.py %*
if errorlevel 1 (
    echo.
    echo It stopped with an error; paste the output above to Claude.
    exit /b 1
)

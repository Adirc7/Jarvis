@echo off
rem Check that Jarvis's Kaggle token works: gets the latest code, installs the
rem Kaggle package (with the same options as update.cmd, plus the ml tools),
rem then signs in to Kaggle and says so. Quick: it doesn't run the tests.
rem The token stays in .env and is never printed.
if not "%~1"=="--from-temp" (
    copy /y "%~f0" "%TEMP%\jarvis-check-kaggle.cmd" >nul
    call "%TEMP%\jarvis-check-kaggle.cmd" --from-temp "%~dp0.."
    exit /b
)
setlocal
cd /d "%~2"
set "PYTHONUTF8=1"
where uv >nul 2>nul || set "PATH=%USERPROFILE%\.local\bin;%PATH%"

echo === Getting the latest code
git pull
if errorlevel 1 goto :fail

set "EXTRAS=--extra voice --extra vision --extra desktop --extra dev --extra ml"
uv pip show nvidia-cudnn-cu12 >nul 2>nul && set "EXTRAS=%EXTRAS% --extra gpu"
uv pip show torch >nul 2>nul && set "EXTRAS=%EXTRAS% --extra mms"

echo.
echo === Installing the Kaggle package: uv sync %EXTRAS%
uv sync %EXTRAS%
if errorlevel 1 goto :fail

echo.
echo === Signing in to Kaggle
uv run python scripts\check_kaggle.py
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo The check stopped with an error; paste the output above to Claude.
exit /b 1

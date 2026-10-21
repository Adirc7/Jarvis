@echo off
rem Update Jarvis: get the latest code, then install any new or changed
rem packages with the same options setup chose (GPU and Tamil voice only if
rem they're already installed). Close Jarvis first: Windows locks files in use.
rem "git pull" may change this very file while it runs, which confuses cmd,
rem so it runs from a copy in the temp folder.
if not "%~1"=="--from-temp" (
    copy /y "%~f0" "%TEMP%\jarvis-update.cmd" >nul
    call "%TEMP%\jarvis-update.cmd" --from-temp "%~dp0.."
    exit /b
)
setlocal
cd /d "%~2"
set "PYTHONUTF8=1"
where uv >nul 2>nul || set "PATH=%USERPROFILE%\.local\bin;%PATH%"

echo === Getting the latest code
git pull
if errorlevel 1 goto :fail

set "EXTRAS=--extra voice --extra vision --extra desktop --extra dev"
uv pip show nvidia-cudnn-cu12 >nul 2>nul && set "EXTRAS=%EXTRAS% --extra gpu"
uv pip show torch >nul 2>nul && set "EXTRAS=%EXTRAS% --extra mms"

echo.
echo === Installing packages: uv sync %EXTRAS%
uv sync %EXTRAS%
if errorlevel 1 goto :fail

echo.
echo === Checking
uv run python -c "import onnxruntime as o; print('onnxruntime', o.__version__, '|', ', '.join(o.get_available_providers()))"
uv run pytest -q
if errorlevel 1 goto :fail
echo.
echo Updated. Start Jarvis as usual.
exit /b 0

:fail
echo.
echo The update stopped with an error; paste the output above to Claude.
exit /b 1

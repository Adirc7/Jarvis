@echo off
rem Update Jarvis: get the latest code, then install any new or changed
rem packages with the same options setup chose (GPU and Tamil voice only if
rem they're already installed). Close Jarvis first: Windows locks files in use.
setlocal
cd /d "%~dp0.."
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

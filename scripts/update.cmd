@echo off
rem Update Jarvis: get the latest code, then install any new or changed
rem packages with the same options setup chose (GPU and Tamil voice only if
rem they're already installed). Close Jarvis first: Windows locks files in use.
rem "git pull" may change this very file while it runs, which confuses cmd,
rem so it runs from a copy in the temp folder.
rem "scripts\update.cmd ml" also installs the intent-model tools (docs/TRAINING_INTENT.md).
if not "%~1"=="--from-temp" (
    copy /y "%~f0" "%TEMP%\jarvis-update.cmd" >nul
    call "%TEMP%\jarvis-update.cmd" --from-temp "%~dp0.." %*
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
set "ML="
uv pip show scikit-learn >nul 2>nul && set "ML=1"
if /i "%~3"=="ml" set "ML=1"
if defined ML set "EXTRAS=%EXTRAS% --extra ml"

echo.
echo === Installing packages: uv sync %EXTRAS%
uv sync %EXTRAS%
if errorlevel 1 goto :fail
rem MediaPipe brings opencv-contrib-python. Removing the old opencv-python
rem (24 Oct) also deletes files in the cv2 folder the two share (on the
rem laptop cv2.__version__ went missing), so put them back.
uv run python -c "import cv2; cv2.__version__; cv2.VideoCapture" >nul 2>nul || uv sync %EXTRAS% --reinstall-package opencv-contrib-python

echo.
echo === Checking
uv run python -c "import onnxruntime as o; print('onnxruntime', o.__version__, '|', ', '.join(o.get_available_providers()))"
uv run pytest -q
if errorlevel 1 goto :fail
echo.
echo === Shortcuts
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_shortcuts.ps1
echo.
echo Updated. Start Jarvis as usual (the desktop icon).
exit /b 0

:fail
echo.
echo The update stopped with an error; paste the output above to Claude.
exit /b 1

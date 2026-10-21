@echo off
rem Is Jarvis's voice faster on the graphics card? Times Kokoro saying a first
rem sentence three ways and prints a table for each:
rem   1. on the CPU, as Jarvis runs now
rem   2. the smaller int8 model on the CPU
rem   3. on the GPU through DirectML (any DirectX 12 graphics card)
rem   try_tts_gpu.cmd cuda    the CPU, then NVIDIA CUDA only (downloads up to 1 GB)
rem The GPU builds of onnxruntime go into test folders NEXT TO the Jarvis
rem folder, so Jarvis itself isn't changed. Delete them afterwards with
rem   rmdir /s /q ..\tts-test-dml ..\tts-test-cuda
setlocal
cd /d "%~dp0.."
set "PYTHONUTF8=1"
for %%I in ("%~dp0..\..") do set "PARENT=%%~fI"
set "DML=%PARENT%\tts-test-dml"
set "CUDA=%PARENT%\tts-test-cuda"
set "INT8_URL=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"

echo.
echo === 1. CPU, as Jarvis runs now
uv run python scripts\bench_tts.py
if errorlevel 1 goto :fail

if /i "%~1"=="cuda" goto :cuda

echo.
echo === 2. Smaller int8 model, CPU
if not exist models\kokoro-v1.0.int8.onnx (
    echo Downloading the int8 model, about 90 MB...
    curl -L --fail -o models\kokoro-v1.0.int8.onnx "%INT8_URL%"
    if errorlevel 1 goto :fail
)
uv run python scripts\bench_tts.py --model models\kokoro-v1.0.int8.onnx

echo.
echo === 3. GPU through DirectML
if not exist "%DML%\Scripts\python.exe" uv venv "%DML%" --python 3.12 -q
uv pip install -q --python "%DML%\Scripts\python.exe" onnxruntime-directml numpy espeakng-loader "phonemizer>=3.4"
uv pip install -q --python "%DML%\Scripts\python.exe" --no-deps kokoro-onnx==0.6.1
"%DML%\Scripts\python.exe" scripts\bench_tts.py --provider DmlExecutionProvider

goto :done

:cuda
echo.
echo === 4. GPU through CUDA
rem 1.26 is the newest onnxruntime-gpu built for CUDA 12, the CUDA Whisper
rem already uses; 1.27 and later need CUDA 13 and could clash with it.
echo Installing onnxruntime-gpu and the CUDA libraries: about 0.5-1.3 GB to download
echo (less if Whisper's copies are reused), then Windows may scan the files. This can
echo take several minutes; the progress bars show it's working.
if not exist "%CUDA%\Scripts\python.exe" uv venv "%CUDA%" --python 3.12 -q
uv pip install --python "%CUDA%\Scripts\python.exe" "onnxruntime-gpu[cuda,cudnn]==1.26.0" numpy espeakng-loader "phonemizer>=3.4"
if errorlevel 1 goto :fail
uv pip install -q --python "%CUDA%\Scripts\python.exe" --no-deps kokoro-onnx==0.6.1
"%CUDA%\Scripts\python.exe" scripts\bench_tts.py --provider CUDAExecutionProvider

:done
echo.
echo Done. Copy everything above and paste it to Claude.
exit /b 0

:fail
echo.
echo Something failed above; paste the output to Claude.
exit /b 1

@echo off
rem Friday's voice test: can Friday have native Sinhala pronunciation in Emma's
rem voice? Piper's "dilu" (trained on real Sinhala speech) is re-voiced as Emma
rem with kNN-VC, and three versions are written to compare:
rem   1_friday_now_espeak   today's Friday (Kokoro Emma reading eSpeak's Sinhala)
rem   2_dilu_original       the native Sinhala voice
rem   3_friday_converted_k2, _k4, _k8   dilu's pronunciation in Emma's voice;
rem                         k = how many of Emma's closest sounds are blended
rem                         (fewer: more Emma but rougher; more: smoother)
rem   try_friday_voice.cmd again    redo only the conversion and the files
rem Torch goes into a test folder NEXT TO the Jarvis folder (about 0.3 GB, plus
rem 1.3 GB of kNN-VC models in the torch cache), so Jarvis isn't changed.
rem Delete afterwards: rmdir /s /q ..\friday-voice-test
setlocal
cd /d "%~dp0.."
set "PYTHONUTF8=1"
for %%I in ("%~dp0..\..") do set "PARENT=%%~fI"
set "TEST=%PARENT%\friday-voice-test"
set "AUDIO=%TEST%\audio"
rem kNN-VC's models download into the torch cache; keep it off C:
if not defined TORCH_HOME set "TORCH_HOME=%PARENT%\.cache\torch"

if /i "%~1"=="again" goto :convert

echo.
echo === 1. Emma's reference speech, dilu's Sinhala and today's Friday
uv run python scripts\friday_voice_test.py --prepare "%AUDIO%"
if errorlevel 1 goto :fail

echo.
echo === 2. Voice conversion with kNN-VC
echo Installing torch for the test (about 0.3 GB); then kNN-VC downloads its
echo models (about 1.3 GB). This takes a few minutes; progress bars show it's working.
if not exist "%TEST%\venv\Scripts\python.exe" uv venv "%TEST%\venv" --python 3.12 -q
uv pip install --python "%TEST%\venv\Scripts\python.exe" "torch==2.7.1" "torchaudio==2.7.1" numpy
if errorlevel 1 goto :fail
:convert
if exist "%AUDIO%\converted" rmdir /s /q "%AUDIO%\converted"
"%TEST%\venv\Scripts\python.exe" scripts\friday_voice_test.py --convert "%AUDIO%"
if errorlevel 1 goto :fail

echo.
echo === 3. Jarvis's voice effects on all three, files to compare
uv run python scripts\friday_voice_test.py --finish "%AUDIO%"
if errorlevel 1 goto :fail
start "" "%AUDIO%\listen"
echo.
echo Done: the folder with the three files has opened. Listen and tell Claude
echo which Friday sounds best.
exit /b 0

:fail
echo.
echo Something failed above; paste the output to Claude.
exit /b 1

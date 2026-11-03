# Ollama: the model on this computer

The cloud models are free but limited: Groq's gpt-oss models 200,000 tokens a
day each (about 40 questions), OpenRouter 50 requests a day, Gemini often
busy. Ollama runs a model on the laptop's graphics card: no daily limit, no
internet. It is the last model on every route, so it answers when the others
can't. It's weaker than gpt-oss-120b, and weaker still in Sinhala.

Jarvis starts it by himself when he starts (`[ollama]` in
`config/settings.toml`): `ollama serve` in the background, no window, its
output in `logs/ollama.log`. It keeps running when Jarvis quits; idle, it holds
no graphics memory (a model leaves the GPU five minutes after its last answer).

## Installing it on D: (cmd)

```
mkdir D:\Ollama\models
setx OLLAMA_MODELS "D:\Ollama\models"
set OLLAMA_MODELS=D:\Ollama\models
curl -L -o D:\Ollama\OllamaSetup.exe https://ollama.com/download/OllamaSetup.exe
D:\Ollama\OllamaSetup.exe /DIR="D:\Ollama\app"
```

Click Install in the setup window. Then, in a new cmd window:

```
echo %OLLAMA_MODELS%
ollama pull qwen3:4b
dir D:\Ollama\models\blobs
ollama run qwen3:4b "Say hi in one sentence."
```

`echo` must print `D:\Ollama\models`, or the model goes to C:. qwen3:4b is
about 2.5 GB and fits in the RTX 4050's 6 GB next to Whisper.

## If it doesn't start

- "[ollama] not installed" when Jarvis starts: `ollama` isn't on PATH. Set
  `path = "D:/Ollama/app/ollama.exe"` under `[ollama]` in
  `config/settings.local.toml`.
- "[ollama] couldn't start": see `logs/ollama.log`.
- Not wanted: `start = false` under `[ollama]` in `config/settings.local.toml`.

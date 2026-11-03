"""Ollama, the model on this computer, started by Jarvis when it isn't running (agent/local_model.py)."""

from __future__ import annotations

from jarvis.agent.local_model import ensure, find, server_root


def test_only_a_model_on_this_computer_is_started():
    assert server_root("http://localhost:11434/v1") == "http://127.0.0.1:11434"
    assert server_root("http://127.0.0.1:9999/v1") == "http://127.0.0.1:9999"
    assert server_root("https://api.groq.com/openai/v1") is None
    assert ensure("https://api.groq.com/openai/v1") == "remote"


def test_started_when_installed_and_not_running(tmp_path):
    state = {"up": False, "started": []}

    def starter(exe, models_dir, log_dir):
        state["started"].append((exe, models_dir, log_dir))
        state["up"] = True

    status = ensure("http://localhost:11434/v1", "", "D:/Ollama/models", tmp_path, is_running=lambda root: state["up"],
                    finder=lambda path: "D:/Ollama/app/ollama.exe", starter=starter, sleep=lambda s: None)
    assert status == "started" and state["started"] == [("D:/Ollama/app/ollama.exe", "D:/Ollama/models", tmp_path)]


def test_left_alone_when_running_and_reported_when_missing_or_stuck():
    never = {"starter": lambda *a: None, "sleep": lambda s: None}
    assert ensure("http://localhost:11434/v1", is_running=lambda r: True, finder=lambda p: None, **never) == "running"
    assert ensure("http://localhost:11434/v1", is_running=lambda r: False, finder=lambda p: None,
                  **never) == "not_installed"
    assert ensure("http://localhost:11434/v1", is_running=lambda r: False, finder=lambda p: "ollama", wait_s=1,
                  **never) == "failed"


def test_a_configured_path_must_exist(tmp_path):
    exe = tmp_path / "ollama.exe"
    assert find(str(exe)) is None
    exe.write_bytes(b"")
    assert find(str(exe)) == str(exe)


async def test_jarvis_starts_it_and_stops_resting_it(settings, monkeypatch):
    from conftest import FakeClient

    from jarvis.agent import local_model
    from jarvis.agent.llm import FallbackLLM, Provider
    from jarvis.app import App
    from jarvis.telemetry import Telemetry
    calls = []
    monkeypatch.setattr(local_model, "ensure", lambda *a, **k: calls.append(a) or "started")
    ollama = Provider("ollama", "qwen3:4b", FakeClient(), base_url="http://localhost:11434/v1")
    app = App(settings, Telemetry.disabled(), llm=FallbackLLM([ollama]), out=lambda *a, **k: None)
    app.llm.resting[ollama.quota_key] = app.llm.clock() + 60          # it was down a moment ago
    app._start_ollama()
    assert calls == []                                                # tests turn it off ([ollama] start)
    settings.raw["ollama"]["start"] = True
    app._start_ollama()
    assert calls and calls[0][0] == "http://localhost:11434/v1" and ollama.quota_key not in app.llm.resting


def test_one_model_cache_however_jarvis_starts(monkeypatch, tmp_path):
    """4 Nov: started by three claps from a console with HF_HOME=D:\\hf-cache, Jarvis downloaded the emotion
    model again. [general] model_cache wins over whatever the console had."""
    from jarvis.config import Settings, use_model_cache
    monkeypatch.setenv("HF_HOME", "D:/somewhere-else")
    use_model_cache(Settings(raw={"general": {"model_cache": str(tmp_path / "hf")}}, languages={}))
    import os
    assert os.environ["HF_HOME"] == str(tmp_path / "hf")
    monkeypatch.setenv("HF_HOME", "left-alone")
    use_model_cache(Settings(raw={"general": {"model_cache": ""}}, languages={}))
    assert os.environ["HF_HOME"] == "left-alone"


def test_the_intent_model_and_the_stand_in_share_one_encoder(monkeypatch):
    import sys
    import types
    made = []
    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = lambda name, device=None: made.append((name, device)) or object()
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    from jarvis import encoders
    monkeypatch.setattr(encoders, "_loaded", {})
    a = encoders.sentence_encoder("intfloat/multilingual-e5-small", "cpu")
    b = encoders.sentence_encoder("intfloat/multilingual-e5-small", "cpu")
    assert a is b and made == [("intfloat/multilingual-e5-small", "cpu")]

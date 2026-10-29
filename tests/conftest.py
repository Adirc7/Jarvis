from __future__ import annotations

from types import SimpleNamespace

import pytest

from jarvis.config import load_settings


class FakeStream:
    def __init__(self, pieces, fail_at=None):
        self.pieces = pieces
        self.fail_at = fail_at
        self.closed = False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for i, p in enumerate(self.pieces):
            if self.fail_at is not None and i == self.fail_at:
                raise RuntimeError("connection dropped mid-stream")
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=p))])

    async def close(self):
        self.closed = True


class FakeClient:
    """Mimics openai.AsyncOpenAI().chat.completions.create."""

    def __init__(self, pieces=("Hello", " there"), error=None, fail_at=None):
        self.pieces = list(pieces)
        self.error = error
        self.fail_at = fail_at
        self.calls = 0
        self.last_messages = None
        self.last_stream = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, model, messages, stream=False, **kwargs):
        self.calls += 1
        self.last_messages = messages
        if self.error:
            raise self.error
        if stream:
            self.last_stream = FakeStream(self.pieces, self.fail_at)
            return self.last_stream
        msg = SimpleNamespace(content="".join(self.pieces), tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


@pytest.fixture
def settings(tmp_path):
    s = load_settings(local=False, load_env=False)   # the committed config, and no API keys
    # Keep Jarvis's memory of "when you last talked" out of the real state/ folder.
    s.raw.setdefault("general", {})["state_dir"] = str(tmp_path / "state")
    s.raw.setdefault("tools", {})["web"] = False      # tests never open a browser or press media keys
    s.raw["tools"]["desktop"] = False                 # nor use the real PC tools (tests pass stand-ins)
    s.raw["tools"]["knowledge"] = False               # nor fetch news or papers from the internet
    s.raw.setdefault("window", {})["enabled"] = False # nor open the window
    s.raw.setdefault("general", {})["log_dir"] = str(tmp_path / "logs")
    return s

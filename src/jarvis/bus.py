"""In-process event bus built on asyncio queues.

Why this exists (plan section 10.3): camera, mic, agent and UI must never block
each other. Producers run in their own threads and hand events to the asyncio
loop with `publish_threadsafe`. Consumers each get their own queue, so a slow
consumer (the LLM) can't freeze a fast one (gesture tracking).
"""

from __future__ import annotations

import asyncio
import threading
from collections import Counter
from dataclasses import dataclass

from .events import Event


@dataclass
class _Subscription:
    types: tuple[type[Event], ...]
    queue: asyncio.Queue
    drop_oldest: bool
    name: str


class EventBus:
    def __init__(self) -> None:
        self._subs: list[_Subscription] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self.dropped: Counter[str] = Counter()

    def bind(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Attach to the running loop. Call once from the loop thread."""
        self._loop = loop or asyncio.get_running_loop()

    @property
    def is_bound(self) -> bool:
        return self._loop is not None

    def subscribe(
        self,
        *types: type[Event],
        maxsize: int = 256,
        drop_oldest: bool = False,
        name: str = "",
    ) -> asyncio.Queue:
        """Get a queue that receives every event that is an instance of `types`.

        drop_oldest=True suits high-rate streams (gesture frames) where only the
        newest value matters. Leave it False for things you must not lose
        (transcripts, kill switch).
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        with self._lock:
            self._subs.append(_Subscription(types or (Event,), q, drop_oldest, name or "anon"))
        return q

    def publish(self, event: Event) -> None:
        """Publish from the loop thread."""
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            if not isinstance(event, sub.types):
                continue
            if sub.queue.full():
                if sub.drop_oldest:
                    try:
                        sub.queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                else:
                    self.dropped[f"{sub.name}:{event.kind}"] += 1
                    continue
            sub.queue.put_nowait(event)

    def publish_threadsafe(self, event: Event) -> None:
        """Publish from any thread (camera, mic, hotkey listener)."""
        if self._loop is None:
            raise RuntimeError("EventBus.bind() must be called before publishing from threads")
        self._loop.call_soon_threadsafe(self.publish, event)

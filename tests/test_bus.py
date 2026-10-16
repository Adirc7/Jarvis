import asyncio
import threading

from jarvis.bus import EventBus
from jarvis.events import Event, GestureEvent, KillSwitchPressed, UserText


async def test_typed_subscription():
    bus = EventBus()
    bus.bind()
    text_q = bus.subscribe(UserText)
    all_q = bus.subscribe(Event)
    bus.publish(UserText(text="hi", language="en"))
    bus.publish(KillSwitchPressed())
    assert (await text_q.get()).text == "hi"
    assert text_q.empty()
    assert all_q.qsize() == 2


async def test_publish_from_another_thread():
    bus = EventBus()
    bus.bind()
    q = bus.subscribe(KillSwitchPressed)
    t = threading.Thread(target=lambda: bus.publish_threadsafe(KillSwitchPressed(source="thread")))
    t.start()
    t.join()
    ev = await asyncio.wait_for(q.get(), timeout=1)
    assert ev.source == "thread"


async def test_drop_oldest_keeps_newest_gesture():
    bus = EventBus()
    bus.bind()
    q = bus.subscribe(GestureEvent, maxsize=2, drop_oldest=True)
    for i in range(5):
        bus.publish(GestureEvent(name="point", x=i / 10, y=0))
    xs = [q.get_nowait().x for _ in range(q.qsize())]
    assert xs == [0.3, 0.4]


async def test_full_queue_without_drop_oldest_counts_drops():
    bus = EventBus()
    bus.bind()
    q = bus.subscribe(UserText, maxsize=1, name="agent")
    bus.publish(UserText(text="a", language="en"))
    bus.publish(UserText(text="b", language="en"))
    assert q.get_nowait().text == "a"            # first one is never lost
    assert bus.dropped["agent:UserText"] == 1

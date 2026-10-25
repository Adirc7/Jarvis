"""Palm to pause: when an open palm counts (perception/gestures.py, decision D29)."""

import math

import pytest

from jarvis.perception.gestures import HandSeen, PalmHold, PalmSettings, PalmTrigger

FPS = 15                    # about what the laptop camera gives
DT = 1 / FPS


def right_palm(x=320.0, y=240.0, score=0.7, side="Right", gesture="Open_Palm"):
    return HandSeen(side=side, gesture=gesture, score=score, centre=(x, y), size=90.0)


def feed(trigger, frames, start=0.0):
    """frames: a list of 'what was seen' per result. Returns the times a palm was accepted."""
    times = []
    for i, hands in enumerate(frames):
        t = start + i * DT
        if trigger.update(t, hands):
            times.append(round(t, 3))
    return times


def seconds(s, hands):
    return [hands] * round(s * FPS)


def test_a_palm_held_half_a_second_counts_once():
    times = feed(PalmTrigger(), seconds(0.6, [right_palm()]) + seconds(0.5, []))
    assert len(times) == 1 and 0.5 <= times[0] < 0.6


def test_a_short_palm_does_not_count():
    assert feed(PalmTrigger(), seconds(0.3, [right_palm()]) + seconds(1, [])) == []


def test_a_long_palm_still_counts_once():
    assert len(feed(PalmTrigger(), seconds(3, [right_palm()]))) == 1


def test_the_left_hand_never_counts_unless_chosen():
    left = right_palm(side="Left")
    assert feed(PalmTrigger(), seconds(1, [left])) == []
    assert len(feed(PalmTrigger(PalmSettings(hand="left")), seconds(1, [left]))) == 1


def test_the_right_hand_counts_with_the_left_in_view():
    both = [right_palm(side="Left", x=100), right_palm(x=500)]
    assert len(feed(PalmTrigger(), seconds(1, both))) == 1


def test_an_unsure_palm_does_not_count():
    assert feed(PalmTrigger(), seconds(1, [right_palm(score=0.55)])) == []
    assert feed(PalmTrigger(), seconds(1, [right_palm(gesture="Closed_Fist", score=0.9)])) == []


def test_one_lost_result_mid_hold_is_forgiven():
    frames = seconds(0.3, [right_palm()]) + [[]] + seconds(0.4, [right_palm()])
    assert len(feed(PalmTrigger(), frames)) == 1


def test_a_hand_lost_for_longer_starts_the_hold_again():
    frames = seconds(0.4, [right_palm()]) + seconds(0.33, []) + seconds(0.3, [right_palm()])
    assert feed(PalmTrigger(), frames) == []


def test_after_a_palm_the_hand_must_drop_before_the_next():
    palm, gone = seconds(0.7, [right_palm()]), seconds(0.6, [])
    assert len(feed(PalmTrigger(), palm + gone + palm)) == 2
    blink = seconds(0.2, [])                                  # dropped too briefly
    assert len(feed(PalmTrigger(), palm + blink + palm)) == 1


def test_a_closed_hand_also_rearms():
    fist = seconds(0.6, [right_palm(gesture="Closed_Fist", score=0.9)])
    palm = seconds(0.7, [right_palm()])
    assert len(feed(PalmTrigger(), palm + fist + palm)) == 2


def test_a_waving_hand_does_not_count():
    # The palm swings 1.5 palm-sizes left and right, twice a second.
    wave = [[right_palm(x=320 + 135 * math.sin(2 * math.pi * 2 * i * DT))] for i in range(3 * FPS)]
    assert feed(PalmTrigger(), wave) == []


def test_a_little_shake_is_still_still():
    shaky = [[right_palm(x=320 + (4 if i % 2 else -4))] for i in range(FPS)]
    assert len(feed(PalmTrigger(), shaky)) == 1


def test_a_rising_hand_counts_once_it_stops():
    rising = [[right_palm(y=400 - 40 * i)] for i in range(5)]            # moving up, 0.33 s
    still = seconds(0.6, [right_palm(y=240)])
    times = feed(PalmTrigger(), rising + still)
    assert len(times) == 1 and times[0] >= 0.5 + 4 * DT                  # the hold started when it stopped


def test_stillness_can_be_switched_off():
    wave = [[right_palm(x=320 + 135 * math.sin(2 * math.pi * 2 * i * DT))] for i in range(3 * FPS)]
    assert len(feed(PalmTrigger(PalmSettings(max_move=0)), wave)) >= 1


def test_hand_seen_from_mediapipe_points():
    points = [(0.5, 0.8)] + [(0.5, 0.5)] * 20       # wrist low, everything else 0.3 higher
    hand = HandSeen.from_points("Right", "Open_Palm", 0.7, points, width=640, height=480)
    assert hand.size == pytest.approx(0.3 * 480)
    assert hand.centre == pytest.approx((320.0, (0.8 + 4 * 0.5) / 5 * 480))


def test_settings_come_from_the_config(settings):
    config = PalmSettings.from_settings(settings)
    assert config.hand == "right" and config.min_score == 0.6 and config.max_move == 0.35
    assert config.hold_s == 0.5 and config.rearm_s == 0.5


def test_palm_hold_on_its_own():
    hold = PalmHold(max_move=None)
    fired = [hold.update(i * DT, True) for i in range(10)]
    assert fired.count(True) == 1 and hold.state == "fired"

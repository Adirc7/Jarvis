"""Phase 1: the spoken conversation loop.

capture.py     push-to-talk microphone recording
stt.py         Whisper transcription, aware of the active language
text_split.py  cut a streamed reply into speakable sentences
tts.py         Kokoro / Piper / MMS voices behind one interface
effects.py     the "Jarvis feel" effects chain + loudness matching
player.py      ordered playback that stops instantly
sink.py        printed-only or printed-and-spoken replies
audio_io.py    WAV read/write
"""

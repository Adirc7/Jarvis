"""The Friday voice-conversion test script imports without torch and has sane inputs."""

import importlib.util

from jarvis.config import PROJECT_ROOT
from jarvis.voice.clarity import foreign_script_share


def _load():
    spec = importlib.util.spec_from_file_location("friday_voice_test", PROJECT_ROOT / "scripts" / "friday_voice_test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)                 # torch is only imported inside --convert
    return module


def test_inputs():
    fv = _load()
    assert len(fv.HARVARD) == 40 and len(set(fv.HARVARD)) == 40
    assert len(fv.LONGER) >= 20
    assert all(foreign_script_share(s, "si") == 0 for s in fv.SINHALA)
    # Emma needs a few minutes of speech: about 2.5 s per Harvard sentence, 6 s per longer one
    assert 40 * 2.5 + len(fv.LONGER) * 6 >= 200

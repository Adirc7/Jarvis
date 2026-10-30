"""Moving Jarvis to a new PC: the carry file, bringing it in, and knowing which computer this is."""

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jarvis.carry import CarryError, carry_in, carry_out, hotkeys_block
from jarvis.machines import Machine, Machines, machine_id

OLD_LOCAL = """[audio]
input_device = 3

[hotkeys]
push_to_talk = "alt_gr"
"""


def old_pc(tmp_path):
    root, home = tmp_path / "old" / "Jarvis", tmp_path / "old" / "Documents" / "Jarvis"
    (root / "state").mkdir(parents=True)
    (root / "state" / "memory.json").write_text(json.dumps({
        "name": "Adhi", "facts": [{"text": "my exam is on Saturday", "added": "2026-10-29T10:00:00"}],
        "recent": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello, sir."}],
        "last": "2026-10-30T03:00:00"}), encoding="utf-8")
    (root / "state" / "machines.json").write_text(json.dumps({"current": "a1", "machines": {
        "a1": {"id": "a1", "name": "ASUS-TUF", "gpu": "RTX 4050", "gpu_mb": 6141}}}))
    (root / "data" / "intent").mkdir(parents=True)
    (root / "data" / "intent" / "mine.jsonl").write_text('{"text": "open notepad", "intent": "open_app"}\n')
    (root / "models" / "intent").mkdir(parents=True)
    (root / "models" / "intent" / "intent.joblib").write_bytes(b"model")
    (root / "config").mkdir()
    (root / "config" / "settings.local.toml").write_text(OLD_LOCAL)
    (root / ".env").write_text("GROQ_API_KEY=secret\n")
    (home / "notes").mkdir(parents=True)
    (home / "notes" / "exam.md").write_text("Exam on Saturday", encoding="utf-8")
    (home / "screenshots").mkdir()
    (home / "screenshots" / "big.png").write_bytes(b"png")
    return root, home


def test_the_carry_file_holds_what_jarvis_knows_and_not_the_keys(tmp_path):
    root, home = old_pc(tmp_path)
    path, _ = carry_out(root, home, tmp_path / "out", "ASUS TUF", now=datetime(2026, 10, 30, 3, 30, tzinfo=UTC))
    assert path.name == "Jarvis-carry-ASUS-TUF-20261030-0330.zip"
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        assert {"project/state/memory.json", "project/state/machines.json", "project/data/intent/mine.jsonl",
                "project/models/intent/intent.joblib", "home/notes/exam.md", "project/config/hotkeys.toml"} <= names
        assert not any(".env" in n or "screenshots" in n for n in names)
        assert z.read("project/config/hotkeys.toml").decode() == '[hotkeys]\npush_to_talk = "alt_gr"\n'
    path, _ = carry_out(root, home, tmp_path / "keys.zip", "ASUS", with_keys=True)
    with zipfile.ZipFile(path) as z:
        assert "keys/.env" in z.namelist() and json.loads(z.read("jarvis-carry.json"))["with_keys"]


def test_a_new_pc_gets_the_memory_merged_and_keeps_its_own_things(tmp_path):
    root, home = old_pc(tmp_path)
    path, _ = carry_out(root, home, tmp_path / "out", "ASUS-TUF", with_keys=True)
    new_root, new_home = tmp_path / "new" / "Jarvis", tmp_path / "new" / "Documents" / "Jarvis"
    (new_root / "state").mkdir(parents=True)
    (new_root / "state" / "memory.json").write_text(json.dumps({
        "name": "", "facts": [{"text": "I like lofi", "added": "2026-10-31T09:00:00"}], "recent": [],
        "last": "2026-10-29T09:00:00"}))
    (new_root / ".env").write_text("GROQ_API_KEY=new-pc-key\n")
    manifest, done = carry_in(path, new_root, new_home)
    assert manifest["from_pc"] == "ASUS-TUF"
    memory = json.loads((new_root / "state" / "memory.json").read_text(encoding="utf-8"))
    assert memory["name"] == "Adhi" and {f["text"] for f in memory["facts"]} == {"my exam is on Saturday", "I like lofi"}
    assert memory["recent"][-1]["content"] == "Hello, sir."                      # the newer conversation
    assert (new_root / "state" / "memory.json.before-carry").exists()            # nothing lost quietly
    assert (new_home / "notes" / "exam.md").read_text(encoding="utf-8") == "Exam on Saturday"
    assert (new_root / "models" / "intent" / "intent.joblib").read_bytes() == b"model"
    assert (new_root / ".env").read_text() == "GROQ_API_KEY=new-pc-key\n"       # its own keys stay
    local = (new_root / "config" / "settings.local.toml").read_text()
    assert 'push_to_talk = "alt_gr"' in local and "input_device" not in local     # not the old PC's devices
    assert any("kept it" in line for line in done)


def test_a_carry_file_cant_write_outside_jarvis(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("jarvis-carry.json", json.dumps({"format": 1}))
        z.writestr("project/../../evil.txt", "x")
    with pytest.raises(CarryError):
        carry_in(bad, tmp_path / "root", tmp_path / "home")
    odd = tmp_path / "odd.zip"
    with zipfile.ZipFile(odd, "w") as z:
        z.writestr("jarvis-carry.json", json.dumps({"format": 1}))
        z.writestr("project/src/jarvis/app.py", "print('replaced')")          # not something it carries
        z.writestr("project/models/intent/run.py", "x")                       # only models in that folder
    _, done = carry_in(odd, tmp_path / "root", tmp_path / "home")
    assert done == [] and not (tmp_path / "root" / "src").exists()
    with pytest.raises(CarryError):
        carry_in(tmp_path / "missing.zip", tmp_path, tmp_path)
    plain = tmp_path / "plain.zip"
    with zipfile.ZipFile(plain, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(CarryError):
        carry_in(plain, tmp_path, tmp_path)


def test_hotkeys_are_found_in_a_settings_file():
    assert hotkeys_block(OLD_LOCAL) == '[hotkeys]\npush_to_talk = "alt_gr"\n'
    assert hotkeys_block("[audio]\nx = 1\n") == ""


def test_jarvis_knows_which_pc_he_is_on_and_where_he_came_from(tmp_path):
    path = tmp_path / "machines.json"
    pcs = Machines.load(path)
    old = Machine(machine_id("ASUS-TUF", 1), "ASUS-TUF", gpu="RTX 4050", gpu_mb=6141)
    _, before = pcs.see(old, datetime(2026, 10, 30, tzinfo=UTC))
    assert before is None                                                  # the very first run
    pcs.save()
    pcs = Machines.load(path)
    _, before = pcs.see(Machine(machine_id("ASUS-TUF", 1), "ASUS-TUF"), datetime(2026, 10, 31, tzinfo=UTC))
    assert before is None and pcs.known[old.id].first_seen.startswith("2026-10-30")   # same PC again
    new = Machine(machine_id("NEW-LAPTOP", 2), "NEW-LAPTOP", ram_gb=32)
    _, before = pcs.see(new, datetime(2026, 11, 6, tzinfo=UTC))
    assert before.name == "ASUS-TUF" and pcs.current == new.id
    assert new.describe() == "NEW-LAPTOP, no NVIDIA graphics card, 32 GB memory"
    assert old.describe().startswith("ASUS-TUF, RTX 4050 (6 GB)")
    assert machine_id("ASUS-TUF", 1) != machine_id("ASUS-TUF", 2) and len(machine_id("x", 1)) == 16
    assert Machines.load(tmp_path / "missing.json").known == {}
    (tmp_path / "broken.json").write_text("{not json")
    assert Machines.load(tmp_path / "broken.json").known == {}


async def test_on_a_new_pc_jarvis_says_so(settings, monkeypatch, tmp_path):
    from jarvis.app import App
    from jarvis.telemetry import Telemetry
    said = []
    settings.raw.setdefault("general", {})["state_dir"] = str(tmp_path)
    (tmp_path / "machines.json").write_text(json.dumps({"current": "old", "machines": {
        "old": {"id": "old", "name": "ASUS-TUF"}}}))
    monkeypatch.setattr("jarvis.machines.this_machine", lambda: Machine("new", "NEW-LAPTOP", gpu="RTX 5060"))
    app = App(settings, Telemetry.disabled(), out=lambda *a, **k: None)

    async def say(text, lang, token):
        said.append(text)
    app.sink.say = say
    app.memory.name = "Adhi"
    before = app._note_machine()
    await app._say_new_pc(before)
    assert said == [("New computer, sir: NEW-LAPTOP, moved from ASUS-TUF; the RTX 5060 runs my ears and voice. "
                     "Your memory came along.")]
    assert app._snapshot()["pc"] == "NEW-LAPTOP"
    assert json.loads((tmp_path / "machines.json").read_text())["current"] == "new"


def test_carry_on_the_command_line(tmp_path, monkeypatch, capsys, settings):
    import jarvis.__main__ as main
    root, home = old_pc(tmp_path)
    monkeypatch.setattr("jarvis.config.PROJECT_ROOT", root)
    monkeypatch.setattr("jarvis.machines.this_machine", lambda: Machine("a1", "ASUS-TUF"))
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    settings.raw.setdefault("tools", {})["jarvis_folder"] = str(home)
    assert main.main(["--carry-out", str(tmp_path / "out")]) == 0
    made = next((tmp_path / "out").glob("Jarvis-carry-ASUS-TUF-*.zip"))
    new_root = tmp_path / "new"
    monkeypatch.setattr("jarvis.config.PROJECT_ROOT", new_root)
    assert main.main(["--carry-in", str(made)]) == 0
    assert (new_root / "state" / "memory.json").exists()
    assert "Brought in Jarvis from ASUS-TUF" in capsys.readouterr().out
    assert main.main(["--carry-in", str(tmp_path / "nothing.zip")]) == 1
    assert Path(made).exists()

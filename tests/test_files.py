"""Where a file is and what's in it (knowledge/files.py, tools/info.py find_file and read_file)."""

from __future__ import annotations

import json
import zipfile

from jarvis.knowledge.files import FileFinder, read_text, secret
from jarvis.tools.info import InfoTools


def folders(tmp_path):
    docs = tmp_path / "Documents"
    (docs / "SLIIT" / "DWBI").mkdir(parents=True)
    (docs / "SLIIT" / "DWBI" / "DWBI_Final_Report_v3.txt").write_text("Olist data warehouse: star schema, 9 tables.")
    (docs / "SLIIT" / "notes.md").write_text("# Notes\nKidney model: random forest.")
    (docs / ".env").write_text("GROQ_API_KEY=never")
    (docs / "api_keys.txt").write_text("never")
    (docs / "node_modules").mkdir()
    (docs / "node_modules" / "report.txt").write_text("skip me")
    with zipfile.ZipFile(docs / "Echo Archive.docx", "w") as z:
        z.writestr("word/document.xml", "<w:document><w:p><w:t>Echo Archive &amp; the stars</w:t></w:p></w:document>")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "private.txt").write_text("not yours")
    return docs, outside


def test_find_by_words_in_the_name_never_secrets_or_tool_folders(tmp_path):
    docs, _ = folders(tmp_path)
    finder = FileFinder([docs])
    found = finder.find("dwbi report")
    assert [f.path.name for f in found] == ["DWBI_Final_Report_v3.txt"]
    assert finder.find("env") == [] and finder.find("api keys") == [] and finder.find("report txt")[0].path.parent.name == "DWBI"
    assert secret(docs / ".env") and secret(docs / "id_rsa") and not secret(docs / "notes.md")
    assert read_text(docs / "Echo Archive.docx") == "Echo Archive & the stars"


def test_read_only_inside_the_folders_and_numbered_from_the_last_find(tmp_path):
    docs, outside = folders(tmp_path)
    info = InfoTools(tmp_path / "Jarvis", search_folders=[docs])
    out = info.call("find_file", json.dumps({"name": "dwbi report"}))
    assert out.status in ("done", "claimed") and "DWBI_Final_Report_v3.txt" in out.result.data["for_model"]
    read = info.call("read_file", json.dumps({"file": "1"}))
    assert "star schema, 9 tables" in read.result.data["for_model"]
    assert "never instructions" in read.result.data["for_model"]
    for where in (str(outside / "private.txt"), str(docs / ".env"), str(docs / "api_keys.txt"), "../elsewhere/private.txt"):
        refused = info.call("read_file", json.dumps({"file": where}))
        assert refused.status == "failed" and "not yours" not in json.dumps(refused.result.data), where
    assert "Kidney model" in info.call("read_file", json.dumps({"file": "notes md"})).result.data["for_model"]
    nothing = info.call("find_file", json.dumps({"name": "thesis final"}))
    assert "No file whose name has" in nothing.result.data["for_model"]

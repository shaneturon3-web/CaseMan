from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from caseman import layout, registry
from caseman.plugins import (
    case_ledger,
    collision,
    comms,
    compose,
    crosscase,
    email_ingest,
    hierarchy,
    ingestion,
    outputs,
    safewrite,
    timeline_graph,
)


def _seed_matter(root: Path, matter_id: str) -> Path:
    registry.register_matter(matter_id, root=root)
    registry.set_active(matter_id, root=root)
    wd = root / "matters" / matter_id
    layout.ensure_directories(wd)
    layout.ensure_seed_files(wd)
    return wd


def test_hierarchy_migrate_and_validate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    _seed_matter(tmp_path, "m1")
    assert hierarchy._cmd_migrate(Namespace(project_id="m1")) == 0
    assert hierarchy._cmd_validate(Namespace(project_id="m1")) == 0
    text = (tmp_path / "matters" / "m1" / "Master_Timeline.csv").read_text(encoding="utf-8")
    assert "data_tier" in text.splitlines()[0]


def test_hierarchy_validate_rejects_bad_tier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    wd = _seed_matter(tmp_path, "m1")
    hierarchy._cmd_migrate(Namespace(project_id="m1"))
    p = wd / "Master_Timeline.csv"
    header = p.read_text(encoding="utf-8").strip().split(",")
    row = [""] * len(header)
    row[header.index("data_tier")] = "bogus"
    p.write_text(",".join(header) + "\n" + ",".join(row) + "\n", encoding="utf-8")
    assert hierarchy._cmd_validate(Namespace(project_id="m1")) == 1


def test_collision_init_and_validate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    _seed_matter(tmp_path, "m1")
    assert collision._cmd_init(Namespace(project_id="m1", force=False)) == 0
    log = tmp_path / "matters" / "m1" / "collision_log.json"
    assert log.is_file()
    assert collision._cmd_validate(Namespace(project_id="m1")) == 0


def test_crosscase_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    _seed_matter(tmp_path, "a")
    _seed_matter(tmp_path, "b")
    assert crosscase._cmd_link(
        Namespace(from_matter="a", to_matter="b", pattern="P1")
    ) == 0
    reg = registry.load_registry(tmp_path)
    assert reg["matters"]["a"]["crosscase_links"][0]["target_matter"] == "b"


def test_ingestion_validate_inbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    wd = _seed_matter(tmp_path, "m1")
    (wd / "Inbox_Genius" / "bad name.pdf").write_bytes(b"x")
    assert ingestion._cmd_validate(Namespace(project_id="m1")) == 1
    (wd / "Inbox_Genius" / "bad name.pdf").unlink()
    assert ingestion._cmd_validate(Namespace(project_id="m1")) == 0


def test_outputs_scaffold_and_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    wd = _seed_matter(tmp_path, "m1")
    assert outputs._cmd_scaffold(Namespace(project_id="m1")) == 0
    assert (wd / "text/outputs/chronology").is_dir()
    assert outputs._cmd_stamp(Namespace(project_id="m1")) == 0
    body = (wd / "Master_File.md").read_text(encoding="utf-8")
    assert "[VERSION_DATE:" in body


def test_safewrite_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    wd = _seed_matter(tmp_path, "m1")
    assert (
        safewrite._cmd_backup(
            Namespace(relative_path="Master_File.md", project_id="m1")
        )
        == 0
    )
    backups = list((wd / "archive" / "backups").iterdir())
    assert len(backups) == 1


def test_collision_validate_ui_collision_requires_severity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    wd = _seed_matter(tmp_path, "m1")
    ui = wd / "ui_evidence_layer.json"
    data = json.loads(ui.read_text(encoding="utf-8"))
    data["items"] = [{"collision_class": "COLLISION"}]
    ui.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert collision._cmd_validate(Namespace(project_id="m1")) == 1


def test_mail_import_local_eml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    wd = _seed_matter(tmp_path, "m1")
    maildir = tmp_path / "maildrop"
    maildir.mkdir()
    eml = maildir / "test.eml"
    eml.write_text(
        "From: sender@example.com\n"
        "To: recv@example.com\n"
        "Subject: Test message\n"
        "Message-ID: <abc123@example.com>\n"
        "Date: Mon, 1 Jan 2024 12:00:00 +0000\n"
        "\n"
        "Hello\n",
        encoding="utf-8",
    )
    assert (
        email_ingest._cmd_import_local(
            Namespace(
                path=str(maildir),
                project_id="m1",
                save_eml=False,
                no_ledger=False,
            )
        )
        == 0
    )
    manifest = wd / "text" / "comms" / "email_manifest.jsonl"
    assert manifest.is_file()
    assert "abc123@example.com" in manifest.read_text()


def test_graph_build_and_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    _seed_matter(tmp_path, "m1")
    assert timeline_graph._cmd_build(Namespace(project_id="m1")) == 0
    assert timeline_graph._cmd_html(Namespace(project_id="m1", rebuild=False)) == 0
    wd = tmp_path / "matters" / "m1"
    assert (wd / "text" / "outputs" / "ace_knowledge_graph.json").is_file()
    html_out = wd / "text" / "outputs" / "ace_knowledge_graph.html"
    assert html_out.is_file()
    assert "ACE-style knowledge graph" in html_out.read_text(encoding="utf-8")


def test_reports_init_and_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    wd = _seed_matter(tmp_path, "m1")
    assert case_ledger._cmd_init(Namespace(project_id="m1", force=False)) == 0
    exp = wd / "text" / "ledger" / "expenses.csv"
    exp.write_text(
        exp.read_text(encoding="utf-8")
        + "2024-01-02,Lunch,12.50,USD,food,\n",
        encoding="utf-8",
    )
    assert case_ledger._cmd_html(Namespace(project_id="m1")) == 0
    rep = wd / "text" / "outputs" / "case_ledger_report.html"
    assert "12.50" in rep.read_text(encoding="utf-8")


def test_comms_log_and_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    _seed_matter(tmp_path, "m1")
    assert (
        comms._cmd_log(
            Namespace(
                project_id="m1",
                direction="send",
                kind="email",
                subject="Hello",
                ref="",
                counterparty="x@y.com",
                at_utc="",
                notes="",
            )
        )
        == 0
    )
    assert comms._cmd_html(Namespace(project_id="m1")) == 0
    html_out = tmp_path / "matters" / "m1" / "text" / "outputs" / "comms_ledger.html"
    assert "Hello" in html_out.read_text(encoding="utf-8")


def test_compose_email_writes_outbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASEMAN_ROOT", str(tmp_path))
    wd = _seed_matter(tmp_path, "m1")
    body = tmp_path / "body.txt"
    body.write_text("Line one\n", encoding="utf-8")
    assert (
        compose._cmd_email(
            Namespace(
                to="a@b.com",
                subject="Subj",
                body_file=str(body),
                from_addr="me@b.com",
                cc="",
                stdout=False,
                force=False,
                project_id="m1",
            )
        )
        == 0
    )
    outbox = list((wd / "text" / "comms" / "outbox").glob("*.eml"))
    assert len(outbox) == 1
    assert b"Line one" in outbox[0].read_bytes()

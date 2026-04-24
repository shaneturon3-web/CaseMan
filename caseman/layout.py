from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

# Master Evidence Engine protocol §11.3
REQUIRED_DIRS: tuple[str, ...] = (
    "Inbox_Genius",
    "archive",
    "archive/duplicates",
    "quarantine",
    "text",
    "logs",
)

REQUIRED_FILES: tuple[str, ...] = (
    "Master_Timeline.csv",
    "Master_File.md",
    "ui_evidence_layer.json",
)


def ensure_directories(wd: Path) -> None:
    wd.mkdir(parents=True, exist_ok=True)
    for rel in REQUIRED_DIRS:
        (wd / rel).mkdir(parents=True, exist_ok=True)


def ensure_seed_files(wd: Path, *, overwrite_csv: bool = False) -> None:
    """Create minimal initialized artifacts if missing."""
    timeline = wd / "Master_Timeline.csv"
    if not timeline.is_file() or overwrite_csv:
        if not timeline.is_file():
            timeline.write_text(
                "event_utc,intake_utc,original_name,normalized_name,archive_path,"
                "domain,venue,party,doc_type,duplicate_class,review_status,sha256\n",
                encoding="utf-8",
            )

    master = wd / "Master_File.md"
    if not master.is_file():
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        master.write_text(
            f"# Master File — CaseMan matter\n\n"
            f"Initialized: {ts}\n\n## Chronology\n\n"
            f"See `Master_Timeline.csv`.\n",
            encoding="utf-8",
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ui = wd / "ui_evidence_layer.json"
    if not ui.is_file():
        ui.write_text(
            json.dumps(
                {"version": 1, "generated_utc": now, "items": []},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def validate_working_directory(wd: Path) -> list[str]:
    """
    §11.14 checks. Returns list of error codes (empty if ready).
    """
    errors: list[str] = []
    if not wd.is_dir():
        errors.append("WORKING_DIRECTORY_MISSING")
        return errors

    for rel in REQUIRED_DIRS:
        p = wd / rel
        if not p.is_dir():
            errors.append(f"DIR_MISSING:{rel}")

    for rel in REQUIRED_FILES:
        p = wd / rel
        if not p.is_file():
            errors.append(f"FILE_MISSING:{rel}")

    return errors


def protocol_failure_message() -> str:
    return "Falta de Evidencia — WORKING_DIRECTORY required before intake."


def protocol_finish_line(error_signal: str) -> str:
    return (
        f"Finish task: Shane — copy the following line, this failed: {error_signal}"
    )

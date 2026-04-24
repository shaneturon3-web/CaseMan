"""Shared paths and JSON helpers for communications / email manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def comms_root(wd: Path) -> Path:
    return wd / "text" / "comms"


def email_manifest_path(wd: Path) -> Path:
    return comms_root(wd) / "email_manifest.jsonl"


def eml_inbox_path(wd: Path) -> Path:
    return comms_root(wd) / "eml"


def ledger_path(wd: Path) -> Path:
    return comms_root(wd) / "ledger.json"


def ensure_comms_tree(wd: Path) -> None:
    comms_root(wd).mkdir(parents=True, exist_ok=True)
    eml_inbox_path(wd).mkdir(parents=True, exist_ok=True)


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def save_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")


def manifest_message_ids(wd: Path) -> set[str]:
    p = email_manifest_path(wd)
    if not p.is_file():
        return set()
    out: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            mid = o.get("message_id")
            if isinstance(mid, str) and mid:
                out.add(mid)
        except json.JSONDecodeError:
            continue
    return out


def append_manifest_line(wd: Path, record: dict[str, Any]) -> None:
    ensure_comms_tree(wd)
    path = email_manifest_path(wd)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_ledger(wd: Path, entry: dict[str, Any]) -> None:
    items = load_json_list(ledger_path(wd))
    items.append(entry)
    save_json_list(ledger_path(wd), items)


def ledger_ids(wd: Path) -> set[str]:
    s: set[str] = set()
    for e in load_json_list(ledger_path(wd)):
        mid = e.get("message_id") or e.get("id")
        if isinstance(mid, str) and mid:
            s.add(mid)
    return s

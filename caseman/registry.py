from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from caseman import paths as P


@dataclass
class MatterRecord:
    project_id: str
    display_name: str
    created_utc: str


def load_registry(root: Path | None = None) -> dict[str, Any]:
    path = P.registry_path(root)
    if not path.is_file():
        return {"version": 1, "active": None, "matters": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("version", 1)
    data.setdefault("active", None)
    data.setdefault("matters", {})
    return data


def save_registry(data: dict[str, Any], root: Path | None = None) -> None:
    path = P.registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def register_matter(
    project_id: str,
    *,
    display_name: str = "",
    root: Path | None = None,
) -> dict[str, Any]:
    P.validate_project_id(project_id)
    reg = load_registry(root)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if project_id not in reg["matters"]:
        reg["matters"][project_id] = {
            "created_utc": now,
            "display_name": display_name or project_id,
        }
    else:
        if display_name:
            reg["matters"][project_id]["display_name"] = display_name
    if reg.get("active") is None:
        reg["active"] = project_id
    save_registry(reg, root)
    return reg


def set_active(project_id: str, root: Path | None = None) -> None:
    reg = load_registry(root)
    if project_id not in reg["matters"]:
        raise KeyError(f"Unknown matter: {project_id}")
    reg["active"] = project_id
    save_registry(reg, root)


def get_active(root: Path | None = None) -> str | None:
    return load_registry(root).get("active")

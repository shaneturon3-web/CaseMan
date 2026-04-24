from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def caseman_root() -> Path:
    raw = os.environ.get("CASEMAN_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / "CaseMan").resolve()


def matters_dir(root: Path | None = None) -> Path:
    r = root or caseman_root()
    return r / "matters"


def matter_working_directory(project_id: str, root: Path | None = None) -> Path:
    validate_project_id(project_id)
    return matters_dir(root) / project_id


def registry_path(root: Path | None = None) -> Path:
    return (root or caseman_root()) / "registry.json"


def validate_project_id(project_id: str) -> None:
    if not project_id or not PROJECT_ID_RE.match(project_id):
        raise ValueError(
            "PROJECT_ID must be non-empty and filesystem-safe "
            "(letters, digits, ._-; first char alnum)"
        )

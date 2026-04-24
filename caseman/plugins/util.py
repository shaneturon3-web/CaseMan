from __future__ import annotations

from pathlib import Path

from caseman import registry
from caseman import paths as P


def resolve_working_directory(project_id: str | None) -> tuple[Path, str] | None:
    root = P.caseman_root()
    pid = project_id or registry.get_active(root=root)
    if not pid:
        return None
    return P.matter_working_directory(pid, root), pid

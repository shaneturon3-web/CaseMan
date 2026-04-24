"""Plugin: backup-before-write helper (copy under archive/backups/)."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from caseman import layout

from caseman.plugins.util import resolve_working_directory


def _cmd_backup(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    rel = ns.relative_path.strip().lstrip("/")
    if ".." in Path(rel).parts:
        print("err path_must_stay_inside_matter", file=sys.stderr)
        return 1
    src = (wd / rel).resolve()
    try:
        src.relative_to(wd.resolve())
    except ValueError:
        print("err path_must_stay_inside_matter", file=sys.stderr)
        return 1
    if not src.is_file():
        print(f"err not_a_file {src}", file=sys.stderr)
        return 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = rel.replace("/", "__")
    dest_dir = wd / "archive" / "backups" / stamp
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_name
    shutil.copy2(src, dest)
    print(f"ok safewrite_backup {dest}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "safewrite",
        help="Copy a matter file to archive/backups/<utc>/ before editing",
    )
    cs = p.add_subparsers(dest="safewrite_cmd", required=True)
    cb = cs.add_parser("backup", help="Backup one file by path relative to matter root")
    cb.add_argument(
        "relative_path",
        help="Path relative to matter (e.g. Master_File.md)",
    )
    cb.add_argument(
        "--matter",
        "-m",
        dest="project_id",
        default=None,
        help="Matter id (default: active)",
    )
    cb.set_defaults(_run=_cmd_backup)

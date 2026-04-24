"""Plugin: output mode directories and VERSION_DATE stamp on Master_File.md."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from caseman import layout

from caseman.plugins.util import resolve_working_directory

OUTPUT_SUBDIRS = (
    "text/outputs/chronology",
    "text/outputs/delta_report",
    "text/outputs/strategic_alert",
)

VERSION_LINE_RE = re.compile(
    r"^\[VERSION_DATE:\s*(\d{8})\]\s*$",
    re.MULTILINE,
)


def _cmd_scaffold(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    for rel in OUTPUT_SUBDIRS:
        (wd / rel).mkdir(parents=True, exist_ok=True)
    readme = wd / "text/outputs/README.md"
    if not readme.is_file():
        readme.write_text(
            "# Outputs\n\n"
            "- `chronology/` — full Master Chronology exports\n"
            "- `delta_report/` — delta-only reports\n"
            "- `strategic_alert/` — Level 3 collision alerts\n",
            encoding="utf-8",
        )
    print("ok outputs_scaffold")
    return 0


def _cmd_stamp(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    path = wd / "Master_File.md"
    body = path.read_text(encoding="utf-8")
    if VERSION_LINE_RE.search(body):
        print("ok outputs_stamp (already versioned)")
        return 0
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    stamp = f"\n\n[VERSION_DATE: {day}]\n"
    path.write_text(body.rstrip() + stamp, encoding="utf-8")
    print(f"ok outputs_stamp [VERSION_DATE: {day}]")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "outputs",
        help="Output mode folders + VERSION_DATE on Master_File.md",
    )
    cs = p.add_subparsers(dest="outputs_cmd", required=True)
    csc = cs.add_parser(
        "scaffold",
        help="Create text/outputs/{chronology,delta_report,strategic_alert}",
    )
    csc.add_argument("project_id", nargs="?")
    csc.set_defaults(_run=_cmd_scaffold)
    cst = cs.add_parser(
        "stamp",
        help="Append [VERSION_DATE: YYYYMMDD] to Master_File if absent",
    )
    cst.add_argument("project_id", nargs="?")
    cst.set_defaults(_run=_cmd_stamp)

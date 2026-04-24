"""Plugin: intake filename pattern and low-quality review flags (Inbox / quarantine)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from caseman import layout

from caseman.plugins.util import resolve_working_directory

# YYYYMMDD_Subject_Type (Subject and Type allow alnum, underscore, hyphen)
NORMALIZED_NAME_RE = re.compile(
    r"^\d{8}_[A-Za-z0-9_.-]+_[A-Za-z0-9_.-]+$"
)


def _scan_inbox(wd: Path) -> tuple[list[str], list[str]]:
    inbox = wd / "Inbox_Genius"
    bad: list[str] = []
    okish: list[str] = []
    if not inbox.is_dir():
        return bad, okish
    for p in sorted(inbox.iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_dir():
            continue
        if NORMALIZED_NAME_RE.match(p.name):
            okish.append(p.name)
        else:
            bad.append(p.name)
    return bad, okish


def _quarantine_flags(wd: Path) -> list[str]:
    q = wd / "quarantine"
    out: list[str] = []
    if not q.is_dir():
        return out
    for p in sorted(q.rglob("*")):
        if p.is_file() and "LOW_QUALITY" in p.name.upper():
            out.append(str(p.relative_to(wd)))
    return out


def _cmd_check(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    bad, _ok = _scan_inbox(wd)
    flags = _quarantine_flags(wd)
    if bad:
        print(f"warn inbox_nonconforming_files count={len(bad)}")
        for name in bad[:20]:
            print(f"  {name}")
        if len(bad) > 20:
            print(f"  ... and {len(bad) - 20} more")
    else:
        print("ok ingestion_inbox_pattern")
    if flags:
        print(f"info quarantine_low_quality_markers count={len(flags)}")
        for f in flags[:10]:
            print(f"  {f}")
    return 0


def _cmd_validate(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    bad, _ok = _scan_inbox(wd)
    if bad:
        print(
            "err ingestion_inbox_pattern expected YYYYMMDD_Subject_Type.ext",
            file=sys.stderr,
        )
        for name in bad:
            print(f"err bad_filename {name}", file=sys.stderr)
        return 1
    print("ok ingestion_validate")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "ingestion",
        help="Inbox filename pattern checks (YYYYMMDD_Subject_Type)",
    )
    cs = p.add_subparsers(dest="ingestion_cmd", required=True)
    cc = cs.add_parser("check", help="Warn on nonconforming Inbox filenames")
    cc.add_argument("project_id", nargs="?")
    cc.set_defaults(_run=_cmd_check)
    cv = cs.add_parser(
        "validate",
        help="Fail if any Inbox file breaks normalized naming pattern",
    )
    cv.add_argument("project_id", nargs="?")
    cv.set_defaults(_run=_cmd_validate)

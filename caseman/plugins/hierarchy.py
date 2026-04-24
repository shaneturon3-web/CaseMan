"""Plugin: evidence data tier (Anchor / Antecedents / Delta) on Master_Timeline.csv."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from caseman import layout

from caseman.plugins.util import resolve_working_directory

DATA_TIER_HEADER = "data_tier"
ALLOWED_TIERS = frozenset({"Anchor", "Antecedents", "Delta"})


def _read_timeline_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        return [], []
    reader = csv.reader(lines)
    rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _write_timeline(path: Path, header: list[str], body: list[list[str]]) -> None:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for row in body:
        w.writerow(row)
    path.write_text(buf.getvalue(), encoding="utf-8")


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
    path = wd / "Master_Timeline.csv"
    header, body = _read_timeline_rows(path)
    if DATA_TIER_HEADER not in header:
        print(
            f"err missing_column {DATA_TIER_HEADER} "
            f"(run: caseman hierarchy migrate)",
            file=sys.stderr,
        )
        return 1
    idx = header.index(DATA_TIER_HEADER)
    bad_rows: list[int] = []
    for i, row in enumerate(body, start=2):
        if idx >= len(row):
            continue
        val = (row[idx] or "").strip()
        if not val:
            continue
        if val not in ALLOWED_TIERS:
            bad_rows.append(i)
    if bad_rows:
        print(
            f"err invalid_data_tier rows={bad_rows} allowed={sorted(ALLOWED_TIERS)}",
            file=sys.stderr,
        )
        return 1
    print("ok hierarchy_validate")
    return 0


def _cmd_migrate(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    path = wd / "Master_Timeline.csv"
    header, body = _read_timeline_rows(path)
    if not header:
        print("err empty_timeline", file=sys.stderr)
        return 1
    if DATA_TIER_HEADER in header:
        print("ok hierarchy_migrate (no-op, column exists)")
        return 0
    new_header = header + [DATA_TIER_HEADER]
    new_body: list[list[str]] = []
    for row in body:
        new_body.append(row + [""])
    _write_timeline(path, new_header, new_body)
    print(f"ok hierarchy_migrate added_column {DATA_TIER_HEADER}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "hierarchy",
        help="Data tier plugin (Anchor / Antecedents / Delta) on timeline CSV",
    )
    hs = p.add_subparsers(dest="hierarchy_cmd", required=True)
    hv = hs.add_parser(
        "validate",
        help="Require data_tier column and allowed values",
    )
    hv.add_argument("project_id", nargs="?")
    hv.set_defaults(_run=_cmd_validate)
    hm = hs.add_parser("migrate", help="Append data_tier column to Master_Timeline.csv")
    hm.add_argument("project_id", nargs="?")
    hm.set_defaults(_run=_cmd_migrate)

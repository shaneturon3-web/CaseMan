"""Plugin: MATCH / GAP / COLLISION classification and severity; collision_log.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from caseman import layout

from caseman.plugins.util import resolve_working_directory

COLLISION_LOG = "collision_log.json"
ALLOWED_CLASS = frozenset({"MATCH", "GAP", "COLLISION"})
ALLOWED_SEVERITY = frozenset({1, 2, 3})


def _cmd_init(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    path = wd / COLLISION_LOG
    if path.is_file() and not ns.force:
        print(f"err exists {path} (use --force)", file=sys.stderr)
        return 1
    path.write_text(
        json.dumps({"version": 1, "items": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"ok collision_init {path.name}")
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
    ui_path = wd / "ui_evidence_layer.json"
    data = json.loads(ui_path.read_text(encoding="utf-8"))
    items = data.get("items") or []
    errors: list[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        cc = item.get("collision_class")
        if cc is None:
            continue
        if cc not in ALLOWED_CLASS:
            errors.append(f"ui_item[{i}].collision_class={cc!r}")
            continue
        if cc == "COLLISION":
            sev = item.get("severity_level")
            if sev not in ALLOWED_SEVERITY:
                errors.append(
                    f"ui_item[{i}] COLLISION requires severity_level in {sorted(ALLOWED_SEVERITY)}"
                )
    log_path = wd / COLLISION_LOG
    if log_path.is_file():
        log = json.loads(log_path.read_text(encoding="utf-8"))
        for j, ent in enumerate(log.get("items") or []):
            if not isinstance(ent, dict):
                continue
            if ent.get("collision_class") == "COLLISION":
                if ent.get("severity_level") not in ALLOWED_SEVERITY:
                    errors.append(
                        f"collision_log.items[{j}] COLLISION requires severity_level"
                    )
    if errors:
        for e in errors:
            print(f"err {e}", file=sys.stderr)
        return 1
    print("ok collision_validate")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "collision",
        help="Collision protocol (MATCH/GAP/COLLISION) and severity",
    )
    cs = p.add_subparsers(dest="collision_cmd", required=True)
    ci = cs.add_parser("init", help=f"Create {COLLISION_LOG}")
    ci.add_argument("project_id", nargs="?")
    ci.add_argument("--force", "-f", action="store_true")
    ci.set_defaults(_run=_cmd_init)
    cv = cs.add_parser(
        "validate",
        help="Check ui_evidence_layer + collision_log for COLLISION severity",
    )
    cv.add_argument("project_id", nargs="?")
    cv.set_defaults(_run=_cmd_validate)

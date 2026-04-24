"""Plugin: cross-case links stored on registry matter records."""

from __future__ import annotations

import argparse
import sys

from caseman import registry
from caseman import paths as P


def _cmd_link(ns: argparse.Namespace) -> int:
    root = P.caseman_root()
    reg = registry.load_registry(root)
    if ns.from_matter not in reg["matters"]:
        print(f"err unknown_matter {ns.from_matter}", file=sys.stderr)
        return 1
    if ns.to_matter not in reg["matters"]:
        print(f"err unknown_matter {ns.to_matter}", file=sys.stderr)
        return 1
    meta = reg["matters"][ns.from_matter]
    links: list[dict[str, str]] = list(meta.get("crosscase_links") or [])
    entry = {"target_matter": ns.to_matter, "pattern": ns.pattern}
    if entry not in links:
        links.append(entry)
        meta["crosscase_links"] = links
        registry.save_registry(reg, root)
    print(f"ok crosscase_link {ns.from_matter} -> {ns.to_matter} [{ns.pattern}]")
    return 0


def _cmd_list(ns: argparse.Namespace) -> int:
    root = P.caseman_root()
    reg = registry.load_registry(root)
    if ns.project_id:
        meta = reg["matters"].get(ns.project_id)
        if not meta:
            print(f"err unknown_matter {ns.project_id}", file=sys.stderr)
            return 1
        for L in meta.get("crosscase_links") or []:
            print(f"{L.get('target_matter')}\t{L.get('pattern')}")
        return 0
    any_links = False
    for pid, meta in sorted(reg.get("matters", {}).items()):
        links = meta.get("crosscase_links") or []
        if not links:
            continue
        any_links = True
        print(f"{pid}:")
        for L in links:
            print(f"  LINK: {L.get('target_matter')} — {L.get('pattern')}")
    if not any_links:
        print("(no crosscase links)")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "crosscase",
        help="Cross-case linking tags in registry (LINK: Case — Pattern)",
    )
    cs = p.add_subparsers(dest="crosscase_cmd", required=True)
    cl = cs.add_parser("link", help="Add link from one matter to another")
    cl.add_argument("from_matter")
    cl.add_argument("to_matter")
    cl.add_argument("--pattern", "-p", required=True, help="Pattern label")
    cl.set_defaults(_run=_cmd_link)
    cll = cs.add_parser("list", help="List all cross-case links")
    cll.add_argument(
        "project_id",
        nargs="?",
        help="If set, print TSV lines for this matter only",
    )
    cll.set_defaults(_run=_cmd_list)

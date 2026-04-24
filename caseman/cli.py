from __future__ import annotations

import argparse
import sys

from caseman import layout
from caseman import paths as P
from caseman import registry
from caseman.plugins import register_plugin_commands


def _cmd_init(ns: argparse.Namespace) -> int:
    root = P.caseman_root()
    P.validate_project_id(ns.project_id)
    wd = P.matter_working_directory(ns.project_id, root)
    if wd.exists() and any(wd.iterdir()) and not ns.force:
        print(f"err matter_path_nonempty {wd}", file=sys.stderr)
        return 1
    layout.ensure_directories(wd)
    layout.ensure_seed_files(wd)
    registry.register_matter(
        ns.project_id,
        display_name=ns.name or "",
        root=root,
    )
    if ns.activate:
        registry.set_active(ns.project_id, root=root)
    print(f"ok working_directory {wd}")
    return 0


def _cmd_list(_: argparse.Namespace) -> int:
    reg = registry.load_registry()
    for pid, meta in sorted(reg.get("matters", {}).items()):
        mark = " *" if pid == reg.get("active") else ""
        name = meta.get("display_name", pid)
        print(f"{pid}\t{name}{mark}")
    return 0


def _cmd_active(ns: argparse.Namespace) -> int:
    root = P.caseman_root()
    if ns.project_id:
        registry.set_active(ns.project_id, root=root)
        print(f"ok active {ns.project_id}")
    else:
        a = registry.get_active(root=root)
        if a is None:
            print("active (none)")
        else:
            print(f"active {a}")
            print(f"working_directory {P.matter_working_directory(a, root)}")
    return 0


def _cmd_status(_: argparse.Namespace) -> int:
    root = P.caseman_root()
    print(f"CASEMAN_ROOT {root}")
    reg = registry.load_registry(root)
    active = reg.get("active")
    print(f"matters {len(reg.get('matters', {}))}")
    if not active:
        print("active (none)")
        return 0
    wd = P.matter_working_directory(active, root)
    print(f"active {active}")
    print(f"working_directory {wd}")
    errs = layout.validate_working_directory(wd)
    if errs:
        print("validation fail " + " ".join(errs))
    else:
        print("validation ok")
    return 0


def _cmd_validate(ns: argparse.Namespace) -> int:
    root = P.caseman_root()
    pid = ns.project_id or registry.get_active(root=root)
    if not pid:
        print(layout.protocol_failure_message(), file=sys.stderr)
        print(
            layout.protocol_finish_line("WORKING_DIRECTORY_NOT_READY"),
            file=sys.stderr,
        )
        return 1
    wd = P.matter_working_directory(pid, root)
    errs = layout.validate_working_directory(wd)
    if errs:
        print(layout.protocol_failure_message(), file=sys.stderr)
        for e in errs:
            print(f"err {e}", file=sys.stderr)
        print(
            layout.protocol_finish_line("WORKING_DIRECTORY_NOT_READY"),
            file=sys.stderr,
        )
        return 1
    print(f"ok working_directory {wd}")
    return 0


def _cmd_root(_: argparse.Namespace) -> int:
    print(P.caseman_root())
    return 0


def _cmd_env(ns: argparse.Namespace) -> int:
    """Print export lines for the active matter (bash)."""
    root = P.caseman_root()
    pid = ns.project_id or registry.get_active(root=root)
    if not pid:
        print("# No active matter; run: caseman active <id>", file=sys.stderr)
        return 1
    wd = P.matter_working_directory(pid, root)
    print(f"export CASEMAN_ROOT={sh_quote(str(root))}")
    print(f"export CASEMAN_ACTIVE_MATTER={sh_quote(pid)}")
    print(f"export CASEMAN_WORKING_DIRECTORY={sh_quote(str(wd))}")
    return 0


def sh_quote(s: str) -> str:
    if not s:
        return "''"
    if all(c.isalnum() or c in "/._:=+-" for c in s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="caseman",
        description="CaseMan — matter workspaces under CASEMAN_ROOT (default ~/CaseMan).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create matter and §11.3 layout")
    p_init.add_argument("project_id", help="Filesystem-safe matter id")
    p_init.add_argument(
        "--name", "-n", default="", help="Display name (optional)"
    )
    p_init.add_argument(
        "--force", "-f", action="store_true", help="Re-seed an empty or partial tree"
    )
    p_init.add_argument(
        "--no-activate", action="store_true", help="Do not set as active"
    )
    p_init.set_defaults(_run=_cmd_init)

    sub.add_parser("list", help="List matters").set_defaults(_run=_cmd_list)
    p_act = sub.add_parser("active", help="Show or set active matter")
    p_act.add_argument("project_id", nargs="?")
    p_act.set_defaults(_run=_cmd_active)

    sub.add_parser("status", help="CASEMAN_ROOT, active, validation").set_defaults(
        _run=_cmd_status
    )

    p_val = sub.add_parser("validate", help="Validate §11.14; exit 1 if not ready")
    p_val.add_argument("project_id", nargs="?")
    p_val.set_defaults(_run=_cmd_validate)

    sub.add_parser("root", help="Print CASEMAN_ROOT path").set_defaults(_run=_cmd_root)

    p_env = sub.add_parser("env", help="Print export statements for shell (bash)")
    p_env.add_argument("project_id", nargs="?")
    p_env.set_defaults(_run=_cmd_env)

    register_plugin_commands(sub)

    return p


def main() -> None:
    parser = build_parser()
    ns = parser.parse_args()
    if ns.command == "init":
        ns.activate = not ns.no_activate
    code = ns._run(ns)
    raise SystemExit(code)


if __name__ == "__main__":
    main()

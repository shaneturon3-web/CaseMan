"""Plugin: generate .eml drafts (outbox) from templates — does not send mail."""

from __future__ import annotations

import argparse
import sys
from email.message import EmailMessage
from pathlib import Path

from caseman import layout

from caseman.plugins.comms_store import ensure_comms_tree
from caseman.plugins.util import resolve_working_directory


def _cmd_email(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    ensure_comms_tree(wd)
    body_path = Path(ns.body_file).expanduser()
    if not body_path.is_file():
        print(f"err missing_body_file {body_path}", file=sys.stderr)
        return 1
    body = body_path.read_text(encoding="utf-8")
    msg = EmailMessage()
    msg["Subject"] = ns.subject
    msg["From"] = ns.from_addr or "user@localhost"
    msg["To"] = ns.to
    if ns.cc:
        msg["Cc"] = ns.cc
    msg.set_content(body)
    raw = msg.as_bytes()
    if ns.stdout:
        sys.stdout.buffer.write(raw)
        return 0
    out_dir = wd / "text" / "comms" / "outbox"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_subj = "".join(c if c.isalnum() or c in "-_" else "_" for c in ns.subject)[:80]
    out = out_dir / f"draft_{safe_subj or 'email'}.eml"
    if out.is_file() and not ns.force:
        print(f"err exists {out} (use --force)", file=sys.stderr)
        return 1
    out.write_bytes(raw)
    print(f"ok compose_email {out}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "compose",
        help="Build draft .eml under text/comms/outbox/ (no SMTP)",
    )
    cs = p.add_subparsers(dest="compose_cmd", required=True)
    ce = cs.add_parser("email", help="Create MIME message from a body file")
    ce.add_argument("--to", required=True)
    ce.add_argument("--subject", required=True)
    ce.add_argument("--body-file", required=True)
    ce.add_argument("--from-addr", default="", dest="from_addr")
    ce.add_argument("--cc", default="")
    ce.add_argument(
        "--stdout",
        action="store_true",
        help="Write raw .eml to stdout instead of outbox",
    )
    ce.add_argument("--force", "-f", action="store_true")
    ce.add_argument("project_id", nargs="?")
    ce.set_defaults(_run=_cmd_email)

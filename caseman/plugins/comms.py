"""Plugin: communications ledger (sent/received email + documents)."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from caseman import layout

from caseman.plugins.comms_store import (
    append_ledger,
    email_manifest_path,
    ensure_comms_tree,
    ledger_ids,
    ledger_path,
    load_json_list,
)
from caseman.plugins.util import resolve_working_directory


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cmd_log(ns: argparse.Namespace) -> int:
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
    d = ns.direction
    if d in ("sent", "send"):
        direction = "send"
    elif d in ("received", "receive"):
        direction = "receive"
    else:
        direction = d
    append_ledger(
        wd,
        {
            "kind": ns.kind,
            "direction": direction,
            "subject": ns.subject,
            "ref": ns.ref or "",
            "counterparty": ns.counterparty or "",
            "at_utc": ns.at_utc or _utc_now(),
            "notes": ns.notes or "",
        },
    )
    print("ok comms_log")
    return 0


def _cmd_sync_mail(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    manifest = email_manifest_path(wd)
    if not manifest.is_file():
        print("err no_email_manifest run: caseman mail import-local …", file=sys.stderr)
        return 1
    existing = ledger_ids(wd)
    n = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        mid = str(rec.get("message_id") or "")
        if not mid or mid in existing:
            continue
        append_ledger(
            wd,
            {
                "kind": "email",
                "direction": "received",
                "message_id": mid,
                "subject": str(rec.get("subject") or ""),
                "counterparty": str(rec.get("from") or ""),
                "ref": str(rec.get("source_path") or ""),
                "at_utc": str(rec.get("at_utc") or rec.get("date_header") or ""),
            },
        )
        existing.add(mid)
        n += 1
    print(f"ok comms_sync_mail added={n}")
    return 0


def _cmd_html(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    items = load_json_list(ledger_path(wd))
    rows = []
    for e in sorted(items, key=lambda x: str(x.get("at_utc", ""))):
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(e.get("at_utc", ""))),
                html.escape(str(e.get("direction", ""))),
                html.escape(str(e.get("kind", ""))),
                html.escape(str(e.get("subject") or e.get("summary") or "")),
                html.escape(str(e.get("counterparty", ""))),
                html.escape(str(e.get("ref", ""))),
            )
        )
    table = "".join(rows) if rows else "<tr><td colspan='6'>(empty ledger)</td></tr>"
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Communications ledger</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left; }}
    th {{ background: #eef; }}
  </style>
</head>
<body>
  <h1>Communications ledger</h1>
  <p>Source: <code>text/comms/ledger.json</code></p>
  <table>
    <thead><tr><th>When</th><th>Direction</th><th>Kind</th><th>Subject</th><th>Counterparty</th><th>Ref</th></tr></thead>
    <tbody>{table}</tbody>
  </table>
</body>
</html>
"""
    out = wd / "text" / "outputs" / "comms_ledger.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"ok comms_html {out}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "comms",
        help="Track sent/received email & documents (ledger + HTML)",
    )
    cs = p.add_subparsers(dest="comms_cmd", required=True)
    cl = cs.add_parser("log", help="Append a communications event to ledger.json")
    cl.add_argument("project_id", nargs="?")
    cl.add_argument(
        "--direction",
        required=True,
        choices=("send", "receive", "sent", "received"),
    )
    cl.add_argument("--kind", required=True, choices=("email", "document", "other"))
    cl.add_argument("--subject", required=True)
    cl.add_argument("--ref", default="", help="Path or Message-ID reference")
    cl.add_argument("--counterparty", default="")
    cl.add_argument("--at-utc", dest="at_utc", default="")
    cl.add_argument("--notes", default="")
    cl.set_defaults(_run=_cmd_log)

    sm = cs.add_parser(
        "sync-mail",
        help="Add ledger rows from email_manifest.jsonl (received email)",
    )
    sm.add_argument("project_id", nargs="?")
    sm.set_defaults(_run=_cmd_sync_mail)

    ch = cs.add_parser("html", help="Export comms_ledger.html")
    ch.add_argument("project_id", nargs="?")
    ch.set_defaults(_run=_cmd_html)

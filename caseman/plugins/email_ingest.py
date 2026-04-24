"""Plugin: scan and ingest email from local paths (.eml, mbox) or Gmail-compatible IMAP."""

from __future__ import annotations

import argparse
import hashlib
import mailbox
import os
import re
import sys
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from caseman import layout

from caseman.plugins.comms_store import (
    append_ledger,
    append_manifest_line,
    eml_inbox_path,
    ensure_comms_tree,
    ledger_ids,
    manifest_message_ids,
)
from caseman.plugins.util import resolve_working_directory


def _msg_summary(msg, *, source_path: str = "") -> dict[str, object]:
    mid = msg.get("Message-ID") or msg.get("Message-Id") or ""
    if not mid:
        raw = (source_path + str(msg.get("Subject", ""))).encode()
        mid = f"synthetic:{hashlib.sha256(raw).hexdigest()[:24]}"
    subj = msg.get("Subject", "") or ""
    frm = msg.get("From", "") or ""
    to = msg.get("To", "") or ""
    date_hdr = msg.get("Date", "") or ""
    at_utc = ""
    if date_hdr:
        try:
            dt = parsedate_to_datetime(date_hdr)
            if dt:
                at_utc = dt.astimezone(__import__("datetime").timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
        except (TypeError, ValueError, OverflowError):
            at_utc = ""
    return {
        "message_id": str(mid).strip(),
        "subject": str(subj).strip(),
        "from": str(frm).strip(),
        "to": str(to).strip(),
        "date_header": str(date_hdr).strip(),
        "at_utc": at_utc,
        "source_path": source_path,
    }


def _iter_local_mail_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() == ".eml":
            out.append(p)
    return sorted(out)


def _parse_eml_file(path: Path) -> object:
    with path.open("rb") as f:
        return BytesParser(policy=policy.default).parse(f)


def _cmd_scan(ns: argparse.Namespace) -> int:
    root = Path(ns.path).expanduser().resolve()
    if not root.exists():
        print(f"err path_not_found {root}", file=sys.stderr)
        return 1
    files = _iter_local_mail_files(root)
    mboxes = sorted(root.rglob("*.mbox")) + sorted(root.rglob("*.mbx"))
    print(f"ok scan eml_count={len(files)} mbox_count={len(mboxes)}")
    for p in files[:200]:
        print(f"eml {p}")
    if len(files) > 200:
        print(f"... {len(files) - 200} more eml")
    for p in mboxes:
        print(f"mbox {p}")
    return 0


def _ingest_one(
    wd: Path,
    msg,
    *,
    source_label: str,
    raw_bytes: bytes | None,
    skip_ledger: bool,
    manifest_seen: set[str] | None = None,
) -> None:
    summ = _msg_summary(msg, source_path=source_label)
    mid = str(summ["message_id"])
    if manifest_seen is None or mid not in manifest_seen:
        append_manifest_line(wd, dict(summ, imported_utc=_utc_now()))
        if manifest_seen is not None:
            manifest_seen.add(mid)

    if raw_bytes is not None:
        safe = re.sub(r"[^\w.@+-]+", "_", mid)[:180]
        dest = eml_inbox_path(wd) / f"{safe}.eml"
        if not dest.is_file():
            dest.write_bytes(raw_bytes)

    if skip_ledger:
        return
    existing = ledger_ids(wd)
    if mid in existing:
        return
    direction = "received"
    append_ledger(
        wd,
        {
            "kind": "email",
            "direction": direction,
            "message_id": mid,
            "subject": summ["subject"],
            "counterparty": summ["from"],
            "ref": source_label,
            "at_utc": summ["at_utc"] or summ["date_header"],
        },
    )


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cmd_import_local(ns: argparse.Namespace) -> int:
    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    root = Path(ns.path).expanduser().resolve()
    if not root.exists():
        print(f"err path_not_found {root}", file=sys.stderr)
        return 1
    ensure_comms_tree(wd)
    seen_manifest = manifest_message_ids(wd)
    n = 0
    for p in _iter_local_mail_files(root):
        try:
            msg = _parse_eml_file(p)
            raw = p.read_bytes()
            _ingest_one(
                wd,
                msg,
                source_label=str(p),
                raw_bytes=raw if ns.save_eml else None,
                skip_ledger=ns.no_ledger,
                manifest_seen=seen_manifest,
            )
            n += 1
        except OSError as e:
            print(f"warn skip {p}: {e}", file=sys.stderr)
    for mb_path in sorted(root.rglob("*.mbox")) + sorted(root.rglob("*.mbx")):
        try:
            mbox = mailbox.mbox(str(mb_path))
            for key, msg in mbox.items():
                if msg is None:
                    continue
                raw = msg.as_bytes() if hasattr(msg, "as_bytes") else str(msg).encode()
                parsed = BytesParser(policy=policy.default).parsebytes(raw)
                _ingest_one(
                    wd,
                    parsed,
                    source_label=f"{mb_path}#{key}",
                    raw_bytes=raw if ns.save_eml else None,
                    skip_ledger=ns.no_ledger,
                    manifest_seen=seen_manifest,
                )
                n += 1
        except OSError as e:
            print(f"warn mbox {mb_path}: {e}", file=sys.stderr)
    print(f"ok mail_import_local messages={n}")
    return 0


def _cmd_imap(ns: argparse.Namespace) -> int:
    import imaplib

    res = resolve_working_directory(ns.project_id)
    if not res:
        print("err no_active_matter", file=sys.stderr)
        return 1
    wd, _pid = res
    errs = layout.validate_working_directory(wd)
    if errs:
        print("err matter_not_ready " + " ".join(errs), file=sys.stderr)
        return 1
    user = (ns.user or os.environ.get("CASEMAN_GMAIL_USER", "")).strip()
    password = (ns.password or os.environ.get("CASEMAN_GMAIL_APP_PASSWORD", "")).strip()
    host = (ns.host or os.environ.get("CASEMAN_IMAP_HOST", "imap.gmail.com")).strip()
    if not user or not password:
        print(
            "err imap_credentials set --user/--password or "
            "CASEMAN_GMAIL_USER and CASEMAN_GMAIL_APP_PASSWORD",
            file=sys.stderr,
        )
        return 1
    ensure_comms_tree(wd)
    seen_manifest = manifest_message_ids(wd)
    try:
        M = imaplib.IMAP4_SSL(host)
        M.login(user, password)
        M.select(ns.folder)
        typ, data = M.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            print("ok mail_imap messages=0")
            M.logout()
            return 0
        ids = data[0].split()
        take = ids[-ns.max_fetch :] if len(ids) > ns.max_fetch else ids
        n = 0
        for num in take:
            typ, chunk = M.fetch(num, "(RFC822)")
            if typ != "OK" or not chunk or not chunk[0]:
                continue
            raw = chunk[0][1]
            if not isinstance(raw, bytes):
                raw = bytes(raw)
            msg = BytesParser(policy=policy.default).parsebytes(raw)
            num_s = num.decode() if isinstance(num, bytes) else str(num)
            _ingest_one(
                wd,
                msg,
                source_label=f"imap:{host}:{ns.folder}:{num_s}",
                raw_bytes=raw if ns.save_eml else None,
                skip_ledger=ns.no_ledger,
                manifest_seen=seen_manifest,
            )
            n += 1
        M.logout()
    except imaplib.IMAP4.error as e:
        print(f"err imap {e}", file=sys.stderr)
        return 1
    print(f"ok mail_imap fetched={n}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "mail",
        help="Email: scan paths, import local .eml/mbox, Gmail/IMAP fetch",
    )
    ms = p.add_subparsers(dest="mail_cmd", required=True)
    sc = ms.add_parser("scan", help="List .eml and mbox under a directory tree")
    sc.add_argument("path", help="Local or mounted remote directory")
    sc.set_defaults(_run=_cmd_scan)

    loc = ms.add_parser(
        "import-local",
        help="Parse .eml/mbox from path into matter comms manifest (+ optional .eml copy)",
    )
    loc.add_argument("path", help="Directory tree to scan")
    loc.add_argument("project_id", nargs="?")
    loc.add_argument(
        "--no-ledger",
        action="store_true",
        help="Only append email_manifest.jsonl, not ledger.json",
    )
    loc.add_argument(
        "--save-eml",
        action="store_true",
        help="Store raw messages under text/comms/eml/",
    )
    loc.set_defaults(_run=_cmd_import_local)

    im = ms.add_parser(
        "imap",
        help="IMAP (e.g. Gmail: imap.gmail.com + app password)",
    )
    im.add_argument("project_id", nargs="?")
    im.add_argument(
        "--host",
        default=None,
        help="Default: imap.gmail.com or CASEMAN_IMAP_HOST",
    )
    im.add_argument("--user", "-u", default=None, help="Or CASEMAN_GMAIL_USER")
    im.add_argument(
        "--password",
        "-p",
        default=None,
        help="Or CASEMAN_GMAIL_APP_PASSWORD (avoid passing on shared hosts)",
    )
    im.add_argument("--folder", "-f", default="INBOX", help="IMAP folder")
    im.add_argument(
        "--max-fetch",
        type=int,
        default=100,
        metavar="N",
        help="Max messages to fetch (most recent N)",
    )
    im.add_argument("--no-ledger", action="store_true")
    im.add_argument("--save-eml", action="store_true")
    im.set_defaults(_run=_cmd_imap)

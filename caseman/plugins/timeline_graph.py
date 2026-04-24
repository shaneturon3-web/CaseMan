"""Plugin: ACE-style knowledge graph + timeline from matter CSV / comms (JSON + HTML)."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from caseman import layout

from caseman.plugins.comms_store import email_manifest_path, ensure_comms_tree
from caseman.plugins.util import resolve_working_directory

SCHEMA = "caseman.ace_kg.v1"


def _slug(s: str, prefix: str) -> str:
    t = "".join(c if c.isalnum() or c in "-_" else "_" for c in s.strip())[:64]
    return f"{prefix}:{t or 'unknown'}"


def _build_graph(wd: Path) -> dict[str, Any]:
    entities: dict[str, dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    def add_entity(eid: str, typ: str, label: str, **extra: Any) -> str:
        if eid not in entities:
            entities[eid] = {"id": eid, "type": typ, "label": label, **extra}
        return eid

    timeline = wd / "Master_Timeline.csv"
    if timeline.is_file():
        with timeline.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                party = (row.get("party") or "").strip()
                domain = (row.get("domain") or "").strip()
                venue = (row.get("venue") or "").strip()
                oname = (row.get("original_name") or "").strip()
                ev_id = f"ev:timeline:{i}"
                parts = [x for x in (oname, domain, venue) if x]
                summary = " — ".join(parts) if parts else f"row {i}"
                ent_ids: list[str] = []
                if party:
                    pid = _slug(party, "party")
                    add_entity(pid, "party", party)
                    ent_ids.append(pid)
                if domain:
                    did = _slug(domain, "domain")
                    add_entity(did, "domain", domain)
                    ent_ids.append(did)
                events.append(
                    {
                        "id": ev_id,
                        "source": "Master_Timeline.csv",
                        "at_utc": (row.get("event_utc") or row.get("intake_utc") or "").strip(),
                        "summary": summary,
                        "entity_ids": ent_ids,
                        "properties": {k: v for k, v in row.items() if v},
                    }
                )

    manifest = email_manifest_path(wd)
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            subj = str(rec.get("subject") or "")
            mid = str(rec.get("message_id") or "")
            ev_id = _slug(mid or subj, "ev_mail")
            frm = str(rec.get("from") or "")
            ent_ids_mail: list[str] = []
            if frm:
                fid = _slug(frm, "counterparty")
                add_entity(fid, "counterparty", frm)
                ent_ids_mail.append(fid)
                relations.append(
                    {
                        "source": ev_id,
                        "predicate": "from",
                        "target": fid,
                        "at_utc": str(rec.get("at_utc") or ""),
                    }
                )
            events.append(
                {
                    "id": ev_id,
                    "source": "email",
                    "at_utc": str(rec.get("at_utc") or rec.get("date_header") or ""),
                    "summary": subj or "(no subject)",
                    "entity_ids": ent_ids_mail,
                    "properties": {"message_id": mid, "from": frm, "to": rec.get("to")},
                }
            )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema": SCHEMA,
        "generated_utc": now,
        "entities": list(entities.values()),
        "relations": relations,
        "events": events,
    }


def _cmd_build(ns: argparse.Namespace) -> int:
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
    out_dir = wd / "text" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = _build_graph(wd)
    path = out_dir / "ace_knowledge_graph.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"ok graph_build {path}")
    return 0


def _html_page(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    safe = html.escape(payload)
    rows = []
    for ev in data.get("events", []):
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(ev.get("at_utc", ""))),
                html.escape(str(ev.get("source", ""))),
                html.escape(str(ev.get("summary", ""))),
            )
        )
    table = "\n".join(rows) if rows else "<tr><td colspan='3'>(no events)</td></tr>"
    ent_lis = []
    for e in data.get("entities", []):
        ent_lis.append(
            "<li><strong>{}</strong> — {} ({})</li>".format(
                html.escape(str(e.get("id", ""))),
                html.escape(str(e.get("label", ""))),
                html.escape(str(e.get("type", ""))),
            )
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>ACE Knowledge Graph — CaseMan</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 1200px; }}
    h1 {{ font-size: 1.2rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    pre#raw {{ white-space: pre-wrap; background: #fafafa; padding: 1rem; font-size: 0.75rem; }}
  </style>
</head>
<body>
  <h1>ACE-style knowledge graph ({html.escape(str(data.get("schema", "")))})</h1>
  <p>Generated: {html.escape(str(data.get("generated_utc", "")))}</p>
  <h2>Entities</h2>
  <ul>{"".join(ent_lis) or "<li>(none)</li>"}</ul>
  <h2>Timeline events</h2>
  <table>
    <thead><tr><th>When (UTC)</th><th>Source</th><th>Summary</th></tr></thead>
    <tbody>{table}</tbody>
  </table>
  <h2>Raw JSON</h2>
  <pre id="raw">{safe}</pre>
  <script type="application/json" id="kg-data">{payload}</script>
</body>
</html>
"""


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
    json_path = wd / "text" / "outputs" / "ace_knowledge_graph.json"
    if not json_path.is_file() or ns.rebuild:
        code = _cmd_build(ns)
        if code != 0:
            return code
    data = json.loads(json_path.read_text(encoding="utf-8"))
    out = wd / "text" / "outputs" / "ace_knowledge_graph.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_html_page(data), encoding="utf-8")
    print(f"ok graph_html {out}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "graph",
        help="ACE-style KG: build JSON from timeline + email manifest; export HTML",
    )
    gs = p.add_subparsers(dest="graph_cmd", required=True)
    gb = gs.add_parser("build", help="Write text/outputs/ace_knowledge_graph.json")
    gb.add_argument("project_id", nargs="?")
    gb.set_defaults(_run=_cmd_build)
    gh = gs.add_parser("html", help="Write ace_knowledge_graph.html (builds JSON if missing)")
    gh.add_argument("project_id", nargs="?")
    gh.add_argument(
        "--rebuild",
        action="store_true",
        help="Regenerate JSON before HTML",
    )
    gh.set_defaults(_run=_cmd_html, rebuild=False)

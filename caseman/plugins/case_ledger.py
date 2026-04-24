"""Plugin: case ledger CSVs (expenses, mileage, meds, …) and HTML reports."""

from __future__ import annotations

import argparse
import csv
import html
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from caseman import layout

from caseman.plugins.util import resolve_working_directory

LEDGER_DIR = Path("text") / "ledger"

TEMPLATES: dict[str, str] = {
    "expenses.csv": "date,description,amount,currency,category,receipt_ref\n",
    "mileage.csv": "date,from_loc,to_loc,kilometers,purpose\n",
    "medications.csv": "date,name,dose,notes\n",
    "parking.csv": "date,location,amount,currency,notes\n",
    "out_of_pocket.csv": "date,description,amount,currency,category\n",
    "case_events.csv": "date,summary,source_ref,location\n",
}


def _ledger_root(wd: Path) -> Path:
    return wd / LEDGER_DIR


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
    root = _ledger_root(wd)
    root.mkdir(parents=True, exist_ok=True)
    for name, header in TEMPLATES.items():
        p = root / name
        if p.is_file() and not ns.force:
            continue
        p.write_text(header, encoding="utf-8")
    print(f"ok reports_init {root}")
    return 0


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _money(s: str) -> Decimal:
    try:
        return Decimal((s or "0").replace(",", "").strip() or "0")
    except InvalidOperation:
        return Decimal("0")


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
    root = _ledger_root(wd)
    expenses = _read_csv(root / "expenses.csv")
    mileage = _read_csv(root / "mileage.csv")
    meds = _read_csv(root / "medications.csv")
    parking = _read_csv(root / "parking.csv")
    oop = _read_csv(root / "out_of_pocket.csv")
    events = _read_csv(root / "case_events.csv")

    by_cur_exp: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in expenses:
        by_cur_exp[r.get("currency") or "USD"] += _money(r.get("amount", "0"))

    by_cur_park: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in parking:
        by_cur_park[r.get("currency") or "USD"] += _money(r.get("amount", "0"))

    by_cur_oop: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in oop:
        by_cur_oop[r.get("currency") or "USD"] += _money(r.get("amount", "0"))

    total_km = Decimal("0")
    for r in mileage:
        total_km += _money(r.get("kilometers", "0"))

    def table(title: str, rows: list[dict[str, str]]) -> str:
        if not rows:
            return f"<h2>{html.escape(title)}</h2><p>(no rows)</p>"
        keys = list(rows[0].keys())
        head = "".join(f"<th>{html.escape(k)}</th>" for k in keys)
        body = []
        for row in rows:
            body.append(
                "<tr>"
                + "".join(
                    f"<td>{html.escape(str(row.get(k, '')))}</td>" for k in keys
                )
                + "</tr>"
            )
        return (
            f"<h2>{html.escape(title)}</h2>"
            f"<table><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )

    cur_summary = []
    all_curs = sorted(set(by_cur_exp) | set(by_cur_park) | set(by_cur_oop))
    for c in all_curs:
        tot = by_cur_exp[c] + by_cur_park[c] + by_cur_oop[c]
        cur_summary.append(f"<li>{html.escape(c)}: total {tot} (expenses+park+oop)</li>")

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Case reports — CaseMan</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 1100px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
    th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left; }}
    th {{ background: #f0f4ff; }}
  </style>
</head>
<body>
  <h1>Case ledger report</h1>
  <p>Matter-relative path: <code>text/ledger/</code></p>
  <h2>Totals</h2>
  <p><strong>Total kilometers (mileage.csv):</strong> {html.escape(str(total_km))}</p>
  <ul>{"".join(cur_summary) or "<li>(no monetary rows)</li>"}</ul>
  {table("Expenses", expenses)}
  {table("Mileage", mileage)}
  {table("Medications", meds)}
  {table("Parking", parking)}
  {table("Out of pocket", oop)}
  {table("Case events", events)}
</body>
</html>
"""
    out = wd / "text" / "outputs" / "case_ledger_report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"ok reports_html {out}")
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "reports",
        help="Ledger CSVs (expenses, km, meds, parking, OOP, events) + HTML report",
    )
    rs = p.add_subparsers(dest="reports_cmd", required=True)
    ri = rs.add_parser("init", help=f"Create {LEDGER_DIR}/*.csv templates")
    ri.add_argument("project_id", nargs="?")
    ri.add_argument("--force", "-f", action="store_true", help="Overwrite CSV headers")
    ri.set_defaults(_run=_cmd_init)
    rh = rs.add_parser("html", help="Build text/outputs/case_ledger_report.html")
    rh.add_argument("project_id", nargs="?")
    rh.set_defaults(_run=_cmd_html)

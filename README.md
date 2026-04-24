# CaseMan

Portable multi-case evidence workspaces under `CASEMAN_ROOT` (default `~/CaseMan`). Each matter is a **working directory** with the layout required by the Master Evidence Engine protocol (§11.3), validated before intake (§11.14). Insulated from legacy `Case_Vault`.

## Install

```bash
cd ~/CaseMan
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Commands

- `caseman root` — print `CASEMAN_ROOT` (default `~/CaseMan`)
- `caseman init <project_id> [--name "Label"]` — create `matters/<id>/` with §11.3 tree
- `caseman list` — matters (`*` = active)
- `caseman active [project_id]` — show or set active matter
- `caseman status` — root, active, quick validation
- `caseman validate [project_id]` — §11.14; exit 1 with protocol lines if not ready
- `caseman env [project_id]` — print `export` lines for `CASEMAN_ROOT`, `CASEMAN_ACTIVE_MATTER`, `CASEMAN_WORKING_DIRECTORY` (active matter if omitted)

## Environment

- `CASEMAN_ROOT` — override the engine root (default: `~/CaseMan`)

## Layout per matter

`$CASEMAN_ROOT/matters/<project_id>/` contains: `Inbox_Genius`, `archive/duplicates`, `quarantine`, `text`, `logs`, `Master_Timeline.csv`, `Master_File.md`, `ui_evidence_layer.json`.

Registry: `$CASEMAN_ROOT/registry.json`.

## Cursor

Open the `~/CaseMan` folder as the project if you want `.cursor/rules/caseman.mdc` applied. Agents should run `caseman status` / `caseman validate` and use `CASEMAN_WORKING_DIRECTORY` for the active matter. Pin your **Master Evidence Engine** prompt in session or merge it into that rule as needed.

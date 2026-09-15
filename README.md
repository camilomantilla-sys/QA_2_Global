# Innovid QA2 Automation

QA2 checks that an Innovid implementation matches what was requested in the
Traffic Sheet (TS). It compares the TS against the Innovid
Placement-Creative View, Placement View, and delivered Tag files, and
reports every mismatch as a structured finding (PASS / FAIL / REVIEW /
NOT_VERIFIED).

## Documentation

| Document | For whom |
|---|---|
| [`docs/INSTALACION.md`](docs/INSTALACION.md) | Whoever is installing QA2 for the first time: download, first run, connecting Innovid, and what to do when something fails |
| [`docs/GUIA_TECNICA.md`](docs/GUIA_TECNICA.md) | Whoever maintains QA2: every rule, the key functions of each file, and the traps that cost a debugging session |
| [`docs/SEGURIDAD.md`](docs/SEGURIDAD.md) | IT / information-security review before rollout |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | The whole team: what changed in each release. Also shown inside the app, under **What's new** in the sidebar |
| [`docs/QA2_RULEBOOK.md`](docs/QA2_RULEBOOK.md) | The original rule definitions |

## Sharing configuration with the team (SharePoint)

The vendor/pixel tables and the team roster can live in one shared folder
instead of a copy per machine. A synced SharePoint library is a normal
folder on Windows, so this is all it takes:

```bat
setx QA2_CONFIG_DIR "%USERPROFILE%\WPP Media\QA2 - Documentos\config"
setx QA2_OUTPUT_DIR "%USERPROFILE%\WPP Media\QA2 - Documentos\evidencia"
```

Edit a table in the app on one machine and the next person to run QA2
picks it up. If the folder is empty, QA2 keeps working off the values it
ships with and starts using the shared one as soon as somebody saves —
there is no migration to coordinate.

**The Innovid sign-in is deliberately excluded from this.**
`config/innovid_credentials.env` and `config/innovid_session.json` always
resolve to the local project folder, whatever those variables say. A
shared drive is exactly where they must not go. See
[`docs/SEGURIDAD.md`](docs/SEGURIDAD.md) §4.

## Distributing QA2 to the team

```bash
python scripts/package_release.py
```

Builds `QA2-<version>.zip` next to the project and prints a SHA-256.
It leaves out the sign-in, every spreadsheet, the Git history and the
virtual environment, and refuses to finish if a credential file made it
in. Upload the zip to the team's SharePoint library and send the link;
whoever receives it unzips it and double-clicks `run_qa2.bat`.

Bump `VERSION` and add an entry to `docs/CHANGELOG.md` before packaging —
the app reads both, so the team sees what changed without opening a
repository.


## Running QA2 (no terminal needed)

1. Download or clone this repository to your computer.
2. Double-click the launcher for your OS:
   - **Windows:** `run_qa2.bat`
   - **Mac:** `run_qa2.command` (first time only: right-click it → Open, to
     bypass the "unidentified developer" warning)
3. The first run installs Python packages into a local `.venv` folder
   (a few minutes, one-time). Every run after that starts in seconds.
4. Your browser opens automatically at `http://localhost:8501` with the
   QA2 app. Closing the terminal window that opened stops the app.

Requirements: [Python 3.10+](https://www.python.org/downloads/) installed
and on your PATH. Everything else (Streamlit, pandas, openpyxl, etc.) is
installed automatically by the launcher into `.venv`, so it never touches
your system Python. No internet connection is needed after the first
install — QA2 runs entirely on your machine.

### Windows, no visible console window (experimental)

`run_qa2.bat` deliberately keeps its console window open (so it's obvious
QA2 is still running, and closing it is how you stop QA2). If you'd
rather it not show a window at all:

1. Double-click **`Launch QA2 (Silent).vbs`**. On a first-time setup
   you'll get a one-time popup saying it may take a minute; after that,
   your browser opens automatically with no window ever appearing.
2. When you're done, double-click **`Stop QA2.vbs`** — since there's no
   window to close, this is how you shut QA2 down (it stops whatever's
   listening on port 8501).

This is a first test of that flow, not yet the final packaging — if
anything about it misbehaves, `run_qa2.bat` is still there as the
known-working fallback.

### Manual run (if you prefer a terminal)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run ui/app_v2.py
```

## Using QA2

In the sidebar, upload:

1. **Traffic Sheet** (required) — source of scope, placements, and requested changes.
2. **Innovid Placement-Creative View** (required) — export with Creative_ID, association, status, Decision Tree, Clicktag, Third Party ID.
3. **Innovid Placement View** (optional, recommended) — needed for 1x1s, pixels, and placement-level URL validation.
4. **Tag files** (optional, multiple) — delivered ad tags to validate against the TS and Innovid.

Pick a Traffic Sheet profile (or leave it on auto-detect) and click
**Run QA2**. Results are organized into tabs: Worked Placements, Findings,
Rules Executed, Files & Extraction, and Tag Coverage. Findings can be
exported as CSV from the Findings tab.

Supported Traffic Sheet formats: Adobe Variant A (Decision Tree), Adobe
Variant B (Direct & Site-Served), WPP Standard.

## Project layout

```
ui/            Streamlit app (the interface you interact with)
parsers/       Read and interpret uploaded Excel files (TS, exports, tags)
core/          Matching engine, URL/date/color normalization, findings model
rules/         Individual QA rules, grouped by domain (tags, urls, naming, ...)
cli/           Command-line tools for diagnosing a single file without the UI
scripts/       One-off diagnostic and regression scripts
docs/          GUIA_TECNICA.md, SEGURIDAD.md, CHANGELOG.md, QA2_RULEBOOK.md
archive/       Deprecated code kept for reference only
```

### Extending QA2

- **New or changed rule:** add/edit a function in `rules/<domain>.py`, wire
  it into `run_rules()` in `core/engine.py` if it is a new family, and note
  it in `docs/CHANGELOG.md`. The step-by-step is in
  [`docs/GUIA_TECNICA.md`](docs/GUIA_TECNICA.md) §5. Rules are plain Python functions
  that read from the matched data and append findings — no framework code
  to learn.
- **New column, tag format, or Traffic Sheet layout:** parsing lives in
  `parsers/` (`ts_parser.py`, `innovid_export.py`, `innovid_tags.py`) and
  is schema-driven via `core/schema.py` / `core/ts_schema.py` — most
  format variations can be added there without touching the UI.
- **UI changes:** everything visible lives in `ui/app_v2.py`.

Traffic Sheets, Innovid exports, and tag files are never committed to this
repository (see `.gitignore`) — they may contain confidential campaign
data. Keep local copies for testing outside of git, e.g. in a `data/`
folder (already git-ignored).

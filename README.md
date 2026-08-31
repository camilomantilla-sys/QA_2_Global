# Innovid QA2 Automation

QA2 checks that an Innovid implementation matches what was requested in the
Traffic Sheet (TS). It compares the TS against the Innovid
Placement-Creative View, Placement View, and delivered Tag files, and
reports every mismatch as a structured finding (PASS / FAIL / REVIEW /
NOT_VERIFIED).

Full rule definitions live in [`docs/QA2_RULEBOOK.md`](docs/QA2_RULEBOOK.md).

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
docs/          QA2_RULEBOOK.md — the source of truth for every rule
archive/       Deprecated code kept for reference only
```

### Extending QA2

- **New or changed rule:** add/edit a function in `rules/<domain>.py` and
  document it in `docs/QA2_RULEBOOK.md`. Rules are plain Python functions
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

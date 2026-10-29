# Innovid QA2 Automation

QA2 checks that an Innovid implementation matches what was requested in the
Traffic Sheet (TS). It compares the TS against the Innovid
Placement-Creative View, Placement View, and delivered Tag files, and
reports every mismatch as a structured finding (PASS / FAIL / REVIEW /
NOT_VERIFIED).

| | |
|---|---|
| **What it replaces** | The manual second QA of an Innovid implementation |
| **Measured result** | 55 s for a 156-placement request, against about 5 minutes per decision set by hand |
| **Where it runs** | Locally, on the analyst's machine (`localhost` only). No server, no database, no telemetry |
| **What it reads** | Files the analyst already downloads, plus (optionally) Innovid itself, with the analyst's own sign-in |
| **What it writes** | A branded Excel and PDF report, with evidence and sign-offs |
| **Stack** | Python 3.11, Streamlit, pandas, openpyxl, Playwright, ReportLab, pytest |

## How a run works

```
Traffic Sheet (.xlsx)      Innovid exports         Tag files
        |                        |                     |
 parsers/ts_parser.py   parsers/innovid_export.py  parsers/innovid_tags.py
        |                        |                     |
        +-----------+------------+                     |
                    v                                  |
          core/matching.py   match()  -> MatchResult   |
                    |                                  |
                    |   core/innovid_api.py (optional) |
                    |   reads what no export carries   |
                    v                                  v
          core/engine.py   run_rules()  <--------------+
                    |
          core/findings.py   FindingsBuffer
                    |
          core/verdict.py    Implementation vs Tags & pixels
                    |
     ui/app_v2.py   core/excel_report.py   core/pdf_report.py
```

1. **Read.** `parsers/` turns each uploaded file into plain Python
   objects. In the Traffic Sheet the *fill colour* of a cell is the
   request: green means add, red means remove, grey/yellow is out of
   scope, white is context (`core/colors.py`, `core/intent.py`).
2. **Match.** `core/matching.py` pairs every placement and creative the
   TS asks for with what Innovid actually has.
3. **Reconcile.** The `core/*_reconciliation.py` modules handle the
   specialised cross-checks: vendor pixels, Adobe tag policy,
   DoubleVerify, default ads, and the fields that only exist in
   Innovid's interface.
4. **Evaluate.** `run_rules()` in `core/engine.py` calls every rule in
   `rules/`, in order. **It is the first function to read**: it is the
   complete list of what QA2 checks.
5. **Report.** Each rule emits findings through `FindingsBuffer`
   (`core/findings.py`). Two verdicts are computed, Implementation and
   Tags & pixels, and the overall verdict is the worse of the two
   (`core/verdict.py`).

### Design principles

- **Deterministic.** Rules are plain Python comparisons. The same input
  always gives the same result, and every result can be traced to the
  line of code that produced it. There is no AI at runtime.
- **What could not be checked never passes.** If a source was missing
  (for example, Innovid was not connected), the finding is
  `NOT_VERIFIED`, never `PASS`.
- **A failed read cannot end green.** If the Traffic Sheet could not be
  read, the run is blocked (`EXT-000`) instead of passing on zero checks.
- **Every value keeps its origin.** `core/provenance.py` records the
  sheet, row and column each value came from, so the report can show
  the evidence.

### Key files

| File | What it does |
|---|---|
| `core/engine.py` | `run_rules()`: the ordered list of every check |
| `core/matching.py` | Pairs the TS with Innovid, placement by placement |
| `core/findings.py` | The findings model and `FindingsBuffer` |
| `core/verdict.py` | The two verdicts and the overall one |
| `parsers/ts_parser.py` | Reads the Traffic Sheet, colours included |
| `parsers/innovid_export.py` | Reads the Innovid exports |
| `core/innovid_api.py` | The optional Innovid connection (Playwright) |
| `core/paths.py` | Where QA2 reads and writes; keeps credentials local |
| `core/excel_report.py`, `core/pdf_report.py` | The deliverables |
| `ui/app_v2.py` | The whole interface |
| `rules/*.py` | One family of rules per file (catalogue in `docs/GUIA_TECNICA.md` section 4) |

Every module opens with a docstring that explains what it does and why.
The full index of functions is in [`docs/MAPA_DEL_CODIGO.md`](docs/MAPA_DEL_CODIGO.md),
and `.github/copilot-instructions.md` gives code assistants the project's
ground rules.

## Security at a glance

The full review is in [`docs/SEGURIDAD.md`](docs/SEGURIDAD.md). In short:

- **Local only.** The app listens on `localhost:8501` and nowhere else
  (`.streamlit/config.toml`), with XSRF protection on and usage
  statistics off.
- **No data leaves the machine** except the read-only requests to
  Innovid/Flashtalking described below. No telemetry, no third-party
  calls, no AI services. A test lists every host the code can reach
  and fails if a new one appears.
- **Innovid access uses the analyst's own sign-in.** The analyst signs
  in by hand once, in a normal browser window that Playwright opens.
  QA2 never sees the password on that path. It then reuses that
  session to *read* the campaign (`GET`, plus one `POST` that only
  queries), with the analyst's own permissions. It never changes
  anything in Innovid.
- **Secrets stay on the machine.** `config/innovid_session.json` and
  `config/innovid_credentials.env` are git-ignored, can never be
  redirected to a shared folder (`core/paths.py`), and the packaging
  scripts leave them out and refuse to finish if one slips in.
- **Diagnostic logs are redacted.** Sign-in URLs are dropped and
  request bodies are reduced to field names (`redact_url`,
  `redact_body` in `core/innovid_api.py`).
- **Client data is never committed.** Traffic Sheets, exports and tag
  files are git-ignored.

## Documentation

| Document | For whom |
|---|---|
| [`docs/COMANDOS.md`](docs/COMANDOS.md) | The copy-paste reference: which package to build for a given change, and how to publish a release |
| [`docs/INSTALACION.md`](docs/INSTALACION.md) | Whoever is installing QA2 for the first time: download, first run, connecting Innovid, and what to do when something fails |
| [`docs/LEEME_PRIMERO.md`](docs/LEEME_PRIMERO.md) | Anyone opening the project for the first time: reading order, where everything is, and preparation for security questions |
| [`docs/copilot/`](docs/copilot/GUIA_AGENTE_COPILOT.md) | Setting up the Copilot agent: the instruction block, the knowledge files (`scripts/export_copilot_context.py`) and how to paste its changes safely |
| [`docs/REFERENCIA_TECNICA.md`](docs/REFERENCIA_TECNICA.md) | Developers and code assistants: how every part works, key functions with code, the JSON tables, the Innovid connection and Playwright, tests, recipes and a technical FAQ |
| [`docs/MAPA_DEL_CODIGO.md`](docs/MAPA_DEL_CODIGO.md) | Where everything is: every module, class and function with its signature, and every test file. Generated from the code by `scripts/generate_code_map.py` |
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

**The team installs nothing** — no Python, no admin rights, nothing
from IT. The package carries its own interpreter, so they extract the
zip and double-click `run_qa2.bat`.

Build it once per release, on a Windows machine:

```bash
python scripts/build_bundle.py
```

It downloads a portable Python (python-build-standalone, the same one
`uv` uses), installs the libraries into it, adds Playwright's Chromium,
copies the project and zips the lot — about 500 MB, and a few minutes.
It refuses to finish if a credential file made it in.

The first build writes `requirements-lock-<platform>.txt`. **Commit
it**: `requirements.txt` says `pandas>=2.2.0`, which is right for
development and wrong for a release — without the lock, rebuilding in
two months ships versions nobody tested.

For a code-only zip (no interpreter, for someone who already has
Python) there is still:

```bash
python scripts/package_release.py
```

Full instructions, including what to do when a corporate proxy blocks
the Chromium download, are in
[`docs/INSTALACION.md`](docs/INSTALACION.md).

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
config/        Editable tables (vendors, Adobe pixels, team roster). No secrets in Git
tests/         Automated tests: run `python -m pytest tests/` before any release
docs/          LEEME_PRIMERO.md (start here), REFERENCIA_TECNICA.md, SEGURIDAD.md, MAPA_DEL_CODIGO.md, copilot/, ...
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

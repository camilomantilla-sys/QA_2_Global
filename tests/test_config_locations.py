"""
Where QA2 keeps things, pinned.

Two claims are made to whoever reviews this tool before it is rolled
out, and both are the kind of claim that quietly stops being true a
few commits later unless something checks it:

  * the shared tables can live in a SharePoint-synced folder, so the
    team edits one copy;
  * the sign-in cannot, however the environment is set.

These tests are that check. The security note in docs/SEGURIDAD.md
points at this file.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core import paths
from core.paths import (
    LOCAL_ONLY_FILES,
    SHARED_CONFIG_FILES,
    config_dir,
    local_config_dir,
    output_dir,
    project_root,
    shared_config_path,
)

ROOT = project_root()


@pytest.fixture
def shared(tmp_path, monkeypatch):
    target = tmp_path / "SharePoint" / "QA2 Config"
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(target))
    return target


# ── the shared tables follow QA2_CONFIG_DIR ──────────────────────────

def test_without_the_variable_everything_is_local(monkeypatch):
    monkeypatch.delenv(paths.CONFIG_DIR_ENV, raising=False)
    assert config_dir() == local_config_dir()
    for name in SHARED_CONFIG_FILES:
        assert shared_config_path(name).parent == local_config_dir()


def test_a_shared_table_is_written_to_the_shared_folder(shared):
    for name in SHARED_CONFIG_FILES:
        assert shared_config_path(name, for_write=True) == shared / name


def test_an_empty_shared_folder_still_reads_the_shipped_defaults(shared):
    """Rollout has to work before anyone has saved anything."""
    assert not shared.exists()
    for name in SHARED_CONFIG_FILES:
        assert shared_config_path(name).parent == local_config_dir()


def test_once_saved_the_shared_copy_wins(shared):
    shared.mkdir(parents=True)
    (shared / "team_roster.json").write_text("{}", encoding="utf-8")
    assert shared_config_path("team_roster.json") == shared / "team_roster.json"


# ── the sign-in does not ─────────────────────────────────────────────

def test_the_sign_in_is_never_redirected(shared):
    for name in LOCAL_ONLY_FILES:
        assert shared_config_path(name) == local_config_dir() / name
        assert shared_config_path(name, for_write=True) == local_config_dir() / name


def test_innovid_credentials_and_session_resolve_locally(shared):
    from core import innovid_api

    assert innovid_api.CREDENTIALS_PATH.parent == local_config_dir()
    assert innovid_api.SESSION_PATH.parent == local_config_dir()


def test_the_sign_in_files_are_gitignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for name in LOCAL_ONLY_FILES:
        assert name in ignored, f"{name} must stay out of git"


def test_the_sign_in_files_are_not_tracked():
    tracked = subprocess.run(
        [_git(), "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    for name in LOCAL_ONLY_FILES:
        assert name not in tracked


# ── the tables really do round-trip through the shared folder ────────

def test_saving_the_roster_lands_in_the_shared_folder(shared):
    from core import team_roster

    roster = team_roster.load_roster()
    roster["Support"] = ["Shared Copy"]
    team_roster.save_roster(roster)

    assert (shared / "team_roster.json").exists()
    assert team_roster.load_roster()["Support"] == ["Shared Copy"]
    # and the copy that ships with the project is untouched
    local = json.loads(
        (local_config_dir() / "team_roster.json").read_text(encoding="utf-8")
    )
    assert local.get("Support") != ["Shared Copy"]


def test_saving_the_vendor_table_lands_in_the_shared_folder(shared):
    from core import pixel_reconciliation as px

    rows = px.load_vendor_rows()
    px.save_vendor_rows(rows)
    assert (shared / "vendor_pixels.json").exists()


# ── the run log follows QA2_OUTPUT_DIR ───────────────────────────────

def test_the_log_folder_can_be_moved(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.OUTPUT_DIR_ENV, str(tmp_path / "evidence"))
    assert output_dir() == tmp_path / "evidence"


def test_without_the_variable_the_log_stays_in_the_project(monkeypatch):
    monkeypatch.delenv(paths.OUTPUT_DIR_ENV, raising=False)
    assert output_dir() == project_root() / "logs"


def test_a_blank_variable_is_not_a_path(monkeypatch):
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, "   ")
    assert config_dir() == local_config_dir()


# ── the app is not exposed to the network ────────────────────────────

def test_streamlit_binds_to_localhost_only():
    cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'address = "localhost"' in cfg


def test_streamlit_telemetry_is_off():
    cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in cfg


def test_xsrf_protection_is_on():
    cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "enableXsrfProtection = true" in cfg


# ── nothing in the shipped code points anywhere unexpected ───────────

def test_the_only_outbound_hosts_are_the_ad_servers():
    """
    QA2 talks to Innovid/Flashtalking and to nothing else. A new host in
    the shipped code is a decision someone has to make on purpose, not
    something that arrives with a copy-paste.
    """
    import re

    allowed = {
        "api.flashtalking.net",
        "campaign-manager.flashtalking.net",
        "servedby.flashtalking.com",
        "uam-login.mediaocean.com",
        "127.0.0.1",
        "localhost",
        "schemas.openxmlformats.org",  # the Excel XML namespace, not a call
    }
    found: set[str] = set()
    for folder in ("core", "rules", "parsers", "ui", "cli"):
        for py in (ROOT / folder).rglob("*.py"):
            text = py.read_text(encoding="utf-8", errors="replace")
            # Skip the examples inside docstrings and comments: what
            # matters is hosts the code can actually reach.
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for host in re.findall(r"https?://([A-Za-z0-9._-]+)", line):
                    found.add(host)

    unexpected = {
        h
        for h in found - allowed
        # sample landing pages and ad URLs quoted in docstrings
        if not h.endswith(".example") and "example" not in h
    }
    # Hosts that only ever appear as data being *parsed* (landing pages
    # from real Traffic Sheets quoted in docstrings) are not calls.
    documented = {
        "www.martinsfoods.com",
        "www.adobe.com",
        "m-wendys.com",
        "www.efront.com",
        # Los dos pixeles oficiales de Adobe, DISQO e iSpot. Viajan
        # como VALOR DE REFERENCIA en la tabla editable: QA2 compara
        # contra ellos el pixel que encuentra en los tags o en
        # Innovid, y nunca los pide.
        "track.activemetering.com",
        "pi.ispot.tv",
        "ad-score.com",
        "x.com",
        "api.",
    }
    assert not (unexpected - documented), f"new outbound host(s): {unexpected - documented}"


def test_the_shipped_code_names_no_ai_assistant():
    """
    The tool is QA2's, not a vendor's. Nothing in what ships carries an
    assistant's name, an account or a session link -- the question
    Camilo asked before the launch, kept answered.
    """
    import re

    banned = re.compile(r"claude|anthropic|chatgpt|openai|copilot", re.I)
    offenders = []
    for folder in ("core", "rules", "parsers", "ui", "cli", "scripts", "config"):
        base = ROOT / folder
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.suffix not in {".py", ".json", ".toml", ".md", ".txt"}:
                continue
            if banned.search(f.read_text(encoding="utf-8", errors="replace")):
                offenders.append(str(f.relative_to(ROOT)))
    assert not offenders, f"assistant name in shipped files: {offenders}"


def _git() -> str:
    return "git" if sys.platform != "win32" else "git.exe"


# ── the release notes reach the people who run QA2 ───────────────────

def test_the_version_is_readable():
    from core.release import qa2_version

    assert qa2_version() != "dev", "VERSION should say which release this is"


def test_the_notes_are_the_newest_entry_only():
    from core.release import release_notes

    notes = release_notes()
    assert notes.startswith("## "), notes[:40]
    assert notes.count("\n## ") == 0, "only one version's entry"


def test_the_template_at_the_bottom_is_never_shown():
    from core.release import release_notes

    assert "Plantilla para la próxima" not in release_notes()


def test_a_missing_changelog_is_not_a_crash(monkeypatch, tmp_path):
    from core import release

    monkeypatch.setattr(release, "project_root", lambda: tmp_path)
    assert release.release_notes() == ""
    assert release.qa2_version() == "dev"


def test_the_app_shows_the_notes():
    """The place the team finds out what changed is the app itself."""
    app = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")
    assert "release_notes()" in app
    assert "What's new in QA2" in app


# ── the zip that goes to the team carries no credentials ─────────────

def test_the_packager_refuses_to_ship_the_sign_in(tmp_path, monkeypatch):
    from scripts import package_release

    # A sign-in exists on a machine that has been used for real.
    monkeypatch.setattr(package_release, "ROOT", ROOT)
    target = tmp_path / "QA2-test.zip"
    package_release.build(target)

    import zipfile

    with zipfile.ZipFile(target) as zf:
        entries = zf.namelist()
    names = [Path(n).name for n in entries]

    for banned in LOCAL_ONLY_FILES:
        assert banned not in names
    assert not [n for n in names if n.endswith((".xlsx", ".xlsm", ".xls"))]
    # .gitignore belongs in the download; the .git folder does not.
    parts = {part for n in entries for part in Path(n).parts}
    assert not parts & {".git", ".venv", "__pycache__", "logs", "data"}


def test_the_packager_ships_what_the_team_needs(tmp_path):
    from scripts import package_release

    target = tmp_path / "QA2-test.zip"
    package_release.build(target)

    import zipfile

    with zipfile.ZipFile(target) as zf:
        names = {n.split("/", 1)[1] for n in zf.namelist() if "/" in n}

    for needed in (
        "requirements.txt",
        "run_qa2.bat",
        "ui/app_v2.py",
        "core/engine.py",
        "docs/CHANGELOG.md",
        "docs/SEGURIDAD.md",
        "docs/GUIA_TECNICA.md",
        "VERSION",
    ):
        assert needed in names, f"{needed} must be in the download"

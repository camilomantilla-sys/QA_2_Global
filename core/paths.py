"""
Where QA2 reads and writes its own files.

Two kinds of file live under config/, and they are not the same kind of
thing:

  Shared, editable tables -- vendor_pixels.json, vendor_pixels_adobe.json,
  team_roster.json. These are the team's rules of the game. Everyone
  running QA2 should see the same ones, so they are the files that
  belong in a shared location: a SharePoint / OneDrive library synced to
  the machine is a normal folder, so pointing QA2_CONFIG_DIR at it is
  enough. Edit the table in the app on one machine and the next person to
  run QA2 picks it up.

  The sign-in -- innovid_credentials.env and innovid_session.json. The
  first holds the Innovid password; the second holds session cookies,
  which are as good as the password until they expire. Those two are
  deliberately NOT redirectable: they resolve to the local project
  folder and nowhere else, whatever the environment says. A shared drive
  is precisely where they must not go.

  QA2_OUTPUT_DIR moves the run log (and anything else QA2 writes for the
  record) somewhere else -- also fine to point at SharePoint, since it
  holds QA evidence rather than credentials.

Every lookup reads the environment at call time, not at import, so a
machine can be repointed by changing the variable and restarting QA2.
"""
from __future__ import annotations

import os
from pathlib import Path

CONFIG_DIR_ENV = "QA2_CONFIG_DIR"
OUTPUT_DIR_ENV = "QA2_OUTPUT_DIR"

#: Shared tables: safe to keep in a synced SharePoint folder.
SHARED_CONFIG_FILES = (
    "vendor_pixels.json",
    "vendor_pixels_adobe.json",
    "team_roster.json",
)

#: Never leaves the machine running QA2, whatever QA2_CONFIG_DIR says.
LOCAL_ONLY_FILES = (
    "innovid_credentials.env",
    "innovid_session.json",
)


def project_root() -> Path:
    """The QA2 folder itself -- the parent of core/."""
    return Path(__file__).resolve().parents[1]


def local_config_dir() -> Path:
    """<project>/config. The shipped defaults and the sign-in live here."""
    return project_root() / "config"


def _env_dir(name: str) -> Path | None:
    raw = str(os.environ.get(name, "")).strip().strip('"')
    if not raw:
        return None
    try:
        return Path(raw).expanduser()
    except (OSError, ValueError):
        return None


def config_dir() -> Path:
    """
    Where shared tables are written: QA2_CONFIG_DIR if it is set,
    otherwise the local config folder.
    """
    return _env_dir(CONFIG_DIR_ENV) or local_config_dir()


def shared_config_path(name: str, *, for_write: bool = False) -> Path:
    """
    The file to use for one of the shared tables.

    Writing always goes to config_dir(), so an edit made in the app
    lands in the shared folder once one is configured. Reading prefers
    the shared copy but falls back to the local one, which is what makes
    the rollout painless: point QA2_CONFIG_DIR at an empty SharePoint
    folder and QA2 keeps working off the shipped defaults until someone
    saves a table for the first time.

    A name that is not a shared table (the sign-in, say) is answered
    locally and is never redirected.
    """
    if name in LOCAL_ONLY_FILES or name not in SHARED_CONFIG_FILES:
        return local_config_dir() / name

    shared = config_dir() / name
    if for_write:
        return shared
    if shared.exists():
        return shared
    return local_config_dir() / name


def output_dir() -> Path:
    """Where the run log goes: QA2_OUTPUT_DIR, else <project>/logs."""
    return _env_dir(OUTPUT_DIR_ENV) or (project_root() / "logs")

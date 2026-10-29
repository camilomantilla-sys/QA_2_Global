"""The Copilot knowledge export carries all the code and never a secret."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "export_copilot_context", ROOT / "scripts" / "export_copilot_context.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_python_file_goes_to_the_agent():
    export = _load()
    exported = {f for files in export.build().values() for f in files}
    missing = [p for p in export.candidates() if p.endswith(".py") and p not in exported]
    assert missing == []


def test_the_sign_in_files_and_spreadsheets_never_go_to_the_agent():
    export = _load()
    exported = [f for files in export.build().values() for f in files]
    for rel in exported:
        name = Path(rel).name
        assert name not in ("innovid_session.json", "innovid_credentials.env", "secrets.toml")
        assert Path(rel).suffix.lower() not in (".xlsx", ".xlsm", ".xls", ".csv", ".har", ".env")


def test_the_export_refuses_if_a_secret_slips_in():
    export = _load()
    with pytest.raises(SystemExit):
        export.guard({"x.md": ["config/innovid_session.json"]})

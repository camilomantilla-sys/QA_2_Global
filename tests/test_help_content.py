"""
La ayuda dentro de la app (FB-05, FB-19) dice lo mismo que la pantalla.

Run with pytest, or directly:
    python tests/test_help_content.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from core.verdict import VERDICT_LABELS  # noqa: E402
from ui.help_content import DOWNLOAD_PURPOSE, STATUS_HELP, help_markdown  # noqa: E402

APP = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")


def test_every_verdict_is_explained():
    text = help_markdown()
    for label in VERDICT_LABELS.values():
        assert f"**{label}**" in text, label


def test_every_status_on_screen_is_explained():
    start = APP.index("STATUS_LABEL = {")
    block = APP[start:APP.index("}", start)]
    for label in STATUS_HELP:
        assert f'"{label}"' in block, f"{label} is not a status the app shows"
    assert block.count(":") == len(STATUS_HELP)


def test_every_download_says_what_it_is_for():
    for key in ("pdf", "excel", "bundle"):
        assert f'DOWNLOAD_PURPOSE["{key}"]' in APP, key
    assert all(DOWNLOAD_PURPOSE.values())


def test_the_help_is_in_the_app():
    assert "st.markdown(help_markdown())" in APP


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

"""
Las capturas pegadas (FB-04) entran como cualquier archivo subido, y
viajan en el session bundle.

Run with pytest, or directly:
    python tests/test_paste_image.py
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from ui.paste_image import decode  # noqa: E402

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
APP = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")
PAGE = (ROOT / "ui" / "components" / "paste_image" / "index.html").read_text(encoding="utf-8")


def test_a_pasted_image_looks_like_an_upload():
    [image] = decode([{"name": "pasted_screenshot_1.png", "type": "image/png", "data": PNG}])
    assert image.name == "pasted_screenshot_1.png"
    assert image.getvalue().startswith(b"\x89PNG")
    assert image.size == len(image.getvalue())


def test_anything_else_is_ignored():
    assert decode([{"name": "a.svg", "type": "image/svg+xml", "data": PNG}]) == []
    assert decode([{"name": "a.png", "type": "image/png", "data": "not base64!"}]) == []
    assert decode(None) == []
    [image] = decode([{"name": "../../evil.png", "type": "image/png", "data": PNG}])
    assert image.name == "evil.png"


def test_evidence_travels_in_the_bundle():
    assert 'f"files/evidence/{_stored_as}"' in APP
    assert '_restored["evidence"] = _restored_evidence' in APP


def test_the_paste_zone_loads_nothing_from_outside():
    assert "http://" not in PAGE and "https://" not in PAGE


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

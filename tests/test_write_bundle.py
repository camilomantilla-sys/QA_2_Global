"""
Guardar un session bundle y volver a abrirlo da los mismos archivos.

Las dos interfaces guardan con core.session_bundle.write_bundle, y
read_bundle es quien lo abre: si algun dia se separan, QA2 guardaria
bundles que no puede leer.

Run with pytest, or directly:
    python tests/test_write_bundle.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.session_bundle import read_bundle, write_bundle  # noqa: E402


def test_what_is_saved_comes_back():
    data = write_bundle(
        {
            "ts": [("DEMO_TS.xlsx", b"ts")],
            "pc": [("DEMO_PC.xlsm", b"pc")],
            "pl": [],
            "tags": [("tags.xlsx", b"t1"), ("tags.xlsx", b"t2")],
            "evidence": [("../shot.png", b"\x89PNG")],
        },
        {"account": "Unilever", "wrike_id": "123"},
    )
    bundle = read_bundle(data)
    assert bundle.one("ts") == ("DEMO_TS.xlsx", b"ts")
    assert bundle.one("pc") == ("DEMO_PC.xlsm", b"pc")
    assert bundle.one("pl") is None
    # Dos archivos con el mismo nombre no se pisan.
    assert [c for _, c in bundle.files["tags"]] == [b"t1", b"t2"]
    assert bundle.files["evidence"] == [("shot.png", b"\x89PNG")]
    assert bundle.manifest["account"] == "Unilever"
    assert bundle.manifest["saved_at"]


def test_streamlit_saves_with_the_shared_writer():
    app = (Path(__file__).resolve().parents[1] / "ui" / "app_v2.py").read_text(encoding="utf-8")
    assert "write_bundle(" in app


if __name__ == "__main__":
    test_what_is_saved_comes_back()
    test_streamlit_saves_with_the_shared_writer()
    print("ok")

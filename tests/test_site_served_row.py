"""
El 1x1 de un site-served no tenia fila, y el nombre de Innovid no era
el mismo en la app que en el Excel.

Dos cosas que se veian como "la app muestra mal los creativos":

1. En Adobe la TS escribe "N/A" en Creative Names --el creativo lo
   sirve el publisher-- asi que no hay creativo esperado y la seccion
   "2. Creatives & Assignment" salia vacia. Pero Innovid SI tiene algo
   asignado, el pixel de la cuenta, y es lo unico que hay que mirar
   ahi. Camilo: "me trae espacios en blanco, me gustaria que trajera
   asi fuera el N/A de la TS... y asi identifico que es 1x1.gif".

2. El export trae DOS nombres por creativo y en Unilever son
   distintos: Creative_Name es el limpio
   (OLD-LOTION-GOOD-RUN_LOTION_20OZ-PUMP_...) y Filename arrastra el
   sello de subida (VAS_Cherry_Lotion_PopCultureEnthusiasts1_...).
   El Excel enseñaba el primero y la app el segundo, asi que la app
   parecia estar mostrando un creativo que no era.

Run with pytest, or directly:
    python tests/test_site_served_row.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

APP = (
    Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"
).read_text(encoding="utf-8")
EXCEL = (
    Path(__file__).resolve().parents[1] / "core" / "qa_export.py"
).read_text(encoding="utf-8")


def _innovid_name_order(source: str) -> str:
    """Cual de los dos nombres se pide primero."""
    match = re.search(
        r"(?:creative_actual|actual_creative)\.(name|filename)\s+or\s+"
        r"(?:creative_actual|actual_creative)\.(name|filename)",
        source,
    )
    assert match, "no se encontro de donde sale el nombre de Innovid"
    return match.group(1)


def test_the_app_and_the_excel_ask_for_the_same_name():
    assert _innovid_name_order(APP) == _innovid_name_order(EXCEL)


def test_and_that_name_is_the_clean_one():
    """
    Creative_Name es el nombre limpio; Filename trae el sello que
    Innovid le pega al subirlo.
    """
    assert _innovid_name_order(APP) == "name"


# ── la fila del 1x1 ──────────────────────────────────────────────────

def test_a_site_served_placement_shows_its_tracker():
    assert "actual_trackers" in APP
    assert '"N/A (site-served)"' in APP


def test_the_tracker_row_only_appears_when_there_is_nothing_else():
    """
    Es el relleno de un hueco, no una fila mas: si la TS declaro
    creativos, manda lo que se pidio.
    """
    assert "if not creative_rows and _trackers:" in APP


def test_the_empty_message_is_still_there_for_a_real_empty():
    # Un placement sin creativos y sin pixel sigue diciendolo.
    assert "No individual creatives are" in APP


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

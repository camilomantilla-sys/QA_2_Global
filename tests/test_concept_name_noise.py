"""
Setenta revisiones que firmar, y un Excel que las desmentia.

El caso real (Unilever, UNE_VIC_072_VASELINE, 35 placements):

  * la TS pide  CHERRY-HYDRATION_LOTION_20OZ-PUMP_..._160X600_...
    con Creative ID 6398957
  * el export Placement-Creative lo trae con ESE mismo nombre
  * dentro del decision set, el nodo 6398957 se llama
    VAS_Cherry_Lotion_LapsedBuyers1_Static_Display_160x600_082726.jpg

Son dos etiquetas de Innovid para el mismo id: el archivo en el export,
el concepto dentro del decision set. INV-004 comparaba solo contra la
del decision set, asi que salto en los 70 creativos de la solicitud --
70 revisiones que firmar a mano-- mientras el Excel, que compara contra
el export, enseñaba las dos columnas de nombre iguales y en verde.

Camilo: "me lo flaggea en 2. Creative & Assignments, pero en el excel
descargado me lo compara con el placement creative export y ahi si hace
match... pierdo tiempo validando manualmente que todo esta bien".

Si el nombre de la TS concuerda con ALGUNA de las dos etiquetas, hay
dos hechos independientes diciendo que es el creativo correcto: el id y
ese nombre. No hay nada que decidir.

Lo que si queda: el id lo escribe una persona. Un id mal tecleado
emparejaria con el creativo equivocado, y el unico aviso seria que
NINGUNO de los dos nombres concuerda.

Run with pytest, or directly:
    python tests/test_concept_name_noise.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN  # noqa: E402
from core.findings import FindingsBuffer  # noqa: E402
from core.innovid_reconciliation import (  # noqa: E402
    CreativeFlightCheck,
    InnovidReconciliation,
)
from core.qa_export import _dset_name  # noqa: E402
from rules import innovid as innovid_rules  # noqa: E402

TS = "CHERRY-HYDRATION_LOTION_20OZ-PUMP_CHERRY-AURA_160X600_149654400"
CONCEPTO = "VAS_Cherry_Lotion_LapsedBuyers1_Static_Display_160x600_082726.jpg"


def _check(*, dset: str, export: str, matched_by="creative_id"):
    return CreativeFlightCheck(
        placement_id="11142248",
        creative_name=TS,
        intent=GREEN,
        matched_by=matched_by,
        actual_name=dset,
        export_name=export,
    )


def _inv004(check) -> list:
    out = InnovidReconciliation()
    out.flights = [check]
    buffer = FindingsBuffer()
    innovid_rules.evaluate(out, buffer)
    return [f for f in buffer.findings if f.rule_id == "INV-004"]


# ── lo que dejo de sonar ─────────────────────────────────────────────

def test_the_concept_name_alone_is_not_a_rename():
    """El caso de Unilever, tal cual: 70 de estos en una solicitud."""
    assert _inv004(_check(dset=CONCEPTO, export=TS)) == []


def test_it_is_quiet_however_the_node_was_found():
    # Por el id de la TS o por el del export: da igual, el que
    # corrobora es el nombre del export.
    assert _inv004(
        _check(dset=CONCEPTO, export=TS, matched_by="export_creative_id")
    ) == []


def test_the_same_name_on_both_sides_says_nothing_either():
    assert _inv004(_check(dset=TS, export=TS)) == []


# ── y lo que sigue sonando ───────────────────────────────────────────

def test_a_name_that_matches_neither_is_still_reviewed():
    """
    El id lo teclea una persona. Si ninguno de los dos nombres de
    Innovid concuerda, puede ser el creativo equivocado -- y ese aviso
    es el unico que hay.
    """
    found = _inv004(_check(dset=CONCEPTO, export="otra_cosa_entera.jpg"))
    assert len(found) == 1, found
    assert "under another name" in found[0].message


def test_an_empty_export_name_does_not_excuse_anything():
    # Sin nombre del export no hay corroboracion: se revisa.
    assert len(_inv004(_check(dset=CONCEPTO, export=""))) == 1


# ── el dato que obligaba a abrir Innovid ─────────────────────────────

def test_the_decision_set_name_travels_to_the_report():
    assert _dset_name(_check(dset=CONCEPTO, export=TS), TS) == CONCEPTO


def test_it_stays_blank_when_the_decision_set_agrees():
    """
    Una columna que casi siempre repite a la de al lado es ruido en
    una hoja de treinta. Una celda escrita quiere decir "aqui Innovid
    lo etiqueta asi".
    """
    assert _dset_name(_check(dset=TS, export=TS), TS) == ""
    assert _dset_name(None, TS) == ""


def test_both_surfaces_show_the_same_three_values():
    root = Path(__file__).resolve().parents[1]
    excel = (root / "core" / "qa_export.py").read_text(encoding="utf-8")
    app = (root / "ui" / "app_v2.py").read_text(encoding="utf-8")
    assert '"Innovid Creative Name (Decision Set)"' in excel
    assert '"Innovid Creative (DS)"' in app
    # La misma funcion en los dos sitios: dos criterios de "se llama
    # distinto" es como vuelven a discrepar.
    assert "_dset_name" in app


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

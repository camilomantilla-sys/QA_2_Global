"""
La app hacia firmar una discrepancia que el Excel desmentia.

Innovid tiene dos vistas del mismo creativo y no siempre lo llama
igual en las dos: dentro del decision set suele mostrar el nombre del
CONCEPTO, y en el export Placement-Creative el del ARCHIVO. QA2
comparaba el decision set en la app y el export en el Excel, asi que
el mismo creativo salia marcado en una pantalla y en verde en la otra.

Camilo: "me lo flaggea en 2. Creative & Assignments, pero en el excel
descargado me lo compara con el placement creative export y ahi si
hace match... si en un lado me muestra el creativo dentro del DS y en
otro el del export, pierdo tiempo validando manualmente que todo esta
bien, siento que no es un tema de lectura, sino de como presenta los
datos".

Tenia razon. "No esta en Innovid" era falso: el export prueba que esta
asignado. Pero tampoco esta comprobado -- sin nodo no se pueden leer
sus fechas ni su rotacion dentro del decision set. Eso es exactamente
NOT_VERIFIED, que es lo que QA2 dice cuando algo no se pudo mirar.

Run with pytest, or directly:
    python tests/test_creative_name_two_sources.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, RED  # noqa: E402
from core.findings import FindingsBuffer, Status  # noqa: E402
from core.innovid_reconciliation import (  # noqa: E402
    MATCHED,
    MISSING_IN_INNOVID,
    ONLY_IN_EXPORT,
    CreativeFlightCheck,
    InnovidReconciliation,
    _compare_creatives,
)
from core.matching import ExpectedCreative, norm_creative  # noqa: E402
from rules import innovid as innovid_rules  # noqa: E402

PID = "10707596"
ARCHIVO = "USWA_A_Static_BINC_300x600.jpg"


#: El id que Innovid le dio al creativo. El export lo trae, y es el
#: mismo con el que el decision set identifica su nodo.
ID_INNOVID = "6078568"


class _Node:
    """Un nodo del decision set, con el nombre del concepto."""

    def __init__(self, name="BINC Static Concept", creative_id=""):
        self.creative_name = name
        self.creative_id = creative_id
        self.is_default = False
        self.start_timestamp = "2026-04-09T00:00:00Z"
        self.end_timestamp = "2026-09-07T00:00:00Z"
        self.weight = "50"
        self.dtree_id = ""
        self.dtree_name = ""


def _run(*, in_export: bool, intent=GREEN, nodes=None,
         export_id=ID_INNOVID, ts_id=""):
    out = InnovidReconciliation()
    expected = [
        ExpectedCreative(name=ARCHIVO, intent=intent, creative_id=ts_id)
    ]
    _compare_creatives(
        PID,
        expected,
        nodes if nodes is not None else [_Node()],
        out,
        {norm_creative(ARCHIVO): export_id} if in_export else {},
    )
    return out.flights[0]


# ── el id del export es el tercer enganche ───────────────────────────

def test_the_export_id_finds_the_node_the_name_could_not():
    """
    El conector es el creative id. Pero la TS no siempre lo declara
    --las de Adobe casi nunca-- y sin el se caia al nombre, que es
    justo el que no coincide.

    El export SI trae el id de Innovid, y es el mismo del nodo. Con
    el, las fechas y la rotacion se leen de verdad.
    """
    check = _run(in_export=True, nodes=[_Node(creative_id=ID_INNOVID)])
    assert check.status == MATCHED
    assert check.matched_by == "export_creative_id"
    assert check.actual_start is not None
    assert check.actual_weight == "50"


def test_the_traffic_sheet_id_still_wins_when_it_has_one():
    check = _run(
        in_export=True,
        ts_id="999",
        nodes=[_Node(creative_id="999"), _Node(creative_id=ID_INNOVID)],
    )
    assert check.matched_by == "creative_id"


def test_the_name_still_works_when_it_does_match():
    check = _run(in_export=True, nodes=[_Node(name=ARCHIVO)])
    assert check.status == MATCHED
    assert check.matched_by == "name"


# ── y cuando de verdad no hay nodo ───────────────────────────────────

def test_in_the_export_but_in_no_node_is_not_missing_from_innovid():
    """
    Ni por nombre ni por ninguno de los dos ids. Esta asignado --el
    export lo prueba-- pero no hay nodo que leer.
    """
    check = _run(in_export=True, nodes=[_Node(creative_id="otro")])
    assert check.status == ONLY_IN_EXPORT


def test_not_in_the_export_either_is_still_missing():
    # Si no esta en ninguna de las dos vistas, si falta de verdad.
    assert _run(in_export=False).status == MISSING_IN_INNOVID


def test_a_removal_is_still_a_removal():
    """
    Un creativo en ROJO fuera del decision set es la solicitud
    cumplida, y eso no lo cambia que siga figurando en el export. Esa
    otra pregunta la contesta CRE-001.
    """
    check = _run(in_export=True, intent=RED,
                 nodes=[_Node(creative_id="otro")])
    assert check.status == MISSING_IN_INNOVID


# ── lo que el reporte dice ───────────────────────────────────────────

def _findings(check: CreativeFlightCheck) -> list:
    out = InnovidReconciliation()
    out.flights = [check]
    buffer = FindingsBuffer()
    innovid_rules.evaluate(out, buffer)
    return [f for f in buffer.findings if f.rule_id == "INV-001"]


def test_it_is_not_reported_as_a_failure():
    found = _findings(_run(in_export=True, nodes=[_Node(creative_id='otro')]))
    assert len(found) == 1, found
    assert found[0].status == Status.NOT_VERIFIED


def test_it_does_not_claim_the_creative_is_absent():
    message = _findings(_run(in_export=True, nodes=[_Node(creative_id='otro')]))[0].message
    assert "not in the decision set" not in message
    assert "assigned in Innovid" in message


def test_it_says_what_could_not_be_read():
    """
    Lo que no se pudo comprobar nunca pasa en verde, y tiene que
    decir QUE fue lo que no se pudo comprobar.
    """
    message = _findings(_run(in_export=True, nodes=[_Node(creative_id='otro')]))[0].message
    assert "flight dates and rotation" in message


def test_a_creative_that_really_is_absent_still_fails():
    found = _findings(_run(in_export=False))
    assert len(found) == 1, found
    assert found[0].status == Status.FAIL


def test_the_app_labels_the_cell_without_contradicting_the_excel():
    source = (
        Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"
    ).read_text(encoding="utf-8")
    assert "ONLY_IN_EXPORT" in source
    assert "assigned, named differently in DS" in source


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

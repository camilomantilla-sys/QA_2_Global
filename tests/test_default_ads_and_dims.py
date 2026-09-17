"""
El default ad de BlackRock, y la rotacion que no es del tamano del
placement.

Dos cosas distintas que se juntaban en la misma fila de la app.

1. BlackRock retira el default viejo pintandolo de GRIS y escribe el
   nuevo debajo, en blanco. La recuperacion de filas ocultas se traia
   el gris de vuelta como contexto blanco: el default retirado volvia a
   exigirse en Innovid -- donde ya no esta, porque termino -- y ocupaba
   el lugar del creativo que si se pidio. Camilo: "sigue teniendo el
   problema de que me trae grises a la app... me trae el current
   default, el default viejo en gris".

   Recuperar es rellenar lo que no se alcanzo a leer, no revivir lo
   que la TS descarto a proposito.

2. Los creativos de un grupo se filtran por dimension a proposito: un
   grupo de Adobe trae los 5 tamanos y un placement de 160x600 solo
   sirve los suyos. Pero cuando el filtro se lleva TODOS los creativos
   pedidos, el placement se queda sin nada que comparar y nadie lo
   decia: el hueco lo tapaba el default ad, que se engancha por
   dimension, y la fila se leia como si estuviera revisada.

   Le paso a dos placements cuyas rotaciones quedaron cruzadas en la
   TS -- el de 300x600 nombrando la rotacion de 300x250 y al reves.
   Innovid corria el creativo correcto; la TS era la que estaba mal, y
   el creativo bueno salia en "extra creatives" sin explicacion.

Run with pytest, or directly:
    python tests/test_default_ads_and_dims.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, WHITE  # noqa: E402
from core.findings import FindingsBuffer, Status  # noqa: E402
from core.matching import build_expected  # noqa: E402
from rules.placements import _evaluate_rotation_dims  # noqa: E402


class _Row:
    def __init__(self, row, intent, **values):
        self.row = row
        self.intent = intent
        self.values = values
        self.intent_fields = ()
        self.impl_type = ""
        self.fmt = ""


class _Sheet:
    def __init__(self, rows, sheet="Placements"):
        self.rows = rows
        self.sheet = sheet


class _Scope:
    def __init__(self, request_type, groups):
        self.request_type = request_type
        self.groups = set(groups)
        self.visual_review = False
        self.source = ""


class _TS:
    def __init__(self, placements, rotations, scope, rotations_all=None):
        self.profile = "wpp_standard"
        self.placements = _Sheet(placements)
        self.rotations = _Sheet(rotations, sheet="Creative Rotations")
        self.rotations_all = _Sheet(
            rotations if rotations_all is None else rotations_all,
            sheet="Creative Rotations",
        )
        self.landing_pages = None
        self.scope = scope or {}
        self.groups = {}
        self.lp_worked = set()


# ------------------------------------------------------- el default ad

def default_sheet():
    """
    Un placement de 300x600 con la rotacion que le toca, y arriba el
    grupo de defaults: el viejo en gris, ya terminado, y el nuevo en
    blanco.
    """
    placements = [
        _Row(23, GREEN,
             placement_id="11135651", placement_name="Ticker Banner",
             dimensions="300x600",
             group_name="Ticker Search Banner 300x600 - Tax"),
    ]
    rotations = [
        _Row(4, "SCOPE_EXCLUDED", group_name="300x600 USWA Default Web Ad",
             creative_name="USWA_A_Static_BINC_300x600.jpg",
             creative_id="6078568", dims_or_duration="300x600"),
        _Row(5, WHITE, group_name="300x600 USWA Default Web Ad",
             creative_name="BincDigitalBaner_300x600_DEFAULT.png",
             creative_id="6412621", dims_or_duration="300x600"),
        _Row(42, GREEN, group_name="Ticker Search Banner 300x600 - Tax",
             creative_name="2025_BLK_TAX_300x600.jpg",
             creative_id="5835717", dims_or_duration="300x600"),
    ]
    scope = {
        "11135651": _Scope(
            "NEW_PLACEMENT", {"ticker search banner 300x600 - tax"}
        )
    }
    return _TS(placements, rotations, scope)


def test_the_live_default_is_hooked_by_dimension():
    expected = build_expected(default_sheet())
    defaults = [c for c in expected["11135651"].creatives if c.is_default]
    assert [c.name for c in defaults] == [
        "BincDigitalBaner_300x600_DEFAULT.png"
    ], [c.name for c in defaults]


def test_the_retired_default_is_not_brought_back():
    expected = build_expected(default_sheet())
    names = [c.name for c in expected["11135651"].creatives]
    assert "USWA_A_Static_BINC_300x600.jpg" not in names, names


def test_the_requested_creative_is_still_there():
    expected = build_expected(default_sheet())
    pedidos = [
        c for c in expected["11135651"].creatives
        if not c.is_default and c.intent == GREEN
    ]
    assert [c.name for c in pedidos] == ["2025_BLK_TAX_300x600.jpg"]


def test_a_hidden_white_row_is_still_recovered():
    """
    La otra mitad de la misma regla: cuando la hoja entera esta oculta,
    `rotations` viene vacia y lo unico que hay es `rotations_all`. Sin
    esto el placement se quedaba sin el contenido de su decision set.
    """
    ts = default_sheet()
    ocultas = list(ts.rotations.rows)
    ts.rotations.rows = []
    ts.rotations_all.rows = ocultas
    expected = build_expected(ts)
    names = [c.name for c in expected["11135651"].creatives]
    assert "2025_BLK_TAX_300x600.jpg" in names, names
    # Recuperada, pero como contexto: una fila oculta no es parte de la
    # solicitud, por verde que este pintada.
    recuperado = next(
        c for c in expected["11135651"].creatives
        if c.name == "2025_BLK_TAX_300x600.jpg"
    )
    assert recuperado.intent == WHITE
    # Y el gris sigue sin volver, tambien cuando esta oculto.
    assert "USWA_A_Static_BINC_300x600.jpg" not in names, names


# ------------------------------------------- la rotacion cruzada (PLC-007)

def crossed_sheet():
    """El placement de 300x600 nombrando la rotacion de 300x250."""
    ts = default_sheet()
    ts.placements.rows[0].values["group_name"] = (
        "Ticker Search Banner 300x250 - Tax"
    )
    ts.rotations.rows[2].values["group_name"] = (
        "Ticker Search Banner 300x250 - Tax"
    )
    ts.rotations.rows[2].values["creative_name"] = "2025_BLK_TAX_300x250.jpg"
    ts.rotations.rows[2].values["dims_or_duration"] = "300x250"
    ts.rotations_all.rows = list(ts.rotations.rows)
    ts.scope["11135651"] = _Scope(
        "NEW_PLACEMENT", {"ticker search banner 300x250 - tax"}
    )
    return ts


def _findings(ts, pid):
    buffer = FindingsBuffer()
    _evaluate_rotation_dims(build_expected(ts)[pid], buffer)
    return [f for f in buffer.findings if f.rule_id == "PLC-007"]


def test_a_rotation_of_the_wrong_size_is_reported():
    findings = _findings(crossed_sheet(), "11135651")
    assert len(findings) == 1, findings
    assert findings[0].status == Status.REVIEW
    assert "300x250" in findings[0].actual
    assert "300x600" in findings[0].expected


def test_the_placement_is_left_with_no_requested_creative():
    # El sintoma que Camilo vio: solo el default, y el creativo bueno
    # en "extra creatives".
    expected = build_expected(crossed_sheet())
    pedidos = [
        c for c in expected["11135651"].creatives if not c.is_default
    ]
    assert pedidos == [], [c.name for c in pedidos]


def test_a_group_with_several_sizes_says_nothing():
    """
    Adobe: el grupo trae los 5 tamanos y el placement se queda con el
    suyo. Eso es el filtro haciendo su trabajo, no un hallazgo.
    """
    ts = crossed_sheet()
    ts.rotations.rows.append(
        _Row(43, GREEN, group_name="Ticker Search Banner 300x250 - Tax",
             creative_name="2025_BLK_TAX_300x600.jpg",
             creative_id="5835717", dims_or_duration="300x600")
    )
    ts.rotations_all.rows = list(ts.rotations.rows)
    assert _findings(ts, "11135651") == []


def test_a_landing_page_only_swap_says_nothing():
    """
    Sin creativos pedidos no hay nada que el filtro pueda tumbar: un
    swap de solo landing page no debe disparar esto.
    """
    ts = default_sheet()
    ts.rotations.rows[2].intent = WHITE
    ts.rotations_all.rows = list(ts.rotations.rows)
    assert _findings(ts, "11135651") == []


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

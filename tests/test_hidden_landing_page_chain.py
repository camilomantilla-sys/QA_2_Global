"""
La tabla que dice a que landing page apunta un grupo puede estar oculta.

El caso: "TS_Q2-Q4 2026 Co Marketing" de BlackRock, un swap de solo
URL. La pestana Landing Pages trae 33 pares rojo/verde -- una
solicitud sin ninguna ambiguedad -- y QA2 no revisaba nada:

    request types: {'NOT_WORKED': 56}

La cadena de BlackRock es

    placement -> creative rotation -> landing page -> URL

El placement no nombra su landing page: dice "See Creative Rotation
Tab". El eslabon del medio son las 67 filas de Creative Rotations... y
en esta Traffic Sheet estan las 67 ocultas. El parser las salta, con
razon -- una fila oculta no es parte de la solicitud, es la regla del
equipo y las plantillas vienen llenas de ejemplos ocultos -- pero al
saltarlas se lleva por delante tambien el mapa grupo -> landing page,
que no es una solicitud sino la estructura de la campana.

Sin ese mapa ningun placement llegaba a URL_SWAP y los 56 salian
NOT_WORKED.

La distincion que arregla esto: de las filas ocultas se toma
UNICAMENTE a que landing page apunta cada grupo. Ni un verde, ni un
rojo, ni un blanco. El color -- lo que de verdad se pidio -- se sigue
leyendo solo de lo visible.

Run with pytest, or directly:
    python tests/test_hidden_landing_page_chain.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, RED, WHITE  # noqa: E402
from parsers.ts_parser import (  # noqa: E402
    GroupScope,
    _build_groups,
    _merge_hidden_lp_refs,
)


class _Row:
    def __init__(self, row, intent, **values):
        self.row = row
        self.intent = intent
        self.values = values


class _Sheet:
    def __init__(self, rows, sheet="Creative Rotations"):
        self.rows = rows
        self.sheet = sheet


GROUP = "Magnificent 300x600 SGOV"
LP = "Magnificent 300x600 SGOV"


def visible_rotations():
    """Lo que el parser ve cuando las filas estan ocultas: nada."""
    return _Sheet([])


def every_rotation_row():
    """La misma hoja leida entera, que es como se resuelve la referencia."""
    return _Sheet([
        _Row(5, WHITE, group_name=GROUP,
             creative_name="ishares_300x600.jpg", lp_url=LP),
        _Row(6, WHITE, group_name="AV ROS Display 728x90 SGOV",
             creative_name="ishares_728x90.jpg",
             lp_url="AV ROS Display 728x90 SGOV"),
    ])


# ── la referencia se recupera ────────────────────────────────────────

def test_without_the_hidden_rows_there_is_no_chain():
    groups = _build_groups(visible_rotations())
    assert groups == {}


def test_the_hidden_rows_supply_the_landing_page_of_each_group():
    groups = _build_groups(visible_rotations())
    _merge_hidden_lp_refs(groups, every_rotation_row())
    assert groups["magnificent 300x600 sgov"].lp_names == {
        "magnificent 300x600 sgov"
    }


def test_every_group_in_the_hidden_table_is_recovered():
    groups = _build_groups(visible_rotations())
    _merge_hidden_lp_refs(groups, every_rotation_row())
    assert set(groups) == {
        "magnificent 300x600 sgov",
        "av ros display 728x90 sgov",
    }


# ── pero solo la referencia ──────────────────────────────────────────

def test_a_hidden_row_never_counts_as_a_request():
    """
    Lo importante. Si un verde oculto contara, volveria justo el
    problema que la regla de filas ocultas existe para evitar: los
    ejemplos de la plantilla entrando al QA como trabajo pedido.
    """
    groups = _build_groups(visible_rotations())
    _merge_hidden_lp_refs(groups, _Sheet([
        _Row(5, GREEN, group_name=GROUP, creative_name="a.jpg", lp_url=LP),
        _Row(6, RED, group_name=GROUP, creative_name="b.jpg", lp_url=LP),
        _Row(7, WHITE, group_name=GROUP, creative_name="c.jpg", lp_url=LP),
    ]))
    g = groups["magnificent 300x600 sgov"]
    assert (g.green_creatives, g.red_creatives, g.white_creatives) == (0, 0, 0)


def test_a_row_without_a_landing_page_adds_nothing():
    groups = _build_groups(visible_rotations())
    _merge_hidden_lp_refs(groups, _Sheet([
        _Row(5, WHITE, group_name=GROUP, creative_name="a.jpg"),
    ]))
    assert groups == {}


def test_what_is_visible_is_not_overwritten():
    """Un grupo que si se leyo conserva sus conteos."""
    visible = _Sheet([
        _Row(9, GREEN, group_name=GROUP, creative_name="new.jpg", lp_url=LP),
    ])
    groups = _build_groups(visible)
    before = groups["magnificent 300x600 sgov"].green_creatives
    _merge_hidden_lp_refs(groups, every_rotation_row())
    assert groups["magnificent 300x600 sgov"].green_creatives == before == 1


def test_nothing_happens_without_a_second_read():
    groups = _build_groups(every_rotation_row())
    snapshot = {k: set(v.lp_names) for k, v in groups.items()}
    _merge_hidden_lp_refs(groups, None)
    assert {k: set(v.lp_names) for k, v in groups.items()} == snapshot


# ── y el scope llega a URL_SWAP ──────────────────────────────────────

def test_the_placement_reaches_url_swap():
    """
    El final de la cadena: con la referencia recuperada, un placement
    que dice "See Creative Rotation Tab" y cuyo grupo apunta a una
    landing page pintada se marca como swap de URL.
    """
    from parsers.ts_parser import _build_scope

    class _PlRow:
        def __init__(self):
            self.row = 30
            self.intent = WHITE
            self.values = {
                "placement_id": "10963993",
                "placement_name": "P3J6GSF_BRK_ISH_187_Endemic",
                "dimensions": "300 x 600",
                "group_name": GROUP,
                "lp_ref": "See Creative Rotation Tab",
            }
            self.colors = {}
            self.intent_fields = ()
            self.inherited = set()
            self.impl_type = ""
            self.fmt = "display"

    groups = _build_groups(visible_rotations())
    _merge_hidden_lp_refs(groups, every_rotation_row())

    scope = _build_scope(
        _Sheet([_PlRow()], sheet="Placements"),
        groups,
        {"magnificent 300x600 sgov"},
        propagate=True,
    )
    assert scope["10963993"].request_type == "URL_SWAP"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))

"""
En BlackRock un placement ocupa varias filas, y no todas valen igual.

La Traffic Sheet acumula solicitudes: el mismo placement aparece una
vez en gris con la rotacion de entonces y otra en verde con la que se
acaba de hacer. Quedarse con la primera fila que trajera un dato tomaba
la rotacion vieja -- y con ella sus creativos -- asi que el swap que se
pedia revisar se comparaba contra el grupo equivocado o contra nada.

Camilo, sobre BlackRock_test_3: "me esta leyendo los que estan en gris
en la ts... en el placement tab sale en gris y tambien en blanco con el
creative rotation en verde con el swap realizado y esa info no me la
trae ni me la compara."

Y el otro lado del mismo desorden: cuando el placement entero va en
rojo -- desasignar -- sus creativos se quedaban en blanco, porque la
rotacion la comparten placements que siguen corriendo. La fila del
placement que hay que apagar se leia igual que una que no hay que
tocar. Camilo: "su placement 10657690 esta en rojo asi que toca
desasignarlo".

Run with pytest, or directly:
    python tests/test_blackrock_greys.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, RED, WHITE  # noqa: E402
from core.matching import build_expected  # noqa: E402


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


class _Group:
    def __init__(self):
        self.lp_names = set()


class _TS:
    def __init__(self, placements, rotations=None, scope=None):
        self.profile = "wpp_standard"
        self.placements = _Sheet(placements)
        self.rotations = _Sheet(rotations or [], sheet="Creative Rotations")
        self.landing_pages = None
        self.scope = scope or {}
        self.groups = {}
        self.lp_worked = set()


def swap_sheet():
    """
    El placement 10632209 de BlackRock_test_3, tal cual: la fila vieja
    en gris con su rotacion, y la nueva en verde con el swap.
    """
    placements = [
        _Row(20, "SCOPE_EXCLUDED",
             placement_id="10632209", placement_name="eFront Reuters",
             dimensions="1x1", group_name="30s Video Neverdone Podcast"),
        _Row(23, GREEN,
             placement_id="10632209", placement_name="eFront Reuters",
             dimensions="1x1", group_name="Reuters_eFrontInsight Video 1x1"),
    ]
    rotations = [
        _Row(5, WHITE, group_name="30s Video Neverdone Podcast",
             creative_name="NeverDonePodcast_Video30s.mp4",
             dims_or_duration="1x1"),
        _Row(9, GREEN, group_name="Reuters_eFrontInsight Video 1x1",
             creative_name="eFront_Insights_Reuters_24s.mp4",
             dims_or_duration="1x1"),
    ]
    scope = {
        "10632209": _Scope(
            "NEW_PLACEMENT", {"reuters_efrontinsight video 1x1"}
        )
    }
    return _TS(placements, rotations, scope)


def test_the_group_comes_from_the_row_of_this_request():
    expected = build_expected(swap_sheet())
    assert expected["10632209"].group_name == "Reuters_eFrontInsight Video 1x1"


def test_the_creatives_are_the_ones_of_that_group():
    expected = build_expected(swap_sheet())
    names = [c.name for c in expected["10632209"].creatives]
    assert names == ["eFront_Insights_Reuters_24s.mp4"], names


def test_the_grey_row_still_wins_when_it_is_the_only_one():
    # Si no hay ninguna fila de esta solicitud, lo que haya es lo que
    # hay: quedarse sin grupo seria peor.
    ts = swap_sheet()
    ts.placements.rows = ts.placements.rows[:1]
    expected = build_expected(ts)
    assert expected["10632209"].group_name == "30s Video Neverdone Podcast"


def removal_sheet():
    """Un placement entero en rojo, con su default en blanco."""
    placements = [
        _Row(30, RED,
             placement_id="10657690", placement_name="ISH 300x250",
             dimensions="300x250",
             group_name="Competitor Ticker Targeting 300x250"),
    ]
    rotations = [
        _Row(15, WHITE, group_name="Competitor Ticker Targeting 300x250",
             creative_name="IQQ_InOneFund_300x250px.gif",
             dims_or_duration="300x250"),
        _Row(2, WHITE, group_name="300x250 ISH Default Web Ad",
             creative_name="IQQ_Default_300x250px.gif",
             dims_or_duration="300x250"),
    ]
    scope = {
        "10657690": _Scope(
            "CREATIVE_REMOVE", {"competitor ticker targeting 300x250"}
        )
    }
    return _TS(placements, rotations, scope)


def test_a_placement_being_unassigned_marks_its_creatives_as_going():
    expected = build_expected(removal_sheet())
    intents = {c.name: c.intent for c in expected["10657690"].creatives}
    assert intents, "el placement se quedo sin creativos"
    assert set(intents.values()) == {RED}, intents


def test_its_default_goes_too():
    expected = build_expected(removal_sheet())
    defaults = [
        c for c in expected["10657690"].creatives if c.is_default
    ]
    assert defaults, "el default no se engancho"
    assert all(c.intent == RED for c in defaults)


def test_a_placement_that_is_not_being_unassigned_keeps_its_context():
    ts = removal_sheet()
    ts.placements.rows[0].intent = GREEN
    ts.scope["10657690"] = _Scope(
        "CREATIVE_SWAP", {"competitor ticker targeting 300x250"}
    )
    expected = build_expected(ts)
    intents = {c.intent for c in expected["10657690"].creatives}
    assert intents == {WHITE}, intents


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
        else:
            passed += 1
            print(f"ok   {name}")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

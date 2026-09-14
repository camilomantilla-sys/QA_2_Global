"""
Un 1x1 va asignado directo al placement.

Tres consecuencias que QA trataba mal, las tres del mismo hecho:

  - No tiene decision set, y no le falta ninguno. La Traffic Sheet le
    pone un Creative Rotation Name igual, pero eso es una etiqueta
    para quien trafica. Camilo: "en la ts si marca un creative
    rotation name como guia, pero en la implementacion en innovid van
    directo al placement." Se reportaban los treinta 1x1 de una
    solicitud correcta como "grupo faltante".

  - Su clicktag ES el del placement, y suele venir en la fila del
    creativo del export placement-creative, no en el Placement View.
    Mirando solo alli, la URL se quedaba sin comparar con el export
    delante: "las urls estan implementadas a nivel de creativo... sin
    embargo, no esta leyendo las urls de los exports."

  - En un swap de 1x1 la TS deja el creativo viejo en blanco, que en
    Innovid ya no esta. Hay un link y ninguna comparacion, asi que la
    URL del placement no la miraba nadie: el respaldo a nivel de
    placement tiene que entrar cuando NINGUN creativo dio veredicto,
    no solo cuando no hay creativos declarados.

Run with pytest, or directly:
    python tests/test_one_by_one_placements.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, WHITE  # noqa: E402
from core.matching import (  # noqa: E402
    ActualCreative,
    ActualPlacement,
    ExpectedCreative,
    ExpectedPlacement,
    MatchResult,
    PlacementMatch,
    _match_group,
    compare_placement,
    is_site_served_1x1,
    placement_clicktags,
)

URL = "https://www.efront.com/en/alternative-investment-software/insights"


def expected_placement(dims="1x1", group="Reuters_eFrontInsight Video 1x1",
                       creatives=None, url=URL) -> ExpectedPlacement:
    return ExpectedPlacement(
        placement_id="10632209",
        name="eFront Reuters 1x1",
        dims=dims,
        fmt=dims,
        group_name=group,
        url=url,
        creatives=creatives or [],
    )


def innovid_creative(name: str, url: str = URL,
                     running: bool = True) -> ActualCreative:
    creative = ActualCreative(
        creative_id="6404062",
        filename=name,
        name=name,
        enabled=running,
        status="Active" if running else "Disabled",
    )
    creative.clicktags = [url] if url else []
    return creative


def actual_placement(creatives=None, placement_tags=None) -> ActualPlacement:
    actual = ActualPlacement(
        placement_id="10632209",
        name="eFront Reuters 1x1",
        status="Active",
        # Sin grupo: el creativo va directo al placement.
        group_name="",
    )
    actual.creatives = creatives or []
    actual.clicktags = list(placement_tags or [])
    return actual


# ------------------------------------------------- el decision set

def test_a_1x1_without_a_decision_set_is_not_missing_one():
    result, trace = _match_group(expected_placement(), actual_placement())
    assert result == "N/A", trace.note
    assert "assigned straight to the placement" in trace.note


def test_the_rotation_name_is_called_a_label():
    _, trace = _match_group(expected_placement(), actual_placement())
    assert "label for the trafficker" in trace.note


def test_a_display_without_its_group_is_still_a_finding():
    # Lo contrario: un 300x250 que declara grupo y no lo tiene en
    # Innovid si es algo que mirar.
    result, _ = _match_group(
        expected_placement(dims="300x250"), actual_placement()
    )
    assert result == "MISSING"


def test_the_format_column_also_says_1x1():
    assert is_site_served_1x1(ExpectedPlacement("1", fmt="1x1"))
    assert is_site_served_1x1(ExpectedPlacement("1", dims="1x1"))
    assert not is_site_served_1x1(ExpectedPlacement("1", dims="300x250"))


# ------------------------------------------------------ el clicktag

def test_the_placement_clicktag_can_come_from_its_creative():
    actual = actual_placement(creatives=[innovid_creative("video.mp4")])
    assert placement_clicktags(actual) == [URL]


def test_the_placement_view_wins_when_it_has_one():
    actual = actual_placement(
        creatives=[innovid_creative("video.mp4", "https://other.example")],
        placement_tags=[URL],
    )
    assert placement_clicktags(actual) == [URL]


def test_a_creative_that_is_not_running_does_not_lend_its_clicktag():
    actual = actual_placement(
        creatives=[innovid_creative("old.mp4", running=False)]
    )
    assert placement_clicktags(actual) == []


def test_no_creatives_and_no_placement_tag_is_empty():
    assert placement_clicktags(actual_placement()) == []
    assert placement_clicktags(None) == []


# --------------------------------------------------- el swap de 1x1

def compare(expected, actual) -> PlacementMatch:
    match = PlacementMatch(
        placement_id=expected.placement_id,
        expected=expected,
        actual=actual,
    )
    compare_placement(match, MatchResult())
    return match


def test_a_1x1_swap_still_gets_its_url_checked():
    # La TS deja el creativo viejo en blanco; Innovid ya tiene el
    # nuevo, con la URL en su clicktag.
    expected = expected_placement(
        creatives=[ExpectedCreative(name="old_video_30s.mp4", intent=WHITE)]
    )
    actual = actual_placement(
        creatives=[innovid_creative("new_video_24s.mp4")]
    )
    match = compare(expected, actual)

    assert match.creative_links and match.creative_links[0].actual is None
    assert match.url is not None, "la URL del placement se quedo sin mirar"
    assert match.url.result == "MATCH"


def test_a_placement_whose_creative_did_get_checked_is_not_checked_twice():
    # Donde el creativo si dio veredicto manda el, y repetirlo a nivel
    # de placement pondria dos filas para la misma revision.
    expected = expected_placement(
        creatives=[
            ExpectedCreative(name="video.mp4", intent=GREEN, url=URL)
        ]
    )
    actual = actual_placement(creatives=[innovid_creative("video.mp4")])
    match = compare(expected, actual)

    assert match.creative_links[0].url is not None
    assert match.url is None


def test_the_creative_level_check_also_reads_the_placement_clicktag():
    # Un 1x1 donde el creativo esta pero su fila no trae clicktag.
    creative = innovid_creative("video.mp4", url="")
    expected = expected_placement(
        creatives=[ExpectedCreative(name="video.mp4", intent=GREEN, url=URL)]
    )
    actual = actual_placement(creatives=[creative], placement_tags=[URL])
    match = compare(expected, actual)

    assert match.creative_links[0].url.result == "MATCH"


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

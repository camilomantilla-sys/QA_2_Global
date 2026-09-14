"""
Un creativo que no esta en Innovid es UN problema, no tres.

Caso real (Adobe STE Discover, placement 11038710): la Traffic Sheet
declara cinco creativos y en Innovid hay cuatro. QA reportaba:

    FAIL  CRE-001  Creative missing in export
    FAIL  URL-001  TS declares a URL, but Innovid has no Clicktag
    FAIL  ATR-001  TS=R726NC76 vs Innovid=P3JPFSN (missing URL)

El unico cierto es el primero. Los otros dos comparan contra un
creativo que no existe, y el "CGEN de Innovid" del tercero -- P3JPFSN
-- no es un CGEN: es el Third_Party_ID que el Placement View lleva
para el placement entero, otro campo que no se compara con esto.
Camilo, viendo el export: "hay una mala lectura".

La excepcion es el site-served: alli el creativo nombrado en la TS no
aparece NUNCA, porque Innovid sirve el pixel generico de la cuenta --
y esa fila si trae el CGEN correcto del placement.

Run with pytest, or directly:
    python tests/test_missing_creative_noise.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN  # noqa: E402
from core.matching import (  # noqa: E402
    ActualCreative,
    ActualPlacement,
    ExpectedCreative,
    ExpectedPlacement,
    MatchResult,
    PlacementMatch,
    compare_placement,
)

URL = "https://www.adobe.com/education/students/creativecloud/pro.html?sdid=VKW3JZD9"
CGEN = "VKW3JZD9"


def creative(name: str, cgen: str, url: str) -> ExpectedCreative:
    return ExpectedCreative(
        name=name, intent=GREEN, cgen=cgen, url=url, dims="300x600",
    )


def build(in_innovid: bool, site_served: bool = False):
    """Un placement con un creativo que Innovid tiene, o no."""
    expected = ExpectedPlacement(
        placement_id="11038710",
        name="Brainly_FY26EDU_BEH_StandardDisplay",
        dims="1x1" if site_served else "300x600",
        creatives=[creative("banner_300x600.jpg", CGEN, URL)],
    )
    actual = ActualPlacement(
        placement_id="11038710",
        name="Brainly_FY26EDU_BEH_StandardDisplay",
        status="Active",
        # El Third_Party_ID del Placement View. NO es un CGEN.
        third_party_id="P3JPFSN",
    )
    if in_innovid:
        found = ActualCreative(
            creative_id="6377305",
            filename="banner_300x600.jpg",
            name="banner_300x600.jpg",
            third_party_id=CGEN,
            enabled=True,
            status="Active",
        )
        found.clicktags = [URL]
        actual.creatives = [found]
    elif site_served:
        actual.creatives = [
            ActualCreative(
                creative_id="50126",
                filename="1x1.gif (50126)",
                name="1x1.gif",
                third_party_id=CGEN,
                row_type="TRACKER",
                enabled=True,
                status="Active",
            )
        ]
    return expected, actual


def links(in_innovid: bool, site_served: bool = False):
    expected, actual = build(in_innovid, site_served)
    match = PlacementMatch(
        placement_id=expected.placement_id,
        expected=expected,
        actual=actual,
    )
    compare_placement(match, MatchResult())
    return match


def test_a_creative_that_is_there_is_compared():
    match = links(in_innovid=True)
    link = match.creative_links[0]
    assert link.url is not None and link.url.result == "MATCH"
    assert link.triangle is not None and link.triangle.is_ok


def test_a_creative_that_is_not_there_gets_no_url_verdict():
    match = links(in_innovid=False)
    assert match.creative_links[0].actual is None
    assert match.creative_links[0].url is None


def test_a_creative_that_is_not_there_gets_no_attribution_verdict():
    match = links(in_innovid=False)
    assert match.creative_links[0].triangle is None


def test_the_placement_third_party_id_is_never_read_as_a_cgen():
    # P3JPFSN es otro campo. Compararlo contra el CGEN de la TS daba
    # un fallo de atribucion inventado sobre cada creativo faltante.
    match = links(in_innovid=False)
    triangle = match.creative_links[0].triangle
    assert triangle is None or "P3JPFSN" not in str(triangle.export)


def test_site_served_still_reads_the_cgen_from_the_pixel():
    # Aqui el creativo nombrado NO esta y aun asi hay que comparar:
    # el pixel generico lleva el CGEN de este placement.
    match = links(in_innovid=False, site_served=True)
    link = match.creative_links[0]
    assert link.triangle is not None, "se dejo de revisar el site-served"
    assert link.triangle.export == CGEN


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

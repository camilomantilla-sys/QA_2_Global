"""
Adobe Direct / Site-Served: lo que se revisa cuando no hay creativos.

Un 1x1 de Adobe escribe "N/A" en Creative Names. El creativo en
Innovid es el pixel generico de la cuenta -- el mismo 1x1.gif para
todos los placements -- y todo lo que hay que revisar vive a nivel de
placement: la landing page en su columna de la TS, el CGEN en la suya,
y del lado de Innovid el Clicktag_1 del Placement View y el
Third_Party_ID de la fila del pixel.

Sin creativos declarados no habia CreativeLink, y URL-001 y ATR-001 --
que recorren los links -- no tenian por donde entrar. Resultado sobre
casos reales: los 4 placements de Acrobat y los 95 1x1 de STE Discover
pasaban el QA sin que nadie comparara ni una URL ni un CGEN, y el
pixel salia ademas como "creativo no declarado en la TS".

Run with pytest, or directly:
    python tests/test_adobe_direct.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.findings import FindingsBuffer  # noqa: E402
from core.matching import (  # noqa: E402
    ActualCreative,
    ActualPlacement,
    ExpectedPlacement,
    PlacementMatch,
    _tracker_cgen,
)
from core.urls import check_triangle, compare_urls  # noqa: E402
from rules import attribution, urls  # noqa: E402

URL = "https://www.adobe.com/acrobat/campaign/stylize.html?sdid=JZBJVKVF"
CGEN = "JZBJVKVF"


def pixel(third_party_id: str = CGEN) -> ActualCreative:
    """El 1x1.gif que Innovid asigna a un placement site-served."""
    return ActualCreative(
        creative_id="50126",
        filename="1x1.gif (50126)",
        name="1x1.gif",
        third_party_id=third_party_id,
        row_type="TRACKER",
        enabled=True,
        status="Active",
    )


def placement(ts_url: str = URL, ts_cgen: str = CGEN,
              innovid_url: str = URL, innovid_cgen: str = CGEN,
              creatives=None) -> PlacementMatch:
    actual = ActualPlacement(
        placement_id="11096219",
        name="HBOMax_FY26Acrobat_CTX_Brightline-DoThat",
        status="Available",
        placement_type="Pixel",
        third_party_id="P3K74DP",
    )
    actual.clicktags = [innovid_url] if innovid_url else []
    actual.creatives = (
        [pixel(innovid_cgen)] if creatives is None else creatives
    )

    match = PlacementMatch(
        placement_id="11096219",
        expected=ExpectedPlacement(
            placement_id="11096219",
            name="HBOMax_FY26Acrobat_CTX_Brightline-DoThat",
            dims="1x1",
            url=ts_url,
            cgen=ts_cgen,
        ),
        actual=actual,
    )
    # Lo que hace `match()` cuando el placement no trae creativos.
    if ts_url or innovid_url:
        match.url = compare_urls(ts_url, innovid_url)
    if ts_cgen:
        match.triangle = check_triangle(
            ts_cgen,
            _tracker_cgen(actual) or actual.third_party_id,
            innovid_url,
        )
    return match


class _Result:
    def __init__(self, matched):
        self.matched = matched
        self.only_expected = []
        self.only_actual_in_scope = []
        self.ambiguous = []


def run(match, account="Adobe"):
    buffer = FindingsBuffer()
    urls.evaluate(_Result([match]), buffer)
    attribution.evaluate(_Result([match]), buffer, account=account)
    return buffer.findings


def only(findings, rule_id):
    return [f for f in findings if f.rule_id == rule_id]


def test_the_landing_page_is_checked_without_any_creative():
    found = only(run(placement()), "URL-003")
    assert found and found[0].status.value == "PASS", found


def test_a_wrong_landing_page_fails():
    found = only(
        run(placement(innovid_url="https://www.adobe.com/other.html")),
        "URL-003",
    )
    assert found and found[0].status.value == "FAIL", found


def test_no_clicktag_in_innovid_is_not_verified():
    found = only(run(placement(innovid_url="")), "URL-003")
    assert found and found[0].status.value == "NOT_VERIFIED", found


def test_the_cgen_is_checked_without_any_creative():
    found = only(run(placement()), "ATR-002")
    assert found and found[0].status.value == "PASS", found


def test_a_cgen_that_does_not_match_innovid_fails():
    found = only(run(placement(innovid_cgen="XXXXXXXX")), "ATR-002")
    assert found and found[0].status.value == "FAIL", found


def test_the_cgen_comes_from_the_pixel_row_not_the_placement():
    # El Third_Party_ID del Placement View (P3K74DP) es otro campo y
    # usarlo como sustituto marcaba en revision todos los 1x1.
    actual = placement().actual
    assert _tracker_cgen(actual) == CGEN
    assert actual.third_party_id != CGEN


def test_without_a_single_tracker_there_is_nothing_to_read():
    # Dos pixeles, o ninguno: no se puede decir cual es el CGEN.
    actual = placement().actual
    actual.creatives = [pixel("AAA"), pixel("BBB")]
    assert _tracker_cgen(actual) == ""


def test_a_placement_with_creatives_is_left_to_the_creative_rules():
    # URL-003 y ATR-002 son el plan B. Donde hay creativos declarados
    # mandan URL-001 y ATR-001, y duplicar el hallazgo solo pondria
    # dos filas para la misma revision.
    match = placement()
    match.url = None
    match.triangle = None
    findings = run(match)
    assert not only(findings, "URL-003")
    assert not only(findings, "ATR-002")


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

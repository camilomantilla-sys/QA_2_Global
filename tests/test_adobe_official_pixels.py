"""
Los pixeles oficiales de Adobe: uno universal y uno por linea de
negocio.

iSpot es el mismo para todo Adobe, asi que va SIN campaña y una fila
sola aplica a todas. DISQO cambia por linea de negocio --Acrobat,
Firefly, Everyone Can, STE, PGA, MLB-- y cada una trae su propio
`cid`, asi que va una fila por linea.

La columna Campaña es la etiqueta que se elige arriba en "Account /
Campaign": no tiene que coincidir con el nombre de la campaña en la
Traffic Sheet, que cambia cada trimestre.

Y la comprobacion es solo para 3P. Un site-served 1x1 no lleva el
pixel oficial de Adobe: lo pone el sitio en su propio tag, con sus
macros. Camilo: "solo aplica para 3p, no site served".

Run with pytest, or directly:
    python tests/test_adobe_official_pixels.py
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adobe_pixel_reconciliation import (  # noqa: E402
    AdobePixelCheck,
    AdobePixelReconciliation,
    PixelResult,
    _default_adobe_vendor_rows,
    _flag_official_pixel_drift,
    _official_pixels,
)
from core.team_roster import base_account  # noqa: E402

LINEAS = (
    "Adobe Acrobat", "Adobe Firefly", "Adobe Everyone Can",
    "Adobe STE", "Adobe PGA", "Adobe MLB",
)


# ── la tabla de fabrica ──────────────────────────────────────────────

def test_ispot_is_universal():
    filas = _default_adobe_vendor_rows()
    ispot = [f for f in filas if f["name"] == "iSpot"]
    assert len(ispot) == 1
    assert ispot[0]["campaign"] == ""
    assert "pi.ispot.tv" in ispot[0]["official_pixel"]


def test_disqo_has_one_row_per_line_of_business():
    filas = _default_adobe_vendor_rows()
    disqo = {f["campaign"]: f["official_pixel"]
             for f in filas if f["name"] == "DISQO"}
    assert set(disqo) == set(LINEAS)
    # Cada linea con su propio cid: eso es lo que las distingue.
    cids = {url.split("cid=")[1].split("&")[0] for url in disqo.values()}
    assert len(cids) == len(LINEAS), cids


def test_picking_a_line_of_business_gives_both_vendors():
    for linea in LINEAS:
        pixels = _official_pixels(linea)
        assert set(pixels) == {"iSpot", "DISQO"}, linea
        assert "pi.ispot.tv" in pixels["iSpot"]


def test_each_line_gets_its_own_disqo():
    acrobat = _official_pixels("Adobe Acrobat")["DISQO"]
    firefly = _official_pixels("Adobe Firefly")["DISQO"]
    assert acrobat != firefly


def test_with_no_line_picked_disqo_is_not_guessed():
    """
    Sin saber la linea de negocio no hay un DISQO correcto que
    comparar. Elegir uno al azar marcaria como drift un pixel que
    esta bien.
    """
    pixels = _official_pixels("")
    assert set(pixels) == {"iSpot"}


# ── la etiqueta sigue sabiendo de que cuenta es ──────────────────────

def test_a_line_of_business_still_resolves_to_its_account():
    # Si no, los tres desplegables de "By" se quedan sin el equipo.
    for linea in LINEAS:
        assert base_account(linea) == "Adobe", linea


# ── solo 3P ──────────────────────────────────────────────────────────

def _check(dimensions: str, evidencia: str) -> AdobePixelCheck:
    return AdobePixelCheck(
        placement_id="11154704",
        dimensions=dimensions,
        requirements=("DISQO",),
        result=PixelResult.PASS.value,
        tag_evidence=(f"row 12 | third_party_impression | {evidencia}",),
    )


def _run(check) -> AdobePixelCheck:
    out = AdobePixelReconciliation()
    out.checks = [check]
    return _flag_official_pixel_drift(out, "Adobe Acrobat").checks[0]


OTRO = "https://track.activemetering.com/pixel/v1/all/pixel.gif?cid=0000"


def test_a_3p_placement_with_a_different_pixel_is_flagged():
    salida = _run(_check("300x600", OTRO))
    assert salida.result == PixelResult.REVIEW.value
    assert "official pixel" in salida.message


def test_a_site_served_1x1_is_left_alone():
    salida = _run(_check("1x1", OTRO))
    assert salida.result == PixelResult.PASS.value


def test_the_official_pixel_still_passes_on_3p():
    bueno = _official_pixels("Adobe Acrobat")["DISQO"]
    assert _run(_check("300x600", bueno)).result == PixelResult.PASS.value


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

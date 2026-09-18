"""
Un 1x1 de Adobe: la TS dice N/A y QA2 no comprobaba nada.

En Adobe, un 1x1 lo sirve el publisher. El creativo de verdad nunca
pasa por Innovid, asi que la Traffic Sheet escribe "N/A" en Creative
Names -- no es un dato que falte, es que no aplica.

Pero "N/A" no genera ningun creativo esperado, y sin creativo esperado
el placement se quedaba sin UNA SOLA comprobacion de creativo: la
seccion salia vacia, nadie confirmaba que el pixel estuviera asignado,
y el reporte cerraba limpio. Camilo: "en adobe los 1x1 en la ts
aparecen como N/A porque en innovid se asigna un 1x1.gif. No me esta
leyendo eso la app".

Comparar el nombre no sirve: 1x1.gif es el mismo para toda la cuenta.
Que este asignado o no, si.

Sobre la solicitud real (GumGum / Acrobat, 2 placements nuevos), antes
salian 8 hallazgos y ninguno hablaba del creativo.

Run with pytest, or directly:
    python tests/test_site_served_tracker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN  # noqa: E402
from core.findings import FindingsBuffer, Status  # noqa: E402
from core.matching import (  # noqa: E402
    ActualCreative,
    ActualPlacement,
    ExpectedCreative,
    ExpectedPlacement,
    MatchResult,
    PlacementMatch,
    compare_placement,
)
from rules import creatives  # noqa: E402

PID = "11154704"
NAME = "GumGum_FY26Acrobat_CTX_EnhancedOLV_1x1_P3KPCSM"


def _pixel() -> ActualCreative:
    """El 1x1.gif de la cuenta: mismo id para todos los placements."""
    return ActualCreative(
        creative_id="50126",
        filename="1x1.gif",
        name="1x1.gif",
        row_type="TRACKER",
        third_party_id="12B9DHS9",
        enabled=True,
        status="Active",
    )


def build(*, with_pixel: bool, declares_creative: bool = False,
          in_innovid: bool = True):
    expected = ExpectedPlacement(
        placement_id=PID, name=NAME, dims="1x1", fmt="1x1",
    )
    if declares_creative:
        expected.creatives = [
            ExpectedCreative(name="banner.jpg", intent=GREEN, dims="1x1")
        ]

    actual = None
    if in_innovid:
        actual = ActualPlacement(
            placement_id=PID, name=NAME, status="Active",
        )
        if with_pixel:
            actual.creatives = [_pixel()]

    result = MatchResult()
    pm = PlacementMatch(placement_id=PID, expected=expected, actual=actual)
    if actual is not None:
        compare_placement(pm, result)
    result.matched = [pm]
    return result


def _findings(result) -> list:
    buffer = FindingsBuffer()
    creatives.evaluate(result, buffer)
    return [f for f in buffer.findings if f.rule_id == "CRE-002"]


def test_the_assigned_pixel_is_confirmed():
    found = _findings(build(with_pixel=True))
    assert len(found) == 1, found
    assert found[0].status == Status.PASS
    assert "1x1.gif" in (found[0].actual or "")


def test_a_placement_with_no_pixel_fails():
    """
    Era el silencio completo: ni PASS ni FAIL, la seccion vacia.
    """
    found = _findings(build(with_pixel=False))
    assert len(found) == 1, found
    assert found[0].status == Status.FAIL


def test_a_placement_missing_from_the_export_is_not_verified():
    # Lo que no se pudo mirar nunca pasa en verde.
    found = _findings(build(with_pixel=False, in_innovid=False))
    assert len(found) == 1, found
    assert found[0].status == Status.NOT_VERIFIED


def test_a_1x1_that_does_declare_a_creative_is_left_alone():
    """
    Entonces si hay algo que comparar, y lo juzga el resto de la
    regla. Esto solo cubre el hueco del N/A.
    """
    assert _findings(build(with_pixel=True, declares_creative=True)) == []


def test_a_display_placement_is_left_alone():
    result = build(with_pixel=True)
    result.matched[0].expected.dims = "300x600"
    result.matched[0].expected.fmt = "display"
    assert _findings(result) == []


def test_the_reason_says_why_there_is_no_name_to_compare():
    """
    Quien lea el reporte no tiene por que saber que "N/A" es correcto
    en una TS de Adobe.
    """
    reason = _findings(build(with_pixel=True))[0].reason or ""
    assert "publisher serves the creative" in reason
    assert "N/A" in reason


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

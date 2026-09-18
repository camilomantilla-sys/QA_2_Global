"""
La implementacion y los tags no son lo mismo, y no pueden compartir
veredicto.

Camilo: "yo implemento bien para adobe, pasa el QA y se puede demorar
2 dias en recibir pixels pero ya envie tags, entonces es diferente la
implementacion a los tags".

Metidos en un solo veredicto, un vendor que todavia no ha mandado su
pixel tiñe de rojo un reporte donde los placements, los creativos, las
fechas y las URLs estan perfectos. Quien lo recibe no sabe si tiene
que rehacer la implementacion o solo esperar un correo.

El veredicto general sigue siendo el peor de los dos -- con los tags
mal el QA no esta aprobado -- pero ahora el reporte dice CUAL de los
dos falla, y lo dice en la app, en el Excel y en el PDF.

Run with pytest, or directly:
    python tests/test_scope_guard_verdict.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.findings import (  # noqa: E402
    Domain, Finding, Severity, Status,
)
from core.verdict import (  # noqa: E402
    IMPLEMENTATION,
    TAGS,
    headline,
    overall,
    scope_of,
    verdicts_by_scope,
)


def _finding(domain: Domain, status: Status, severity: Severity) -> Finding:
    return Finding(
        rule_id="X-001",
        domain=domain,
        status=status,
        severity=severity,
        message="",
    )


PASS_IMPL = _finding(Domain.CREATIVE, Status.PASS, Severity.INFO)
FAIL_IMPL = _finding(Domain.CREATIVE, Status.FAIL, Severity.ERROR)
PASS_TAG = _finding(Domain.PIXEL, Status.PASS, Severity.INFO)
FAIL_TAG = _finding(Domain.PIXEL, Status.FAIL, Severity.ERROR)
REVIEW_TAG = _finding(Domain.TAG, Status.REVIEW, Severity.WARN)


# ── a que lado va cada hallazgo ──────────────────────────────────────

def test_pixels_and_tags_are_one_side():
    assert scope_of(PASS_TAG) == TAGS
    assert scope_of(REVIEW_TAG) == TAGS


def test_everything_that_was_trafficked_is_the_other():
    for domain in (
        Domain.CREATIVE, Domain.DATES, Domain.ROTATION, Domain.URL,
        Domain.SCOPE, Domain.IDENTITY, Domain.ATTRIBUTION,
        Domain.DIMENSIONS,
    ):
        assert scope_of(
            _finding(domain, Status.PASS, Severity.INFO)
        ) == IMPLEMENTATION, domain


# ── los dos veredictos ───────────────────────────────────────────────

def test_a_missing_pixel_does_not_sink_the_implementation():
    """El caso de Camilo, tal cual: tags enviados, pixel pendiente."""
    verdicts = verdicts_by_scope([PASS_IMPL, FAIL_TAG])
    assert verdicts[IMPLEMENTATION] == "PASSED"
    assert verdicts[TAGS] == "FAILED"


def test_the_overall_verdict_is_still_the_worse_of_the_two():
    # Con los tags mal, el QA no esta aprobado. Lo que cambia es que
    # ahora se sabe cual de los dos es.
    assert overall([PASS_IMPL, FAIL_TAG]) == "FAILED"
    assert overall([FAIL_IMPL, PASS_TAG]) == "FAILED"
    assert overall([PASS_IMPL, PASS_TAG]) == "PASSED"


def test_a_broken_implementation_does_not_blame_the_tags():
    verdicts = verdicts_by_scope([FAIL_IMPL, PASS_TAG])
    assert verdicts[IMPLEMENTATION] == "FAILED"
    assert verdicts[TAGS] == "PASSED"


# ── la frase que se lee primero ──────────────────────────────────────

def test_it_says_the_implementation_is_fine_and_where_to_look():
    said = headline([PASS_IMPL, FAIL_TAG])
    assert "implementation is fine" in said
    assert "tags and pixels" in said


def test_it_says_when_the_tags_are_not_the_problem():
    said = headline([FAIL_IMPL, PASS_TAG])
    assert "tags and pixels are fine" in said


def test_it_says_nothing_when_everything_passed():
    # Una frase que no aporta es una frase que se aprende a saltar.
    assert headline([PASS_IMPL, PASS_TAG]) == ""


def test_it_says_nothing_when_there_are_no_tags_in_the_request():
    assert headline([PASS_IMPL]) == ""
    assert headline([FAIL_IMPL]) == ""


def test_both_sides_bad_says_both():
    said = headline([FAIL_IMPL, REVIEW_TAG])
    assert "Both sides" in said


def test_an_unreadable_traffic_sheet_beats_everything():
    blocked = _finding(Domain.INGESTION, Status.FAIL, Severity.BLOCKER)
    assert headline([blocked, PASS_TAG]).startswith(
        "The files could not be read"
    )
    assert overall([blocked, PASS_TAG]) == "BLOCKED"


# ── y lo mismo llega a los reportes ──────────────────────────────────

def test_the_excel_and_the_pdf_carry_the_split():
    for module in ("excel_report", "pdf_report"):
        source = (
            Path(__file__).resolve().parents[1] / "core" / f"{module}.py"
        ).read_text(encoding="utf-8")
        assert "meta.scope_verdicts" in source, module
        assert "meta.scope_summary" in source, module


def test_the_labels_live_in_one_place():
    """
    Tres copias de la misma tabla es como terminan diciendo cosas
    distintas: el Excel y el PDF las leen de core.verdict.
    """
    app = (
        Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"
    ).read_text(encoding="utf-8")
    assert "VERDICT_LABELS = {" not in app
    assert "from core.verdict import" in app


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

"""
"70 to review", y nada mas.

El panel de firma decia cuantos faltaban y no de que eran: para
saberlo habia que bajar a la tabla y leer fila por fila. Y el selector
de grupos solo aparecia con DOS motivos o mas, asi que en el caso
tipico --los 70 creativos con la misma diferencia de fechas-- la unica
opcion visible era "Sign off all", que tampoco dice que se esta
firmando.

Camilo: "me gustaria tener una anotacion que sea, los 70 creativos por
firmar tienen una diferencia de fechas o algo asi, como para saber. y
si hay mas de una diferencia pues agrupar y firmar por grupos como
opcion tambien".

Run with pytest, or directly:
    python tests/test_review_panel_reasons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.findings import (  # noqa: E402
    Domain, EntityType, Finding, Severity, Status,
)
from core.review import bulk_groups, group_review_findings  # noqa: E402

APP = (
    Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"
).read_text(encoding="utf-8")


def _date_finding(name: str) -> Finding:
    return Finding(
        rule_id="INV-001", domain=Domain.DATES,
        entity_type=EntityType.CREATIVE,
        status=Status.REVIEW, severity=Severity.WARN,
        placement_id="11142248", creative_name=name,
        message=(
            f"{name} has no end date in Innovid, and the Traffic Sheet "
            "closes it on 2026-12-28"
        ),
    )


def _name_finding(name: str) -> Finding:
    return Finding(
        rule_id="INV-004", domain=Domain.IDENTITY,
        entity_type=EntityType.CREATIVE,
        status=Status.REVIEW, severity=Severity.WARN,
        placement_id="11142249", creative_name=name,
        message=f"{name} is in Innovid under another name",
    )


NOMBRES = [f"CHERRY-{i}_LOTION_20OZ-PUMP" for i in range(70)]


def test_the_reasons_are_countable_before_signing():
    """Lo que el panel enseña: cuantos, y de que."""
    reasons = group_review_findings([_date_finding(n) for n in NOMBRES])
    assert len(reasons) == 1
    (rule, reason), items = next(iter(reasons.items()))
    assert len(items) == 70
    assert "no end date in Innovid" in reason
    assert "INV-001" in rule


def test_two_different_reasons_stay_apart():
    reasons = group_review_findings(
        [_date_finding(n) for n in NOMBRES[:40]]
        + [_name_finding(n) for n in NOMBRES[40:]]
    )
    assert len(reasons) == 2
    assert sorted(len(items) for items in reasons.values()) == [30, 40]


def test_a_single_reason_is_still_a_signable_group():
    # Antes el selector solo salia con dos o mas, asi que con un solo
    # motivo no habia nada que dijera que se firmaba.
    groups = bulk_groups([_date_finding(n) for n in NOMBRES])
    assert len(groups) == 1
    label = next(iter(groups))
    assert "(70)" in label
    assert "no end date in Innovid" in label


# ── y el panel los usa ───────────────────────────────────────────────

def test_the_panel_lists_what_is_pending():
    assert "group_review_findings(review_findings)" in APP
    assert "What is waiting for a signature" in APP


def test_the_group_selector_shows_with_one_group_too():
    assert "if len(_panel_groups) > 1:" not in APP
    assert "if _panel_groups:" in APP


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

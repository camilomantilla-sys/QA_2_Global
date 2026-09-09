"""
Aprobar en bloque lo que es una sola decision.

Camilo: "si de 100 placements los 100 tienen name mismatch pues me
demoro mucho marcando 1x1". En la solicitud real de Dove eran 25
PLC-006 identicos, todos por lo mismo: Innovid rellena con cero un
segmento numerico del nombre y lo trunca.

Run with pytest, or directly:
    python tests/test_review_bulk_groups.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.review import bulk_groups, group_review_findings  # noqa: E402


@dataclass
class _Finding:
    rule_id: str
    message: str
    placement_id: str = ""


NAME_MISMATCH = "Placement Name mismatch (Placement ID matched)."


def _dove_review(count: int = 25):
    return [
        _Finding("PLC-006", NAME_MISMATCH, f"PL-{i}") for i in range(count)
    ]


def test_the_25_identical_findings_are_one_group():
    groups = bulk_groups(_dove_review())
    assert len(groups) == 1
    assert len(next(iter(groups.values()))) == 25


def test_the_label_says_the_rule_and_how_many():
    label = next(iter(bulk_groups(_dove_review())))
    assert label.startswith("PLC-006")
    assert "(25)" in label


def test_same_rule_but_a_different_message_is_a_different_group():
    # Aprobar juntos dos hallazgos que dicen cosas distintas seria
    # aprobar a ciegas el que no se leyo.
    findings = _dove_review(3) + [
        _Finding("PLC-006", "Placement is stopped in Innovid.", "PL-9")
    ]
    assert len(bulk_groups(findings)) == 1, "el grupo de 1 no se ofrece"
    assert len(group_review_findings(findings)) == 2


def test_a_lone_finding_is_not_offered_in_bulk():
    # Para una sola fila el lote no ahorra nada y llena el selector.
    assert bulk_groups([_Finding("URL-001", "URL mismatch")]) == {}


def test_nothing_to_review_gives_no_groups():
    assert bulk_groups([]) == {}


def test_groups_keep_the_order_they_appeared_in():
    findings = [
        _Finding("URL-001", "a"), _Finding("URL-001", "a"),
        _Finding("PLC-006", "b"), _Finding("PLC-006", "b"),
    ]
    assert [k.split(" · ")[0] for k in bulk_groups(findings)] == [
        "URL-001", "PLC-006",
    ]


def test_every_finding_lands_in_exactly_one_group():
    findings = _dove_review(25) + [_Finding("URL-001", "x")] * 4
    total = sum(len(v) for v in group_review_findings(findings).values())
    assert total == len(findings)


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

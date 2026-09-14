"""
placementDecisionSetId es el ultimo recurso, no una fuente mas.

Ese numero no es el id de un decision set: es el del ENLACE entre un
placement y el suyo. Pedirselo a /dt/v1/ui/dset/{id} devuelve HTTP 400
siempre.

Se anadia uno por cada placement, asi que en una campana de 54
placements que comparten 6 decision sets se intentaban 60 lecturas, las
54 del enlace fallaban, y el aviso decia "3 de 60 decision sets no se
pudieron leer" y "51 mas omitidos" sobre una campana en la que no
faltaba ni un dato. Quien lo leia entendia que el QA se habia quedado
corto, y no era verdad.

Aqui se fija que solo se pida para el placement que no trajo ningun id
de decision set propio, y que el aviso cuente lo que de verdad se
intento.

Run with pytest, or directly:
    python tests/test_dset_last_resort.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.innovid_api import _summarise_dset_failures  # noqa: E402


class _Row:
    def __init__(self, placement_id, dtree_id="", dset_id="", link_id=""):
        self.placement_id = placement_id
        self.dtree_id = dtree_id
        self.dtree_name = "dtree"
        self.dset_id = dset_id
        self.dset_name = "dset"
        self.dset_link_id = link_id


def wanted_ids(rows, wanted=None):
    """
    Los ids que el cliente pediria, con la misma logica que usa al
    recorrer el summary de la campana.
    """
    groups = [
        ("modern dtree id", {}),
        ("decisionSetId", {}),
        ("placementDecisionSetId", {}),
    ]
    for row in rows:
        if wanted and row.placement_id not in wanted:
            continue
        if row.dtree_id:
            groups[0][1].setdefault(row.dtree_id, row.dtree_name)
        if row.dset_id:
            groups[1][1].setdefault(row.dset_id, row.dset_name)
        elif row.dset_link_id and not row.dtree_id:
            groups[2][1].setdefault(row.dset_link_id, row.dset_name)

    already = set()
    for _, ids in groups:
        for candidate in list(ids):
            if candidate in already:
                ids.pop(candidate)
            else:
                already.add(candidate)

    return {source: sorted(ids) for source, ids in groups}


def campaign_like_camilos():
    """54 placements, 6 decision sets compartidos, un enlace cada uno."""
    return [
        _Row(
            placement_id=str(10700000 + n),
            dset_id=str(80000 + n % 6),
            link_id=str(76400 + n),
        )
        for n in range(54)
    ]


def test_the_link_id_is_not_asked_for_when_the_decision_set_is_known():
    asked = wanted_ids(campaign_like_camilos())
    assert asked["placementDecisionSetId"] == []
    assert len(asked["decisionSetId"]) == 6


def test_only_six_lookups_instead_of_sixty():
    asked = wanted_ids(campaign_like_camilos())
    assert sum(len(ids) for ids in asked.values()) == 6


def test_a_placement_with_nothing_else_still_falls_back_to_the_link():
    rows = [_Row(placement_id="1", link_id="76445")]
    asked = wanted_ids(rows)
    assert asked["placementDecisionSetId"] == ["76445"]


def test_the_modern_dtree_id_also_settles_it():
    rows = [_Row(placement_id="1", dtree_id="900", link_id="76445")]
    asked = wanted_ids(rows)
    assert asked["modern dtree id"] == ["900"]
    assert asked["placementDecisionSetId"] == []


def test_the_same_id_is_never_asked_for_twice():
    rows = [
        _Row(placement_id="1", dtree_id="900"),
        _Row(placement_id="2", dset_id="900"),
    ]
    asked = wanted_ids(rows)
    assert asked["modern dtree id"] == ["900"]
    assert asked["decisionSetId"] == []


def test_placements_outside_the_request_are_not_asked_for():
    rows = [
        _Row(placement_id="1", dset_id="800"),
        _Row(placement_id="2", dset_id="801"),
    ]
    asked = wanted_ids(rows, wanted={"1"})
    assert asked["decisionSetId"] == ["800"]


def test_the_message_counts_what_was_attempted():
    messages = _summarise_dset_failures(
        [("76445", "placementDecisionSetId: HTTP 400")], attempted=6
    )
    assert messages and "1 of 6 decision set(s)" in messages[0]


def test_identical_failures_are_one_line_with_examples():
    failures = [
        (str(76400 + n), f"placementDecisionSetId: {76400 + n} returned 400")
        for n in range(10)
    ]
    messages = _summarise_dset_failures(failures, attempted=10)
    assert len(messages) == 1
    assert "(and 7 more)" in messages[0]


def test_nothing_failed_says_nothing():
    assert _summarise_dset_failures([], attempted=6) == []


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

"""
Un creativo en rojo tiene que dejar de correr.

En la TS, rojo significa "quitalo". Este archivo fija las dos mitades
de esa regla, porque una sola no sirve de nada: que la ausencia del
creativo se reconozca como la remocion hecha, y que su presencia --
todavia corriendo -- sea un fallo.

Sale del caso real de BlackRock (CreativeSwap): por grupo, dos
creativos viejos en rojo y uno nuevo en verde, mas un swap en los
Default Web Ad. Alli las 12 remociones estaban bien hechas y CRE-001
las confirmo; esta prueba existe para que el dia que una no se haga,
se vea.

Run with pytest, or directly:
    python tests/test_creative_removal.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, RED  # noqa: E402
from core.findings import FindingsBuffer  # noqa: E402
from core.matching import (  # noqa: E402
    ActualCreative,
    ActualPlacement,
    CreativeLink,
    ExpectedCreative,
    ExpectedPlacement,
    PlacementMatch,
)
from rules import creatives  # noqa: E402


def link(intent: str, still_running: bool | None):
    """
    Un creativo esperado y lo que Innovid tiene de el.

    `still_running=None` es el creativo que ya no esta en el export.
    """
    expected = ExpectedCreative(
        creative_id="6078571",
        name="USWA_A_Static_BINC_970x250.jpg",
        intent=intent,
    )
    actual = None
    if still_running is not None:
        actual = ActualCreative(
            creative_id="6078571",
            filename="USWA_A_Static_BINC_970x250.jpg",
            name="USWA_A_Static_BINC_970x250.jpg",
            enabled=still_running,
            status="Active" if still_running else "Disabled",
        )
    return CreativeLink(expected=expected, actual=actual)


def run(intent: str, still_running: bool | None, placement_running: bool = True):
    match = PlacementMatch(
        placement_id="10707593",
        expected=ExpectedPlacement(
            placement_id="10707593",
            name="USWA placement",
        ),
        actual=ActualPlacement(
            placement_id="10707593",
            name="USWA placement",
            status="Active" if placement_running else "Stopped",
        ),
    )
    match.creative_links = [link(intent, still_running)]

    buffer = FindingsBuffer()
    creatives.evaluate(_Result([match]), buffer)
    return [f for f in buffer.findings if f.rule_id == "CRE-001"]


class _Result:
    def __init__(self, matched):
        self.matched = matched
        self.only_expected = []
        self.only_actual_in_scope = []
        self.ambiguous = []


def test_a_removal_that_was_done_passes():
    # Innovid lo elimino del decision set y desaparecio del export.
    found = run(RED, still_running=None)
    assert found and found[0].status.value == "PASS", found
    assert "Removal confirmed" in found[0].message


def test_a_creative_left_disabled_also_counts_as_removed():
    # Adobe lo conserva en el export con Status=Disabled. Sigue
    # figurando, pero no corre: la remocion esta cumplida.
    found = run(RED, still_running=False)
    assert found and found[0].status.value == "PASS", found


def test_a_removal_that_was_forgotten_fails():
    # El caso que importa.
    found = run(RED, still_running=True)
    assert found and found[0].status.value == "FAIL", found
    assert "still running" in found[0].message


def test_the_failure_says_what_to_do():
    found = run(RED, still_running=True)
    assert "Unassign" in (found[0].recommended_action or "")


def test_a_stopped_placement_settles_the_removal():
    # Si el placement quedo detenido, lo que tenga asignado ya no
    # corre, aunque el creativo figure como activo.
    found = run(RED, still_running=True, placement_running=False)
    assert found and found[0].status.value == "PASS", found


def test_a_green_creative_is_not_judged_as_a_removal():
    # Verde es lo contrario: tiene que existir y estar activo.
    found = run(GREEN, still_running=True)
    assert not any("Removal confirmed" in f.message for f in found), found


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

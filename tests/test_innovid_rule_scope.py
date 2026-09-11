"""
Dos cosas que QA marcaba y estaban bien traficadas.

Las dos salen del caso BlackRock CreativeSwap, y las dos ponian en
rojo -- o en revision -- un QA correcto:

  Un creativo en rojo que ya no esta en el decision set salia como
  "is in the Traffic Sheet but not in the decision set". No falta:
  se quito, que es justo lo que la TS pedia. En la misma tabla, la
  columna de al lado ya decia "Removed (confirmed)".

  Un placement sin Verification Partner pedia revision. Pero el
  partner es como Innovid implementa DV Blocking, y esa TS dice "DV
  Event Monitoring": no hay nada que configurar.

Run with pytest, or directly:
    python tests/test_innovid_rule_scope.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, RED, WHITE  # noqa: E402
from core.findings import FindingsBuffer  # noqa: E402
from core.innovid_reconciliation import (  # noqa: E402
    MISSING_IN_INNOVID,
    CreativeFlightCheck,
    InnovidReconciliation,
    VerificationPartnerCheck,
    _asks_for_dv_blocking,
)
from rules import innovid  # noqa: E402


def flights(intent: str):
    reconciliation = InnovidReconciliation()
    reconciliation.flights = [
        CreativeFlightCheck(
            placement_id="10707593",
            creative_name="USWA_B_Animated_BINC_970x250.gif",
            status=MISSING_IN_INNOVID,
            intent=intent,
        )
    ]
    buffer = FindingsBuffer()
    innovid.evaluate(reconciliation, buffer)
    return [f for f in buffer.findings if f.rule_id == "INV-001"]


def partners(expected: bool, configured: bool):
    reconciliation = InnovidReconciliation()
    reconciliation.partners = [
        VerificationPartnerCheck(
            placement_id="10707593",
            configured=configured,
            actual_partner="DoubleVerify" if configured else "",
            partner_expected=expected,
        )
    ]
    buffer = FindingsBuffer()
    innovid.evaluate(reconciliation, buffer)
    return [f for f in buffer.findings if f.rule_id == "INV-003"]


class _Expected:
    def __init__(self, vendors):
        self.vendors = vendors


class _Match:
    def __init__(self, vendors):
        self.expected = _Expected(vendors)


def test_a_removed_creative_missing_from_the_decision_set_passes():
    found = flights(RED)
    assert found and found[0].status.value == "PASS", found
    assert "as the Traffic Sheet asked" in found[0].message


def test_a_new_creative_missing_from_the_decision_set_still_fails():
    # El caso que la regla existe para encontrar.
    found = flights(GREEN)
    assert found and found[0].status.value == "FAIL", found


def test_a_context_creative_is_not_judged_at_all():
    assert flights(WHITE) == []


def test_monitoring_only_needs_no_verification_partner():
    found = partners(expected=False, configured=False)
    assert found and found[0].status.value == "PASS", found
    assert "doesn't ask for DV Blocking" in found[0].message


def test_dv_blocking_without_a_partner_still_asks():
    found = partners(expected=True, configured=False)
    assert found and found[0].status.value == "REVIEW", found


def test_a_partner_that_is_set_passes_either_way():
    for expected in (True, False):
        found = partners(expected=expected, configured=True)
        assert found and found[0].status.value == "PASS", (expected, found)


def test_dv_event_monitoring_is_not_blocking():
    # Literal de la TS de BlackRock.
    assert not _asks_for_dv_blocking(_Match("DV Event Monitoring, Dynata"))


def test_dv_monitoring_blocking_is_blocking():
    assert _asks_for_dv_blocking(_Match("DV Monitoring / Blocking"))


def test_no_vendors_asks_for_nothing():
    assert not _asks_for_dv_blocking(_Match(""))


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

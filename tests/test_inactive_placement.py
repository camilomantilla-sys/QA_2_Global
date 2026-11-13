"""
Un placement desactivado en Innovid (en gris) se dice tal cual (FB-25).

Una solicitud posterior apago esos placements. QA2 decia "No
Verification Partner is set" y "no decision set could be read", que
suenan a errores de trafico. Ahora dice que el placement esta
desactivado y no revisa lo que ya no corre.

Run with pytest, or directly:
    python tests/test_inactive_placement.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN  # noqa: E402
from core.innovid_api import InnovidFetchResult, parse_summary_response  # noqa: E402
from core.innovid_reconciliation import reconcile  # noqa: E402
from core.matching import ExpectedCreative  # noqa: E402
from tests.test_innovid_reconciliation import V1, _findings, _ts  # noqa: E402


def innovid(status: str) -> InnovidFetchResult:
    rows = parse_summary_response({"items": [
        {"placementId": "11310594", "level": "PLACEMENT", "status": status,
         "startDate": "2026-09-14", "endDate": "2026-10-31"},
    ]})
    return InnovidFetchResult(campaign_id="337552", placements=rows)


def rules(findings):
    return {(f.rule_id, f.status.name) for f in findings.findings}


def ts():
    return _ts("11310594", [ExpectedCreative(name=V1, intent=GREEN)])


def test_a_stopped_placement_says_it_is_deactivated():
    result = reconcile(ts(), innovid("Stopped"))
    assert result.inactive == [("11310594", "Stopped")]
    found = rules(_findings(result))
    assert found == {("INV-005", "INFO")}, found


def test_an_active_placement_still_gets_its_checks():
    result = reconcile(ts(), innovid("Active"))
    assert result.inactive == []
    found = rules(_findings(result))
    assert ("INV-001", "NOT_VERIFIED") in found
    assert not any(rule == "INV-005" for rule, _ in found)


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failed else 0)

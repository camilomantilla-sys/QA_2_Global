"""
Un placement apagado en Innovid frente a lo que pide la TS (FB-25).

Caso real: la TS era de una solicitud vieja y una posterior apago esos
placements (en gris en Innovid). QA2 daba PASSED con un Info, o Reviews
que hablaban de otra cosa ("No Verification Partner", "no decision set
could be read"). La lectura correcta:

- la TS desasigna el placement entero -> apagado es lo pedido (PLC-002);
- la TS le pide cualquier otra cosa -> lo quiere corriendo, y apagado es
  un Review que impide el PASSED: PLC-003 si ya lo dice el export,
  INV-005 si solo lo dice Innovid en vivo (lo apagaron despues).

Run with pytest, or directly:
    python tests/test_inactive_placement.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN  # noqa: E402
from core.findings import FindingsBuffer  # noqa: E402
from core.innovid_api import InnovidFetchResult, parse_summary_response  # noqa: E402
from core.innovid_reconciliation import reconcile  # noqa: E402
from core.matching import ExpectedCreative  # noqa: E402
from core.verdict import overall  # noqa: E402
from parsers.ts_parser import REQ_CREATIVE_REMOVE, REQ_NEW_PLACEMENT  # noqa: E402
from rules import placements  # noqa: E402
from tests.test_innovid_reconciliation import V1, _findings, _ts  # noqa: E402

PID = "11310594"


def innovid(status: str) -> InnovidFetchResult:
    rows = parse_summary_response({"items": [
        {"placementId": PID, "level": "PLACEMENT", "status": status,
         "startDate": "2026-09-14", "endDate": "2026-10-31"},
    ]})
    return InnovidFetchResult(campaign_id="337552", placements=rows)


def ts(request_type=REQ_NEW_PLACEMENT, export_status="Available"):
    match = _ts(PID, [ExpectedCreative(name=V1, intent=GREEN)])
    pm = match.matched[0]
    pm.expected.request_type = request_type
    pm.actual = NS(status=export_status, creatives=[])
    return match


def rules(findings):
    return {(f.rule_id, f.status.name) for f in findings.findings}


def export_rules(match):
    buffer = FindingsBuffer()
    for pm in match.matched:
        placements._evaluate_switched_off(pm, buffer)
    return buffer


# --- apagado solo en Innovid en vivo (los exports son de antes) ---------

def test_turned_off_after_the_exports_is_one_review():
    result = reconcile(ts(), innovid("Stopped"))
    assert result.inactive == [(PID, "Stopped")]
    assert rules(_findings(result)) == {("INV-005", "REVIEW")}


def test_a_switched_off_placement_keeps_the_request_from_passing():
    findings = _findings(reconcile(ts(), innovid("Stopped"))).findings
    assert overall(findings) != "PASSED"


# --- apagado ya en el export ---------------------------------------------

def test_the_export_already_shows_it_off():
    match = ts(export_status="Stopped")
    assert rules(export_rules(match)) == {("PLC-003", "REVIEW")}
    # Innovid en vivo no lo repite ni pide revisar lo que no corre.
    assert rules(_findings(reconcile(match, innovid("Stopped")))) == set()


def test_the_message_says_what_the_ts_asked_for():
    finding = export_rules(ts(export_status="Disabled")).findings[0]
    assert "new placement" in finding.message
    assert "Disabled" in finding.message


# --- lo que la TS si pide apagado ----------------------------------------

def test_a_full_disassignment_is_meant_to_be_off():
    match = ts(request_type=REQ_CREATIVE_REMOVE, export_status="Stopped")
    assert rules(export_rules(match)) == set()
    result = reconcile(match, innovid("Stopped"))
    assert result.inactive == []
    assert rules(_findings(result)) == set()


# --- encendido: nada cambia ----------------------------------------------

def test_a_running_placement_gets_its_usual_checks():
    match = ts()
    assert rules(export_rules(match)) == set()
    found = rules(_findings(reconcile(match, innovid("Active"))))
    assert ("INV-001", "NOT_VERIFIED") in found
    assert not any(rule == "INV-005" for rule, _ in found)


def test_draft_is_not_switched_off():
    assert rules(export_rules(ts(export_status="Draft"))) == set()


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

"""
La Traffic Sheet contra lo que Innovid realmente tiene.

Los casos vienen de las dos campanas verificadas a mano:
  323492 -- placement del 20 de julio con creativo que arranca el 24
  327957 -- rotacion secuencial correcta, que no debe generar nada

Run with pytest, or directly:
    python tests/test_innovid_reconciliation.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, RED, WHITE  # noqa: E402
from core.findings import FindingsBuffer  # noqa: E402
from core.innovid_api import (  # noqa: E402
    InnovidFetchResult,
    parse_dset_response,
    parse_summary_response,
)
from core.innovid_reconciliation import (  # noqa: E402
    AMBIGUOUS,
    EXTRA_IN_INNOVID,
    MATCHED,
    MISSING_IN_INNOVID,
    reconcile,
)
from core.matching import ExpectedCreative, ExpectedPlacement  # noqa: E402
from rules import innovid as innovid_rules  # noqa: E402


# --- lo minimo de un match_result para estas pruebas -------------

@dataclass
class FakeMatch:
    placement_id: str
    expected: ExpectedPlacement


@dataclass
class FakeMatchResult:
    matched: list = field(default_factory=list)


def _ts(placement_id: str, creatives: list[ExpectedCreative]) -> FakeMatchResult:
    expected = ExpectedPlacement(
        placement_id=placement_id,
        start=date(2026, 9, 14),
        end=date(2026, 10, 31),
        creatives=creatives,
    )
    return FakeMatchResult(matched=[FakeMatch(placement_id, expected)])


def _innovid(placement_id: str, dset_id: int, nodes: list,
             partner: str = "DoubleVerify") -> InnovidFetchResult:
    rows = parse_summary_response({"items": [
        {"placementId": placement_id, "level": "PLACEMENT",
         "startDate": "2026-09-14", "endDate": "2026-10-31",
         "verificationPartner": partner or None,
         "verificationStatus": "Applied" if partner else None},
        {"placementId": placement_id, "level": "PLACEMENT-CREATIVE",
         "decisionSetId": dset_id, "decisionSetName": "Display 300x600"},
    ]})
    dset = {"id": dset_id, "name": "Display 300x600",
            "servingMethod": "Weighted Rotation", "nodes": nodes}
    return InnovidFetchResult(
        campaign_id="327957", placements=rows,
        creative_nodes=parse_dset_response(dset),
    )


def _node(name, start, end, weight=1, node_id=1, creative_id=6389150):
    return {"id": node_id,
            "serving": {"id": creative_id, "name": name},
            "startTimestamp": f"{start} 00:00:00",
            "endTimestamp": f"{end} 23:59:00" if end else None,
            "weight": weight}


V1 = "PC_40938_TARG_DMC_Naturals_PbR_Banners_V1_300x600.jpg"
V2 = "PC_40938_TARG_DMC_Naturals_PbR_Banners_V2_300x600.jpg"


def _findings(reconciliation):
    buffer = FindingsBuffer()
    innovid_rules.evaluate(reconciliation, buffer)
    return buffer


def _by_rule(buffer, rule_id):
    return [f for f in buffer.findings if f.rule_id == rule_id]


# --- fechas de vuelo ---------------------------------------------

def test_matching_dates_pass():
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN,
                         start=date(2026, 9, 14), end=date(2026, 9, 26)),
        ExpectedCreative(name=V1, intent=GREEN,
                         start=date(2026, 9, 27), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-09-26", node_id=3),
        _node(V1, "2026-09-27", "2026-10-31", node_id=4),
    ])

    rec = reconcile(ts, got)
    assert len(rec.flights) == 2
    assert all(c.status == MATCHED for c in rec.flights)

    findings = _by_rule(_findings(rec), "INV-001")
    assert all(f.status.name == "PASS" for f in findings)


def test_a_creative_flighting_late_fails():
    """El caso del Frosty: la TS pide el 14, Innovid lo tiene el 27."""
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN,
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-27", "2026-10-31"),
    ])

    findings = _by_rule(_findings(reconcile(ts, got)), "INV-001")
    fails = [f for f in findings if f.status.name == "FAIL"]

    assert len(fails) == 1
    assert "2026-09-14" in fails[0].expected
    assert "2026-09-27" in fails[0].actual


def test_a_creative_the_ts_asks_for_and_innovid_lacks_fails():
    ts = _ts("11087616", [
        ExpectedCreative(name=V1, intent=GREEN,
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [_node(V2, "2026-09-14", "2026-10-31")])

    rec = reconcile(ts, got)
    statuses = {c.creative_name: c.status for c in rec.flights}

    assert statuses[V1] == MISSING_IN_INNOVID
    assert statuses[V2] == EXTRA_IN_INNOVID


def test_a_white_creative_is_context_and_makes_no_finding():
    # Convencion del proyecto: los WHITE se matchean pero no generan
    # hallazgos. Sin esto, el contenido preexistente del decision set
    # llenaria el reporte de ruido.
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=WHITE,
                         start=date(2026, 9, 14), end=date(2026, 9, 26)),
    ])
    got = _innovid("11087616", 40316, [_node(V2, "2026-10-01", "2026-10-31")])

    rec = reconcile(ts, got)
    assert rec.flights[0].intent == WHITE
    assert _by_rule(_findings(rec), "INV-001") == []


def test_a_ts_without_creative_dates_is_not_verified_not_passed():
    """
    Lo mas importante de esta regla.

    Una TS que no declara fechas por creativo no prueba que Innovid
    este bien. Decir PASS ahi seria aprobar una comparacion que nunca
    ocurrio.
    """
    ts = _ts("11087616", [ExpectedCreative(name=V2, intent=GREEN)])
    got = _innovid("11087616", 40316, [_node(V2, "2026-09-27", "2026-10-31")])

    findings = _by_rule(_findings(reconcile(ts, got)), "INV-001")

    assert len(findings) == 1
    assert findings[0].status.name == "NOT_VERIFIED"


def test_a_duplicate_creative_is_not_verified_rather_than_guessed():
    """Elegir mal daria un veredicto sin fundamento."""
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN,
                         start=date(2026, 9, 14), end=date(2026, 9, 26)),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-09-26", node_id=1),
        _node(V2, "2026-10-01", "2026-10-31", node_id=2),
    ])

    rec = reconcile(ts, got)
    assert rec.flights[0].status == AMBIGUOUS
    assert rec.flights[0].candidates == 2

    findings = _by_rule(_findings(rec), "INV-001")
    assert findings[0].status.name == "NOT_VERIFIED"


def test_a_placement_innovid_never_returned_is_unchecked():
    ts = _ts("99999999", [ExpectedCreative(name=V2, intent=GREEN)])
    got = _innovid("11087616", 40316, [_node(V2, "2026-09-14", "2026-10-31")])

    rec = reconcile(ts, got)
    assert rec.flights == []
    assert rec.unchecked and rec.unchecked[0][0] == "99999999"

    findings = _by_rule(_findings(rec), "INV-001")
    assert findings[0].status.name == "NOT_VERIFIED"


def test_the_default_creative_is_not_compared():
    # Su timestamp es cuando se adjunto, no un vuelo.
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN,
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31"),
        {"id": 99, "serving": {"id": 6389150, "name": V2},
         "startTimestamp": "2026-08-31 10:07:12", "endTimestamp": None,
         "isDefault": True},
    ])

    rec = reconcile(ts, got)
    assert len(rec.flights) == 1, "el default no entra como duplicado"
    assert rec.flights[0].status == MATCHED


def test_filename_differences_do_not_break_the_match():
    # La TS escribe el nombre sin extension y con espacios.
    ts = _ts("11087616", [
        ExpectedCreative(name="PC_40938_TARG_DMC_Naturals_PbR_Banners_V2_300x600",
                         intent=GREEN,
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [_node(V2, "2026-09-14", "2026-10-31")])

    rec = reconcile(ts, got)
    assert rec.flights[0].status == MATCHED


# --- peso de rotacion --------------------------------------------

def test_matching_weight_passes_and_a_different_one_fails():
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN, rotation_weight="1",
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=1),
    ])
    assert _by_rule(_findings(reconcile(ts, got)), "INV-002")[0].status.name == "PASS"

    ts_50 = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN, rotation_weight="50",
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got_5 = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=5),
    ])
    assert _by_rule(_findings(reconcile(ts_50, got_5)), "INV-002")[0].status.name == "FAIL"


def test_even_is_an_instruction_not_a_number_to_compare():
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN, rotation_weight="Even",
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=1),
    ])
    assert _by_rule(_findings(reconcile(ts, got)), "INV-002") == []


# --- verification partner ----------------------------------------

def test_a_configured_verification_partner_passes():
    ts = _ts("11087616", [ExpectedCreative(name=V2, intent=GREEN)])
    got = _innovid("11087616", 40316, [_node(V2, "2026-09-14", "2026-10-31")])

    findings = _by_rule(_findings(reconcile(ts, got)), "INV-003")
    assert findings[0].status.name == "PASS"
    assert "DoubleVerify" in findings[0].message


def test_a_missing_verification_partner_is_a_review_not_a_failure():
    # Muchas campanas legitimamente no llevan. Afirmar que esta mal
    # seria inventar un requisito.
    ts = _ts("11087616", [ExpectedCreative(name=V2, intent=GREEN)])
    got = _innovid("11087616", 40316,
                   [_node(V2, "2026-09-14", "2026-10-31")], partner="")

    findings = _by_rule(_findings(reconcile(ts, got)), "INV-003")
    assert findings[0].status.name == "REVIEW"


# --- sin Innovid --------------------------------------------------

def test_no_innovid_result_means_no_findings_at_all():
    # QA2 tiene que seguir corriendo cuando Innovid no responde.
    ts = _ts("11087616", [ExpectedCreative(name=V2, intent=GREEN)])
    rec = reconcile(ts, None)

    assert rec.flights == [] and rec.partners == []
    assert _findings(rec).findings == []

def test_a_request_with_no_creatives_makes_no_extra_noise():
    """
    Caso real: TS_3360_UNIC_US_MDS declara 15 placements de default
    web ads y ningun creativo en Creative Rotations.

    Sin esto, cada creativo que Innovid tenga se reportaba como
    "extra", llenando el reporte de hallazgos sobre creativos que
    nadie pidio revisar.
    """
    ts = _ts("11087616", [])
    got = _innovid("11087616", 40316, [
        _node(V1, "2026-09-14", "2026-10-31", node_id=1),
        _node(V2, "2026-09-27", "2026-10-31", node_id=2),
    ])

    rec = reconcile(ts, got)

    assert rec.flights == [], "nada que comparar es nada que reportar"
    assert len(rec.unchecked) == 1
    assert "declares no creatives" in rec.unchecked[0][1]

    # Pero el Verification Partner si se revisa: no depende de que la
    # TS declare creativos.
    assert len(rec.partners) == 1
    findings = _by_rule(_findings(rec), "INV-003")
    assert findings and findings[0].status.name == "PASS"


def test_extra_creatives_are_still_reported_when_the_ts_declares_some():
    # La regla anterior no debe silenciar el caso legitimo.
    ts = _ts("11087616", [
        ExpectedCreative(name=V1, intent=GREEN,
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [
        _node(V1, "2026-09-14", "2026-10-31", node_id=1),
        _node(V2, "2026-09-27", "2026-10-31", node_id=2),
    ])

    rec = reconcile(ts, got)
    extras = [c for c in rec.flights if c.status == EXTRA_IN_INNOVID]
    assert len(extras) == 1 and extras[0].creative_name == V2


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
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
        else:
            passed += 1
            print(f"ok   {name}")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

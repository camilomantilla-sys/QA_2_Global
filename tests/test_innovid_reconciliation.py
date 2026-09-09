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


def _ts(placement_id: str, creatives: list[ExpectedCreative],
        fmt: str = "display", dims: str = "300x600") -> FakeMatchResult:
    expected = ExpectedPlacement(
        placement_id=placement_id,
        start=date(2026, 9, 14),
        end=date(2026, 10, 31),
        creatives=creatives,
        fmt=fmt,
        dims=dims,
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
V3 = "PC_40938_TARG_DMC_Naturals_PbR_Banners_V3_300x600.jpg"


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
    # Un peso de rotacion es relativo, asi que se compara el reparto,
    # no el numero suelto: la TS trae fracciones de Excel y en Innovid
    # se escriben porcentajes enteros.
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN, rotation_weight="0.25",
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
        ExpectedCreative(name=V3, intent=GREEN, rotation_weight="0.75",
                         start=date(2026, 9, 14), end=date(2026, 10, 31)),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=25),
        _node(V3, "2026-09-14", "2026-10-31", node_id=2, creative_id=6389151, weight=75),
    ])
    statuses = {
        f.status.name
        for f in _by_rule(_findings(reconcile(ts, got)), "INV-002")
    }
    assert statuses == {"PASS"}

    got_swapped = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=75),
        _node(V3, "2026-09-14", "2026-10-31", node_id=2, creative_id=6389151, weight=25),
    ])
    assert "FAIL" in {
        f.status.name
        for f in _by_rule(_findings(reconcile(ts, got_swapped)), "INV-002")
    }


def test_innovids_whole_percent_is_not_a_failure_against_excels_decimals():
    # Innovid solo admite enteros en el decision set: un 13,33% de la
    # TS se traduce a 13%. Exigir el decimal marcaria como error algo
    # que nadie puede corregir.
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN,
                         rotation_weight="0.13333333333333333"),
        ExpectedCreative(name=V3, intent=GREEN,
                         rotation_weight="0.8666666666666667"),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=13),
        _node(V3, "2026-09-14", "2026-10-31", node_id=2, creative_id=6389151, weight=87),
    ])
    statuses = {
        f.status.name
        for f in _by_rule(_findings(reconcile(ts, got)), "INV-002")
    }
    assert statuses == {"PASS"}


def test_a_lone_creative_takes_the_whole_rotation_whatever_is_written():
    # Consecuencia deliberada de comparar el reparto: si el decision
    # set tiene un solo creativo, se lleva el 100% diga 50 o diga 5.
    # No es un peso mal puesto -- no hay con quien repartir. Que
    # falten los demas creativos lo reporta INV-001, que es la
    # pregunta de verdad en ese caso.
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN, rotation_weight="50"),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=5),
    ])
    statuses = {
        f.status.name
        for f in _by_rule(_findings(reconcile(ts, got)), "INV-002")
    }
    assert statuses == {"PASS"}


def test_even_becomes_the_share_it_means():
    # "Even" es que roten por igual. Con el grupo entero en Even, cada
    # creativo se lleva 100/N y ya se puede comparar contra Innovid,
    # que es lo que pidio Camilo.
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN, rotation_weight="Even"),
        ExpectedCreative(name=V3, intent=GREEN, rotation_weight="Even"),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=50),
        _node(V3, "2026-09-14", "2026-10-31", node_id=2, creative_id=6389151, weight=50),
    ])
    statuses = {
        f.status.name
        for f in _by_rule(_findings(reconcile(ts, got)), "INV-002")
    }
    assert statuses == {"PASS"}


def test_even_against_an_uneven_rotation_fails():
    ts = _ts("11087616", [
        ExpectedCreative(name=V2, intent=GREEN, rotation_weight="Even"),
        ExpectedCreative(name=V3, intent=GREEN, rotation_weight="Even"),
    ])
    got = _innovid("11087616", 40316, [
        _node(V2, "2026-09-14", "2026-10-31", weight=90),
        _node(V3, "2026-09-14", "2026-10-31", node_id=2, creative_id=6389151, weight=10),
    ])
    assert "FAIL" in {
        f.status.name
        for f in _by_rule(_findings(reconcile(ts, got)), "INV-002")
    }


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

def test_a_1x1_is_not_asked_for_a_verification_partner():
    """
    Regla del negocio, de Camilo: a los 1x1 no se les valida
    Verification Partner. El sitio sirve el creativo y no hay nada
    que verificar, asi que pedir revision seria ruido sobre
    placements correctos.
    """
    ts = _ts("11102553", [ExpectedCreative(name=V2, intent=GREEN)],
             fmt="1x1", dims="1x1")
    got = _innovid("11102553", 40316,
                   [_node(V2, "2026-09-14", "2026-10-31")], partner="")

    rec = reconcile(ts, got)
    assert rec.partners[0].site_served_1x1 is True
    assert _by_rule(_findings(rec), "INV-003") == []


def test_a_1x1_recognised_by_dimensions_alone():
    # El formato puede no venir derivado; las dimensiones bastan.
    ts = _ts("11102553", [ExpectedCreative(name=V2, intent=GREEN)],
             fmt="", dims="1x1")
    got = _innovid("11102553", 40316,
                   [_node(V2, "2026-09-14", "2026-10-31")], partner="")

    assert _by_rule(_findings(reconcile(ts, got)), "INV-003") == []


def test_a_display_placement_is_still_checked():
    # La exencion no puede tragarse el caso normal.
    ts = _ts("11102553", [ExpectedCreative(name=V2, intent=GREEN)],
             fmt="display", dims="300x600")
    got = _innovid("11102553", 40316,
                   [_node(V2, "2026-09-14", "2026-10-31")], partner="")

    findings = _by_rule(_findings(reconcile(ts, got)), "INV-003")
    assert findings and findings[0].status.name == "REVIEW"


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


# ---------------------------------------------------------------- sello de subida

DOVE_TS = (
    "Scent-and-Softness-Your-Skin-Deserves-Both_Scrapbook_Core-Body-Wash"
    "_Renew_NONE_NA_160x600-NA_DISP_08s_BYNW_EN_STP_MikMak_MOD_BASE_003"
    "_Green-v01"
)
DOVE_INNOVID = (
    DOVE_TS
    + "__38383730-3934-5731-b931-623638616639__145194828.zip"
)


def test_innovids_upload_stamp_does_not_break_the_match():
    """
    Al subir el archivo Innovid le pega "__<uuid>__<id>.zip". La TS
    nunca lo lleva, asi que el mismo creativo llegaba con dos nombres
    y se reportaba a la vez como "no esta en Innovid" y "no esta en la
    Traffic Sheet". Camilo lo vio con este creativo exacto.
    """
    from core.matching import norm_creative
    assert norm_creative(DOVE_TS) == norm_creative(DOVE_INNOVID)


def test_the_variant_at_the_end_of_the_name_still_tells_them_apart():
    # Estos creativos se distinguen por el ultimo tramo: _Renew,
    # _Refresh, _Uplift. Recortar de mas los volveria el mismo.
    from core.matching import norm_creative
    assert norm_creative(DOVE_TS) != norm_creative(
        DOVE_TS.replace("_Renew_", "_Refresh_")
    )


def test_only_a_full_uuid_is_stripped():
    # Recortar cualquier "__loquesea" final se llevaria nombres reales.
    from core.matching import norm_creative
    for tail in ("__final_v2", "__2026", "__base", "__38383730-3934"):
        name = "banner_300x250" + tail
        assert norm_creative(name) == name.lower(), tail

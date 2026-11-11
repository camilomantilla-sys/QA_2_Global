"""
Donde se revisa DoubleVerify, segun lo que pide la TS y el formato.

Reglas de AdOps (11-nov-2026), por FB-28, FB-22, FB-20 y FB-12:

    DV Monitoring, 1x1      wrapping de DV Pinnacle (DV-001). Sin pixel.
    DV Monitoring, Display  pixel en Third Party Survey 1 (PIX-002).
                            El archivo de tags no trae doubleverify_html.
    DV Monitoring, Video    no existe: lo revisa una persona.
    DV Omni, Video          nada en Third Party Impression ni Survey.
                            doubleverify_vast en el archivo de tags,
                            siempre con contenido (DV-003).

En FB-28 la tabla "Pixels by account" tenia formatos de mas en las
filas de DV, y PIX-002 pedia el pixel de DV Omni y el de DV Monitoring
a placements que no lo llevan. La ruta de DV ya no depende de esa tabla.

Run with pytest, or directly:
    python tests/test_dv_routing.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.pixel_reconciliation as pixels  # noqa: E402
from core.dv_omni_reconciliation import reconcile_dv_omni  # noqa: E402
from core.findings import FindingsBuffer  # noqa: E402
from core.tag_inventory import TagInventory, TagSourceRow  # noqa: E402
from parsers.innovid_tags import (  # noqa: E402
    TAG_DV_HTML, TAG_DV_VAST, TagRow, TagsResult, TagValue,
    _classify_tag_header,
)
from parsers.ts_parser import (  # noqa: E402
    REQ_NEW_PLACEMENT, PlacementScope, TSRow,
)
from rules import dv_omni  # noqa: E402

DV_PIXEL = "https://cdn.doubleverify.com/dvtp_src.js#ctx=715607&cmp=1&sid=2&plc=3"

#: Una tabla mal llenada: todos los formatos en todas las filas de DV.
GREEDY_TABLE = tuple(
    pixels.Vendor(
        name=name, ts_terms=terms, host_terms=("doubleverify.com",),
        column=pixels.SURVEY if name == "DV Monitoring" else pixels.IMPRESSION,
        formats=frozenset({"1x1", "display", "video"}),
    )
    for name, terms in (
        ("DV Monitoring", ("dv", "doubleverify")),
        ("DV Omni", ("dv omni",)),
        ("DV Blocking", ("dv blocking",)),
    )
)


def ts(*placements):
    """placements: (id, dimensions, vendors)."""
    rows = [
        TSRow(row=i + 2, values={
            "placement_id": pid, "placement_name": f"P{pid}",
            "dimensions": dims, "vendors": vendors, "site": "Site",
        })
        for i, (pid, dims, vendors) in enumerate(placements)
    ]
    worked = [PlacementScope(placement_id=pid, request_type=REQ_NEW_PLACEMENT)
              for pid, _d, _v in placements]
    return SimpleNamespace(worked=worked, placements=SimpleNamespace(rows=rows))


def view(**survey):
    return SimpleNamespace(rows=[
        SimpleNamespace(values={"placement_id": pid, "status": "active"},
                        multi={"third_party_survey": [url] if url else []})
        for pid, url in survey.items()
    ])


def inventory(placement_id: str, columns: dict[str, str]) -> TagInventory:
    """Un archivo de tags con una fila para el placement."""
    row = TagRow(row=2, placement_id=placement_id, tags=[
        TagValue(column_name=name, tag_type=_classify_tag_header(name), raw=raw)
        for name, raw in columns.items() if raw
    ])
    result = TagsResult(path="tags.xlsx", rows=[row],
                        tag_columns={name: i for i, name in enumerate(columns, 5)})
    inv = TagInventory(results=[result])
    inv.by_placement[placement_id] = [TagSourceRow("tags.xlsx", "Tags", "1", row)]
    return inv


def pixel_checks(ts_result, placement_view):
    original = pixels.load_vendors
    pixels.load_vendors = lambda: GREEDY_TABLE
    try:
        return pixels.reconcile_pixels(ts_result, placement_view).checks
    finally:
        pixels.load_vendors = original


# ----------------------------------------------------------- PIX-002

def test_no_placement_pixel_for_omni_or_monitoring_1x1():
    result = ts(("1", "1x1", "Flashtalking, DV Monitoring"),
                ("2", "1920x1080", "Flashtalking/DV OMNI"))
    assert pixel_checks(result, view(**{"1": "", "2": ""})) == []


def test_monitoring_display_needs_the_survey_pixel():
    result = ts(("3", "300x250", "DV Monitoring"))
    [missing] = pixel_checks(result, view(**{"3": ""}))
    assert missing.result == "FAIL"
    assert "Third Party Survey" in missing.message
    [loaded] = pixel_checks(result, view(**{"3": DV_PIXEL}))
    assert loaded.result == "PASS"


# ----------------------------------------------------------- DV-003

def test_omni_video_needs_doubleverify_vast_content():
    result = ts(("4", "1920x1080", "DV Omni"))
    [empty] = reconcile_dv_omni(result, None, inventory("4", {
        "doubleverify_vast": "", "Preroll_https": "<VAST/>"})).checks
    assert empty.result == "FAIL"
    [full] = reconcile_dv_omni(result, None, inventory("4", {
        "doubleverify_vast": "<VAST dv/>"})).checks
    assert full.result == "PASS"


def test_monitoring_on_video_goes_to_a_person():
    result = ts(("5", "1920x1080", "DV Monitoring"))
    [check] = reconcile_dv_omni(result, None, inventory("5", {})).checks
    assert check.result == "REVIEW"
    assert "doesn't exist for video" in check.message
    buffer = FindingsBuffer()
    dv_omni.evaluate(SimpleNamespace(checks=[check]), buffer)
    assert [f.status for f in buffer.findings] == ["REVIEW"]


def test_display_without_html_column_is_not_asked_for_it():
    result = ts(("6", "300x250", "DV Monitoring/Blocking"))
    no_column = reconcile_dv_omni(result, None, inventory("6", {"JS_https": "<script/>"}))
    assert no_column.checks == []
    [empty] = reconcile_dv_omni(result, None, inventory("6", {
        "JS_https": "<script/>", "doubleverify_html": ""})).checks
    assert empty.result == "FAIL"


def test_dv_vast_header_is_not_a_video_tag():
    assert _classify_tag_header("DoubleVerify VAST Tag") == TAG_DV_VAST
    assert _classify_tag_header("doubleverify_html") == TAG_DV_HTML


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")


# ----------------------------------------------------------- INV-003

def _partner(vendors, fmt, partner="", status=""):
    from core.innovid_reconciliation import (
        InnovidReconciliation, VerificationPartnerCheck, _partner_expected_for,
    )
    from rules import innovid

    pm = SimpleNamespace(expected=SimpleNamespace(vendors=vendors, fmt=fmt))
    reason = _partner_expected_for(pm)
    rec = InnovidReconciliation()
    rec.partners = [VerificationPartnerCheck(
        placement_id="11315575", actual_partner=partner, actual_status=status,
        configured=bool(partner), partner_expected=bool(reason),
        expected_for=reason,
    )]
    buffer = FindingsBuffer()
    innovid.evaluate(rec, buffer)
    return [f.status.value for f in buffer.findings if f.rule_id == "INV-003"]


def test_omni_video_needs_doubleverify_as_verification_partner():
    assert _partner("Flashtalking/DV OMNI", "video", "DoubleVerify", "Applied") == ["PASS"]
    assert _partner("Flashtalking/DV OMNI", "video") == ["FAIL"]
    assert _partner("Flashtalking/DV OMNI", "video", "IAS", "Applied") == ["FAIL"]
    assert _partner("Flashtalking/DV OMNI", "video", "DoubleVerify", "Pending") == ["REVIEW"]


def test_omni_1x1_and_monitoring_need_no_partner():
    assert _partner("DV Omni", "1x1") == ["PASS"]
    assert _partner("Flashtalking, DV Monitoring", "display") == ["PASS"]


def test_dv_pixel_macros_of_either_kind_compare_equal():
    # El pixel que entrega DV trae macros de CM (%ebuy!, %25esid!); el
    # cargado en Innovid, los de Innovid ([%campaignID%]). Son el mismo.
    official = ("https://cdn.doubleverify.com/dvtp_src.js?ctx=1&cmp=%ebuy!"
                "&sid=%25esid!&plc=%25epid!&num=")
    loaded = ("https://cdn.doubleverify.com/dvtp_src.js?ctx=1&cmp=[%campaignID%]"
              "&sid=[%siteID%]&plc=[%placementID%]&num=")
    assert pixels.pixel_matches_official(loaded, official)
    assert not pixels.pixel_matches_official(loaded.replace("ctx=1", "ctx=2"), official)

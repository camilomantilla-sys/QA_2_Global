"""
FB-09 y FB-03: fechas del placement, Remove VPAID por site y los
callouts del reporte.

- Las fechas del placement se comparan como fechas (11/16/2026 es
  2026-11-16). Una diferencia no bloquea: es INFO y va a los callouts.
- Remove VPAID se revisa a mano una vez por site, solo en video y solo
  en Unilever y Wendy's.
- Todo lo que pide una mirada humana sale agrupado, con un texto
  predeterminado y la firma de QA2.

Run with pytest, or directly:
    python tests/test_callouts.py
"""
from __future__ import annotations

import io
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from core.callouts import TEXTS, build_callouts  # noqa: E402
from core.excel_report import build_excel_report  # noqa: E402
from core.findings import Domain, FindingsBuffer  # noqa: E402
from core.matching import ExpectedPlacement  # noqa: E402
from core.pdf_report import ReportMeta, build_pdf_report  # noqa: E402
from core.reports import apply_review_overrides  # noqa: E402
from core.verdict import overall  # noqa: E402
from rules import placements, video  # noqa: E402


def _pm(pid, ts=(date(2026, 11, 16), date(2026, 12, 31)), innovid=("2026-11-16", "2026-12-31"),
        fmt="display", site="Amazon (17627)", actual_site="Amazon"):
    ep = ExpectedPlacement(placement_id=pid, name=f"P_{pid}", start=ts[0], end=ts[1],
                           fmt=fmt, site=site)
    ap = SimpleNamespace(start=innovid[0], end=innovid[1], status="Live", site=actual_site)
    return SimpleNamespace(placement_id=pid, expected=ep, actual=ap, creative_links=[])


def _run(pms, rule):
    buffer = FindingsBuffer()
    match = SimpleNamespace(matched=pms, only_expected=[])
    if rule == "dates":
        for pm in pms:
            placements._evaluate_flight_dates(pm, buffer)
    else:
        video.evaluate(match, buffer, account=rule)
    return buffer.findings


# --- FB-09: fechas del placement ------------------------------------

def test_same_dates_written_differently_pass():
    found = _run([_pm("1", innovid=("11/16/2026", "12/31/2026 00:00:00"))], "dates")
    assert [f.status.value for f in found] == ["PASS"]


def test_other_placement_dates_are_info_and_do_not_block():
    found = _run([_pm("1", innovid=("2026-11-15", "2026-12-31"))], "dates")
    assert [(f.rule_id, f.status.value) for f in found] == [("PLC-004", "INFO")]
    assert "before the Traffic Sheet start" in found[0].message
    assert found[0].expected == "2026-11-16 → 2026-12-31"
    assert found[0].actual == "2026-11-15 → 2026-12-31"
    other = FindingsBuffer()
    other.pass_("PLC-001", Domain.SCOPE, "Placement found", placement_id="1")
    assert overall(found + other.findings) == "PASSED"


def test_going_live_after_the_ts_start_is_fine():
    # Se trafico el 20-oct; la TS decia 1-oct. No es un problema (AdOps).
    found = _run([_pm("1", ts=(date(2026, 10, 1), date(2026, 11, 30)),
                      innovid=("2026-10-20", "2026-11-30"))], "dates")
    assert [f.status.value for f in found] == ["PASS"]
    assert "trafficked later" in found[0].message


def test_a_different_end_date_still_goes_to_the_callouts():
    found = _run([_pm("1", innovid=("2026-11-20", "2026-12-15"))], "dates")
    assert [f.status.value for f in found] == ["INFO"]
    assert "end date" in found[0].message


def test_video_0x0_is_the_same_as_1920x1080():
    from core.excel_report import _pair_agrees
    from core.normalize import dims_equivalent
    assert dims_equivalent("0x0", "1920x1080")
    assert dims_equivalent("1920 x 1080", "0x0")
    assert not dims_equivalent("300x250", "728x90")
    assert _pair_agrees("TS Dimensions", "0x0", "1920x1080")
    assert _pair_agrees("TS Start Date", "2026-10-01", "2026-10-20")
    assert not _pair_agrees("TS Start Date", "2026-10-20", "2026-10-01")


def test_twitch_tv_and_twitch_are_the_same_site():
    from core.normalize import site_names_match
    assert site_names_match("TWITCH.TV", "Twitch")


# --- FB-03: Remove VPAID por site -----------------------------------

def test_vpaid_is_one_review_per_site_for_unilever_video():
    pms = [_pm("1", fmt="video"), _pm("2", fmt="video"),
           _pm("3", fmt="video", actual_site="Hulu"), _pm("4", fmt="display")]
    found = _run(pms, "Unilever")
    assert [(f.rule_id, f.status.value) for f in found] == [("VID-001", "REVIEW")] * 2
    amazon = next(f for f in found if "Amazon" in f.message)
    assert "1, 2" in amazon.actual and "4" not in amazon.actual
    assert amazon.placement_name == "Site Amazon · 2 video placements"


def test_vpaid_applies_to_wendys_and_not_to_blackrock_or_unknown():
    pms = [_pm("1", fmt="video")]
    assert _run(pms, "Wendy's")
    assert not _run(pms, "BlackRock")
    assert not _run(pms, "")


def _vpaid_with(settings, account="Unilever"):
    buffer = FindingsBuffer()
    match = SimpleNamespace(matched=[_pm("1", fmt="video")], only_expected=[])
    video.evaluate(match, buffer, account=account,
                   innovid_reconciliation=SimpleNamespace(site_media_filters=settings))
    return buffer.findings


def test_with_innovid_remove_vpaid_passes_by_site_id():
    [f] = _vpaid_with({"17627": {"name": "Amazon", "media_filter": "REMOVE_VPAID"}})
    assert (f.rule_id, f.status.value) == ("VID-001", "PASS")


def test_with_innovid_default_fails_matching_by_name():
    [f] = _vpaid_with({"999": {"name": "Amazon", "media_filter": None}})
    assert f.status.value == "FAIL"
    assert "Default" in f.message


def test_an_unknown_media_filter_value_goes_to_a_person():
    [f] = _vpaid_with({"17627": {"name": "Amazon", "media_filter": 3}})
    assert f.status.value == "REVIEW"
    assert "says 3" in f.message


def test_a_site_innovid_did_not_return_stays_manual():
    [f] = _vpaid_with({"1": {"name": "Hulu", "media_filter": None}})
    assert f.status.value == "REVIEW"
    assert "didn't return" in f.actual


def test_media_filter_is_read_where_innovid_puts_it():
    from core.innovid_api import media_filter_of
    detail = {"videoConfig": {"optionGroups": {"ctvOttGroup": {"id": 1, "mediaFilter": None}}}}
    assert media_filter_of(detail) is None
    detail["videoConfig"]["optionGroups"]["ctvOttGroup"]["mediaFilter"] = "REMOVE_VPAID"
    assert media_filter_of(detail) == "REMOVE_VPAID"
    assert media_filter_of({}) is None


# --- callouts -------------------------------------------------------

def _mixed_findings():
    buffer = FindingsBuffer()
    buffer.info("PLC-004", Domain.DATES, "The placement has another start date",
                placement_id="1", placement_name="P_1",
                expected="2026-11-16 → 2026-12-31", actual="2026-11-15 → 2026-12-31")
    a = buffer.review("VID-001", Domain.SCOPE, "Check Remove VPAID on the site Amazon",
                      placement_name="Site Amazon · 2 video placements", actual="1, 2")
    buffer.review("VID-001", Domain.SCOPE, "Check Remove VPAID on the site Hulu",
                  placement_name="Site Hulu · 1 video placement", actual="3")
    buffer.pass_("PLC-001", Domain.SCOPE, "Placement found", placement_id="1")
    signed = apply_review_overrides(buffer.findings, {a.finding_id: {
        "approved": True, "note": "checked in Innovid"}}, approved_by="Tester QA")
    return signed


def test_callouts_group_what_needs_a_person():
    callouts = {c["key"]: c for c in build_callouts(_mixed_findings())}
    assert set(callouts) == {"PLC-004", "VID-001"}
    vpaid = callouts["VID-001"]
    assert vpaid["text"] == TEXTS["VID-001"]
    assert vpaid["state"] == "1 approved · 1 to review"
    signed = next(i for i in vpaid["items"] if "Amazon" in i["label"])
    assert signed["approval"] == "Approved by Tester QA: checked in Innovid"
    dates = callouts["PLC-004"]
    assert dates["state"] == "1 item · doesn't block the QA"
    assert dates["items"][0]["detail"] == (
        "Traffic Sheet 2026-11-16 → 2026-12-31 · Innovid 2026-11-15 → 2026-12-31")


def test_unknown_rules_get_their_title_and_names_fill_in():
    buffer = FindingsBuffer()
    buffer.not_verified("ROT-001", Domain.ROTATION, "Rotation not checked", placement_id="9")
    [c] = build_callouts(buffer.findings, {"9": "P_nine"})
    assert c["text"].startswith("The requested rotation change was applied")
    assert "couldn't check" in c["text"]
    assert c["items"][0]["label"] == "9 P_nine"


def _meta(callouts):
    return ReportMeta(verdict="NEEDS_REVIEW", verdict_label="Review required",
                      profile_used="", detected_profile="", detection_evidence="",
                      scope_guard="OK", scope_evidence="", ts_campaign_id="",
                      export_campaign_id="", callouts=callouts,
                      metrics={"Worked Placements": 3, "Reviews": 2})


def test_the_excel_has_a_callouts_section_and_sheet():
    callouts = build_callouts(_mixed_findings())
    data = build_excel_report(_meta(callouts), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    wb = load_workbook(io.BytesIO(data))
    assert "Callouts" in wb.sheetnames
    summary = [c.value for row in wb["Summary"].iter_rows() for c in row if c.value]
    assert "Callouts" in summary and TEXTS["VID-001"] in summary
    sheet = [c.value for row in wb["Callouts"].iter_rows() for c in row if c.value]
    assert TEXTS["PLC-004"] in sheet
    assert "Approved by Tester QA: checked in Innovid" in sheet
    assert "To review" in sheet


def test_the_pdf_still_builds_with_callouts():
    callouts = build_callouts(_mixed_findings())
    pdf = build_pdf_report(_meta(callouts), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    assert pdf[:4] == b"%PDF"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

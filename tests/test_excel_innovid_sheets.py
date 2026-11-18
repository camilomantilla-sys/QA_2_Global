"""
El Excel lleva todo lo que QA2 leyo de Innovid, no solo la hoja QA (FB-17).

Run with pytest, or directly:
    python tests/test_excel_innovid_sheets.py
"""
from __future__ import annotations

import dataclasses
import sys
import warnings
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from core.excel_report import build_excel_report  # noqa: E402
from core.innovid_reconciliation import (  # noqa: E402
    AMBIGUOUS, EXTRA_IN_INNOVID, MATCHED,
    CreativeFlightCheck, InnovidReconciliation, VerificationPartnerCheck,
)
from core.pdf_report import ReportMeta  # noqa: E402


def _meta() -> ReportMeta:
    fields = {}
    for f in dataclasses.fields(ReportMeta):
        if f.default is not dataclasses.MISSING:
            fields[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:
            fields[f.name] = f.default_factory()
        else:
            fields[f.name] = ""
    fields.update(verdict="PASSED", verdict_label="PASSED", generated_at=datetime.now())
    return ReportMeta(**fields)


def _book(rec):
    blank = pd.DataFrame()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = build_excel_report(_meta(), blank, blank, blank, innovid_reconciliation=rec)
    return load_workbook(BytesIO(data))


def _rows(ws):
    values = list(ws.iter_rows(values_only=True))
    header = list(values[0])
    return [dict(zip(header, row)) for row in values[1:]]


def test_without_innovid_there_are_no_innovid_sheets():
    assert "Innovid Decision Sets" not in _book(None).sheetnames


def test_everything_read_from_innovid_is_in_the_excel():
    rec = InnovidReconciliation(
        flights=[
            CreativeFlightCheck(
                placement_id="900101", creative_name="Spring_A", status=MATCHED,
                dset_id="555", dset_name="DS Spring", actual_name="Spring A concept",
                expected_start=date(2027, 1, 6), actual_start=date(2027, 1, 6),
                expected_weight_pct="50%", actual_weight_pct="50%",
                actual_start_time="06:30",
            ),
            CreativeFlightCheck(placement_id="900101", creative_name="Old_B",
                                status=EXTRA_IN_INNOVID, dset_id="555"),
            CreativeFlightCheck(placement_id="900102", creative_name="Spring_C",
                                status=AMBIGUOUS, candidates=2),
        ],
        partners=[VerificationPartnerCheck(placement_id="900101", actual_partner="DoubleVerify",
                                           actual_status="Active", configured=True)],
        unchecked=[("900103", "decision set could not be read")],
    )
    book = _book(rec)
    rows = _rows(book["Innovid Decision Sets"])
    first = rows[0]
    assert first["Decision Set Name"] == "DS Spring"
    assert first["Creative Name in DS"] == "Spring A concept"
    assert first["Innovid End"] == "ongoing"
    assert first["Innovid Start Time"] == "06:30"
    results = [r["Result"] for r in rows]
    assert "Not in the Traffic Sheet" in results
    assert "Duplicated in DS (x2)" in results
    assert "Not read from Innovid: decision set could not be read" in results
    # El partner va en la hoja QA (AdOps): ya no hay hoja propia.
    assert "Innovid Partners" not in book.sheetnames
    from core.qa_export import _partners_index
    assert _partners_index(rec)["900101"] == "DoubleVerify (Active)"


def test_sheet_order_and_hidden_audit_tabs():
    book = _book(InnovidReconciliation())
    visible = [ws.title for ws in book.worksheets if ws.sheet_state == "visible"]
    hidden = [ws.title for ws in book.worksheets if ws.sheet_state == "hidden"]
    assert visible[:3] == ["Summary", "QA", "Innovid Decision Sets"]
    assert visible.index("Innovid Decision Sets") < visible.index("Worked Placements")
    assert {"Findings", "Files & Extraction", "Rules Executed"} <= set(hidden)


def test_the_innovid_default_shows_even_when_it_repeats_a_creative():
    """
    AdOps: "que igual salga el default, asi sea un creativo repetido".
    El default va despues de los creativos de su placement.
    """
    from core.innovid_api import parse_dset_response
    from core.innovid_export_tables import decision_set_table
    from core.innovid_reconciliation import DEFAULT_AD

    nodes = parse_dset_response({
        "id": 38808, "name": "Frosty 320x50", "servingMethod": "Rotation",
        "defaultServing": {"id": 6312751, "name": "320x50.jpg"},
        "nodes": [
            {"id": 1, "serving": {"id": 6312751, "name": "320x50.jpg"},
             "startTimestamp": "2026-07-24 00:00:00", "endTimestamp": None, "weight": 1},
            {"id": 6312751, "startTimestamp": "2026-07-21 10:02:11",
             "endTimestamp": None, "isDefault": True},
        ],
    })
    default = [n for n in nodes if n.is_default][0]
    assert default.creative_name == "320x50.jpg"

    rec = InnovidReconciliation(
        flights=[CreativeFlightCheck(placement_id="1", creative_name="320x50.jpg",
                                     status=MATCHED, dset_id="38808", dset_name="Frosty 320x50")],
        default_ads=[CreativeFlightCheck(placement_id="1", status=DEFAULT_AD, is_default=True,
                                         dset_id="38808", dset_name="Frosty 320x50",
                                         actual_name="320x50.jpg",
                                         actual_start=date(2026, 7, 21))],
    )
    rows = decision_set_table(rec).to_dict("records")
    assert [r["Result"] for r in rows] == ["In decision set", "Default ad"]
    assert rows[1]["Default Ad"] == "Yes"
    assert rows[1]["Creative Name in DS"] == "320x50.jpg"


def test_reconcile_keeps_the_default_aside():
    from types import SimpleNamespace
    from core.innovid_api import InnovidFetchResult, parse_dset_response, parse_summary_response
    from core.innovid_reconciliation import reconcile
    from core.matching import ExpectedCreative, ExpectedPlacement

    pid = "900201"
    placements = parse_summary_response({"items": [
        {"placementId": pid, "level": "PLACEMENT", "status": "Active",
         "startDate": "2026-09-14", "endDate": "2026-10-31"},
        {"placementId": pid, "level": "PLACEMENT-CREATIVE",
         "decisionSetId": 7, "decisionSetName": "DS 300x250"},
    ]})
    nodes = parse_dset_response({
        "id": 7, "name": "DS 300x250", "defaultServing": {"id": 99, "name": "Default_300x250.jpg"},
        "nodes": [
            {"id": 1, "serving": {"id": 5, "name": "A.jpg"},
             "startTimestamp": "2026-09-14 00:00:00", "endTimestamp": None, "weight": 1},
            {"id": 99, "startTimestamp": "2026-09-14 00:00:00", "isDefault": True},
        ]})
    got = InnovidFetchResult(campaign_id="1", placements=placements, creative_nodes=nodes)
    ep = ExpectedPlacement(placement_id=pid, name="P", dims="300x250",
                           creatives=[ExpectedCreative(name="A.jpg")])
    pm = SimpleNamespace(placement_id=pid, expected=ep, actual=None, creative_links=[])
    rec = reconcile(SimpleNamespace(matched=[pm], only_expected=[]), got)
    assert [c.actual_name for c in rec.default_ads] == ["Default_300x250.jpg"]
    assert all(not c.is_default for c in rec.flights)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

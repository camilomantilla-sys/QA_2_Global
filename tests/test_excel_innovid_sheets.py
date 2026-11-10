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
    partners = _rows(book["Innovid Partners"])
    assert partners[0]["Verification Partner"] == "DoubleVerify"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

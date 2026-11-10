"""
El bundle lleva el rastro del QA1 y el QA2 lo ve (FB-18, FB-21).

Run with pytest, or directly:
    python tests/test_qa1_trail.py
"""
from __future__ import annotations

import dataclasses
import sys
import warnings
from datetime import datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from core.excel_report import build_excel_report  # noqa: E402
from core.pdf_report import ReportMeta  # noqa: E402
from core.qa1_trail import describe_origin, describe_result, result_snapshot  # noqa: E402

APP = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")


def test_the_result_reads_like_the_verdict():
    snap = result_snapshot("FAILED", 2, 3, 0, "2026-11-10T10:00:00")
    assert describe_result(snap) == "REQUIRES CORRECTION (2 failed, 3 to review)"
    assert describe_result(result_snapshot("PASSED", 0, 0, 0, "x")) == "PASSED"
    assert describe_result(None) == ""


def test_the_origin_names_qa1_and_never_invents():
    text = describe_origin({
        "implemented_by": "Analyst A", "implementation_date": "2026-11-09",
        "wrike_id": "123", "saved_at": "2026-11-09T14:02:11",
        "qa1_result": result_snapshot("NEEDS_REVIEW", 0, 1, 2, "x"),
    })
    assert text.startswith("Implemented (QA1) by Analyst A on 2026-11-09")
    assert "Wrike 123" in text and "bundle saved 2026-11-09 14:02" in text
    assert "REVIEW REQUIRED (1 to review, 2 not verified)" in text
    bare = describe_origin({})
    assert bare == "Implemented (QA1) by someone not named in the bundle."


def test_the_bundle_carries_the_trail_and_the_app_shows_it():
    assert '"qa1_result": st.session_state.get("qa2_last_result")' in APP
    assert '"notes": record_notes,' in APP
    assert 'describe_origin(st.session_state["qa2_bundle_origin"])' in APP
    assert '("qa2_record_notes", "notes")' in APP


def _meta(**extra) -> ReportMeta:
    fields = {}
    for f in dataclasses.fields(ReportMeta):
        if f.default is not dataclasses.MISSING:
            fields[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:
            fields[f.name] = f.default_factory()
        else:
            fields[f.name] = ""
    fields.update(verdict="PASSED", verdict_label="PASSED",
                  generated_at=datetime.now(), **extra)
    return ReportMeta(**fields)


def test_both_reports_show_qa1_apart_from_qa2():
    meta = _meta(implemented_by="Analyst A", qa2_by="Analyst B",
                 qa1_result="REQUIRES CORRECTION (2 failed)")
    blank = pd.DataFrame()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        book = load_workbook(BytesIO(build_excel_report(meta, blank, blank, blank)))
    cells = {str(c.value) for row in book["Summary"].iter_rows() for c in row}
    assert "Implemented By (QA1)" in cells
    assert "QA1 Result (from bundle)" in cells
    assert "REQUIRES CORRECTION (2 failed)" in cells
    from core import pdf_report
    table = pdf_report._record_flowable(meta, pdf_report._styles())[2]
    left = table._cellvalues[0][0].text
    assert "Implemented By (QA1):" in left and "QA1 Result:" in left


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

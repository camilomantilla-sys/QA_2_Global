"""
La copia anónima de una TS sirve para reproducir un caso: QA2 la lee
igual que la original, y no queda ningún nombre ni ID de la original.

Run with pytest, or directly:
    python tests/test_anonimizar_ts.py
"""
from __future__ import annotations

import datetime
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.comments import Comment  # noqa: E402
from openpyxl.styles import PatternFill  # noqa: E402

from scripts.anonimizar_ts import anonymize, build_vocab, compare  # noqa: E402

HEADERS = [
    "Site Name", "Placement ID", "Placement Name", "Start Date", "End Date",
    "Dimensions", "Creative Names", "Landing Page", "Vendors / Pixels",
    "Creative Rotation %", "CGEN",
]
GREEN = PatternFill("solid", fgColor="FF00FF00")
RED = PatternFill("solid", fgColor="FFFF0000")
GREY = PatternFill("solid", fgColor="FFBFBFBF")


@pytest.fixture(scope="module")
def vocab():
    return build_vocab()


@pytest.fixture()
def made_up(tmp_path):
    """Una TS inventada con nombres que hacen de marca: Zorbex y Quilmo."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    for col, name in enumerate(HEADERS, start=1):
        ws.cell(1, col, name)
    for i in range(6):
        row = i + 2
        values = [
            "QuilmoTV", 11223300 + i, f"Zorbex_Spring_Video_15s_{i}",
            datetime.date(2027, 1, 6), datetime.date(2027, 3, 30), "1x1",
            f"Zorbex_15s_{i}", "https://www.zorbex.example/spring?utm_source=quilmo",
            "DV Monitoring", 100, "ZRB1234",
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row, col, value)
            cell.fill = GREEN if i < 3 else RED if i == 3 else GREY if i == 4 else PatternFill()
    ws.merge_cells("A2:A3")
    ws.row_dimensions[7].hidden = True
    ws["C2"].comment = Comment("Ana pidió esto", "Ana")
    wb.create_sheet("Campaign Information")
    wb.properties.creator = "Ana Perez"
    source = tmp_path / "Zorbex_TS.xlsx"
    wb.save(source)
    return source


def test_no_name_or_long_id_survives(made_up, vocab, tmp_path):
    target = tmp_path / "out.xlsx"
    anonymize(made_up, target, vocab)
    book = load_workbook(target)
    text = " ".join(
        str(c.value) for ws in book.worksheets for row in ws.iter_rows() for c in row
        if c.value is not None
    ).lower()
    for secret in ("zorbex", "quilmo", "11223300", "zrb1234", "ana"):
        assert secret not in text, secret
    assert book.properties.creator == "QA2"
    assert book.active["C2"].comment is None


def test_the_shape_stays(made_up, vocab, tmp_path):
    target = tmp_path / "out.xlsx"
    anonymize(made_up, target, vocab)
    ws = load_workbook(target).active
    assert ws["B1"].value == "Placement ID", "headers stay"
    assert ws["F2"].value == "1x1"
    assert ws["I2"].value == "DV Monitoring"
    assert ws["D2"].value.date() == datetime.date(2027, 1, 6)
    assert ws["B2"].fill.fgColor.rgb == "FF00FF00"
    assert ws["B5"].fill.fgColor.rgb == "FFFF0000"
    assert "A2:A3" in {str(r) for r in ws.merged_cells.ranges}
    assert ws.row_dimensions[7].hidden
    assert ws["C2"].value.endswith("_Video_15s_0")


def test_the_same_original_gets_the_same_fake(made_up, vocab, tmp_path):
    target = tmp_path / "out.xlsx"
    anonymize(made_up, target, vocab)
    ws = load_workbook(target).active
    brand_a = ws["C2"].value.split("_")[0]
    brand_b = ws["G2"].value.split("_")[0]
    assert brand_a == brand_b
    ids = [ws.cell(r, 2).value for r in range(2, 8)]
    assert len(set(ids)) == 6 and all(len(str(i)) == 8 for i in ids)


def test_qa2_reads_the_copy_like_the_original(made_up, vocab, tmp_path):
    target = tmp_path / "out.xlsx"
    anonymize(made_up, target, vocab)
    assert compare(made_up, target) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

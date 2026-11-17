"""
FB-02: despues del wrapping no queda ninguna celda vacia en el archivo
de tags. El Excel de antes lo avisaba con una formula; QA2 no.

Run with pytest, or directly:
    python tests/test_tag_empty_cells.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook  # noqa: E402

from core.findings import FindingsBuffer  # noqa: E402
from parsers.innovid_tags import parse_innovid_tags  # noqa: E402
from rules.tags import _empty_after_wrapping  # noqa: E402

HEADERS = ["width", "height", "Type", "FileName", "Placement_ID", "Creative_ID",
           "thirdPartyID", "PlacementName", "startDate", "endDate", "PrismaID",
           "pixel", "Impression_container", "Impression_redirect",
           "Static_Clicktag1", "Update_Clicktag1", "protected pixel"]


def _file(rows) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Trackers"
    for _ in range(7):
        ws.append([])
    ws.append(HEADERS)
    for r in rows:
        ws.append(r)
    path = Path(tempfile.mkdtemp()) / "tags.xlsx"
    wb.save(path)
    return path


def _row(pid, **blank):
    values = {h: f"{h}-{pid}" for h in HEADERS}
    values.update({"width": 1, "height": 1, "Placement_ID": pid,
                   "pixel": "https://ad.example.com/p", "protected pixel": ""})
    for h in blank:
        values[h] = ""
    return [values[h] for h in HEADERS]


def _findings(path, in_scope=True):
    result = parse_innovid_tags(path)
    buffer = FindingsBuffer()
    for row in result.rows:
        link = SimpleNamespace(tag_row=row, expected=object() if in_scope else None)
        _empty_after_wrapping(link, buffer)
    return result, buffer.findings


def test_the_parser_remembers_which_columns_came_empty():
    result, _ = _findings(_file([_row("1", Impression_redirect=1)]))
    assert result.rows[0].empty_columns == ["Impression_redirect", "protected pixel"]


def test_an_empty_cell_after_wrapping_fails_and_names_the_column():
    _, found = _findings(_file([_row("1"), _row("2", Impression_container=1, Static_Clicktag1=1)]))
    by_pid = {f.placement_id: f for f in found}
    assert by_pid["1"].status.value == "PASS"
    assert by_pid["2"].status.value == "FAIL"
    assert by_pid["2"].actual == "Empty: Impression_container, Static_Clicktag1"


def test_columns_with_their_own_rule_may_be_empty():
    # protected pixel lo decide TAG-012 segun la politica del placement.
    _, found = _findings(_file([_row("1")]))
    assert [f.status.value for f in found] == ["PASS"]


def test_rows_outside_the_request_are_left_to_tag_003():
    _, found = _findings(_file([_row("1", pixel=1)]), in_scope=False)
    assert found == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

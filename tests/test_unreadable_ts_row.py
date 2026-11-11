"""
Un error de formula en una columna auxiliar no saca a la fila del QA.

Caso real (FB-28, Unilever): la TS pedia 7 placements nuevos, todos en
verde. La fila de uno de ellos traia un #REF! en "P# (Auto)", una
formula de ayuda que QA2 ni lee. Como cualquier error de formula
marcaba la fila entera como corrupta, ese placement desaparecia: QA2
reviso 6 de 7 y no dijo nada.

Ahora solo un error en una columna que QA2 lee deja la fila sin leer,
y cuando pasa, el resultado de la TS lo dice con hoja y fila.

Run with pytest, or directly:
    python tests/test_unreadable_ts_row.py
"""
from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import PatternFill  # noqa: E402

from parsers.ts_parser import ROW_UNREADABLE, parse_ts  # noqa: E402

GREEN = PatternFill("solid", fgColor="FF92D050")
HEADERS = [
    "Site Name", "Placement ID", "Placement Name", "Start Date",
    "End Date", "Dimensions", "Creative Rotation", "Landing Page",
    "Vendors / Pixels", "P# (Auto)",
]


def build(error_column: int) -> Path:
    """Tres placements verdes; el del medio con #REF! en `error_column`."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    for col, name in enumerate(HEADERS, start=1):
        ws.cell(1, col, name)
    for row in range(2, 5):
        values = [
            "Site A", 11300000 + row, f"P{row}_NEW_PLACEMENT",
            "2026-12-01", "2026-12-25", "1x1", f"Group {row}",
            f"LP {row}", "DV Monitoring", row - 1,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row, col, value)
            if col <= 8:
                cell.fill = GREEN
    ws.cell(3, error_column, "#REF!")
    wb.create_sheet("Campaign Information")
    target = Path(tempfile.mkdtemp()) / "ts.xlsx"
    wb.save(target)
    return target


def parse(path: Path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return parse_ts(path)


def test_error_in_helper_column_keeps_the_row():
    result = parse(build(error_column=HEADERS.index("P# (Auto)") + 1))
    assert sorted(result.scope) == ["11300002", "11300003", "11300004"]
    assert result.request_counts.get("NEW_PLACEMENT") == 3
    assert not [a for a in result.anomalies if a.code == ROW_UNREADABLE]


def test_error_in_read_column_is_said_out_loud():
    result = parse(build(error_column=HEADERS.index("Placement Name") + 1))
    assert "11300003" not in result.scope
    found = [a for a in result.anomalies if a.code == ROW_UNREADABLE]
    assert len(found) == 1
    assert found[0].severity == "WARNING"
    assert "Placements row 3" in found[0].message
    assert "Placement Name" in found[0].message


if __name__ == "__main__":
    test_error_in_helper_column_keeps_the_row()
    test_error_in_read_column_is_said_out_loud()
    print("ok")

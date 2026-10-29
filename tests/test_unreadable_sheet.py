"""
Una hoja que no se pudo leer nunca puede acabar en PASSED.

Caso real: llego una TS de BlackRock con la celda B1 de "Creative
Rotations" en blanco -- alguien borro el encabezado "Creative Name".
El parser lo marco FATAL y leyo CERO de sus 384 rotaciones, y el motor
dio **PASSED** sobre 144 comprobaciones que nunca tocaron un creativo.
Verde sobre algo que nadie leyo.

Dos cosas, entonces: que el veredicto sea BLOCKED, y que el mensaje
diga la hoja y la celda, porque "falta creative_name" deja a quien lo
recibe sin saber donde mirar.

Run with pytest, or directly:
    python tests/test_unreadable_sheet.py
"""
from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook  # noqa: E402

from core.engine import _fatal_extraction  # noqa: E402
from core.extraction import map_columns, read_sheet  # noqa: E402
from core.ts_schema import TS_ROTATIONS  # noqa: E402

ROTATIONS = "Creative Rotations"
HEADERS = [
    "Creative Rotation Name", "Creative Name", "Creative Description",
    "Creative ID", "Creative Type", "Dimensions / Durations",
    "Rotation (%) or Even", "Sequential", "Start Date", "End Date",
]


def build_sheet(blank_header_at: int | None) -> Path:
    """Una hoja de rotaciones, opcionalmente con un encabezado borrado."""
    wb = Workbook()
    ws = wb.active
    ws.title = ROTATIONS
    for col, name in enumerate(HEADERS, start=1):
        if col != blank_header_at:
            ws.cell(1, col, name)
    for row in range(2, 12):
        ws.cell(row, 1, f"Rotation {row}")
        ws.cell(row, 2, f"CREATIVE_{row}_STA")
        ws.cell(row, 4, 6000000 + row)
        ws.cell(row, 7, 50)
    target = Path(tempfile.mkdtemp()) / "rotations.xlsx"
    wb.save(target)
    return target


def map_it(blank_header_at: int | None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        grid, _ = read_sheet(build_sheet(blank_header_at), ROTATIONS)
    return map_columns(grid, 1, TS_ROTATIONS)


class _Anomaly:
    def __init__(self, severity: str, code: str = "EXT-COLUMN-MISSING"):
        self.severity = severity
        self.code = code
        self.message = f"{code} ({severity})"


class _Sheet:
    def __init__(self, anomalies):
        self.anomalies = anomalies


class _TS:
    def __init__(self, own=(), placements=(), rotations=(), landing=()):
        self.anomalies = list(own)
        self.placements = _Sheet(list(placements))
        self.rotations = _Sheet(list(rotations))
        self.landing_pages = _Sheet(list(landing))


def test_a_complete_header_row_maps_cleanly():
    cmap, anomalies = map_it(blank_header_at=None)
    assert not cmap.missing_required
    assert not [a for a in anomalies if a.severity == "FATAL"]


def test_a_deleted_header_is_fatal():
    _, anomalies = map_it(blank_header_at=2)
    fatal = [a for a in anomalies if a.severity == "FATAL"]
    assert fatal, "un encabezado borrado dejo de ser fatal"


def test_the_message_names_the_sheet():
    _, anomalies = map_it(blank_header_at=2)
    message = anomalies[0].message
    assert ROTATIONS in message, message


def test_the_message_names_the_cell():
    # B1, no "columna 2": se pega en el cuadro de nombres de Excel.
    _, anomalies = map_it(blank_header_at=2)
    assert "B1" in anomalies[0].message, anomalies[0].message


def test_the_message_says_it_looks_like_a_deleted_header():
    _, anomalies = map_it(blank_header_at=2)
    assert "deleted header" in anomalies[0].message


def test_an_empty_column_without_a_header_is_not_reported_as_one():
    # La columna C no lleva datos: en blanco arriba y en blanco
    # abajo es una columna vacia, no un encabezado borrado.
    _, anomalies = map_it(blank_header_at=2)
    cells = anomalies[0].detail["blank_headers_with_data"]
    assert [c for c, _ in cells] == ["B1"], cells


def test_the_detail_carries_the_sheet_and_the_cells():
    _, anomalies = map_it(blank_header_at=2)
    detail = anomalies[0].detail
    assert detail["sheet"] == ROTATIONS
    assert detail["missing"] == ["creative_name"]


def test_a_fatal_on_a_tab_reaches_the_engine():
    # Cada pestana guarda sus anomalias aparte. Mirar solo las del
    # documento dejaba fuera justo las que dicen que una pestana no
    # se pudo leer -- que fue el caso de BlackRock.
    ts = _TS(rotations=[_Anomaly("FATAL")])
    assert len(_fatal_extraction(ts)) == 1


def test_warnings_do_not_block():
    ts = _TS(own=[_Anomaly("WARNING")], rotations=[_Anomaly("INFO")])
    assert _fatal_extraction(ts) == []


def test_the_same_fatal_on_two_tabs_is_reported_once():
    # El parser la deja tanto arriba como en la pestana.
    ts = _TS(own=[_Anomaly("FATAL")], rotations=[_Anomaly("FATAL")])
    assert len(_fatal_extraction(ts)) == 1


def test_no_traffic_sheet_is_not_a_fatal():
    assert _fatal_extraction(None) == []


def test_the_engine_blocks_on_a_fatal_read():
    from core.engine import run_rules

    class _Match:
        scope_guard = "OK"
        scope_evidence = ""
        ts_campaign_id = ""
        export_campaign_id = ""
        matched = []
        only_expected = []
        only_actual_in_scope = []
        ambiguous = []
        confidence_counts = {}
        group_counts = {}
        creative_conf_counts = {}
        expected_total = 0
        actual_total = 0
        url_counts = {}
        triangle_counts = {}
        extra_running_total = 0
        extra_stopped_total = 0

    buffer = run_rules(_Match(), ts_result=_TS(rotations=[_Anomaly("FATAL")]))
    assert buffer.scorecard().verdict == "BLOCKED"


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
        else:
            passed += 1
            print(f"ok   {name}")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

"""
Una hoja de rotaciones filtrada sigue siendo una hoja con datos.

Caso real (Adobe Stock, swap con Decision Tree): la hoja "Creative
Rotations" trae 29.170 filas -- ano y medio de solicitudes, cada bloque
bajo su banner de fecha -- y el analista deja visibles solo las 710 del
bloque de hoy, que empieza en la fila 28.423.

La deteccion de perfil miraba SESENTA filas debajo del encabezado, veia
el hueco de arriba, concluia "Creative Rotations esta vacia" y elegia
el perfil de 1x1. Con ese perfil la hoja no se lee siquiera, asi que
los 384 creativos de la solicitud salian como "no declarados en la TS"
y no se comparaba ni un creativo, ni una URL, ni un CGEN. Todo ello sin
una sola anomalia: el QA daba PASSED.

Run with pytest, or directly:
    python tests/test_hidden_rotations.py
"""
from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook  # noqa: E402

from core.extraction import find_header_row, read_sheet  # noqa: E402
from core.ts_schema import TS_ROTATIONS  # noqa: E402
from parsers.ts_parser import detect_profile  # noqa: E402

PLACEMENT_HEADERS = [
    "Site Name", "Placement ID", "Placement Name", "Start Date",
    "End Date", "Dimensions", "Creative Names", "Landing Page",
    "Vendors / Pixels", "Creative Rotation %", "CGEN",
]
ROTATION_HEADERS = [
    "Creative Rotation Name", "Creative Name", "Creative ID",
    "Creative Type", "Dimensions / Durations", "Rotation (%) or Even",
    "Sequential", "Start Date", "End Date", "Landing Page Name",
]


def build(first_data_row: int, hide_up_to: int | None,
          data_rows: int = 10) -> Path:
    """
    Una TS de Adobe cuyas rotaciones empiezan donde se le diga.

    `hide_up_to` oculta las filas 2..N, como hace el analista al dejar
    visible solo el bloque de la solicitud de hoy.
    """
    wb = Workbook()

    ws = wb.active
    ws.title = "Placements"
    for col, name in enumerate(PLACEMENT_HEADERS, start=1):
        ws.cell(1, col, name)
    for row in range(2, 5):
        ws.cell(row, 2, 11000000 + row)
        ws.cell(row, 3, f"Placement {row}")
        ws.cell(row, 11, "ABCD1234")

    ws = wb.create_sheet("Creative Rotations")
    for col, name in enumerate(ROTATION_HEADERS, start=1):
        ws.cell(1, col, name)
    for offset in range(data_rows):
        row = first_data_row + offset
        ws.cell(row, 1, "FY26_Stock_AU_Display")
        ws.cell(row, 2, f"CREATIVE_{offset}_STA")
        ws.cell(row, 3, 4681700 + offset)

    if hide_up_to:
        for row in range(2, hide_up_to + 1):
            ws.row_dimensions[row].hidden = True

    wb.create_sheet("Campaign Information")

    target = Path(tempfile.mkdtemp()) / "ts.xlsx"
    wb.save(target)
    return target


def profile_of(path: Path) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        name, _ = detect_profile(path)
    return name


def test_rotations_right_below_the_header_are_seen():
    assert profile_of(build(2, None)) == "adobe_variante_a"


def test_rotations_far_below_a_hidden_block_are_seen():
    # El caso real: 200 filas ocultas y los datos al final.
    assert profile_of(build(210, 209)) == "adobe_variante_a"


def test_rotations_further_down_than_the_old_sixty_row_window():
    # Sin filas ocultas de por medio, solo lejos. Esto es lo que la
    # ventana de sesenta filas no alcanzaba a ver.
    assert profile_of(build(120, None)) == "adobe_variante_a"


def test_an_empty_rotations_sheet_is_still_the_1x1_profile():
    # El otro lado: Adobe Direct SI tiene la hoja vacia -- encabezados
    # y nada debajo -- y ese perfil tiene que seguir saliendo.
    assert profile_of(build(2, None, data_rows=0)) == "adobe_variante_b"


def test_a_rotations_sheet_hidden_whole_reads_as_empty():
    # Todas las filas ocultas y ninguna visible: no hay con que
    # trabajar, y eso es el perfil de 1x1, no un error.
    assert profile_of(build(2, 11)) == "adobe_variante_b"


def test_the_grid_only_carries_the_visible_rows():
    # De donde sale que recorrer la hoja entera sea barato: las filas
    # ocultas no llegan al grid.
    path = build(210, 209)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        grid, _ = read_sheet(path, "Creative Rotations", capture_fill=False)
    header, _ = find_header_row(grid, TS_ROTATIONS)
    assert header.row == 1
    assert len([r for r in grid.rows if r > 1]) <= 12, sorted(grid.rows)[:20]


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

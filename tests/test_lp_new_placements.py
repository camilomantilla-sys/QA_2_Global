"""
Una landing page verde que es de los placements nuevos no es un URL swap.

Caso real (FB-07, Unilever Commerce): 8 placements nuevos en verde y 7
existentes en blanco, todos con la misma landing page. La landing page
entraba entera en verde porque la usan los nuevos, y QA2 la propagaba a
los blancos: "15 placements trabajados" donde se pidieron 8, y 7 URL
swap que nadie pidio.

Como lo explica AdOps: si la URL esta en verde pero todo lo demas de la
fila esta en blanco, ese placement ya estaba traficado; el verde aplica
solo a los nuevos.

Y su contraparte (FB-14): un placement nuevo, todo en verde, que reusa
una landing page que ya existia. Esa landing page va en blanco porque
no cambia, y sigue siendo la del placement. QA2 decia que la TS no le
declaraba ninguna; un placement siempre tiene una.

Run with pytest, or directly:
    python tests/test_lp_new_placements.py
"""
from __future__ import annotations

import sys
import tempfile
import warnings
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import PatternFill  # noqa: E402

from parsers.ts_parser import LP_CLAIMED_BY_NEW, parse_ts  # noqa: E402

G = PatternFill("solid", fgColor="FF00FF00")
R = PatternFill("solid", fgColor="FFFF0000")
PL_HEADERS = ["Site Name", "Placement ID", "Placement Name", "Start Date",
              "End Date", "Dimensions", "Creative Rotation", "Landing Page"]


def build(lp_paint: str = "row", new_claims_lp: bool = True) -> Path:
    """
    2 placements existentes en blanco y 2 nuevos en verde, misma LP.

    lp_paint: "row" la LP entra entera en verde; "url" solo la URL en
    verde con la vieja en rojo debajo (un swap de URL de verdad);
    "white" la LP ya existia y va en blanco.
    new_claims_lp: los nuevos pintan su celda de Landing Page.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    ws.append(PL_HEADERS)
    for i, new in enumerate((False, False, True, True)):
        ws.append(["Site", 1100 + i, f"DEMO_P{i}", date(2027, 1, 1),
                   date(2027, 3, 31), "1x1", f"Group {i}", "LP_DEMO"])
        if new:
            for col in range(1, 9):
                if col == 8 and not new_claims_lp:
                    continue
                ws.cell(ws.max_row, col).fill = G
    lp = wb.create_sheet("Landing Pages")
    lp.append(["Landing Page Name", "Landing Page URL"])
    if lp_paint == "row":
        lp.append(["LP_DEMO", "https://landing.example"])
        lp.cell(2, 1).fill = G
        lp.cell(2, 2).fill = G
    elif lp_paint == "white":
        lp.append(["LP_DEMO", "https://landing.example"])
    else:
        lp.append(["LP_DEMO", "https://old.example"])
        lp.cell(2, 2).fill = R
        lp.append(["LP_DEMO", "https://landing.example"])
        lp.cell(3, 2).fill = G
    wb.create_sheet("Campaign Information")
    target = Path(tempfile.mkdtemp()) / "ts.xlsx"
    wb.save(target)
    return target


def parse(**kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return parse_ts(build(**kw))


def test_a_new_lp_used_by_new_placements_is_not_a_swap_for_the_old_ones():
    ts = parse()
    assert ts.request_counts == {"NEW_PLACEMENT": 2, "NOT_WORKED": 2}
    assert sorted(p.placement_id for p in ts.worked) == ["1102", "1103"]


def test_it_is_said_out_loud():
    ts = parse()
    [note] = [a for a in ts.anomalies if a.code == LP_CLAIMED_BY_NEW]
    assert note.severity == "INFO"
    assert "LP_DEMO" in note.message and "2 white placement(s)" in note.message
    assert note.detail["placements"] == ["1100", "1101"]


def test_a_real_url_swap_still_reaches_the_old_placements():
    ts = parse(lp_paint="url")
    assert ts.request_counts.get("URL_SWAP") == 2
    assert not [a for a in ts.anomalies if a.code == LP_CLAIMED_BY_NEW]


def test_an_lp_no_new_placement_paints_still_propagates():
    # La cadena de BlackRock: la LP verde y nadie en Placements la reclama.
    ts = parse(new_claims_lp=False)
    assert ts.request_counts.get("URL_SWAP") == 2


def test_a_new_placement_keeps_an_existing_white_lp():
    from core.matching import build_expected
    ts = parse(lp_paint="white")
    assert ts.request_counts.get("NEW_PLACEMENT") == 2
    expected = build_expected(ts)
    assert expected["1102"].url == "https://landing.example"
    assert expected["1103"].url == "https://landing.example"
    # Un blanco no es un cambio: los existentes no entran al QA.
    assert "1100" not in {p.placement_id for p in ts.worked}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

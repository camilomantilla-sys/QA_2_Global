"""
Principio 5: el color en el nombre o el ID dice si un creativo entra o
sale; el color en otro campo dice que ese campo cambio.

Caso real (FB-13, Unilever Commerce, Dove/Degree): en cada decision set
el creativo Baseline va en blanco con sus fechas viejas en rojo, y
debajo dos filas del mismo creativo con las fechas nuevas en verde (un
tramo antes y otro despues del creativo MVM, que entra entero en
verde). En Innovid eso se implementa duplicando el creativo en el
decision set, un nodo por tramo.

QA2 leia la fila roja como "el creativo sale" y los dos nodos del mismo
creativo como un duplicado ambiguo. Ademas, cada placement de Degree
trae dos filas -- una por marca, cada una con su decision set -- y solo
se leia el primero.

Run with pytest, or directly:
    python tests/test_date_change_rows.py
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

from core.colors import GREEN  # noqa: E402
from core.innovid_reconciliation import MATCHED, reconcile  # noqa: E402
from core.matching import ExpectedCreative, build_expected  # noqa: E402
from parsers.ts_parser import (  # noqa: E402
    RED_FIELDS_ONLY, SUPERSEDED, parse_ts,
)
from tests.test_innovid_reconciliation import (  # noqa: E402
    _innovid, _node, _ts,
)

G = PatternFill("solid", fgColor="FF00FF00")
R = PatternFill("solid", fgColor="FFFF0000")

PL_HEADERS = ["Site Name", "Placement ID", "Placement Name", "Start Date",
              "End Date", "Dimensions", "Creative Rotation", "Landing Page"]
ROT_HEADERS = ["Creative Rotation", "Creative Name", "Creative ID",
               "Creative Type", "Dimensions / Durations", "Rotation (%) or Even",
               "Start Date", "End Date", "Landing Page Name"]

BASE = "Baseline_728x90.jpg"
MVM = "MVM_728x90.jpg"
LONE = "Lonely_728x90.jpg"


def build() -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    ws.append(PL_HEADERS)
    # Un placement con dos decision sets, uno por marca.
    for group in ("728x90 Web Ad", "728x90 Web Ad Degree"):
        ws.append(["Site", 11026727, "P_728", date(2026, 8, 27),
                   date(2026, 12, 31), "728x90", group, "LP"])

    ws = wb.create_sheet("Creative Rotations")
    ws.append(ROT_HEADERS)
    rows = [
        # grupo, creativo, id, inicio, fin, que se pinta
        ("728x90 Web Ad", BASE, 6364771, (8, 27), (12, 31), {"dates": R}),
        ("728x90 Web Ad", BASE, 6364771, (8, 27), (10, 18), {"dates": G}),
        ("728x90 Web Ad", BASE, 6364771, (11, 16), (12, 31), {"dates": G}),
        ("728x90 Web Ad", MVM, 6445545, (10, 19), (11, 15), {"row": G}),
        ("728x90 Web Ad Degree", "Degree_" + BASE, 6364999, (8, 27), (12, 31), {}),
        ("728x90 Web Ad Degree", LONE, 6364888, (8, 27), (12, 31), {"dates": R}),
    ]
    for group, name, cid, start, end, paint in rows:
        ws.append([group, name, cid, "Display", "728x90", "Even",
                   date(2026, *start), date(2026, *end), "LP"])
        r = ws.max_row
        if "dates" in paint:
            ws.cell(r, 7).fill = paint["dates"]
            ws.cell(r, 8).fill = paint["dates"]
        if "row" in paint:
            for col in range(2, 10):
                ws.cell(r, col).fill = paint["row"]
    wb.create_sheet("Landing Pages").append(["Landing Page Name", "Landing Page URL"])
    wb["Landing Pages"].append(["LP", "https://example.com"])
    wb.create_sheet("Campaign Information")
    target = Path(tempfile.mkdtemp()) / "ts.xlsx"
    wb.save(target)
    return target


def parse():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return parse_ts(build())


def test_red_dates_replaced_by_green_dates_is_a_date_change():
    result = parse()
    intents = [(r.values["creative_name"], r.intent) for r in result.rotations.rows]
    assert intents[0] == (BASE, SUPERSEDED)
    assert intents[1] == (BASE, GREEN)
    assert intents[2] == (BASE, GREEN)


def test_red_dates_with_nothing_green_goes_to_a_person():
    result = parse()
    lone = [r for r in result.rotations.rows if r.values["creative_name"] == LONE]
    assert lone[0].intent == "REVIEW"
    warned = [a for a in result.anomalies if a.code == RED_FIELDS_ONLY]
    assert len(warned) == 1 and LONE in warned[0].message


def test_a_placement_reads_every_decision_set_it_declares():
    expected = build_expected(parse())["11026727"]
    names = [(c.name, c.start) for c in expected.creatives]
    # Los dos tramos del Baseline, el MVM, y el decision set de Degree.
    assert (BASE, date(2026, 8, 27)) in names
    assert (BASE, date(2026, 11, 16)) in names
    assert (MVM, date(2026, 10, 19)) in names
    assert ("Degree_" + BASE, date(2026, 8, 27)) in names
    # La fila roja vieja no se espera en Innovid.
    assert not [c for c in expected.creatives
                if c.name == BASE and (c.start, c.end)
                == (date(2026, 8, 27), date(2026, 12, 31))]


def test_two_slots_of_one_creative_pair_with_their_two_nodes():
    ts = _ts("11087616", [
        ExpectedCreative(name=BASE, creative_id="6364771", intent=GREEN,
                         start=date(2026, 8, 27), end=date(2026, 10, 18)),
        ExpectedCreative(name=BASE, creative_id="6364771", intent=GREEN,
                         start=date(2026, 11, 16), end=date(2026, 12, 31)),
    ])
    got = _innovid("11087616", 40316, [
        _node(BASE, "2026-11-16", "2026-12-31", node_id=2, creative_id=6364771),
        _node(BASE, "2026-08-27", "2026-10-18", node_id=1, creative_id=6364771),
    ])
    flights = reconcile(ts, got).flights
    assert [f.status for f in flights] == [MATCHED, MATCHED]
    assert [(f.actual_start, f.actual_end) for f in flights] == [
        (date(2026, 8, 27), date(2026, 10, 18)),
        (date(2026, 11, 16), date(2026, 12, 31)),
    ]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

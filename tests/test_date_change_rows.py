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
    _by_rule, _findings, _innovid, _node, _ts,
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


GREY = PatternFill("solid", fgColor="FFBFBFBF")


def build(grey_first_group: bool = False) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    ws.append(PL_HEADERS)
    # Un placement con dos decision sets, uno por marca.
    for group in ("728x90 Web Ad", "728x90 Web Ad Degree"):
        ws.append(["Site", 11026727, "P_728", date(2026, 8, 27),
                   date(2026, 12, 31), "728x90", group, "LP"])
    if grey_first_group:
        # FB-10: el decision set viejo, desactivado en una solicitud
        # anterior, con su celda en gris.
        ws.cell(2, 7).fill = GREY

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


def parse(**kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return parse_ts(build(**kw))


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


def test_a_grey_decision_set_is_the_old_one_when_another_is_live():
    expected = build_expected(parse(grey_first_group=True))["11026727"]
    assert expected.group_name == "728x90 Web Ad Degree"
    names = {c.name for c in expected.creatives}
    assert names == {"Degree_" + BASE}


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



def test_two_creatives_in_two_slots_rotate_even_with_one_in_between():
    # FB-25/26: v1 y v2 corren del 16-nov al 5-dic y otra vez del 20 al
    # 31-dic; v3 entra en medio. Cinco filas al 20% y cinco nodos en el
    # decision set. Antes: INV-001 "appears 2 times" e INV-002 FAIL.
    v1, v2, v3 = "Holiday_v1_300x600.jpg", "Holiday_v2_300x600.jpg", "Holiday_v3_300x600.jpg"
    first = (date(2026, 11, 16), date(2026, 12, 5))
    middle = (date(2026, 12, 6), date(2026, 12, 19))
    last = (date(2026, 12, 20), date(2026, 12, 31))
    rows = [(v1, 1, first), (v1, 1, last), (v2, 2, first), (v2, 2, last), (v3, 3, middle)]
    ts = _ts("11310594", [
        ExpectedCreative(name=n, creative_id=str(cid), intent=GREEN,
                         start=d[0], end=d[1], rotation_weight="0.2")
        for n, cid, d in rows
    ])
    got = _innovid("11310594", 40316, [
        _node(n, d[0].isoformat(), d[1].isoformat(), node_id=i,
              creative_id=cid, weight=20)
        for i, (n, cid, d) in enumerate(rows, start=1)
    ])
    result = reconcile(ts, got)
    assert [f.status for f in result.flights] == [MATCHED] * 5
    findings = _findings(result)
    assert {f.status.name for f in _by_rule(findings, "INV-001")} == {"PASS"}
    assert {f.status.name for f in _by_rule(findings, "INV-002")} == {"PASS"}

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")


def test_the_second_date_range_shares_the_export_row():
    # El export Placement-Creative lista el creativo una vez por
    # placement; los dos tramos de la TS son la misma asignacion.
    from core.matching import (
        ActualCreative, ActualPlacement, ExpectedPlacement, _match_creatives,
    )
    ep = ExpectedPlacement(placement_id="11026729", creatives=[
        ExpectedCreative(name=BASE, creative_id="6364777", intent=GREEN,
                         start=date(2026, 8, 27), end=date(2026, 10, 18)),
        ExpectedCreative(name=BASE, creative_id="6364777", intent=GREEN,
                         start=date(2026, 11, 16), end=date(2026, 12, 31)),
        ExpectedCreative(name=MVM, creative_id="6445526", intent=GREEN,
                         start=date(2026, 10, 19), end=date(2026, 11, 15)),
    ])
    ap = ActualPlacement(placement_id="11026729", creatives=[
        ActualCreative(creative_id="6364777", filename=BASE),
        ActualCreative(creative_id="6445526", filename=MVM),
    ])
    links, extra = _match_creatives(ep, ap)
    assert [l.actual.creative_id if l.actual else None for l in links] == [
        "6364777", "6364777", "6445526"]
    assert extra == []

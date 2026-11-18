"""
Filas #N/A de Placements, recuperadas por el codigo del Placement Name.

Caso real (Wendy's, 18-nov): cinco filas con #N/A en Site, Placement ID
y fechas porque la formula no encontraba el placement en Prisma Output.
El Placement Name si estaba (P3KK98N|W3Z|HAM|006|...), y ese codigo es
tambien el principio del nombre del placement en Innovid. Regla de
AdOps: se recuperan, y lo que no haga match va a revision.

Y el swap de landing page en el mismo caso: la LP roja y la verde son un
swap, y la nueva va en TODOS los creativos de los decision sets que la
usan. Que uno ya la tenga no basta si otro sigue con la roja.

Run with pytest, or directly:
    python tests/test_ts_row_recovery.py
"""
from __future__ import annotations

import sys
import tempfile
import warnings
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import PatternFill  # noqa: E402

from core.findings import FindingsBuffer  # noqa: E402
from parsers.ts_parser import (  # noqa: E402
    REQ_URL_SWAP, ROW_RECOVERED, ROW_UNREADABLE, parse_ts, placement_code,
    recover_unreadable_rows,
)
from rules import placements, urls  # noqa: E402

G = PatternFill("solid", fgColor="FF00FF00")
R = PatternFill("solid", fgColor="FFFF0000")
OLD, NEW = "https://brand.example/old", "https://brand.example/new"


def build() -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    ws.append(["Site Name", "Placement ID", "Placement Name", "Start Date",
               "End Date", "Dimensions", "Creative Rotation", "Landing Page"])
    ws.append(["Site", 1100, "P3KK98M|W3Z|HAM|006|SITE", "2026-11-01",
               "2026-12-31", "1x1", "Group A", "LP_DEMO"])
    ws.append(["#N/A", "#N/A", "P3KK98N|W3Z|HAM|006|SITE", "#N/A",
               "#N/A", "#N/A", "Group A", "LP_DEMO"])
    ws.append(["#N/A", "#N/A", "P9ZZ99Z|W3Z|HAM|006|SITE", "#N/A",
               "#N/A", "#N/A", "Group A", "LP_DEMO"])
    lp = wb.create_sheet("Landing Pages")
    lp.append(["Landing Page Name", "Landing Page URL"])
    lp.append(["LP_DEMO", OLD])
    lp.cell(2, 2).fill = R
    lp.append(["LP_DEMO", NEW])
    lp.cell(3, 2).fill = G
    wb.create_sheet("Campaign Information")
    target = Path(tempfile.mkdtemp()) / "ts.xlsx"
    wb.save(target)
    return target


def parse():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return parse_ts(build())


def export(**names):
    rows = [SimpleNamespace(values={"placement_id": pid, "placement_name": name,
                                    "dimensions": "1x1"})
            for pid, name in names.items()]
    return SimpleNamespace(rows=rows)


INNOVID = export(**{"1100": "P3KK98M|W3Z|HAM|006|SITE|1 x 1 (1100)",
                    "1200": "P3KK98N|W3Z|HAM|006|SITE|1 x 1 (1200)"})


def test_the_code_is_the_start_of_the_name():
    assert placement_code("P3KK98N|W3Z|HAM|006|DBM") == "P3KK98N"
    assert placement_code("p3kk98n | W3Z") == "P3KK98N"
    assert placement_code("Display banner 300x250") == ""
    assert placement_code("NOCODES|x") == ""


def test_before_the_export_the_rows_wait():
    ts = parse()
    assert sorted(ts.scope) == ["1100"]
    assert len(ts.placements.pending) == 2
    assert len([a for a in ts.anomalies if a.code == ROW_UNREADABLE]) == 2


def test_the_export_gives_the_placement_id():
    ts = parse()
    recover_unreadable_rows(ts, INNOVID, None)
    assert sorted(ts.scope) == ["1100", "1200"]
    assert ts.scope["1200"].request_type == REQ_URL_SWAP
    assert ts.recovered_rows == [(3, "P3KK98N", "1200")]
    [info] = [a for a in ts.anomalies if a.code == ROW_RECOVERED]
    assert info.severity == "INFO" and "1200" in info.message
    [left] = [a for a in ts.anomalies if a.code == ROW_UNREADABLE]
    assert "P9ZZ99Z" in left.message and left.detail["row"] == 4
    assert [r.row for r in ts.unrecovered_rows] == [4]


def test_several_recovered_rows_are_said_once():
    ts = parse()
    recover_unreadable_rows(ts, export(**{"1200": "P3KK98N|W3Z", "1300": "P9ZZ99Z|W3Z"}), None)
    [info] = [a for a in ts.anomalies if a.code == ROW_RECOVERED]
    assert "row 3 → 1200, row 4 → 1300" in info.message
    assert not ts.unrecovered_rows


def test_the_rest_goes_to_review():
    ts = parse()
    recover_unreadable_rows(ts, INNOVID, None)
    buffer = FindingsBuffer()
    placements.evaluate(SimpleNamespace(
        matched=[], only_expected=[], unrecovered_ts_rows=ts.unrecovered_rows), buffer)
    [review] = buffer.findings
    assert (review.rule_id, review.status.value) == ("PLC-001", "REVIEW")
    assert "row 4" in review.message
    assert review.placement_name.startswith("P9ZZ99Z")


def test_another_export_starts_over():
    ts = parse()
    recover_unreadable_rows(ts, INNOVID, None)
    recover_unreadable_rows(ts, INNOVID, None)
    assert ts.recovered_rows == [(3, "P3KK98N", "1200")]
    recover_unreadable_rows(ts, export(**{"1100": "P3KK98M|W3Z"}), None)
    assert sorted(ts.scope) == ["1100"]
    assert ts.recovered_rows == []
    assert len(ts.unrecovered_rows) == 2
    assert not [a for a in ts.anomalies if a.code == ROW_RECOVERED]


# --- el swap de landing page llega a todos los creativos del DS ------

def _url_pm(*creatives, retired=(OLD,)):
    expected = SimpleNamespace(request_type=REQ_URL_SWAP, url=NEW, name="P_1",
                               retired_urls=list(retired), url_is_default_only=False)
    actual = SimpleNamespace(clicktags=[], creatives=[
        SimpleNamespace(name=name, creative_id=name, running=running, clicktags=[url])
        for name, url, running in creatives])
    return SimpleNamespace(placement_id="1", expected=expected, actual=actual)


def _url_findings(pm):
    buffer = FindingsBuffer()
    urls.evaluate_placement_urls(SimpleNamespace(matched=[pm]), buffer)
    return buffer.findings


def test_a_creative_left_on_the_red_page_fails():
    [found] = _url_findings(_url_pm(("old_1x1", OLD, True), ("new_1x1", NEW, True)))
    assert found.status.value == "FAIL"
    assert "1 creative in the decision set still points" in found.message
    assert "old_1x1" in found.message and found.actual == OLD


def test_every_creative_on_the_new_page_passes():
    [found] = _url_findings(_url_pm(("a", NEW, True), ("b", NEW, True)))
    assert found.status.value == "PASS"


def test_a_stopped_creative_or_another_page_is_not_the_swap():
    [found] = _url_findings(_url_pm(("old", OLD, False), ("new", NEW, True)))
    assert found.status.value == "PASS"
    [found] = _url_findings(_url_pm(("other", "https://brand.example/x", True),
                                    ("new", NEW, True)))
    assert found.status.value == "PASS"


def test_the_red_page_reaches_the_expected_placement():
    from core.matching import build_expected
    ts = parse()
    recover_unreadable_rows(ts, INNOVID, None)
    expected = build_expected(ts)
    assert expected["1200"].url == NEW
    assert expected["1200"].retired_urls == [OLD]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

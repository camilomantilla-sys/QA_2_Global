"""
Phase 1 of the Apps Script move (apps_script/poc).

snapshot.js is the reading of a sheet that Code.gs runs inside Google.
Here it gets, from a workbook built in the test, the same raw pieces
Google hands it (values, fills as hex, letter colours, links, hidden
rows, merged ranges), and has to see exactly the cells QA2's Python sees.
What this can't check is Google's own .xlsx conversion: that is what the
test with real Traffic Sheets in Google is for.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.colors import ColorResolver, classify, read_workbook_theme  # noqa: E402
from core.extraction import _fill_rgb, _font_rgb  # noqa: E402
from scripts.compare_ts_snapshots import compare_sheet, text_kind  # noqa: E402
from scripts.ts_snapshot import snapshot  # noqa: E402

SNAPSHOT_JS = ROOT / "apps_script" / "poc" / "snapshot.js"

RUN_JS = r"""
const S = require(process.argv[1]);
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const fmt = (d) => d.toISOString().slice(0, 19).replace("T", " ");
const revive = (v) => (v && typeof v === "object" && v.$date) ? new Date(v.$date + "Z") : v;
const out = {};
out.classify = input.colours.map((c) => S.classify(c)[0]);
out.hidden = input.parts ? S.hiddenRowsFromXlsx(input.parts) : null;
out.sheets = input.sheets.map((raw) => {
  raw.values = raw.values.map((row) => row.map(revive));
  return Object.assign(S.buildSheet(raw, fmt), {name: raw.name});
});
console.log(JSON.stringify(out));
"""


def _node(payload: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node isn't installed here")
    done = subprocess.run([node, "-e", RUN_JS, str(SNAPSHOT_JS)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def raw_like_google(path: Path) -> list[dict]:
    """What Code.gs collects for each sheet, built from the workbook itself."""
    resolver = ColorResolver(read_workbook_theme(path))
    wb = load_workbook(path, data_only=True)
    sheets = []
    for ws in wb.worksheets:
        last_r = max((c.row for row in ws.iter_rows() for c in row if c.value is not None), default=0)
        last_c = max((c.column for row in ws.iter_rows() for c in row if c.value is not None), default=0)
        values, backs, fonts, links = [], [], [], []
        for r in range(1, last_r + 1):
            vr, br, fr, lr = [], [], [], []
            for c in range(1, last_c + 1):
                cell = ws.cell(r, c)
                v = cell.value
                if isinstance(v, dt.datetime):
                    v = {"$date": v.isoformat()}
                vr.append("" if v is None else v)
                rgb = resolver.family(_fill_rgb(cell))[2]
                br.append("#" + (rgb[-6:] if rgb else "ffffff").lower())
                font = _font_rgb(cell)
                fr.append("#" + (font[-6:] if font else "000000").lower())
                lr.append(cell.hyperlink.target if cell.hyperlink else "")
            values.append(vr), backs.append(br), fonts.append(fr), links.append(lr)
        sheets.append({
            "name": ws.title, "values": values, "backgrounds": backs, "fontColors": fonts, "links": links,
            "hiddenRows": sorted(i for i, d in ws.row_dimensions.items() if d.hidden),
            "merges": [{"r1": m.min_row, "c1": m.min_col, "r2": m.max_row, "c2": m.max_col}
                       for m in ws.merged_cells.ranges],
        })
    return sheets


@pytest.fixture(scope="module")
def workbook(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("poc") / "ts.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    green = PatternFill("solid", fgColor="FFC6EFCE")
    red = PatternFill("solid", fgColor="FFFF0000")
    yellow = PatternFill("solid", fgColor="FFFFFF00")
    ws.append(["Placement ID", "Placement Name", "Start Date", "Rate", "Landing Page"])
    ws.append(["P3KK98M", "P3KK98M_ULV_X", dt.datetime(2026, 11, 16), 22789426, "https://lp.example/a"])
    ws.append(["P3KK98N", "  spaced   name ", dt.datetime(2026, 11, 17, 10, 30), 0.25, "#N/A"])
    ws.append(["HIDDEN", "template example", None, None, None])
    ws.append(["P3KK98P", "merged", None, 1.5, None])
    ws.append([None, None, None, None, None])
    ws.append(["P3KK98Q", "fill only next", None, None, None])
    for c in range(1, 6):
        ws.cell(2, c).fill = green
    ws.cell(3, 5).fill = red
    ws.cell(5, 1).fill = yellow
    ws.cell(7, 3).fill = green                 # a fill with no value
    ws.cell(3, 2).font = Font(color="FFFF0000")  # red letters, no fill
    ws.cell(2, 5).hyperlink = "https://lp.example/a"
    ws.row_dimensions[4].hidden = True
    ws.merge_cells("B5:B6")                    # merged: B6 takes B5
    ws.merge_cells("C6:D6")                    # anchor empty: nothing copied
    other = wb.create_sheet("Creative Rotations")
    other.append(["Group", "Creative"])
    other.append(["G1", "v1.jpg"])
    other.merge_cells("A2:A3")
    other.append([None, "v2.jpg"])
    wb.save(path)
    return path


def test_google_side_reads_the_cells_python_reads(workbook):
    py = snapshot(workbook)
    gs = _node({"colours": [], "sheets": raw_like_google(workbook)})
    for p, g in zip(py["sheets"], gs["sheets"]):
        assert p["name"] == g["name"]
        assert (p["maxRow"], p["hiddenRows"], p["mergedApplied"]) == (g["maxRow"], g["hiddenRows"], g["mergedApplied"])
        assert p["cells"] == g["cells"], p["name"]
        r = compare_sheet(p, g)
        assert set(r["texts"]) == {"same"}
        assert r["colours"]["different family"] == 0


def test_what_both_sides_see_in_the_test_sheet(workbook):
    sheet = snapshot(workbook)["sheets"][0]
    cells = {(c[0], c[1]): c for c in sheet["cells"]}
    assert 4 not in {c[0] for c in sheet["cells"]}              # hidden row skipped
    assert cells[(2, 3)][2] == "2026-11-16 00:00:00"
    assert cells[(3, 2)][2] == "spaced name" and cells[(3, 2)][5] == "FF0000"
    assert cells[(3, 5)][4] == "RED" and cells[(2, 1)][4] == "GREEN"
    assert cells[(6, 2)][2] == "merged" and cells[(6, 2)][7] == 5
    assert cells[(7, 3)][2] == "" and cells[(7, 3)][4] == "GREEN"
    assert cells[(2, 5)][6] == "https://lp.example/a"


def test_colour_families_match_python_on_every_shade():
    steps = ["00", "33", "66", "99", "CC", "E6", "FF", "C6", "F4"]
    colours = [r + g + b for r in steps for g in steps for b in steps]
    colours += ["C6EFCE", "FFC7CE", "FFEB9C", "D9D9D9", "92D050", "B0F467", "F2F2F2", "EDEDED"]
    got = _node({"colours": colours, "sheets": []})["classify"]
    assert got == [classify(c)[0] for c in colours]


def test_differences_are_told_apart():
    assert text_kind("22789426", "22789426") == "same"
    assert text_kind("0.25", "0.250") == "same number, written differently"
    assert text_kind("2026-11-16 00:00:00", "2026-11-16 05:00:00") == "same date, different time"
    assert text_kind("10:30:00", "1899-12-30 10:30:00") == "same time of day"
    assert text_kind("Display", "display") == "same text, different case"
    assert text_kind("a", "") == "only one side has a value"
    assert text_kind("a", "b") == "different text"


def xlsx_parts(path: Path) -> dict:
    """What Code.gs unzips from the .xlsx: the workbook, its links and the sheets."""
    import re
    import zipfile
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n).decode("utf-8") for n in z.namelist()
                if re.fullmatch(r"xl/(workbook\.xml|_rels/workbook\.xml\.rels|worksheets/[^/]+\.xml)", n)}


def test_hidden_rows_come_from_the_xlsx_like_python(workbook):
    # Excel's filters hide rows too, and Google's conversion may drop the
    # filter: the hidden rows are read from the .xlsx, as openpyxl does.
    got = _node({"colours": [], "sheets": [], "parts": xlsx_parts(workbook)})["hidden"]
    wb = load_workbook(workbook)
    assert got == {ws.title: sorted(i for i, d in ws.row_dimensions.items() if d.hidden) for ws in wb.worksheets}
    assert got["Placements"] == [4]

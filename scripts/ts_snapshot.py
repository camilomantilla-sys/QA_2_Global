"""
Phase 1 of the Apps Script move: what QA2's Python reads from a workbook.

Writes the same JSON that apps_script/poc/Code.gs writes from Google
Sheets, so scripts/compare_ts_snapshots.py can put the two side by side:
every cell QA2 would see (text, fill colour and its family, letter colour,
link, whether it came from a merged range), hidden rows, merged ranges,
and how long it took.

    python scripts/ts_snapshot.py "TS.xlsx" -o TS.python.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import load_workbook  # noqa: E402

from core.colors import ColorResolver, read_workbook_theme  # noqa: E402
from core.extraction import read_sheet  # noqa: E402

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def _rgb6(token: str | None) -> str | None:
    if not token:
        return None
    token = token.upper()
    return token[2:] if len(token) == 8 else token


def snapshot(path: Path) -> dict:
    started = time.perf_counter()
    timings: list[list] = []

    t = time.perf_counter()
    resolver = ColorResolver(read_workbook_theme(path))
    wb = load_workbook(path, data_only=True, keep_vba=False)
    info = {
        ws.title: (
            ws.sheet_state != "visible",
            sorted(i for i, d in ws.row_dimensions.items() if getattr(d, "hidden", False)),
            len(ws.merged_cells.ranges),
        )
        for ws in wb.worksheets
    }
    wb.close()
    timings.append(["Open the workbook", time.perf_counter() - t])

    sheets = []
    for name, (hidden, hidden_rows, merges) in info.items():
        t = time.perf_counter()
        grid, _ = read_sheet(path, name, capture_fill=True, skip_hidden=True)
        cells = []
        for r in sorted(grid.rows):
            for c in sorted(grid.rows[r]):
                cell = grid.rows[r][c]
                family, _conf, rgb = resolver.family(cell.fill_rgb)
                rgb = _rgb6(rgb)
                if cell.fill_rgb and rgb is None:
                    rgb = "?" + cell.fill_rgb      # a fill Python couldn't resolve
                if rgb == "FFFFFF":
                    rgb = None
                font = _rgb6(cell.font_rgb)
                cells.append([r, c, cell.text, rgb, family if rgb else "WHITE", font,
                              cell.hyperlink or None, cell.inherited_from_row or 0])
        sheets.append({
            "name": name, "hidden": hidden, "maxRow": grid.max_row,
            "hiddenRows": hidden_rows, "merges": merges,
            "mergedApplied": grid.merged_applied, "cells": cells,
        })
        timings.append([f'Read "{name}"', time.perf_counter() - t])

    return {"file": path.name, "reader": "python", "sheets": sheets,
            "timings": timings, "totalSecs": time.perf_counter() - started}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("workbook", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)
    snap = snapshot(args.workbook)
    out = args.out or args.workbook.with_suffix(".python.json")
    out.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    print(f"{out}  ({snap['totalSecs']:.1f} s, {sum(len(s['cells']) for s in snap['sheets'])} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

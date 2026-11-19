"""
Phase 1 of the Apps Script move: does Google read a workbook the way
QA2's Python does?

Takes the JSON from scripts/ts_snapshot.py (Python) and the one from
apps_script/poc/Code.gs (Google) for the same file, and writes a
Markdown report: per sheet, how many cells read the same text, the same
fill colour family, the same letter colour and link, plus hidden rows,
merged ranges and the time each side took.

    python scripts/compare_ts_snapshots.py TS.python.json QA2_test_TS.json -o report.md
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

EXAMPLES = 6
_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?: (\d{2}:\d{2}:\d{2}))?$")
_TIME = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def _number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def text_kind(a: str, b: str) -> str:
    """'same', or why the two readings of one cell differ."""
    if a == b:
        return "same"
    na, nb = _number(a), _number(b)
    if na is not None and nb is not None and abs(na - nb) <= 1e-9 * max(1.0, abs(na), abs(nb)):
        return "same number, written differently"
    da, db = _DATE.match(a), _DATE.match(b)
    if da and db and da.group(1) == db.group(1):
        return "same date, different time"
    if (_TIME.match(a) and db and b.endswith(a)) or (_TIME.match(b) and da and a.endswith(b)):
        return "same time of day"
    if a.casefold() == b.casefold():
        return "same text, different case"
    if not a or not b:
        return "only one side has a value"
    return "different text"


def compare_sheet(py: dict, gs: dict) -> dict:
    keep = lambda s: {(c[0], c[1]): c for c in s["cells"] if c[0] <= s["maxRow"]}  # noqa: E731
    a, b = keep(py), keep(gs)
    texts, colours, fonts, links = Counter(), Counter(), Counter(), Counter()
    examples: dict[str, list] = {}

    def note(kind: str, key, left, right):
        if len(examples.setdefault(kind, [])) < EXAMPLES:
            examples[kind].append((key, left, right))

    for key in sorted(set(a) | set(b)):
        x, y = a.get(key), b.get(key)
        tx, ty = (x[2] if x else ""), (y[2] if y else "")
        if tx or ty:
            k = text_kind(tx, ty)
            texts[k] += 1
            if k != "same":
                note("Text · " + k, key, tx, ty)
        fx, fy = (x[4] if x and x[3] else "none"), (y[4] if y and y[3] else "none")
        if fx != "none" or fy != "none":
            if fx == fy:
                colours["same family"] += 1
                colours["same exact colour" if (x[3] == y[3]) else "same family, other shade"] += 1
            else:
                colours["different family"] += 1
                note("Fill colour", key, f"{fx} {x[3] if x else ''}", f"{fy} {y[3] if y else ''}")
        ox, oy = (x[5] if x else None), (y[5] if y else None)
        if ox or oy:
            fonts["same" if ox == oy else "different"] += 1
            if ox != oy:
                note("Letter colour", key, ox, oy)
        lx, ly = (x[6] if x else None) or "", (y[6] if y else None) or ""
        if lx or ly:
            links["same" if lx == ly else "different"] += 1
            if lx != ly:
                note("Link", key, lx, ly)
    return {"texts": texts, "colours": colours, "fonts": fonts, "links": links, "examples": examples}


def _cell(key) -> str:
    r, c = key
    letters = ""
    while c:
        c, rem = divmod(c - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{r}"


def report(py: dict, gs: dict) -> str:
    out = [f"# {py['file']}", "",
           f"Python: {py['totalSecs']:.1f} s · Google: {gs['totalSecs']:.1f} s", ""]
    gs_steps = ", ".join(f"{t[0]} {t[1]:.1f} s" for t in gs.get("timings", []))
    out += [f"Google steps: {gs_steps}", ""]
    py_sheets = {s["name"]: s for s in py["sheets"]}
    gs_sheets = {s["name"]: s for s in gs["sheets"]}
    only = sorted(set(py_sheets) ^ set(gs_sheets))
    if only:
        out += [f"Sheets on one side only: {', '.join(only)}", ""]

    out += ["| Sheet | Cells with text | Same text | Fills | Same colour family | "
            "Hidden rows (Py/Google) | Merged ranges (Py/Google) | Last row (Py/Google) |",
            "|---|---|---|---|---|---|---|---|"]
    details = []
    for name in [s["name"] for s in py["sheets"] if s["name"] in gs_sheets]:
        p, g = py_sheets[name], gs_sheets[name]
        r = compare_sheet(p, g)
        total_t = sum(r["texts"].values())
        same_t = r["texts"]["same"] + r["texts"]["same number, written differently"]
        fills = r["colours"]["same family"] + r["colours"]["different family"]
        hidden = f"{len(p['hiddenRows'])}/{len(g['hiddenRows'])}" + (
            "" if p["hiddenRows"] == g["hiddenRows"] else " ⚠")
        out.append(f"| {name}{' (hidden)' if p['hidden'] else ''} | {total_t} | {same_t} | {fills} | "
                   f"{r['colours']['same family']} | {hidden} | {p['merges']}/{g['merges']} | "
                   f"{p['maxRow']}/{g['maxRow']} |")
        if r["examples"] or r["fonts"]["different"] or r["links"]["different"]:
            details += [f"## {name}", ""]
            kinds = {k: v for k, v in r["texts"].items() if k != "same"}
            if kinds:
                details.append("Text differences: " + ", ".join(f"{k} {v}" for k, v in kinds.items()))
            if r["colours"]:
                details.append(f"Fills: exact same colour {r['colours']['same exact colour']}, "
                               f"same family other shade {r['colours']['same family, other shade']}, "
                               f"different family {r['colours']['different family']}")
            if r["fonts"]:
                details.append(f"Letter colour: same {r['fonts']['same']}, different {r['fonts']['different']}")
            if r["links"]:
                details.append(f"Links: same {r['links']['same']}, different {r['links']['different']}")
            details.append("")
            for kind, rows in r["examples"].items():
                details.append(f"**{kind}** (Python → Google)")
                for key, left, right in rows:
                    details.append(f"- {_cell(key)}: `{str(left)[:80]}` → `{str(right)[:80]}`")
                details.append("")
    return "\n".join(out + [""] + details)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("python_json", type=Path)
    ap.add_argument("google_json", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args(argv)
    py = json.loads(args.python_json.read_text(encoding="utf-8"))
    gs = json.loads(args.google_json.read_text(encoding="utf-8"))
    text = report(py, gs)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

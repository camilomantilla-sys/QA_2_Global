"""
Fechas de la TS frente a Innovid, para mostrar (FB-24).

La campana del Campaign Information contra el Start/End Date de los
exports, y cada placement trabajado contra su fila del export. Una
diferencia se muestra; no cambia el veredicto.

Run with pytest, or directly:
    python tests/test_compare_dates.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.pipeline import compare_dates  # noqa: E402


def placement(pid, ts, innovid):
    return NS(
        placement_id=pid,
        expected=NS(name=f"DEMO_{pid}", start=ts[0], end=ts[1]),
        actual=NS(name=f"DEMO_{pid}", start=innovid[0], end=innovid[1]),
    )


def sources(campaign_start="2026-11-02 00:00:00", export_start="2026-10-15", matched=()):
    ts = NS(campaign_info={"campaignstart": campaign_start, "campaignend": "2026-12-31 00:00:00"})
    pc = NS(metadata={"startdate": export_start, "enddate": "2026-12-31"})
    return ts, pc, None, NS(matched=list(matched))


def test_a_campaign_start_that_differs_is_shown():
    out = compare_dates(*sources())
    camp = out["campaign"]
    assert camp["ts_start"] == "2026-11-02" and camp["innovid_start"] == "2026-10-15"
    assert camp["start_ok"] is False and camp["end_ok"] is True
    assert out["differences"] == 1


def test_same_dates_have_no_differences():
    same = (date(2026, 11, 2), date(2026, 12, 16))
    out = compare_dates(*sources(export_start="2026-11-02",
                                 matched=[placement("900100", same, same)]))
    assert out["differences"] == 0
    assert out["placements"][0]["start_ok"] is True


def test_a_placement_end_that_differs_comes_first():
    same = (date(2026, 11, 2), date(2026, 12, 16))
    moved = (date(2026, 11, 2), date(2026, 12, 31))
    out = compare_dates(*sources(export_start="2026-11-02", matched=[
        placement("900100", same, same), placement("900101", same, moved)]))
    assert out["differences"] == 1
    assert out["placements"][0]["placement_id"] == "900101"
    assert out["placements"][0]["end_ok"] is False


def test_a_missing_date_is_not_a_difference():
    out = compare_dates(*sources(campaign_start=""))
    assert out["campaign"]["start_ok"] is None
    assert out["differences"] == 0


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failed else 0)

"""
FB-08: revisar una solicitud por decision set.

Una solicitud de 40 placements que comparten 5 rotaciones repetia las
mismas fechas y URLs 40 veces. La vista por decision set las junta:
una fila por creativo (o por tramo), con los placements que lo
comparten, y el estado del peor hallazgo que ya existe.

Run with pytest, or directly:
    python tests/test_decision_set_view.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, WHITE  # noqa: E402
from core.decision_sets import DIRECT, decision_set_view  # noqa: E402
from core.innovid_reconciliation import reconcile  # noqa: E402
from core.matching import ExpectedCreative, ExpectedPlacement, build_expected  # noqa: E402
from tests.test_date_change_rows import BASE, MVM, parse  # noqa: E402
from tests.test_innovid_reconciliation import _innovid, _node  # noqa: E402

NOV = (date(2026, 11, 16), date(2026, 12, 5))


def _creative(name, group, url="https://example.com", dates=NOV, intent=GREEN):
    return ExpectedCreative(name=name, intent=intent, group=group, url=url,
                            start=dates[0], end=dates[1], rotation_weight="Even")


def _pm(pid, creatives, name="", actual_urls=None, group_name=""):
    ep = ExpectedPlacement(placement_id=pid, name=name or f"P_{pid}", dims="300x250",
                           group_name=group_name, creatives=creatives)
    actual_urls = actual_urls or {}
    links = [SimpleNamespace(
        expected=c, actual=None,
        url=SimpleNamespace(actual=SimpleNamespace(raw=actual_urls.get(c.name, c.url))),
    ) for c in creatives]
    return SimpleNamespace(placement_id=pid, expected=ep, creative_links=links)


def _row(pid, status, creative=""):
    return {"placement_id": pid, "status": status, "creative": creative}


def test_the_traffic_sheet_rotation_travels_with_each_creative():
    expected = build_expected(parse())["11026727"]
    groups = {c.name: c.group for c in expected.creatives}
    assert groups[BASE] == "728x90 Web Ad"
    assert groups[MVM] == "728x90 Web Ad"
    assert groups["Degree_" + BASE] == "728x90 Web Ad Degree"


def test_placements_that_share_a_decision_set_are_one_block():
    match = SimpleNamespace(matched=[
        _pm("1", [_creative("A.jpg", "Display 300x250"), _creative("B.jpg", "Display 300x250")]),
        _pm("2", [_creative("A.jpg", "Display 300x250"), _creative("B.jpg", "Display 300x250")]),
    ])
    view = decision_set_view(match, [_row("1", "PASS", "A.jpg"), _row("2", "REVIEW", "B.jpg")])
    assert len(view) == 1
    ds = view[0]
    assert ds["name"] == "Display 300x250"
    assert [p["placement_id"] for p in ds["placements"]] == ["2", "1"]  # el peor primero
    assert ds["status"] == "REVIEW"
    rows = {r["creative"]: r for r in ds["rows"]}
    assert rows["A.jpg"]["placements"] == ["1", "2"]
    assert rows["A.jpg"]["status"] == "PASS"
    assert rows["B.jpg"]["status"] == "REVIEW"
    assert rows["A.jpg"]["ts_start"] == "2026-11-16"
    assert rows["A.jpg"]["innovid_url"] == {
        "value": "https://example.com", "values": ["https://example.com"], "varies": False}


def test_two_date_ranges_of_one_creative_are_two_rows():
    late = (date(2026, 12, 20), date(2026, 12, 31))
    match = SimpleNamespace(matched=[
        _pm("1", [_creative("A.jpg", "DS"), _creative("A.jpg", "DS", dates=late)]),
    ])
    rows = decision_set_view(match, [])[0]["rows"]
    assert [(r["creative"], r["ts_start"]) for r in rows] == [
        ("A.jpg", "2026-11-16"), ("A.jpg", "2026-12-20")]


def test_a_placement_with_a_different_url_is_flagged():
    match = SimpleNamespace(matched=[
        _pm("1", [_creative("A.jpg", "DS")]),
        _pm("2", [_creative("A.jpg", "DS")], actual_urls={"A.jpg": "https://other.com"}),
    ])
    url = decision_set_view(match, [])[0]["rows"][0]["innovid_url"]
    assert url["varies"] is True
    assert url["values"] == ["https://example.com", "https://other.com"]


def test_direct_assignments_and_bare_placements_go_last():
    match = SimpleNamespace(matched=[
        _pm("1", [_creative("Direct.jpg", "", intent=WHITE)]),
        _pm("2", [_creative("A.jpg", "DS")]),
        _pm("3", []),  # un 1x1 sin creativos esperados
    ])
    view = decision_set_view(match, [_row("1", "FAIL")])
    assert [g["name"] for g in view] == ["DS", DIRECT]
    direct = view[1]
    assert direct["status"] == "FAIL"
    assert {p["placement_id"] for p in direct["placements"]} == {"1", "3"}
    assert direct["rows"][0]["intent"] == "No change"


def test_a_placement_missing_from_the_export_still_shows():
    match = SimpleNamespace(
        matched=[_pm("1", [_creative("A.jpg", "DS")])],
        only_expected=[ExpectedPlacement(placement_id="2", name="P_2",
                                         creatives=[_creative("A.jpg", "DS")])],
    )
    ds = decision_set_view(match, [_row("2", "FAIL")])[0]
    assert ds["status"] == "FAIL"
    assert [(p["placement_id"], p["missing"]) for p in ds["placements"]] == [
        ("2", True), ("1", False)]
    assert ds["rows"][0]["placements"] == ["1", "2"]


def test_innovid_dates_and_hours_come_from_the_live_check():
    creative = _creative("V1.jpg", "Display 300x600")
    match = SimpleNamespace(matched=[_pm("11310594", [creative])])
    got = _innovid("11310594", 40316, [_node("V1.jpg", "2026-11-16", "2026-12-05")])
    reconciliation = reconcile(match, got)
    ds = decision_set_view(match, [], reconciliation)[0]
    row = ds["rows"][0]
    assert row["innovid_start"]["value"].startswith("2026-11-16")
    assert row["innovid_end"]["value"].startswith("2026-12-05")
    assert "23:59" in row["innovid_end"]["value"]
    assert ds["innovid_names"] == ["Display 300x600"]


def test_the_innovid_default_shows_in_its_decision_set():
    from core.innovid_reconciliation import DEFAULT_AD, CreativeFlightCheck, InnovidReconciliation
    match = SimpleNamespace(matched=[_pm("1", [_creative("A.jpg", "DS")]),
                                     _pm("2", [_creative("A.jpg", "DS")])])
    rec = InnovidReconciliation(default_ads=[
        CreativeFlightCheck(placement_id=pid, status=DEFAULT_AD, is_default=True,
                            actual_name="A.jpg", actual_start=date(2026, 11, 16))
        for pid in ("1", "2")])
    [d] = decision_set_view(match, [], rec)[0]["defaults"]
    assert d["creative"] == "A.jpg" and d["placements"] == ["1", "2"]
    assert d["innovid_end"] == "ongoing"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

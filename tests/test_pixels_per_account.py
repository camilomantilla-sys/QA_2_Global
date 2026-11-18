"""
El pixel oficial, una columna por cuenta (AdOps, 18-nov-2026).

El DV Monitoring de BlackRock no es el de Unilever: el de Unilever
lleva ctx=715607 y el de BlackRock ctx=27799358. Con un solo "Official
pixel" una solicitud de BlackRock salia con 60 Review por un pixel que
estaba bien. Ahora la tabla tiene Unilever / BlackRock / Wendy's
official pixel, y cada cuenta se compara solo contra la suya.

Run with pytest, or directly:
    python tests/test_pixels_per_account.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.pixel_reconciliation as pixels  # noqa: E402
from tests.test_dv_routing import ts, view  # noqa: E402

UNI = "https://cdn.doubleverify.com/dvtp_src.js#ctx=715607&cmp=[%campaignID%]&plc=[%placementID%]"
BLK = "https://cdn.doubleverify.com/dvtp_src.js#ctx=27799358&cmp=[%campaignID%]&plc=[%placementID%]"
BLK_FOUND = "https://cdn.doubleverify.com/dvtp_src.js#ctx=27799358&cmp=[%campaignID%]&plc=[%placementID%]"


def _table(**by_account):
    row = {"account": "", "name": "DV Monitoring", "ts_terms": ["dv", "doubleverify"],
           "host_terms": [], "column": pixels.SURVEY, "formats": ["display"],
           "official_pixels": by_account}
    return (pixels._dict_to_vendor(row),)


def _check(table, account, found=BLK_FOUND):
    original = pixels.load_vendors
    pixels.load_vendors = lambda: table
    try:
        [check] = pixels.reconcile_pixels(
            ts(("11352823", "300x250", "DV Monitoring")),
            view(**{"11352823": found}), account).checks
        return check
    finally:
        pixels.load_vendors = original


def test_each_account_compares_against_its_own_pixel():
    table = _table(Unilever=UNI, BlackRock=BLK, **{"Wendy's": UNI})
    assert _check(table, "BlackRock").result == "PASS"
    review = _check(table, "Unilever")
    assert review.result == "REVIEW"
    assert "Unilever's official pixel" in review.message
    assert review.official == UNI


def test_an_empty_account_column_only_checks_the_pixel_is_there():
    assert _check(_table(Unilever=UNI, BlackRock=""), "BlackRock").result == "PASS"


def test_with_no_account_any_accounts_pixel_counts():
    table = _table(Unilever=UNI, BlackRock=BLK)
    assert _check(table, "").result == "PASS"
    other = "https://cdn.doubleverify.com/dvtp_src.js#ctx=1&cmp=[%campaignID%]&plc=[%placementID%]"
    assert _check(table, "", found=other).result == "REVIEW"


def test_an_old_row_spreads_its_pixel_to_the_accounts_it_applies_to():
    assert pixels.official_map("", UNI, None) == {
        "Unilever": UNI, "BlackRock": UNI, "Wendy's": UNI}
    assert pixels.official_map("Wendy's", UNI, None) == {
        "Unilever": "", "BlackRock": "", "Wendy's": UNI}
    old = pixels._dict_to_vendor({"name": "DV Monitoring", "official_pixel": UNI})
    assert old.officials_for("BlackRock") == (UNI,)


def test_saving_keeps_the_three_columns():
    [vendor] = _table(Unilever=UNI, BlackRock=BLK)
    saved = pixels._vendor_to_dict(vendor)
    assert saved["official_pixels"] == {"Unilever": UNI, "BlackRock": BLK, "Wendy's": ""}
    assert "official_pixel" not in saved


def test_an_account_row_wins_over_a_general_row_of_the_same_vendor():
    general = _table(Unilever=UNI, BlackRock=UNI)
    scoped = pixels._dict_to_vendor({
        "account": "BlackRock", "name": "DV Monitoring", "ts_terms": ["dv"],
        "column": pixels.SURVEY, "formats": ["display"], "official_pixel": BLK})
    assert _check(general + (scoped,), "BlackRock").result == "PASS"


def test_the_shipped_config_has_the_three_columns():
    import json
    rows = json.loads((Path(__file__).resolve().parents[1] / "config" / "vendor_pixels.json")
                      .read_text(encoding="utf-8"))
    for row in rows:
        assert set(row["official_pixels"]) == set(pixels.PIXEL_ACCOUNTS), row["name"]
        assert "official_pixel" not in row


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

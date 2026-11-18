"""
Solicitudes raras inventadas (estilo Wendy's, 18-nov) y lo que QA2
tiene que decir de cada una.

AdOps pidio probar la interpretacion con TS y exports inventados con
casos extranos. Cada caso esta descrito en tests/odd_requests.py; aqui
se arma la TS y los dos exports con el formato real, se corre el QA
completo y se revisa lo que importa de cada uno.

Run with pytest, or directly:
    python tests/test_odd_requests.py
"""
from __future__ import annotations

import sys
import tempfile
import warnings
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import pipeline as P  # noqa: E402
from core.matching import match  # noqa: E402
from tests.odd_requests import ALL  # noqa: E402
from tests.synthetic_requests import build  # noqa: E402

CASES = {sc["id"].split("_")[0]: sc for sc in ALL}


@lru_cache(maxsize=None)
def run(case: str):
    out = Path(tempfile.mkdtemp())
    build(CASES[case], out)
    one = lambda k: next((out / k).iterdir())  # noqa: E731
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ts = P.parse_traffic_sheet(one("ts").read_bytes(), one("ts").name)
        pc = P.parse_export(one("pc").read_bytes(), "pc.xlsx")
        pl = P.parse_export(one("pl").read_bytes(), "pl.xlsx")
        checks = P.run_checks(match(ts, pc, pl), ts, pc, pl, [], None, account="Wendy's")
    return ts, checks.findings.findings


def status(case, rule, pid="", creative=""):
    _ts, found = run(case)
    return sorted(f.status.value for f in found
                  if f.rule_id == rule and (not pid or f.placement_id == pid)
                  and (not creative or f.creative_name == creative))


def anomalies(case):
    ts, _ = run(case)
    return {a.code for a in ts.anomalies}


def test_lp_swap_reaches_every_creative():
    assert status("s01", "URL-002", "9100001") == ["PASS"]
    assert status("s01", "URL-002", "9100002") == ["FAIL"]   # un creativo con la URL roja


def test_green_url_without_a_name_is_still_the_new_one():
    ts, _ = run("s01")
    assert [r.intent for r in ts.landing_pages.rows] == ["RED", "GREEN"]


def test_whole_red_lp_and_a_new_green_lp_are_a_swap():
    assert status("s02", "URL-002", "9200001") == ["PASS"]
    assert status("s02", "URL-002", "9200002") == ["FAIL"]


def test_removed_creative_still_running_fails():
    assert status("s03", "CRE-001", "9300002", "HOL_300x250_OLD") == ["FAIL"]


def test_date_only_change_is_a_field_change_compared_against_the_export():
    ts, _ = run("s04")
    assert ts.scope["9400001"].request_type == "FIELD_CHANGE"
    # El export trae fechas propias del creativo (12-15) y la TS pide 01-15.
    assert status("s04", "INV-001", "9400001") == ["FAIL"]


def test_export_dates_that_are_the_placement_flight_cannot_prove_a_creative_date():
    assert status("s25", "INV-001", "9250001") == ["PASS"]
    assert status("s25", "INV-001", "9250002") == ["REVIEW"]


def test_new_placement_missing_from_innovid():
    assert status("s05", "PLC-001", "9500002") == ["FAIL"]


def test_na_rows_recovered_or_sent_to_review():
    ts, found = run("s07")
    assert "9700002" in ts.scope
    assert [f.status.value for f in found if f.rule_id == "PLC-001" and not f.placement_id] == ["REVIEW"]


def test_reading_warnings():
    assert "TS-LP-UNKNOWN" in anomalies("s09")
    assert "TS-FONT-COLOUR" in anomalies("s10")
    assert "TS-HIDDEN-ROWS" in anomalies("s14")
    assert "TS-LP-DUPLICATE" in anomalies("s21")


def test_only_the_landing_page_cell_painted_is_a_url_change():
    ts, _ = run("s12")
    assert ts.scope["9120001"].request_type == "URL_SWAP"
    assert ts.scope["9120002"].request_type == "NOT_WORKED"
    assert status("s12", "URL-002", "9120001") == ["PASS"]


def test_a_creative_missing_from_a_new_decision_set_fails():
    assert status("s17", "CRE-001", "9170001", "N_300x250_2") == ["FAIL"]


def test_a_red_placement_is_switched_off_even_if_its_rotation_adds_a_creative():
    ts, _ = run("s19")
    assert ts.scope["9190001"].request_type == "CREATIVE_REMOVE"
    assert status("s19", "PLC-003") == []
    assert status("s19", "PLC-002", "9190001") == ["PASS"]


def test_a_landing_page_listed_twice_goes_to_review():
    assert status("s21", "URL-001", "9210001") == ["REVIEW"]


def test_new_creative_not_uploaded_fails_instead_of_rotation_swap():
    assert status("s22", "CRE-001", "9220001", "NEW_300x250") == ["FAIL"]


def test_placement_size_differs():
    assert status("s23", "PLC-005", "9230001") == ["REVIEW"]


def test_green_url_above_the_red_one_still_wins():
    assert status("s24", "URL-001", "9240001") == ["PASS"]


def test_http_against_https_says_exactly_what_differs():
    _ts, found = run("s20")
    fail = [f.message for f in found if f.rule_id == "URL-002" and f.status.value == "FAIL"]
    assert fail and "Only the protocol differs: https / http (TS / Innovid)" in fail[0]


def test_the_excel_puts_the_differing_part_in_bold():
    from io import BytesIO

    import pandas as pd
    from openpyxl import load_workbook

    from core.excel_report import build_excel_report
    from core.qa_export import COLUMNS
    from tests.test_excel_signed_off import _meta

    row = {column: "" for column in COLUMNS}
    row.update({"Status": "FAIL", "TS URL": "https://brand.example/a?u=1&v=2",
                "Innovid URL": "http://brand.example/a?v=2&u=1"})
    empty = pd.DataFrame()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = build_excel_report(_meta(), empty, empty, empty, qa_rows=[row])
    ws = load_workbook(BytesIO(data), rich_text=True)["QA"]
    header = {c.value: c.column for c in ws[1] if c.value}
    bold = [[b.text for b in ws.cell(2, header[col]).value
             if not isinstance(b, str) and b.font.b]
            for col in ("TS URL", "Innovid URL")]
    assert bold == [["https"], ["http"]]


def test_clean_cases_stay_clean():
    for case in ("s08", "s11", "s13", "s16", "s18"):
        _ts, found = run(case)
        bad = [(f.rule_id, f.message) for f in found if f.status.value in ("FAIL", "REVIEW")]
        assert not bad, (case, bad)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

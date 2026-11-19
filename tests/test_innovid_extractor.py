"""
The Innovid Extractor walks Innovid on its own and writes an Excel.

No real Innovid here: `call` is replaced by canned answers shaped like
the ones the API gives, so the walk, the give-up rule and the workbook
can be checked end to end.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "innovid_extractor"


@pytest.fixture(scope="module")
def ext():
    spec = importlib.util.spec_from_file_location("innovid_extractor_mod", FOLDER / "extractor.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module   # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


def _summary(page, total):
    rows = {
        1: [
            {"level": "PLACEMENT", "placementId": "9001", "placementName": "P1_Video", "siteName": "Site A",
             "status": "Active", "startDate": "2026-11-01", "endDate": "2026-12-31",
             "verificationPartner": "DoubleVerify", "verificationStatus": "Applied",
             "placementModernDtreeId": "500", "modernDtreeName": "DS one"},
            {"level": "PLACEMENT-CREATIVE", "placementId": "9001", "placementName": "P1_Video",
             "creativeId": "71", "fileName": "Spot_A.mp4", "clickTag1": "https://www.brand.example/a",
             "thirdPartyImpression1": "https://px.example/i"},
            {"level": "SITE", "siteName": "Site A"},   # no placement id: not a placement
        ],
        2: [
            {"level": "PLACEMENT", "placementId": "9002", "placementName": "P2_Video", "siteName": "Site B",
             "status": "Active", "verificationPartner": "", "decisionSetId": "600", "decisionSetName": "DS two"},
            {"level": "PLACEMENT-CREATIVE", "placementId": "9002", "creativeId": "72", "fileName": "Spot_B.mp4"},
        ],
    }
    return {"items": rows[page], "totalPages": total}


def _dset(dset_id, name, nodes):
    return {"id": dset_id, "name": name, "servingMethod": "WEIGHTED", "nodes": nodes}


def make_call(dsets=None, sites=True, log=None):
    dsets = dsets if dsets is not None else {
        "500": _dset("500", "DS one", [
            {"serving": {"id": "71", "name": "Spot_A.mp4"}, "startTimestamp": "2026-11-05 00:00:00",
             "endTimestamp": None, "weight": 2},
            {"isDefault": True, "startTimestamp": "2026-11-01 00:00:00", "endTimestamp": "2026-12-31 23:59:00"},
        ]) | {"defaultServing": {"id": "70", "name": "Default.mp4"}},
        "600": _dset("600", "DS two", [
            {"serving": {"id": "72", "name": "Spot_B.mp4"}, "startTimestamp": "2026-11-10 00:00:00",
             "endTimestamp": "2026-11-20 00:00:00", "weight": 1}]),
    }

    def call(url, method, body):
        if log is not None:
            log.append((method, url))
        if "/summary" in url:
            return _summary(body["page"], 2)
        if "/dset/" in url:
            key = url.rsplit("/", 1)[1]
            if key not in dsets:
                raise RuntimeError("HTTP 400")
            return dsets[key]
        if url.endswith("campaign-sites?rpp=543"):
            if not sites:
                raise RuntimeError("HTTP 404")
            return {"items": [{"id": 1, "site": {"id": 11, "name": "Site A"}}]}
        if "/campaign-sites/1" in url:
            return {"videoConfig": {"optionGroups": {"ctvOttGroup": {"mediaFilter": None}}}}
        raise AssertionError(url)

    return call


def test_reads_every_page_every_decision_set_and_the_sites(ext):
    ex = ext.extract("330001", make_call(), say=lambda _m: None)
    assert ex.summary_pages == 2
    assert [p.placement_id for p in ex.placements] == ["9001", "9002"]
    assert [c.file_name for c in ex.creatives] == ["Spot_A.mp4", "Spot_B.mp4"]
    assert (ex.dsets_asked, ex.dsets_read) == (2, 2)
    default = [n for n in ex.nodes if n.is_default][0]
    assert (default.creative_id, default.creative_name) == ("70", "Default.mp4")
    assert ex.media_filters == [("11", "Site A", "Default")]
    assert ex.errors == []
    assert [name for name, _ in ex.timings] == [
        "Campaign summary (placements)", "Decision sets (creatives)", "Media Filters (sites)"]


def test_a_decision_set_that_answers_for_another_id_is_ignored(ext):
    wrong = {"500": _dset("999", "DS one", []), "600": _dset("600", "DS two", [])}
    ex = ext.extract("330001", make_call(dsets=wrong), say=lambda _m: None)
    assert ex.dsets_read == 1
    assert any("returned 999" in e for e in ex.errors)


def test_gives_up_after_three_identical_failures(ext):
    def call(url, method, body):
        if "/summary" in url:
            items = [{"level": "PLACEMENT", "placementId": str(9000 + i), "placementModernDtreeId": str(500 + i)}
                     for i in range(6)]
            return {"items": items, "totalPages": 1}
        if "/dset/" in url:
            raise RuntimeError("HTTP 400")
        return {"items": []}

    log = []
    ex = ext.extract("330001", lambda u, m, b: (log.append(u), call(u, m, b))[1], say=lambda _m: None)
    assert sum("/dset/" in u for u in log) == 3
    assert any("Stopped asking for 3 more" in e for e in ex.errors)


def test_media_filters_failing_does_not_lose_the_rest(ext):
    ex = ext.extract("330001", make_call(sites=False), say=lambda _m: None)
    assert ex.dsets_read == 2
    assert any("Media Filters" in e for e in ex.errors)


def test_an_expired_session_stops_the_walk(ext):
    def call(url, method, body):
        raise ext.SessionProblem("HTTP 401")

    with pytest.raises(ext.SessionProblem):
        ext.extract("330001", call, say=lambda _m: None)


def test_the_workbook_puts_decision_set_dates_next_to_each_creative(ext, tmp_path):
    ex = ext.extract("330001", make_call(), say=lambda _m: None)
    path = ext.write_workbook(ex, tmp_path / "out.xlsx", [("Sign-in", 12.0)])
    wb = load_workbook(path)
    assert wb.sheetnames == ["Summary", "Placements", "Creatives", "Decision sets", "Media Filters"]

    creatives = list(wb["Creatives"].iter_rows(values_only=True))
    head = creatives[0]
    a = dict(zip(head, creatives[1]))
    assert a["File name"] == "Spot_A.mp4"
    assert a["Click URL"] == "https://www.brand.example/a"
    assert (a["DS start"], a["DS end"], a["DS weight"]) == ("2026-11-05 00:00:00", "Ongoing", "2")
    b = dict(zip(head, creatives[2]))
    assert (b["DS start"], b["DS end"]) == ("2026-11-10 00:00:00", "2026-11-20 00:00:00")

    placements = list(wb["Placements"].iter_rows(values_only=True))
    p1 = dict(zip(placements[0], placements[1]))
    assert p1["Verification Partner"] == "DoubleVerify"

    summary = dict(wb["Summary"].iter_rows(min_row=2, values_only=True))
    assert summary["Time · Sign-in"] == "12.0 s"
    assert "Time · total" in summary
    assert summary["Could not read"] == "Nothing: everything was read."


def test_campaign_ids_are_read_from_whatever_is_typed(ext):
    assert ext.campaign_ids("330328, 305807 311907 330328") == ["330328", "305807", "311907"]
    assert ext.campaign_ids("") == []


def test_the_extractor_imports_nothing_from_qa2():
    tree = ast.parse((FOLDER / "extractor.py").read_text(encoding="utf-8"))
    qa2 = {"core", "rules", "parsers", "ui", "cli", "scripts", "config"}
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        assert not {n.split(".")[0] for n in names} & qa2, names


def test_the_sign_in_and_output_never_reach_git():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for path in ("innovid_extractor/session/", "innovid_extractor/output/", "innovid_extractor/.venv/"):
        assert path in ignored


def test_the_qa2_package_does_not_ship_the_extractor():
    from scripts import package_release

    assert "innovid_extractor" in package_release.SKIP_DIRS


def test_the_decision_set_line_under_a_placement_is_not_a_creative(ext, tmp_path):
    """
    Shape seen on a real campaign: the placement row has no decision
    set id; Innovid lists the decision set as a creative-level line with
    no creative id. And the default node is also one of the rotation
    creatives, with a timestamp that is not a flight.
    """
    def call(url, method, body):
        if "/summary" in url:
            return {"totalPages": 1, "items": [
                {"level": "PLACEMENT", "placementId": "9001", "placementName": "P1", "status": "Live"},
                {"level": "PLACEMENT-CREATIVE", "placementId": "9001", "fileName": "Display 160x600",
                 "placementModernDtreeId": "43580", "modernDtreeName": "Display 160x600"},
                {"level": "PLACEMENT-CREATIVE", "placementId": "9001", "creativeId": "1", "fileName": "v1.jpg"},
            ]}
        if "/dset/" in url:
            return {"id": "43580", "name": "Display 160x600", "servingMethod": "Rotation",
                    "defaultServing": {"id": "1", "name": "v1.jpg"}, "nodes": [
                        {"serving": {"id": "1", "name": "v1.jpg"}, "startTimestamp": "2026-11-16 00:00:00",
                         "endTimestamp": "2026-12-05 23:59:00", "weight": 1},
                        {"isDefault": True, "startTimestamp": "2026-11-05 10:01:53", "endTimestamp": None}]}
        return {"items": []}

    ex = ext.extract("337000", call, say=lambda _m: None)
    assert [c.file_name for c in ex.creatives] == ["v1.jpg"]
    wb = load_workbook(ext.write_workbook(ex, tmp_path / "o.xlsx"))

    pl = list(wb["Placements"].iter_rows(values_only=True))
    p1 = dict(zip(pl[0], pl[1]))
    assert (p1["Decision set"], p1["Decision set ID"]) == ("Display 160x600", "43580")

    cr = list(wb["Creatives"].iter_rows(values_only=True))
    assert len(cr) == 2
    v1 = dict(zip(cr[0], cr[1]))
    assert (v1["DS start"], v1["DS end"], v1["DS weight"], v1["Default"]) == (
        "2026-11-16 00:00:00", "2026-12-05 23:59:00", "1", "Yes")

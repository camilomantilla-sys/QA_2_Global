"""
Parser tests for core/innovid_api.

The payloads below are the real shapes captured from Innovid's own
network traffic (campaign 323492, decision set 38808, placements
10988717/10988718), so if Innovid changes its response format these
tests are what notices.

Run with pytest, or directly:  python tests/test_innovid_api.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.innovid_api import (  # noqa: E402
    InnovidFetchResult,
    load_credentials,
    parse_dset_response,
    parse_summary_response,
)

# The dset/38808 response as returned by Innovid.
DSET_38808 = {
    "id": 38808,
    "campaign": {"id": 323492},
    "decisionSetType": "Creative",
    "defaultServing": {"id": 6312751, "name": "320x50.jpg", "adType": "altimage"},
    "dimensions": ["320x50"],
    "hasErrors": False,
    "lastPublished": "2026-07-24T20:59:09+0000",
    "name": "Frosty GM Display 320x50",
    "nodes": [
        {"id": 1, "startTimestamp": "2026-07-24 00:00:00",
         "endTimestamp": None, "weight": 1},
        {"id": 6312751, "startTimestamp": "2026-07-24 15:59:09",
         "endTimestamp": None, "isDefault": True},
    ],
    "placementType": {"name": "HTML"},
    "servingMethod": "Rotation",
    "status": "Published",
    "timezone": None,
}

# A /summary response for the two placements that share that dset.
SUMMARY = {
    "page": 1,
    "rpp": 500,
    "totalItems": 2,
    "totalPages": 1,
    "items": [
        {
            "placementId": 10988718,
            "placementName": "P3JF5Y1|WEN|FRO|001|GUMGUM|320 x 50",
            "siteName": "GumGum",
            "dimensions": ["320x50"],
            "status": "Active",
            "startDate": "2026-07-20",
            "endDate": "2026-08-23",
            "creativeId": 6312751,
            "fileName": "320x50.jpg",
            "clickTag1": "https://m-wendys.com/offer",
            "thirdPartySurvey1": None,
            "thirdPartyImpression1": "",
            "thirdPartyImpression2": None,
            "verificationPartner": "DoubleVerify",
            "verificationStatus": "Applied",
            "rotationWeight": None,
            "bookedUnits": 33333333,
            "placementModernDtreeId": 38808,
            "modernDtreeName": "Frosty GM Display 320x50",
        },
        {
            "placementId": 10988717,
            "placementName": "P3JF5Y2|WEN|FRO|001|GUMGUM|320 x 50",
            "siteName": "GumGum",
            "dimensions": ["320x50"],
            "status": "Active",
            "startDate": "2026-07-20",
            "endDate": "2026-08-23",
            "creativeId": 6312751,
            "fileName": "320x50.jpg",
            "verificationPartner": "DoubleVerify",
            "verificationStatus": "Applied",
            "bookedUnits": 5000000,
            "placementModernDtreeId": 38808,
            "modernDtreeName": "Frosty GM Display 320x50",
        },
    ],
}


def test_dset_gives_creative_dates_weight_and_serving_method():
    nodes = parse_dset_response(DSET_38808)

    assert len(nodes) == 2
    assert nodes[0].dtree_id == "38808"
    assert nodes[0].dtree_name == "Frosty GM Display 320x50"
    assert nodes[0].serving_method == "Rotation"
    assert nodes[0].start_timestamp == "2026-07-24 00:00:00"
    assert nodes[0].weight == "1"
    assert nodes[1].creative_id == "6312751"


def test_null_end_timestamp_means_ongoing_not_missing():
    # Innovid shows "Ongoing" for these; inventing a date would be
    # worse than leaving it blank.
    nodes = parse_dset_response(DSET_38808)
    assert nodes[0].end_timestamp == ""


def test_default_creative_is_flagged():
    nodes = parse_dset_response(DSET_38808)
    assert nodes[0].is_default is False
    assert nodes[1].is_default is True


def test_summary_gives_placement_level_fields():
    rows = parse_summary_response(SUMMARY)

    assert len(rows) == 2
    assert rows[0].placement_id == "10988718"
    assert rows[0].start_date == "2026-07-20"
    assert rows[0].end_date == "2026-08-23"
    assert rows[0].verification_partner == "DoubleVerify"
    assert rows[0].verification_status == "Applied"
    assert rows[0].dtree_id == "38808"
    assert rows[0].click_tag_1 == "https://m-wendys.com/offer"


def test_values_are_flattened_to_strings():
    rows = parse_summary_response(SUMMARY)

    assert rows[0].dimensions == "320x50"      # list -> str
    assert rows[0].booked_units == "33333333"  # int -> str
    assert rows[0].third_party_impression_2 == ""  # null -> ""
    assert rows[1].click_tag_1 == ""           # absent field -> ""


def test_placement_and_creative_dates_can_differ():
    """
    The case this whole client exists for: a placement flighting from
    July 20 whose creative only starts on July 24. Each date has to
    come from its own level.
    """
    rows = parse_summary_response(SUMMARY)
    nodes = parse_dset_response(DSET_38808)
    result = InnovidFetchResult(
        campaign_id="323492", placements=rows, creative_nodes=nodes
    )

    linked = result.nodes_for_placement("10988718")

    assert len(linked) == 2
    assert rows[0].start_date == "2026-07-20"
    assert linked[0].start_timestamp.startswith("2026-07-24")


def test_malformed_payloads_return_empty_rather_than_raising():
    assert parse_summary_response({}) == []
    assert parse_summary_response(None) == []
    assert parse_dset_response({"id": 1, "name": "x"}) == []
    assert parse_dset_response(None) == []


def test_missing_credentials_file_is_not_an_error():
    # QA2 has to keep working for anyone who never sets this up.
    assert load_credentials(Path("/nonexistent/innovid.env")) is None


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
        else:
            passed += 1
            print(f"ok   {name}")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

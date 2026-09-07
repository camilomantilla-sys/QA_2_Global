"""
Field shapes in Innovid's /summary response.

Built from what campaign 323492 actually returned: about 130 fields
with most of them null, two generations of decision set, and rows at
three levels flattened into one list.

Run with pytest, or directly:  python tests/test_innovid_field_shapes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.innovid_api import (  # noqa: E402
    InnovidFetchResult,
    _dset_mismatch,
    count_filled_fields,
    count_levels,
    parse_dset_response,
    parse_summary_response,
    summary_field_names,
)

# Shaped like the real response: modern dtree null, legacy populated,
# rows at two levels.
PAYLOAD = {"items": [
    {"placementId": 10964183, "level": "PLACEMENT", "startDate": "2026-07-20",
     "endDate": "2026-08-23", "placementModernDtreeId": None,
     "modernDtreeId": None, "placementDecisionSetId": 44120,
     "decisionSetName": "Frosty GM 320x50", "verificationPartner": None,
     "rotationWeight": None},
    {"placementId": 10964183, "level": "PLACEMENT-CREATIVE", "startDate": "2026-07-20",
     "endDate": "2026-08-23", "placementModernDtreeId": None,
     "decisionSetId": 44120, "rotationWeight": 50,
     "verificationPartner": None},
]}



def test_legacy_decision_set_is_read_when_the_modern_one_is_null():
    rows = parse_summary_response(PAYLOAD)

    assert len(rows) == 2
    assert rows[0].dtree_id == ""
    assert rows[0].legacy_dset_id == "44120"
    assert rows[0].legacy_dset_name == "Frosty GM 320x50"
    assert rows[1].legacy_dset_id == "44120"


def test_the_two_generations_are_never_conflated():
    # /dt/v1/ui/dset reads modern ids; handing it a legacy one returns
    # the wrong creative rather than nothing, which is worse.
    rows = parse_summary_response(PAYLOAD)
    assert rows[1].dtree_id == ""


def test_row_level_is_kept():
    rows = parse_summary_response(PAYLOAD)
    assert rows[0].level == "PLACEMENT"
    assert rows[1].level == "PLACEMENT-CREATIVE"


def test_coverage_counts_rows_with_a_value():
    cov = count_filled_fields(PAYLOAD, {})

    assert cov["placementModernDtreeId"] == 0
    assert cov["verificationPartner"] == 0
    assert cov["rotationWeight"] == 1
    assert cov["placementId"] == 2
    assert cov["decisionSetId"] == 1


def test_zero_and_false_are_data_not_emptiness():
    cov = count_filled_fields({"items": [{"rotationWeight": 0, "isHidden": False}]}, {})
    assert cov["rotationWeight"] == 1
    assert cov["isHidden"] == 1


def test_field_names_are_the_union_across_rows():
    names = set(summary_field_names(PAYLOAD))
    assert {"placementDecisionSetId", "decisionSetId"} <= names


# ---------------------------------------------------------------
# The summary comes back as a flattened tree: a SITE row, then a
# PLACEMENT row, then that placement's PLACEMENT-CREATIVE rows. Each
# level carries its own dates, which is where the case QA2 exists for
# becomes visible.
# ---------------------------------------------------------------

TREE = {"items": [
    # Site rows carry no placement id at all.
    {"id": 900, "level": "SITE", "name": "GumGum", "siteId": 41},

    # A placement and its creative. The creative genuinely starts on
    # 24 Jul in Innovid, but the summary reports the placement's
    # 20 Jul on both rows -- which is the whole problem.
    {"placementId": 10964183, "level": "PLACEMENT",
     "startDate": "2026-07-20", "endDate": "2026-08-23",
     "verificationPartner": None},
    {"placementId": 10964183, "level": "PLACEMENT-CREATIVE",
     "startDate": "2026-07-20", "endDate": "2026-08-23",
     "creativeId": 6312751, "fileName": "320x50.jpg", "rotationWeight": 50},

    # A placement whose creative matches it exactly.
    {"placementId": 10964181, "level": "PLACEMENT",
     "startDate": "2026-07-20", "endDate": "2026-08-23"},
    {"placementId": 10964181, "level": "PLACEMENT-CREATIVE",
     "startDate": "2026-07-20", "endDate": "2026-08-23",
     "creativeId": 6312752, "rotationWeight": 50},

    {"placementId": 10964182, "level": "PLACEMENT",
     "startDate": "2026-07-20", "endDate": "2026-08-23"},
    {"placementId": 10964182, "level": "PLACEMENT-CREATIVE",
     "startDate": "2026-07-20", "endDate": "2026-08-23",
     "creativeId": 6312753},
]}


def _tree_result():
    from core.innovid_api import InnovidFetchResult
    return InnovidFetchResult(
        campaign_id="323492", placements=parse_summary_response(TREE)
    )


def test_site_rows_are_not_placements():
    rows = parse_summary_response(TREE)
    assert len(rows) == 6                       # 7 items, 1 is a site
    assert all(r.placement_id for r in rows)


def test_levels_are_separated():
    result = _tree_result()
    assert len(result.placement_rows()) == 3
    assert len(result.creative_rows_for("10964183")) == 1
    # Its own date, per the trap above, is not in this row.
    assert result.creative_rows_for("10964183")[0].creative_id == "6312751"


def test_summary_creative_dates_are_the_placements_not_the_creatives():
    """
    The trap this guards against.

    Creative rows in the summary repeat their placement's flight
    dates -- that is what Innovid's grid displays. A creative that
    actually starts four days late looks identical here, so anything
    comparing these two would pass on the exact error QA2 exists to
    catch. Creative dates have to come from the decision set.
    """
    result = _tree_result()

    creative = result.creative_rows_for("10964183")[0]
    assert creative.start_date, "the field is populated, which is the trap"

    # No helper compares these two, and none should be added.
    assert not hasattr(result, "date_mismatches")


def test_creative_rows_are_not_counted_as_placements():
    # 385 rows for 212 placements is only confusing if the two are
    # added together.
    result = _tree_result()
    assert len(result.placement_rows()) == 3
    assert len(result.placements) == 6


def test_a_campaign_with_no_modern_dtree_yields_no_creative_nodes():
    # Campaign 323492 is like this: legacy decision sets only. The
    # honest result is no creative dates, not a silent pass.
    result = _tree_result()
    assert result.creative_nodes == []
    assert all(not r.dtree_id for r in result.placements)

# ---------------------------------------------------------------
# Verifying a decision set is the one that was asked for.
#
# Innovid returned decision set 38808 under `decisionSetId` in
# campaign 323492 and under `placementModernDtreeId` elsewhere, so
# QA2 tries both names. Trying both means it can ask for the wrong
# thing, and a decision set full of somebody else's creatives would
# hand QA2 wrong flight dates -- which is worse than no dates.
# ---------------------------------------------------------------

DSET_38808 = {
    "id": 38808,
    "name": "Frosty GM Display 320x50",
    "servingMethod": "Rotation",
    "nodes": [
        {"id": 1, "startTimestamp": "2026-07-24 00:00:00",
         "endTimestamp": None, "weight": 1},
        {"id": 6312751, "startTimestamp": "2026-07-24 15:59:09",
         "endTimestamp": None, "isDefault": True},
    ],
}


def test_the_right_decision_set_passes():
    assert _dset_mismatch(DSET_38808, "38808", "Frosty GM Display 320x50") == ""


def test_a_different_decision_set_is_refused():
    wrong = dict(DSET_38808, id=44120, name="Some Other Set")
    problem = _dset_mismatch(wrong, "38808", "Frosty GM Display 320x50")

    assert problem
    assert "38808" in problem and "44120" in problem


def test_a_name_that_disagrees_is_refused():
    # Same id, different name: the id spaces overlap between the two
    # generations, so this is the case that catches a collision.
    renamed = dict(DSET_38808, name="Totally Different Set")
    assert _dset_mismatch(renamed, "38808", "Frosty GM Display 320x50")


def test_a_missing_name_in_the_summary_is_not_treated_as_a_mismatch():
    # decisionSetName is empty on plenty of rows; that is not evidence
    # of anything being wrong.
    assert _dset_mismatch(DSET_38808, "38808", "") == ""


def test_garbage_is_refused_rather_than_parsed():
    assert _dset_mismatch(None, "38808", "")
    assert _dset_mismatch("<html>error</html>", "38808", "")


def test_the_verified_decision_set_carries_the_real_creative_date():
    # 24 July, where the summary grid shows the placement's 20 July.
    nodes = parse_dset_response(DSET_38808)
    assert nodes[0].start_timestamp == "2026-07-24 00:00:00"
    assert nodes[0].weight == "1"

# ---------------------------------------------------------------
# Innovid's own summary request asks for no decision-set field at
# all, yet its grid shows decision set 38808. The grid gets it from
# the decision set's own row -- and rows carrying no placementId are
# exactly the ones QA2 discards, which is how that id went missing.
# ---------------------------------------------------------------

FLATTENED_TREE = {"items": [
    {"id": 323492, "level": "CAMPAIGN", "name": "WEN_FRO_003_FROSTY"},
    {"id": 6221, "level": "SITE", "name": "GumGum", "siteId": 6221},
    {"id": 10988717, "level": "PLACEMENT", "placementId": 10988717,
     "name": "P3JF5Y2|WEN|FRO|001|GUMGUM|320 x 50",
     "startDate": "2026-07-20", "endDate": "2026-08-23"},
    # The decision set: its own row, its own id, no placementId.
    {"id": 38808, "level": "PLACEMENT-DTREE",
     "name": "Frosty GM Display 320x50",
     "startDate": "2026-07-20", "endDate": "2026-08-23"},
    {"id": 6312751, "level": "PLACEMENT-CREATIVE", "placementId": 10988717,
     "name": "320x50.jpg", "creativeId": 6312751,
     "startDate": "2026-07-20", "endDate": "2026-08-23"},
]}


def test_the_decision_set_row_is_currently_discarded():
    """
    Documents the gap rather than papering over it.

    parse_summary_response keeps only rows with a placementId, which
    is right for counting placements and wrong for finding decision
    sets. The id is in the response the whole time.
    """
    rows = parse_summary_response(FLATTENED_TREE)

    assert len(rows) == 2
    assert all(r.level != "PLACEMENT-DTREE" for r in rows)
    assert all(not r.dtree_id for r in rows), "38808 never reaches a row"


def test_level_counts_surface_the_discarded_rows():
    # This is what makes the missing decision set visible in a run
    # instead of having to guess at it.
    levels = count_levels(FLATTENED_TREE, {})

    assert set(levels) == {
        "CAMPAIGN", "SITE", "PLACEMENT", "PLACEMENT-DTREE",
        "PLACEMENT-CREATIVE",
    }
    assert levels["PLACEMENT-DTREE"]["_rows"] == 1
    assert levels["PLACEMENT-DTREE"]["id"] == 1
    assert levels["PLACEMENT-DTREE"]["name"] == 1
    assert "placementId" not in levels["PLACEMENT-DTREE"]


def test_level_counts_never_carry_values():
    levels = count_levels(FLATTENED_TREE, {})
    for fields in levels.values():
        for count in fields.values():
            assert isinstance(count, int)


def test_level_counts_accumulate_across_pages():
    levels = count_levels(FLATTENED_TREE, {})
    count_levels(FLATTENED_TREE, levels)
    assert levels["PLACEMENT"]["_rows"] == 2


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

"""
Field shapes in Innovid's /summary response.

Built from what campaign 323492 actually returned: about 130 fields
with most of them null, two generations of decision set, and rows at
three levels flattened into one list.

Run with pytest, or directly:  python tests/test_innovid_field_shapes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.innovid_api import (  # noqa: E402
    InnovidFetchResult,
    _dset_mismatch,
    redact_body,
    redact_url,
    count_filled_fields,
    count_levels,
    InnovidCreativeNode,
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
    assert rows[0].dset_link_id == "44120"
    assert rows[0].dset_name == "Frosty GM 320x50"
    assert rows[1].dset_id == "44120"


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

# ---------------------------------------------------------------
# Redacting recorded URLs.
#
# The first --record run printed an OAuth redirect complete with its
# `code` -- a credential -- because only headers and bodies were being
# filtered and query strings were not. These are the actual URLs from
# that run.
# ---------------------------------------------------------------

OAUTH_REDIRECT = (
    "https://api.flashtalking.net/login/oauth2/code/auth0"
    "?code=7vAZ0_gPNfWqS8T5ruxUz4cnvOdzjPzg7QLL6HwXYLQLI"
    "&state=AyGzp-mdqpvUbTsr4AOyVlYuifzwAkYzIm6O3WCI2Vc%3D"
)
MEDIAOCEAN_LOGIN = (
    "https://uam-login.mediaocean.com/login?state=hKFo2SA5TjY3UzNM"
    "&client=YzenbLU4y1EIvP1dXdXLKMf2OlZqThxh&nonce=1P6sVS2fxHN5AngI"
)
SUMMARY = (
    "https://api.flashtalking.net/cm/v1/ui/campaigns/323492/summary"
    "?getFilterValues=true&fields=status,siteName,placementId"
)
JWT_WIDGET = "https://api.flashtalking.net/zen/v1/ui/generate-web-widget-jwt"


def test_an_oauth_code_is_never_recorded():
    """The leak this guards against."""
    assert redact_url(OAUTH_REDIRECT) == ""


def test_the_identity_provider_is_dropped_wholesale():
    # Its URLs are state, nonce and client id -- all credential-shaped
    # and none of it useful for reading campaigns.
    assert redact_url(MEDIAOCEAN_LOGIN) == ""


def test_the_useful_part_of_a_real_call_survives():
    kept = redact_url(SUMMARY)

    assert "campaigns/323492/summary" in kept
    assert "fields=status,siteName,placementId" in kept
    assert "getFilterValues=true" in kept


def test_unknown_parameters_keep_their_name_but_lose_their_value():
    kept = redact_url(
        "https://api.flashtalking.net/x?sessionToken=abc123&page=2"
    )

    assert "sessionToken=<hidden>" in kept
    assert "abc123" not in kept
    assert "page=2" in kept, "safe parameters still say what they are"


def test_a_long_id_list_is_truncated_not_dropped():
    ids = ",".join(str(10964000 + n) for n in range(200))
    kept = redact_url(
        f"https://api.flashtalking.net/twr/v1/x?rpp=212&placementIds={ids}"
    )

    assert "placementIds=10964000" in kept
    assert "truncated" in kept
    assert len(kept) < 400


def test_paths_are_kept_whole():
    # The path is the entire point of recording.
    assert redact_url(JWT_WIDGET) == JWT_WIDGET
    assert redact_url(
        "https://api.flashtalking.net/dt/v1/ui/dset/38808"
    ) == "https://api.flashtalking.net/dt/v1/ui/dset/38808"


def test_anything_off_innovid_is_ignored():
    assert redact_url("https://example.com/whatever?a=b") == ""
    assert redact_url("") == ""

# Every sign-in address seen across two real --record runs, verbatim.
# The mediaocean one survived a run it should not have, so it is here
# in full rather than shortened.
REAL_SIGN_IN_URLS = (
    "https://uam-login.mediaocean.com/login?state=hKFo2SA5TjY3UzNMR3Rh"
    "M2I3Q2pOWnZMcWNyQUR0dnFkeWJ2SaFupWxvZ2luo3RpZNkgMnVROWhpYXJwT2R0"
    "dnptWXItNU5yTG5zeXRaUDlmczSjY2lk2SBZemVuYkxVNHkxRUl2UDFkWGRYTEtN"
    "ZjJPbFpxVGh4aA&client=YzenbLU4y1EIvP1dXdXLKMf2OlZqThxh"
    "&protocol=oauth2&audience=https%3A%2F%2Fapi.4cinsights.io%2F"
    "&response_type=code&scope=openid%20profile%20email%20offline_access"
    "&redirect_uri=https%3A%2F%2Fapi.flashtalking.net%2Flogin%2Foauth2"
    "%2Fcode%2Fauth0&nonce=1P6sVS2fxHN5AngI206M0QNvQ2qSvDXBPdVrDyHTg9M",

    "https://uam-login.mediaocean.com/authorize/?audience=https://api."
    "4cinsights.io/&response_type=code&client_id=YzenbLU4y1EIvP1dXdXL"
    "&state=AyGzp-mdqpvUbTsr4AOyVlYuifzwAkYzIm6O3WCI2Vc%3D",

    "https://api.flashtalking.net/login/oauth2/code/auth0"
    "?code=7vAZ0_gPNfWqS8T5ruxUz4cnvOdzjPzg7QLL6HwXYLQLI"
    "&state=AyGzp-mdqpvUbTsr4AOyVlYuifzwAkYzIm6O3WCI2Vc%3D",

    "https://api.flashtalking.net/oauth2/authorization/auth0",
    "https://api.flashtalking.net/uilogin"
    "?uri=https://campaign-manager.flashtalking.net",
)


def test_no_sign_in_address_from_a_real_run_survives():
    for url in REAL_SIGN_IN_URLS:
        assert redact_url(url) == "", url


def test_no_credential_value_appears_in_any_redacted_output():
    # Belt and braces: whatever the filter decides, these strings must
    # not come out the other side.
    secrets = (
        "7vAZ0_gPNfWqS8T5ruxUz4cnvOdzjPzg7QLL6HwXYLQLI",
        "AyGzp-mdqpvUbTsr4AOyVlYuifzwAkYzIm6O3WCI2Vc",
        "1P6sVS2fxHN5AngI206M0QNvQ2qSvDXBPdVrDyHTg9M",
        "hKFo2SA5TjY3UzNMR3RhM2I3Q2pOWnZMcWNyQUR0dnFkeWJ2Sa",
    )
    for url in REAL_SIGN_IN_URLS:
        out = redact_url(url)
        for secret in secrets:
            assert secret not in out


def test_the_fields_list_is_never_truncated():
    """
    Which columns Innovid asks for is the answer being hunted, and
    truncating it at 80 characters hid it on the run that found it.
    """
    fields = (
        "dimensions,placementName,clickTag1,bookedUnits,startDate,"
        "endDate,prismaPlacementId,verificationPartner,verificationStatus,"
        "placementModernDtreeId,modernDtreeName,decisionSetId"
    )
    kept = redact_url(
        "https://api.flashtalking.net/cm/v1/ui/campaigns/323492/summary"
        f"?fields={fields}"
    )

    assert fields in kept
    assert "truncated" not in kept


def test_long_id_lists_are_still_truncated():
    ids = ",".join(str(10964000 + n) for n in range(200))
    kept = redact_url(
        f"https://api.flashtalking.net/twr/v1/x?placementIds={ids}"
    )
    assert "truncated" in kept

# ---------------------------------------------------------------
# Request bodies. The summary endpoint is called four times with an
# identical URL; whatever makes Innovid return decision set 38808 is
# in the body, so the body has to be readable -- without carrying
# anything typed into a search box.
# ---------------------------------------------------------------

SUMMARY_URL = (
    "https://api.flashtalking.net/cm/v1/ui/campaigns/323492/summary"
)


def test_the_shape_of_a_summary_body_is_readable():
    body = redact_body(SUMMARY_URL, json.dumps({
        "page": 1, "rpp": 500, "sortBy": "name", "sortOrder": "ASC",
        "parentId": 10988717, "level": "PLACEMENT",
    }))

    assert "parentId=10988717" in body
    assert "level=PLACEMENT" in body
    assert "rpp=500" in body


def test_a_typed_search_term_never_comes_out():
    body = redact_body(SUMMARY_URL, json.dumps({
        "page": 1, "searchTerm": "something personal someone typed",
    }))

    assert "searchTerm=<hidden>" in body
    assert "personal" not in body


def test_bodies_are_only_read_for_the_endpoints_being_investigated():
    other = "https://api.flashtalking.net/crm/v1/user"
    assert redact_body(other, json.dumps({"anything": "at all"})) == ""


def test_a_body_that_is_not_json_is_reported_not_dumped():
    out = redact_body(SUMMARY_URL, "user=camilo&password=hunter2")

    assert "not JSON" in out
    assert "hunter2" not in out


def test_no_body_is_not_an_error():
    assert redact_body(SUMMARY_URL, None) == ""
    assert redact_body(SUMMARY_URL, "") == ""


def test_nested_structure_is_shown_but_bounded():
    body = redact_body(SUMMARY_URL, json.dumps({
        "fields": ["a"] * 200,
    }))
    assert "truncated" in body
    assert len(body) < 300

# ---------------------------------------------------------------
# The two decision-set numbers.
#
# Campaign 323492's creative rows carry decisionSetId AND
# placementDecisionSetId on the same 64 rows. Treating them as the
# same field meant every lookup used placementDecisionSetId -- ids
# 73087..73109, consecutive, the shape of a join table -- and all of
# them were rejected with HTTP 400. Innovid's own UI opens
# /dt/v1/ui/dset/38808 for that campaign.
# ---------------------------------------------------------------

TWO_IDS = {"items": [
    {"placementId": 10988717, "level": "PLACEMENT",
     "startDate": "2026-07-20", "endDate": "2026-08-23"},
    {"placementId": 10988717, "level": "PLACEMENT-CREATIVE",
     "creativeId": 6312751,
     "decisionSetId": 38808,
     "decisionSetName": "Frosty GM Display 320x50",
     "placementDecisionSetId": 73087},
]}


def test_the_decision_set_and_its_link_are_kept_apart():
    row = parse_summary_response(TWO_IDS)[1]

    assert row.dset_id == "38808", "the decision set itself"
    assert row.dset_link_id == "73087", "the placement-to-set link"
    assert row.dset_name == "Frosty GM Display 320x50"


def test_the_link_id_never_stands_in_for_the_decision_set():
    # The whole failure: one is not a fallback for the other.
    row = parse_summary_response(TWO_IDS)[1]
    assert row.dset_id != row.dset_link_id


def test_a_row_with_only_a_link_id_yields_no_decision_set():
    only_link = {"items": [
        {"placementId": 1, "level": "PLACEMENT-CREATIVE",
         "placementDecisionSetId": 73088},
    ]}
    row = parse_summary_response(only_link)[0]

    assert row.dset_id == ""
    assert row.dset_link_id == "73088"

# ---------------------------------------------------------------
# Linking decision sets back to placements.
#
# The run that first read decision sets reported "every creative
# starts the same day as its placement" while linking nothing at all:
# nodes were matched on the modern dtree id, which that campaign does
# not have. An empty comparison read as a clean pass.
# ---------------------------------------------------------------

LINK_ROWS = {"items": [
    {"placementId": 10988717, "level": "PLACEMENT",
     "startDate": "2026-07-20", "endDate": "2026-08-23"},
    {"placementId": 10988717, "level": "PLACEMENT-CREATIVE",
     "decisionSetId": 38808, "decisionSetName": "Frosty GM Display 320x50",
     "placementDecisionSetId": 73087},
]}

DSET_WITH_LATE_CREATIVE = {
    "id": 38808,
    "name": "Frosty GM Display 320x50",
    "servingMethod": "Rotation",
    "defaultServing": {"id": 6312751, "name": "320x50.jpg"},
    "nodes": [
        {"id": 1, "startTimestamp": "2026-07-24 00:00:00",
         "endTimestamp": None, "weight": 1},
        {"id": 6312751, "startTimestamp": "2026-07-21 10:02:11",
         "endTimestamp": None, "isDefault": True},
    ],
}


def _linked_result():
    return InnovidFetchResult(
        campaign_id="323492",
        placements=parse_summary_response(LINK_ROWS),
        creative_nodes=parse_dset_response(DSET_WITH_LATE_CREATIVE),
    )


def test_nodes_link_by_decision_set_id_not_only_the_modern_id():
    result = _linked_result()

    nodes = result.nodes_for_placement("10988717")
    assert len(nodes) == 2, "the campaign has no modern dtree id at all"


def test_the_late_creative_is_found_once_linking_works():
    result = _linked_result()

    late = [
        n for n in result.nodes_for_placement("10988717")
        if not n.is_default and n.start_timestamp.startswith("2026-07-24")
    ]
    assert late, "20 July placement, 24 July creative"


def test_linked_count_distinguishes_no_differences_from_no_comparison():
    result = _linked_result()
    assert result.linked_node_count() == 2

    # Same nodes, but nothing claims them.
    orphaned = InnovidFetchResult(
        campaign_id="323492",
        placements=parse_summary_response({"items": [
            {"placementId": 999, "level": "PLACEMENT",
             "startDate": "2026-07-20"},
        ]}),
        creative_nodes=parse_dset_response(DSET_WITH_LATE_CREATIVE),
    )
    assert orphaned.creative_nodes, "nodes were read"
    assert orphaned.linked_node_count() == 0, "but none belong to a placement"


def test_a_node_id_is_not_mistaken_for_a_creative_id():
    # Node 1 with weight 1 is a rotation slot; 6312751 is the file.
    nodes = parse_dset_response(DSET_WITH_LATE_CREATIVE)

    assert nodes[0].node_id == "1"
    assert nodes[0].creative_id == "", "no creative named on that node"
    assert nodes[1].creative_id == "6312751", "the default one names it"

# ---------------------------------------------------------------
# Which date differences actually cost delivery.
#
# The first working run found eight differences in campaign 323492,
# in both directions: two creatives starting four days after their
# placement (nothing serves for four days) and six ready a week
# early (harmless -- the placement gates delivery). Reporting those
# together would bury two real findings under six non-events.
# ---------------------------------------------------------------

REAL_CASES = {"items": [
    # 10988717/8: placement 20 Jul, creative 24 Jul. A real gap.
    {"placementId": 10988717, "level": "PLACEMENT",
     "startDate": "2026-07-20", "endDate": "2026-08-23"},
    {"placementId": 10988717, "level": "PLACEMENT-CREATIVE",
     "decisionSetId": 38808, "decisionSetName": "Frosty GM Display 320x50"},

    # 10964170: placement 27 Jul, creative 20 Jul. Harmless.
    {"placementId": 10964170, "level": "PLACEMENT",
     "startDate": "2026-07-27", "endDate": "2026-08-23"},
    {"placementId": 10964170, "level": "PLACEMENT-CREATIVE",
     "decisionSetId": 44120, "decisionSetName": "Early Set"},
]}

LATE_DSET = {
    "id": 38808, "name": "Frosty GM Display 320x50",
    "servingMethod": "Rotation",
    "nodes": [{"id": 1, "startTimestamp": "2026-07-24 00:00:00",
               "endTimestamp": "2026-08-23 23:59:00", "weight": 1}],
}
EARLY_DSET = {
    "id": 44120, "name": "Early Set", "servingMethod": "Rotation",
    "nodes": [{"id": 1, "startTimestamp": "2026-07-20 00:00:00",
               "endTimestamp": "2026-08-23 23:59:00", "weight": 1}],
}


def _real_result():
    return InnovidFetchResult(
        campaign_id="323492",
        placements=parse_summary_response(REAL_CASES),
        creative_nodes=(parse_dset_response(LATE_DSET)
                        + parse_dset_response(EARLY_DSET)),
    )


def test_a_creative_starting_late_is_a_gap():
    found = _real_result().creative_flight_gaps()

    gaps = [(p.placement_id, days) for p, _, days in found["gaps"]]
    assert ("10988717", 4) in gaps, "four days with nothing serving"


def test_a_creative_ready_early_is_not_a_gap():
    found = _real_result().creative_flight_gaps()

    assert all(p.placement_id != "10964170" for p, _, _ in found["gaps"])
    assert any(p.placement_id == "10964170" for p, _, _ in found["harmless"])


def test_a_creative_ending_early_is_a_gap():
    short = {
        "id": 44121, "name": "Short Set", "servingMethod": "Rotation",
        "nodes": [{"id": 1, "startTimestamp": "2026-07-20 00:00:00",
                   "endTimestamp": "2026-08-01 23:59:00", "weight": 1}],
    }
    result = InnovidFetchResult(
        campaign_id="x",
        placements=parse_summary_response({"items": [
            {"placementId": 1, "level": "PLACEMENT",
             "startDate": "2026-07-20", "endDate": "2026-08-23"},
            {"placementId": 1, "level": "PLACEMENT-CREATIVE",
             "decisionSetId": 44121},
        ]}),
        creative_nodes=parse_dset_response(short),
    )

    found = result.creative_flight_gaps()
    assert found["gaps"], "the placement outlives its creative"
    assert found["gaps"][0][2] < 0, "negative days = ends short"


def test_the_default_node_is_not_a_flight_date():
    # A default creative's timestamp is when it was attached.
    with_default = dict(LATE_DSET, nodes=[
        {"id": 6312751, "startTimestamp": "2026-07-21 10:02:11",
         "endTimestamp": None, "isDefault": True},
    ])
    result = InnovidFetchResult(
        campaign_id="x",
        placements=parse_summary_response(REAL_CASES),
        creative_nodes=parse_dset_response(with_default),
    )
    found = result.creative_flight_gaps()
    assert not found["gaps"] and not found["harmless"]


def test_unparseable_dates_are_skipped_not_guessed():
    broken = dict(LATE_DSET, nodes=[
        {"id": 1, "startTimestamp": "Ongoing", "endTimestamp": "",
         "weight": 1},
    ])
    result = InnovidFetchResult(
        campaign_id="x",
        placements=parse_summary_response(REAL_CASES),
        creative_nodes=parse_dset_response(broken),
    )
    found = result.creative_flight_gaps()
    assert not found["gaps"]


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

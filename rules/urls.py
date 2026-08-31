from core.findings import Domain
from core.urls import (
    URL_BASE_DIFF,
    URL_BOTH_MISSING,
    URL_MALFORMED,
    URL_MATCH,
    URL_MISSING_ACTUAL,
    URL_MISSING_EXPECTED,
    URL_PARAMS_DIFF,
)


ROTATION_SHEET = "Creative Rotations"


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        # Same criterion as CRE-001: a Creative Rotations variant
        # without a Clicktag in Innovid can be a normal swap if the
        # group has other active variants.
        rotation_links = [
            cl for cl in pm.creative_links
            if cl.expected.ts_sheet == ROTATION_SHEET
        ]
        rotation_has_match = any(
            cl.actual is not None for cl in rotation_links
        )

        for cl in pm.creative_links:

            if cl.url is None:
                continue

            result = cl.url.result

            common = {
                "rule_id": "URL-001",
                "domain": Domain.URL,
                "placement_id": pm.placement_id,
                "placement_name": pm.expected.name,
                "creative_id": (
                    cl.actual.creative_id
                    if cl.actual is not None
                    else cl.expected.creative_id
                ),
                "creative_name": cl.expected.name,
                "expected": cl.url.expected.raw,
                "actual": cl.url.actual.raw,
            }

            if result == URL_MATCH:
                buffer.pass_(
                    message="Traffic Sheet and Innovid URLs match.",
                    **common,
                )

            elif result == URL_MISSING_ACTUAL:
                if cl.expected.ts_sheet == ROTATION_SHEET and rotation_has_match:
                    buffer.review(
                        message=(
                            "TS declares a URL for this rotation variant, "
                            "but the creative isn't running in Innovid "
                            "(possible rotation swap)."
                        ),
                        reason=cl.url.note,
                        recommended_action=(
                            "Confirm whether this variant was swapped "
                            "out of the rotation intentionally."
                        ),
                        **common,
                    )
                else:
                    buffer.fail(
                        message="TS declares a URL, but Innovid has no Clicktag.",
                        reason=cl.url.note,
                        recommended_action=(
                            "Configure the requested Clicktag and re-export."
                        ),
                        **common,
                    )

            elif result == URL_MISSING_EXPECTED:
                buffer.not_verified(
                    message=(
                        "Innovid has a URL, but the TS doesn't declare "
                        "a verifiable URL for this entity."
                    ),
                    reason=cl.url.note,
                    recommended_action=(
                        "Confirm the applicable URL source for this "
                        "profile and request type."
                    ),
                    **common,
                )

            elif result == URL_BOTH_MISSING:
                buffer.not_verified(
                    message="No URL is declared in the TS or in Innovid.",
                    reason=cl.url.note,
                    recommended_action=(
                        "Confirm whether a URL applies to this implementation."
                    ),
                    **common,
                )

            elif result in (URL_BASE_DIFF, URL_PARAMS_DIFF):
                buffer.fail(
                    message="The URL configured in Innovid doesn't match the TS.",
                    reason=cl.url.note,
                    recommended_action=(
                        "Correct the Clicktag destination or parameters in Innovid."
                    ),
                    **common,
                )

            elif result == URL_MALFORMED:
                buffer.review(
                    message="The URL could not be parsed correctly.",
                    reason=cl.url.note,
                    recommended_action=(
                        "Manually review the URL and correct its format."
                    ),
                    **common,
                )

            else:
                buffer.review(
                    message=f"Unclassified URL result: {result}.",
                    reason=cl.url.note,
                    **common,
                )

from core.colors import GREEN
from core.findings import Domain
from core.urls import (
    URL_BASE_DIFF,
    URL_BOTH_MISSING,
    URL_MALFORMED,
    URL_MATCH,
    URL_MISSING_ACTUAL,
    URL_MISSING_EXPECTED,
    URL_PARAMS_DIFF,
    compare_urls,
)
from parsers.ts_parser import REQ_URL_SWAP


ROTATION_SHEET = "Creative Rotations"


def _actual_urls(ap) -> list[str]:
    """
    Clicktags que Innovid tiene realmente para el placement.

    En 1x1 el clicktag vive a nivel de placement; en display y video
    vive en cada creativo. Un swap de URL puede llegar de cualquiera de
    las dos formas, asi que se miran ambas.
    """
    if ap is None:
        return []

    if ap.clicktags:
        return list(ap.clicktags)

    out: list[str] = []
    for creative in ap.creatives:
        if not creative.running:
            continue
        for tag in creative.clicktags:
            if tag and tag not in out:
                out.append(tag)
    return out


def evaluate_placement_urls(match_result, buffer):
    """
    URL-002 - swap de solo URL.

    Cuando lo unico trabajado es la landing page, la TS no declara
    creativos, asi que URL-001 no tiene por donde entrar y el placement
    quedaba aprobado sin haber validado justamente lo unico que cambio.
    """
    for pm in match_result.matched:

        if pm.expected.request_type != REQ_URL_SWAP:
            continue

        expected_url = pm.expected.url

        common = {
            "rule_id": "URL-002",
            "domain": Domain.URL,
            "placement_id": pm.placement_id,
            "placement_name": pm.expected.name,
            "expected": expected_url,
        }

        if not expected_url:
            if pm.expected.url_is_default_only:
                buffer.not_verified(
                    message=(
                        "The only landing page swapped here belongs to "
                        "the default ad, which is a separate creative "
                        "and can't be checked against the placement's "
                        "Clicktag."
                    ),
                    recommended_action=(
                        "Review the default ad's landing page in Innovid."
                    ),
                    **common,
                )
            continue

        actual_urls = _actual_urls(pm.actual)

        if not actual_urls:
            buffer.not_verified(
                message=(
                    "The Traffic Sheet swaps this placement's landing "
                    "page, but Innovid reports no Clicktag to compare."
                ),
                recommended_action=(
                    "Upload the export that carries the Clicktag for "
                    "this placement."
                ),
                **common,
            )
            continue

        comparisons = [compare_urls(expected_url, url) for url in actual_urls]
        best = next(
            (c for c in comparisons if c.result == URL_MATCH),
            comparisons[0],
        )

        if best.result == URL_MATCH:
            buffer.pass_(
                message="The new landing page is live in Innovid.",
                actual=best.actual.raw,
                **common,
            )
        else:
            buffer.fail(
                message=(
                    "The new landing page from the Traffic Sheet isn't "
                    "the one configured in Innovid."
                ),
                actual=best.actual.raw,
                reason=best.note,
                recommended_action=(
                    "Update the Clicktag to the new landing page."
                ),
                **common,
            )


def evaluate(match_result, buffer):

    evaluate_placement_urls(match_result, buffer)

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

            # Los creativos en blanco son el contenido del Decision Set,
            # no lo que se pidio cambiar. Se les calcula la URL para
            # poder mostrarla, pero no generan hallazgos.
            if cl.expected.intent != GREEN:
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

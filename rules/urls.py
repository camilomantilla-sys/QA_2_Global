"""
URL-001 / URL-002 / URL-003 -- landing pages y clicktags.

URL-001: la URL de la TS coincide con el clicktag de Innovid.
URL-002: la landing page nueva quedo viva en Innovid (nivel placement).
URL-003: URLs de placements directos. Un clicktag sobre un placement
retirado o detenido es INFO, no FAIL.
La comparacion de URLs (base, parametros, malformadas) esta en
core/urls.py.
"""

from core.colors import GREEN, RED
from core.findings import Domain
from core.intent import requested
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


def _still_on_old_page(pm, expected_url: str) -> list[str]:
    """
    Creativos que siguen con la landing page que el swap retira.

    Un swap de landing page alcanza a todos los creativos de los
    decision sets que la usan (AdOps, 18-nov). Que uno ya tenga la
    nueva no basta: en Wendy's el 1x1 nuevo de XBOX DIS GM tenia la
    nueva y el viejo seguia con la roja, y el placement pasaba.
    """
    retired = [u for u in getattr(pm.expected, "retired_urls", ())
               if compare_urls(expected_url, u).result != URL_MATCH]
    if not retired or pm.actual is None or pm.actual.clicktags:
        return []
    out: list[str] = []
    for creative in pm.actual.creatives:
        if not creative.running:
            continue
        tags = [t for t in creative.clicktags if t]
        if any(compare_urls(expected_url, t).result == URL_MATCH for t in tags):
            continue
        if any(compare_urls(old, t).result == URL_MATCH
               for t in tags for old in retired):
            out.append(creative.name or creative.creative_id)
    return out


def _creative_urls(ap, names) -> list[str]:
    return [t for c in ap.creatives if (c.name or c.creative_id) in names
            for t in c.clicktags if t]


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
            stale = _still_on_old_page(pm, "")
            candidates = getattr(pm.expected, "url_candidates", [])
            if stale:
                buffer.fail(
                    message=(
                        "The Traffic Sheet retires this landing page (red), "
                        "but Innovid still uses it on: "
                        + ", ".join(stale[:5]) + "."
                    ),
                    actual=" | ".join(dict.fromkeys(_creative_urls(pm.actual, stale))),
                    recommended_action="Update the Clicktag to the new landing page.",
                    **common,
                )
                continue
            if pm.expected.retired_urls and not pm.expected.url_is_default_only:
                buffer.review(
                    message=(
                        "The Traffic Sheet retires this placement's landing "
                        "page, but doesn't say which new one replaces it"
                        + (": it could be " + " or ".join(candidates) if candidates else "")
                        + ". Innovid no longer uses the old one."
                    ),
                    actual=" | ".join(_actual_urls(pm.actual)[:2]),
                    recommended_action=(
                        "Confirm the new landing page with the request and "
                        "check the Clicktag in Innovid."
                    ),
                    **common,
                )
                continue
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

        stale = _still_on_old_page(pm, expected_url)

        inferred = getattr(pm.expected, "url_inferred_from", "")
        inferred_note = (
            f"The Traffic Sheet retires the old landing page and brings "
            f"{inferred} in green; QA2 takes that one as the new landing page."
            if inferred else "")

        if best.result == URL_MATCH and stale:
            names = ", ".join(stale[:5]) + (
                f" and {len(stale) - 5} more" if len(stale) > 5 else "")
            buffer.fail(
                message=(
                    f"The new landing page is live, but {len(stale)} "
                    + ("creative in the decision set still points"
                       if len(stale) == 1 else
                       "creatives in the decision set still point")
                    + f" to the old one: {names}."
                ),
                actual=" | ".join(
                    dict.fromkeys(_creative_urls(pm.actual, stale))),
                reason=(
                    "The Traffic Sheet retires that landing page (red) "
                    "and the swap applies to every creative of the "
                    "decision sets that use it."
                ),
                recommended_action=(
                    "Update the Clicktag of those creatives to the new "
                    "landing page."
                ),
                **common,
            )
        elif best.result == URL_MATCH:
            buffer.pass_(
                message="The new landing page is live in Innovid.",
                actual=best.actual.raw,
                reason=inferred_note,
                **common,
            )
        elif stale:
            buffer.fail(
                message=(
                    "The Traffic Sheet retires this landing page (red), but "
                    "Innovid still uses it on: " + ", ".join(stale[:5]) + "."
                ),
                actual=" | ".join(dict.fromkeys(_creative_urls(pm.actual, stale))),
                reason=inferred_note or best.note,
                recommended_action="Update the Clicktag to the new landing page.",
                **common,
            )
        elif inferred:
            # La nueva es una deduccion: si Innovid tiene otra, puede
            # ser la TS la que no lo dijo. Que lo mire una persona.
            buffer.review(
                message=(
                    "The Traffic Sheet retires this placement's landing page "
                    f"and QA2 expected {inferred}, the new one in green, but "
                    "Innovid has another."
                ),
                actual=best.actual.raw,
                reason=inferred_note,
                recommended_action=(
                    "Confirm which landing page replaces the old one."
                ),
                **common,
            )
        else:
            buffer.fail(
                message=(
                    "The new landing page from the Traffic Sheet isn't "
                    "the one configured in Innovid"
                    + (". " + _sentence(best.note)
                       if best.result in (URL_BASE_DIFF, URL_PARAMS_DIFF) else ".")
                ),
                actual=best.actual.raw,
                reason=best.note,
                recommended_action=(
                    "Update the Clicktag to the new landing page."
                ),
                **common,
            )


def _sentence(note: str) -> str:
    """La diferencia de URL como frase: "Only the protocol differs: http / https"."""
    note = str(note or "").strip()
    return (note[:1].upper() + note[1:] + ".") if note else ""


_NOT_RUNNING = ("stopped", "disabled", "inactive", "paused")


def _is_retired(pm) -> bool:
    """El placement ya no sirve: la TS lo desasigna, o Innovid lo apago."""
    from core.normalize import norm_compare
    from parsers.ts_parser import REQ_CREATIVE_REMOVE as _REMOVE

    if pm.expected.request_type == _REMOVE:
        return True
    status = pm.actual.status if pm.actual else ""
    return norm_compare(status) in _NOT_RUNNING


def evaluate_direct_placement_urls(match_result, buffer):
    """
    URL-003 -- la landing page de un placement sin creativos propios.

    Adobe Direct / Site-Served escribe "N/A" en Creative Names: el
    creativo es el pixel generico de la cuenta y todo lo revisable vive
    a nivel de placement. Sin creativos no hay CreativeLink, y URL-001
    -- que recorre los links -- no tenia por donde entrar, asi que la
    landing page de cada 1x1 salia del QA sin que nadie la mirara.

    La URL esperada es la de la columna "Landing Page" de la TS; la
    real, el Clicktag_1 que el Placement View trae para ese placement.
    """
    for pm in match_result.matched:

        if pm.url is None:
            continue

        common = {
            "rule_id": "URL-003",
            "domain": Domain.URL,
            "placement_id": pm.placement_id,
            "placement_name": pm.expected.name,
            "expected": pm.url.expected.raw,
            "actual": pm.url.actual.raw,
        }

        if pm.url.result == URL_MATCH:
            buffer.pass_(
                message="The placement's landing page matches Innovid.",
                **common,
            )

        elif pm.url.result == URL_BOTH_MISSING:
            continue

        elif pm.url.result == URL_MISSING_ACTUAL:
            buffer.not_verified(
                message=(
                    "The Traffic Sheet declares a landing page for this "
                    "placement, but Innovid reports no Clicktag."
                ),
                recommended_action=(
                    "Upload the Placement View, which is where the "
                    "placement's Clicktag lives."
                ),
                **common,
            )

        elif pm.url.result == URL_MISSING_EXPECTED:
            # Un placement que se esta desasignando, o que Innovid ya
            # tiene detenido, puede conservar su clicktag: no sirve
            # nada, asi que no hay nada que corregir. Criterio de AdOps: "esta
            # bien que flagee eso que aun tiene url, pero pues igual
            # esta apagado el placement entonces no afecta". Se dice,
            # y no ocupa una firma.
            if _is_retired(pm):
                buffer.info(
                    message=(
                        "Innovid still has a Clicktag on this "
                        "placement, but the placement is no longer "
                        "running, so it serves nothing."
                    ),
                    **common,
                )
            else:
                buffer.not_verified(
                    message=(
                        "Innovid has a Clicktag on this placement, but "
                        "the Traffic Sheet declares no landing page to "
                        "compare it against."
                    ),
                    **common,
                )

        else:
            buffer.fail(
                message=(
                    "The placement's landing page isn't the one the "
                    "Traffic Sheet declares"
                    + (". " + _sentence(pm.url.note)
                       if pm.url.result in (URL_BASE_DIFF, URL_PARAMS_DIFF) else ".")
                ),
                reason=pm.url.note,
                recommended_action=(
                    "Update the placement's Clicktag to the landing "
                    "page in the Traffic Sheet."
                ),
                **common,
            )


def evaluate(match_result, buffer):

    evaluate_placement_urls(match_result, buffer)
    evaluate_direct_placement_urls(match_result, buffer)

    for pm in match_result.matched:

        # Same criterion as CRE-001: a Creative Rotations variant
        # without a Clicktag in Innovid can be a normal swap if the
        # group has other active variants.
        rotation_links = [
            cl for cl in pm.creative_links
            if cl.expected.ts_sheet == ROTATION_SHEET
        ]
        rotation_has_match = any(
            cl.actual is not None and cl.actual.running
            and cl.expected.intent != RED
            for cl in rotation_links
        )

        for cl in pm.creative_links:

            if cl.url is None:
                continue

            # Los creativos en blanco son el contenido del Decision Set,
            # no lo que se pidio cambiar. Se les calcula la URL para
            # poder mostrarla, pero no generan hallazgos.
            if cl.expected.intent != GREEN:
                continue

            # Verde tampoco basta: la fila puede estar verde por la
            # rotacion y repetir la landing page sin pintarla. Esa URL
            # es contexto, y juzgarla convertia en fallo algo que nadie
            # pidio cambiar.
            #
            # Pero callarla del todo tampoco: si de verdad difiere, se
            # dice una vez como INFO. No tumba el QA -- no es de esta
            # solicitud -- y no se pierde.
            if not requested(cl.expected, "url"):
                if cl.url.result not in (URL_MATCH, URL_BOTH_MISSING):
                    buffer.info(
                        rule_id="URL-001",
                        domain=Domain.URL,
                        placement_id=pm.placement_id,
                        creative_name=cl.expected.name,
                        message=(
                            "The landing page differs from Innovid, but "
                            "this request didn't ask to change it"
                        ),
                        expected=cl.expected.url,
                        actual=" | ".join(_actual_urls(pm.actual)[:1]),
                        recommended_action=(
                            "Nothing to do for this request. Worth "
                            "raising separately if it looks wrong."
                        ),
                    )
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

            if getattr(cl.expected, "url_alternatives", ()) and result in (
                    URL_MATCH, URL_BASE_DIFF, URL_PARAMS_DIFF):
                result = "AMBIGUOUS"

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

            elif result == "AMBIGUOUS":
                buffer.review(
                    message=(
                        "The Traffic Sheet lists this landing page more than "
                        "once with different URLs ("
                        + " / ".join(cl.expected.url_alternatives[:3])
                        + "), so QA2 can't tell which one Innovid should have."
                    ),
                    reason=cl.url.note,
                    recommended_action=(
                        "Confirm which URL is right and fix the Traffic Sheet "
                        "or the Clicktag."
                    ),
                    **common,
                )

            elif result in (URL_BASE_DIFF, URL_PARAMS_DIFF):
                buffer.fail(
                    message=(
                        "The URL configured in Innovid doesn't match the TS. "
                        + _sentence(cl.url.note)
                    ),
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

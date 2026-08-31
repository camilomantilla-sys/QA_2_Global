from core.findings import Domain


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        for cl in pm.creative_links:

            if cl.triangle is None:
                continue

            if cl.triangle.is_ok:

                buffer.pass_(
                    rule_id="ATR-001",
                    domain=Domain.ATTRIBUTION,
                    message="Attribution is correct",
                    placement_id=pm.placement_id,
                )

            else:

                buffer.review(
                    rule_id="ATR-001",
                    domain=Domain.ATTRIBUTION,
                    message=cl.triangle.note,
                    placement_id=pm.placement_id,
                )
from core.findings import Domain


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        for cl in pm.creative_links:

            if cl.url is None:
                continue

            if cl.url.is_ok:

                buffer.pass_(
                    rule_id="URL-001",
                    domain=Domain.URL,
                    message="URL correcta",
                    placement_id=pm.placement_id,
                )

            else:

                buffer.fail(
                    rule_id="URL-001",
                    domain=Domain.URL,
                    message=cl.url.note,
                    placement_id=pm.placement_id,
                    expected=cl.url.expected.raw,
                    actual=cl.url.actual.raw,
                )
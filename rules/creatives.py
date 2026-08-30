from core.findings import Domain


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        for cl in pm.creative_links:

            if cl.actual is None:

                buffer.fail(
                    rule_id="CRE-001",
                    domain=Domain.CREATIVE,
                    message="Creative faltante en export",
                    placement_id=pm.placement_id,
                    creative_id=cl.expected.creative_id,
                    creative_name=cl.expected.name,
                    expected=cl.expected.name,
                )

            else:

                buffer.pass_(
                    rule_id="CRE-001",
                    domain=Domain.CREATIVE,
                    message="Creative encontrado",
                    placement_id=pm.placement_id,
                    creative_id=cl.actual.creative_id,
                    creative_name=cl.actual.name,
                )
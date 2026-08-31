from core.findings import Domain

def evaluate(match_result, buffer):

    for pm in match_result.matched:

        for cl in pm.creative_links:

            if cl.triangle is None:
                continue

            expected = getattr(cl.triangle, "expected_dtree", None)
            actual = getattr(cl.triangle, "actual_dtree", None)

            if not expected and not actual:
                continue

            if expected == actual:

                buffer.pass_(
                    rule_id="TRK-001",
                    domain=Domain.ATTRIBUTION,
                    message="DTree is correct",
                    placement_id=pm.placement_id,
                )

            else:

                buffer.fail(
                    rule_id="TRK-001",
                    domain=Domain.ATTRIBUTION,
                    message="DTree mismatch",
                    placement_id=pm.placement_id,
                    expected=expected,
                    actual=actual,
                )
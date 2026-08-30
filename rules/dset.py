from core.findings import Domain

def evaluate(match_result, buffer):

    for pm in match_result.matched:

        for cl in pm.creative_links:

            if cl.triangle is None:
                continue

            expected = getattr(cl.triangle, "expected_dset", None)
            actual = getattr(cl.triangle, "actual_dset", None)

            if not expected and not actual:
                continue

            if expected == actual:

                buffer.pass_(
                    rule_id="TRK-002",
                    domain=Domain.ATTRIBUTION,
                    message="DSet correcto",
                    placement_id=pm.placement_id,
                )

            else:

                buffer.fail(
                    rule_id="TRK-002",
                    domain=Domain.ATTRIBUTION,
                    message="DSet mismatch",
                    placement_id=pm.placement_id,
                    expected=expected,
                    actual=actual,
                )
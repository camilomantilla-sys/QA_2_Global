from core.findings import Domain


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        if not pm.actual:
            continue

        expected = (pm.expected.name or "").strip()
        actual = (pm.actual.name_norm or pm.actual.name or "").strip()

        if not expected:
            continue

        if expected == actual:

            buffer.pass_(
                rule_id="PLC-006",
                domain=Domain.IDENTITY,
                message="Placement Name is correct",
                placement_id=pm.placement_id,
            )

        else:

            buffer.fail(
                rule_id="PLC-006",
                domain=Domain.IDENTITY,
                message="Placement Name mismatch",
                placement_id=pm.placement_id,
                expected=expected,
                actual=actual,
            )
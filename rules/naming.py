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

            # Placement ID already matched at this point (this loop
            # only runs over matched placements), so trafficking is
            # correct. A name mismatch doesn't block implementation
            # -- it's a callout for the digital team to clean up the
            # naming later, not a failure.
            buffer.review(
                rule_id="PLC-006",
                domain=Domain.IDENTITY,
                message=(
                    "Placement Name mismatch (Placement ID matched; "
                    "this does not affect trafficking)."
                ),
                placement_id=pm.placement_id,
                expected=expected,
                actual=actual,
                recommended_action=(
                    "Flag to the digital team as a naming cleanup; "
                    "no re-trafficking required."
                ),
            )
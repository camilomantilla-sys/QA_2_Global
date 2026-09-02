from core.findings import Domain, EntityType

RULE_ID = "DEF-001"


def evaluate(reconciliation, buffer):

    for check in reconciliation.checks:

        common = dict(
            rule_id=RULE_ID,
            domain=Domain.CREATIVE,
            entity_type=EntityType.PLACEMENT,
            placement_id=check.placement_id,
            expected=check.expected_creative,
            actual=check.creative,
            reason=f"Default ad · {check.dims}",
        )

        if check.result == "PASS":
            buffer.pass_(message=check.message, **common)

        elif check.result == "REVIEW":
            buffer.review(
                message=check.message,
                recommended_action=(
                    "Confirm which default ad should be running for "
                    "this dimension."
                ),
                **common,
            )

        else:
            buffer.fail(
                message=check.message,
                recommended_action=(
                    "Align the default ad with the one used on the rest "
                    "of the placements of this dimension."
                ),
                **common,
            )

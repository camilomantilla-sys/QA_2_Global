from core.findings import Domain, EntityType


def evaluate(reconciliation, buffer):

    for check in reconciliation.checks:

        common = dict(
            rule_id="DV-001",
            domain=Domain.TAG,
            entity_type=EntityType.PLACEMENT,
            placement_id=check.placement_id,
            placement_name=check.placement_name,
            reason=f"Vendors / Pixels: {check.vendor_raw}",
        )

        if check.result == "PASS":
            buffer.pass_(message=check.message, **common)

        elif check.result == "FAIL":
            buffer.fail(
                message=check.message,
                recommended_action=(
                    "Confirm the DV Pinnacle tag was generated and "
                    "delivered for this placement."
                ),
                **common,
            )

        elif check.result == "REVIEW":
            buffer.review(
                message=check.message,
                recommended_action=(
                    "Confirm this placement's Innovid tags were "
                    "delivered alongside the DV Pinnacle file."
                ),
                **common,
            )

        else:
            buffer.not_verified(message=check.message, **common)

    for placement_id in reconciliation.extra_dv_placements:
        buffer.info(
            rule_id="DV-002",
            domain=Domain.SCOPE,
            entity_type=EntityType.PLACEMENT,
            message=(
                "DV Pinnacle file placement is outside the "
                "worked scope."
            ),
            placement_id=placement_id,
        )

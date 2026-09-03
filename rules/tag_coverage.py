from core.findings import Domain, EntityType

RULE_ID = "TAG-013"


def evaluate(reconciliation, buffer):

    for check in reconciliation.checks:

        common = dict(
            rule_id=RULE_ID,
            domain=Domain.TAG,
            entity_type=EntityType.PLACEMENT,
            placement_id=check.placement_id,
            placement_name=check.placement_name,
            reason=f"Vendors / Pixels: {check.vendor_raw}",
        )

        if check.result == "PASS":
            buffer.pass_(message=check.message, **common)

        else:
            buffer.review(
                message=check.message,
                recommended_action=(
                    "Confirm whether this placement's tags were "
                    "delivered, and upload the file that covers it."
                ),
                **common,
            )

from core.findings import Domain, EntityType

RULE_ID = "DV-003"


def evaluate(reconciliation, buffer):

    for check in reconciliation.checks:

        common = dict(
            rule_id=RULE_ID,
            domain=Domain.PIXEL,
            entity_type=EntityType.PLACEMENT,
            placement_id=check.placement_id,
            placement_name=check.placement_name,
            reason=f"Vendors / Pixels: {check.vendor_raw} ({check.fmt})",
        )

        if check.result == "PASS":
            buffer.pass_(message=check.message, **common)

        elif check.result == "FAIL":
            buffer.fail(
                message=check.message,
                expected=check.expected_column,
                recommended_action=check.recommended_action,
                **common,
            )

        else:
            buffer.not_verified(
                message=check.message,
                recommended_action=check.recommended_action,
                **common,
            )

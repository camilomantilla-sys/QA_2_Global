from core.findings import Domain, EntityType

RULE_ID = "PIX-002"

_COLUMN_LABEL = {
    "third_party_survey": "Third Party Survey",
    "third_party_impression": "Third Party Impression",
}


def evaluate(reconciliation, buffer):

    for check in reconciliation.checks:

        common = dict(
            rule_id=RULE_ID,
            domain=Domain.TAG,
            entity_type=EntityType.PLACEMENT,
            placement_id=check.placement_id,
            placement_name=check.placement_name,
            expected=(
                f"{check.vendor} pixel in "
                f"{_COLUMN_LABEL.get(check.column, check.column)}"
            ),
            actual=check.found,
            reason=f"Vendors / Pixels: {check.vendor_raw}",
        )

        if check.result == "PASS":
            buffer.pass_(message=check.message, **common)

        elif check.result == "FAIL":
            buffer.fail(
                message=check.message,
                recommended_action=(
                    f"Load the {check.vendor} pixel on the placement, in "
                    f"{_COLUMN_LABEL.get(check.column, check.column)}."
                ),
                **common,
            )

        else:
            buffer.not_verified(
                message=check.message,
                recommended_action=(
                    "Upload the Innovid Placement View."
                ),
                **common,
            )

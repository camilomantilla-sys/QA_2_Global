"""
PIX-002 -- el pixel de cada vendor esta en su columna.

Compara los pixeles declarados en la TS (Third Party Survey / Third
Party Impression) con lo que Innovid tiene. La tabla de vendors es
editable desde la app; la conciliacion vive en
core/pixel_reconciliation.py.
"""

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

        elif check.result == "REVIEW":
            buffer.review(
                message=check.message,
                expected=check.official,
                actual=check.found,
                recommended_action=(
                    "Confirm with the team whether the vendor rotated "
                    "its pixel -- if so, update the official pixel in "
                    "the Pixels by account panel."
                ),
                **{k: v for k, v in common.items() if k not in ("expected", "actual")},
            )

        else:
            buffer.not_verified(
                message=check.message,
                recommended_action=(
                    "Upload the Innovid Placement View."
                ),
                **common,
            )

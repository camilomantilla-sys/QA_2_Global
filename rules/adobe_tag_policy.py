"""
TAG-012 -- politica de columnas de tags de Adobe.

Adobe pide columnas distintas segun el tipo de placement (FTRACK,
No FTRACK, Clicktag, Protected). La conciliacion la hace
core/adobe_tag_policy_reconciliation.py; aqui solo se traduce cada
comprobacion en un hallazgo.
"""

from core.findings import Domain, EntityType

RULE_ID = "TAG-012"


def evaluate(reconciliation, buffer):

    for check in reconciliation.checks:

        common = dict(
            rule_id=RULE_ID,
            domain=Domain.TAG,
            entity_type=EntityType.PLACEMENT,
            placement_id=check.placement_id,
            placement_name=check.placement_name,
            reason=(
                f"Vendors / Pixels: {check.vendor_raw} "
                f"({', '.join(check.requirements)})"
            ),
        )

        if check.result == "PASS":
            buffer.pass_(message=check.message, **common)

        elif check.result == "FAIL":
            buffer.fail(
                message=check.message,
                expected=", ".join(check.required_missing),
                actual=", ".join(check.forbidden_present),
                recommended_action=check.recommended_action,
                **common,
            )

        else:
            buffer.not_verified(
                message=check.message,
                recommended_action=check.recommended_action,
                **common,
            )

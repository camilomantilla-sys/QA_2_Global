from core.findings import Domain
from parsers.ts_parser import REQ_CREATIVE_REMOVE


def evaluate(match_result, buffer):

    # Expected placement that doesn't exist
    for ep in match_result.only_expected:

        buffer.fail(
            rule_id="PLC-001",
            domain=Domain.SCOPE,
            message="Expected placement not found in Innovid",
            placement_id=ep.placement_id,
            placement_name=ep.name,
        )

    # Placement found
    for pm in match_result.matched:

        buffer.pass_(
            rule_id="PLC-001",
            domain=Domain.SCOPE,
            message="Placement found",
            placement_id=pm.placement_id,
            placement_name=pm.expected.name,
        )

        _evaluate_disassignment(pm, buffer)


def _evaluate_disassignment(pm, buffer):
    """
    PLC-002 - desasignacion de placement.

    Un placement enteramente en rojo en la TS (solo remociones, ningun
    creativo nuevo) no es un swap: es una desasignacion. En Innovid eso
    debe quedar como Status=Stopped y sin creativos corriendo.
    """
    expected = pm.expected

    # "Todo el placement en rojo" es justo lo que la TS clasifica como
    # CREATIVE_REMOVE: hay remociones y ningun alta.
    if expected.request_type != REQ_CREATIVE_REMOVE:
        return

    actual = pm.actual
    status = str(actual.status or "").strip() if actual else ""

    common = dict(
        rule_id="PLC-002",
        domain=Domain.SCOPE,
        placement_id=pm.placement_id,
        placement_name=expected.name,
        expected="Stopped, with no creatives running",
    )

    if not status:
        buffer.not_verified(
            message=(
                "The placement is a full disassignment, but the export "
                "doesn't report its status."
            ),
            recommended_action=(
                "Upload the Innovid Placement View to verify the status."
            ),
            **common,
        )
        return

    running = [c for c in actual.creatives if c.running]

    if status.casefold() != "stopped":
        # Se reporta como REVIEW y no como FAIL a proposito: apagar o
        # desasignar un placement lo ejecuta Digital, no AdOps, asi que
        # esto es un callout para ellos y no bloquea el envio de tags.
        buffer.review(
            message=(
                "The placement is a full disassignment, but it isn't "
                "stopped in Innovid."
            ),
            actual=f"Status={status}",
            recommended_action=(
                "Flag to Digital so they stop the placement."
            ),
            **common,
        )

    elif running:
        buffer.review(
            message=(
                "The placement is stopped, but it still has creatives "
                "assigned."
            ),
            actual=f"Status={status}, {len(running)} creative(s) running",
            recommended_action=(
                "Confirm whether the remaining creatives should be "
                "unassigned too."
            ),
            **common,
        )

    else:
        buffer.pass_(
            message="Placement disassignment confirmed: stopped and empty.",
            actual=f"Status={status}",
            **common,
        )

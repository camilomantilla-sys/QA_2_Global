from core.findings import Domain


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

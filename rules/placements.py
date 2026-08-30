from core.findings import Domain


def evaluate(match_result, buffer):

    # Placement esperado que no existe
    for ep in match_result.only_expected:

        buffer.fail(
            rule_id="PLC-001",
            domain=Domain.SCOPE,
            message="Placement esperado no encontrado en Innovid",
            placement_id=ep.placement_id,
            placement_name=ep.name,
        )

    # Placement encontrado
    for pm in match_result.matched:

        buffer.pass_(
            rule_id="PLC-001",
            domain=Domain.SCOPE,
            message="Placement encontrado",
            placement_id=pm.placement_id,
            placement_name=pm.expected.name,
        )
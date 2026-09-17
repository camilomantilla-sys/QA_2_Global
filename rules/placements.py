from core.colors import GREEN, RED
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

    # PLC-007 mira la TS, no Innovid: vale igual para un placement que
    # volvio y para uno que no.
    for ep in [pm.expected for pm in match_result.matched] + list(
        match_result.only_expected
    ):
        _evaluate_rotation_dims(ep, buffer)


def _evaluate_rotation_dims(ep, buffer):
    """
    PLC-007 -- la rotacion que el placement declara no es de su tamano.

    Los creativos de un grupo se filtran por dimension a proposito: un
    grupo de Adobe trae los 5 tamanos y un placement de 160x600 solo
    sirve los suyos. Pero cuando el filtro se lleva TODOS los creativos
    pedidos, el placement se queda sin nada que comparar y el reporte
    no lo decia: el hueco se tapaba solo con el default ad, que se
    engancha por dimension, y la fila se leia como si estuviera
    revisada.

    Es lo que paso con dos placements de BlackRock cuyas rotaciones
    quedaron cruzadas en la TS -- el de 300x600 nombrando la rotacion
    de 300x250 y viceversa. Innovid estaba bien; la TS no.
    """
    pedidos = [
        c for c in ep.creatives
        if not c.is_default and c.intent in (GREEN, RED, "SWAP")
    ]

    # Si quedo aunque sea uno, el filtro hizo su trabajo: el grupo
    # traia varios tamanos y este placement se quedo con el suyo.
    if not ep.dims_dropped or pedidos:
        return

    descartados = ", ".join(
        f"{name} ({dims})" if dims else name
        for name, dims in ep.dims_dropped
    )

    buffer.review(
        rule_id="PLC-007",
        domain=Domain.SCOPE,
        message=(
            "The creative rotation this placement declares has no "
            "creative of its dimension, so nothing that was requested "
            "could be compared."
        ),
        placement_id=ep.placement_id,
        placement_name=ep.name,
        expected=f"A {ep.dims} creative in \"{ep.group_name}\"",
        actual=f"{ep.group_name} contains: {descartados}",
        recommended_action=(
            "Check the Creative Rotation column of the Traffic Sheet: "
            f"this placement is {ep.dims} and the rotation it names is "
            "not."
        ),
    )


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

    else:
        # Un placement detenido no sirve nada, lleve o no creativos
        # colgados. La desasignacion se ejecuta apagando el placement,
        # asi que exigir ademas que quede vacio solo generaba ruido
        # sobre algo que ya no corre.
        buffer.pass_(
            message="Placement disassignment confirmed: it's stopped.",
            actual=(
                f"Status={status}"
                + (f", {len(running)} creative(s) still attached" if running else "")
            ),
            **common,
        )

"""
PLC-001 / PLC-002 / PLC-007 -- existencia y estado de los placements.

PLC-001: el placement que pide la TS existe en Innovid.
PLC-002: en una desasignacion, el placement quedo detenido.
PLC-003 (REVIEW): la TS quiere el placement corriendo y el export lo
muestra apagado.
PLC-004 (INFO): las fechas del placement en Innovid no son las de la TS.
No bloquea el QA (decision de AdOps, FB-09): va a los callouts del
reporte para que alguien confirme que es a proposito.
PLC-007 (REVIEW): la rotacion que declara el placement tiene al menos
un creativo de su dimension.
"""

from core.colors import GREEN, RED
from core import placement_state
from core.dates import to_date as _to_date
from core.findings import Domain
from core.normalize import dims_match, norm_dims
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

    # Filas de la TS con #N/A en el Placement ID que tampoco se
    # encontraron en el export por el codigo del Placement Name.
    for row in getattr(match_result, "unrecovered_ts_rows", []):
        name = str(row.values.get("placement_name") or "")
        buffer.review(
            rule_id="PLC-001",
            domain=Domain.SCOPE,
            message=(
                f"Traffic Sheet row {row.row} has a formula error in the "
                "Placement ID, and the code in its Placement Name isn't in "
                "the Innovid export. QA2 can't tell which placement it is."
            ),
            placement_id="",
            placement_name=name,
            recommended_action=(
                "Find the placement in Innovid by its name and check it by "
                "hand, or fix the formula in the Traffic Sheet and run again."
            ),
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
        _evaluate_switched_off(pm, buffer)
        _evaluate_flight_dates(pm, buffer)
        _evaluate_size(pm, buffer)

    # PLC-007 mira la TS, no Innovid: vale igual para un placement que
    # volvio y para uno que no.
    for ep in [pm.expected for pm in match_result.matched] + list(
        match_result.only_expected
    ):
        _evaluate_rotation_dims(ep, buffer)


def _evaluate_size(pm, buffer):
    """
    PLC-005 (REVIEW) -- el tamano del placement en la TS no es el de
    Innovid. Caso de prueba (18-nov): un placement nuevo de 300x250 en
    la TS que en Innovid es 300x600 pasaba sin que nadie lo dijera. El
    tamano lo fija Prisma, no AdOps: puede ser la TS o el placement
    equivocado, asi que lo mira una persona. Video (0x0, duraciones) no
    se compara.
    """
    ts_dims = norm_dims(getattr(pm.expected, "dims", ""))
    actual = getattr(pm, "actual", None)
    inn_dims = norm_dims(getattr(actual, "dims", "")) if actual is not None else ""
    if not ts_dims or not inn_dims or "0x0" in (ts_dims, inn_dims):
        return
    if dims_match(ts_dims, inn_dims):
        return
    buffer.review(
        rule_id="PLC-005",
        domain=Domain.SCOPE,
        message="The placement's size in Innovid isn't the one in the Traffic Sheet",
        placement_id=pm.placement_id,
        placement_name=pm.expected.name,
        expected=ts_dims,
        actual=inn_dims,
        recommended_action=(
            "Check that this is the right placement, or ask for the Traffic "
            "Sheet to be corrected."
        ),
    )


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


def _span(start, end) -> str:
    return f"{start.isoformat() if start else '?'} → {end.isoformat() if end else '?'}"


def _evaluate_flight_dates(pm, buffer):
    """
    PLC-004 -- las fechas del placement, TS contra el export.

    Se comparan como fechas, no como texto: la TS escribe 11/16/2026 y
    el export 2026-11-16, y eso es el mismo dia.

    Una diferencia no bloquea el QA. Suele ser a proposito (el placement
    salio el dia de la implementacion porque el inicio de la TS ya
    habia pasado), pero alguien tiene que verla: por eso es INFO y va a
    los callouts del reporte, todos juntos en una sola lista.
    """
    if pm.actual is None or placement_state.wants_it_off(pm):
        return
    ts_start, ts_end = _to_date(pm.expected.start), _to_date(pm.expected.end)
    in_start, in_end = _to_date(pm.actual.start), _to_date(pm.actual.end)
    # Arrancar despues del inicio de la TS es lo normal cuando se
    # trafica tarde: el inicio de la TS ya habia pasado. Solo cuenta
    # arrancar ANTES.
    start_off = bool(ts_start and in_start and in_start < ts_start)
    started_late = bool(ts_start and in_start and in_start > ts_start)
    end_off = bool(ts_end and in_end and ts_end != in_end)
    if not ((ts_start and in_start) or (ts_end and in_end)):
        return
    common = dict(
        rule_id="PLC-004",
        domain=Domain.DATES,
        placement_id=pm.placement_id,
        placement_name=pm.expected.name,
        expected=_span(ts_start, ts_end),
        actual=_span(in_start, in_end),
    )
    if not (start_off or end_off):
        buffer.pass_(
            message=(f"The placement went live on {in_start.isoformat()}, after the Traffic "
                     f"Sheet start ({ts_start.isoformat()}): it was trafficked later"
                     if started_late else "The placement flights on the Traffic Sheet dates"),
            **common)
        return
    message = (
        "The placement starts in Innovid before the Traffic Sheet start, and ends on another date"
        if start_off and end_off else
        "The placement starts in Innovid before the Traffic Sheet start" if start_off else
        "The placement has another end date in Innovid than in the Traffic Sheet")
    buffer.info(
        message=message,
        reason=("Placement dates don't block the QA. They are listed in the "
                "report callouts so someone confirms the difference is intended "
                "(for example, it went live on the implementation date)."),
        recommended_action="Check that the difference is intended, or correct the placement dates.",
        **common,
    )


def _evaluate_switched_off(pm, buffer):
    """
    PLC-003 -- la TS quiere el placement corriendo y esta apagado.

    Todo lo demas puede coincidir (creativos asignados, URL, CGEN) y aun
    asi el placement no sirve nada. Sin esto el QA salia PASSED con
    placements en gris.
    """
    status = str(pm.actual.status or "").strip() if pm.actual else ""
    if not placement_state.is_inactive(status) or placement_state.wants_it_off(pm):
        return
    buffer.review(
        rule_id="PLC-003",
        domain=Domain.SCOPE,
        placement_id=pm.placement_id,
        placement_name=pm.expected.name,
        message=(
            "The Traffic Sheet wants this placement running "
            f"({placement_state.what_the_ts_asks(pm)}), but the export "
            f"shows it {status}"
        ),
        expected="Running",
        actual=f"Status={status}",
        reason=placement_state.OLDER_TS_NOTE,
        recommended_action=placement_state.ACTION,
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

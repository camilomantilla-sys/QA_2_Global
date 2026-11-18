"""
ROT-001 -- la rotacion que se pidio cambiar.

Un cambio de rotacion no se puede verificar con los archivos. Cuando
el placement corre por Decision Tree, la columna Rotation del export
placement-creative dice literalmente "Decision Tree" en todas sus
filas: el porcentaje vive dentro del decision set y solo lo alcanza
la API de Innovid.

Hasta ahora eso no se decia. CRE-001 encontraba el creativo, emitia
"Creative found" y el reporte cerraba en verde -- sobre una solicitud
de 355 cambios de rotacion de los que no se habia comparado ninguno.
Encontrar el creativo es verdad; que la rotacion quedo como se pidio
no se sabia. Esta regla dice esa segunda parte.

Cuando Innovid si esta conectado, quien compara es INV-002, y esta
regla se calla para no duplicar el hallazgo.
"""
from core.colors import GREEN, RED, WHITE
from core.matching import is_site_served_1x1
from core.findings import Capability, Domain, EntityType, Status
from core.normalize import normalize_weights

ROTATION_FIELD = "rotation_weight"


def _weights_label(creatives) -> str:
    """
    Los pesos pedidos, en porcentaje y sin repetir.

    Se normalizan como grupo y no uno a uno: un peso de rotacion es
    relativo, y la escala solo se ve mirando el reparto entero.
    """
    seen: list[str] = []
    for label in normalize_weights(
        [creative.rotation_weight for creative in creatives],
        removed=[creative.intent == RED or creative.is_default
                 for creative in creatives],
    ):
        if label and label not in seen:
            seen.append(label)
    return ", ".join(seen)


def _requested_rotation(creative) -> bool:
    """
    ¿La TS pinto la celda de rotacion de este creativo?

    La hoja marca el CAMPO que cambia, no la fila entera. Una celda de
    Rotation (%) pintada es una peticion de cambio de rotacion sobre un
    creativo que ya existia.
    """
    return ROTATION_FIELD in (creative.intent_fields or frozenset())


def evaluate(match_result, buffer):

    if buffer.capabilities.available(Capability.ROTATION_WEIGHT):
        # Innovid esta conectado: INV-002 compara de verdad contra el
        # decision set. Repetirlo aqui solo duplicaria el hallazgo.
        return

    _dates_not_verified(match_result, buffer)

    for pm in match_result.matched:

        # Un 1x1 site-served no tiene decision set ni rotacion que
        # configurar: el creativo va directo al placement. Pedir revision
        # ahi es pedir algo que no existe (FB-15).
        if is_site_served_1x1(getattr(pm, "expected", None)):
            continue

        requested = [
            cl.expected
            for cl in pm.creative_links
            if cl.expected.intent != WHITE and _requested_rotation(cl.expected)
        ]
        if not requested:
            continue

        weights = _weights_label(requested)

        # Un hallazgo por placement, no por creativo: una solicitud de
        # 355 cambios generaria 355 lineas identicas y el reporte
        # dejaria de leerse. El conteo y los pesos van en el mensaje.
        buffer.aggregate(
            rule_id="ROT-001",
            domain=Domain.ROTATION,
            status=Status.NOT_VERIFIED,
            message=(
                f"{len(requested)} rotation weight(s) requested on this "
                "placement were not compared: Innovid was not "
                "connected in this run."
            ),
            count=len(requested),
            reason=buffer.capabilities.reason(Capability.ROTATION_WEIGHT),
            entity_type=EntityType.ROTATION,
            placement_id=pm.placement_id,
            expected=weights or "(rotation change requested)",
            requires=[Capability.ROTATION_WEIGHT],
            recommended_action=(
                "Connect Innovid in the sidebar and run again: the "
                "weight is stored in the decision set, and no export "
                "carries it."
            ),
        )


DATE_FIELDS = {"start_date", "end_date"}
#: Un creativo nuevo trae sus fechas pintadas tambien: eso no es un
#: cambio de fechas, es un creativo que entra.
IDENTITY_FIELDS = {"creative_name", "creative_id", "universal_ad_id"}


def _dates_not_verified(match_result, buffer):
    """
    Un cambio de fechas de creativo pedido, sin Innovid conectado.

    Las fechas del creativo dentro del decision set solo las trae la API
    de Innovid (INV-001). Sin ella, CRE-001 encontraba el creativo y el
    placement cerraba en verde sobre una solicitud que solo cambiaba
    fechas: lo unico que se pidio no se habia mirado.
    """
    for pm in match_result.matched:
        changed = [
            cl.expected for cl in pm.creative_links
            if cl.expected.intent == GREEN
            and DATE_FIELDS & set(cl.expected.intent_fields or ())
            and not IDENTITY_FIELDS & set(cl.expected.intent_fields or ())
        ]
        if not changed:
            continue
        names = ", ".join(dict.fromkeys(c.name for c in changed))
        buffer.aggregate(
            rule_id="INV-001",
            domain=Domain.ROTATION,
            status=Status.NOT_VERIFIED,
            message=(
                f"The Traffic Sheet changes the dates of {names} here, and "
                "they were not compared: Innovid was not connected in this run."
            ),
            count=len(changed),
            reason=buffer.capabilities.reason(Capability.ROTATION_WEIGHT),
            entity_type=EntityType.ROTATION,
            placement_id=pm.placement_id,
            expected=" | ".join(dict.fromkeys(
                f"{c.start or '?'} → {c.end or '?'}" for c in changed)),
            requires=[Capability.ROTATION_WEIGHT],
            recommended_action=(
                "Connect Innovid in the sidebar and run again: the "
                "creative's dates live in the decision set."
            ),
        )

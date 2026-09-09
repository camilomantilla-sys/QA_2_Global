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
from core.colors import WHITE
from core.findings import Capability, Domain, EntityType, Status

ROTATION_FIELD = "rotation_weight"


def _as_percent(value: str) -> str:
    """
    Excel guarda un 13,33% como 0.13333333333333333. Mostrarlo crudo
    llena el reporte de decimales que nadie puede contrastar contra la
    hoja. Los pesos de cada grupo suman 1.0000 exacto, asi que son
    fracciones y se leen como porcentaje.

    Lo que no sea un numero (EVEN, o texto libre) se devuelve tal cual:
    inventarle un porcentaje seria peor que mostrarlo como esta.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        number = float(text.rstrip("%"))
    except ValueError:
        return text
    if text.endswith("%"):
        return text
    percent = number * 100
    return f"{percent:.2f}".rstrip("0").rstrip(".") + "%"


def _weights_label(creatives) -> str:
    seen: list[str] = []
    for creative in creatives:
        label = _as_percent(creative.rotation_weight)
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

    for pm in match_result.matched:

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
                "placement were not compared."
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

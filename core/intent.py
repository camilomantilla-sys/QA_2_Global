"""
Que se pidio cambiar de un creativo, campo por campo.

La Traffic Sheet pinta la CELDA que cambia, no la fila entera. Una
solicitud de cambio de rotacion pinta solo la celda de Rotation (%)
sobre un creativo que ya existia; una de creativo nuevo pinta la fila
completa. En la solicitud real de Dove eran 355 filas del primer tipo
y 18 del segundo, y QA2 las trataba todas como creativo nuevo:
validaba nombre, fechas y URL de creativos que nadie pidio tocar.

Lo que se pidio se valida. Lo que no, se muestra pero no se juzga.

La existencia del creativo es la excepcion y se valida siempre: no se
le puede cambiar la rotacion a algo que no esta.
"""
from __future__ import annotations

# De lo que pregunta una regla, a las celdas de la TS que lo declaran.
ASPECTS: dict[str, tuple[str, ...]] = {
    "rotation": ("rotation_weight",),
    "dates": ("start_date", "end_date"),
    "url": ("lp_url",),
    "name": ("creative_name",),
    "identity": ("creative_id", "universal_ad_id"),
    "sequence": ("sequence",),
}


def requested(creative, aspect: str) -> bool:
    """
    ¿La TS pidio cambiar este aspecto de este creativo?

    Sin informacion de color -- TS viejas, hojas sin pintar, filas que
    el parser no pudo clasificar -- se responde que SI a todo. Es la
    respuesta segura: seguir validando de mas nunca deja pasar un
    error, y este proyecto tiene que seguir leyendo formatos que
    cambian cada ano.
    """
    fields = getattr(creative, "intent_fields", None) or frozenset()
    if not fields:
        return True

    wanted = ASPECTS.get(aspect)
    if wanted is None:
        # Un aspecto que nadie mapeo todavia. Se valida, por lo mismo
        # de arriba: callar por no saber es peor que preguntar de mas.
        return True

    return any(field in fields for field in wanted)


def rotation_only(creative) -> bool:
    """
    ¿Lo unico que se pidio fue la rotacion?

    El caso que ocupa 355 de las 382 filas verdes de una solicitud de
    cambios de rotacion.
    """
    fields = set(getattr(creative, "intent_fields", None) or ())
    return fields == {"rotation_weight"}

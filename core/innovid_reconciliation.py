"""
Lo que la Traffic Sheet pide contra lo que Innovid realmente tiene.

Cubre los tres campos que ningun export trae y que hasta ahora solo se
podian revisar abriendo Innovid a mano:

  - las fechas de vuelo de cada creativo, que viven dentro del decision
    set y pueden diferir de las del placement (un placement del 20 de
    julio con creativos que arrancan el 24)
  - el peso de rotacion de cada creativo
  - el Verification Partner configurado en el placement

El emparejamiento va por nombre de archivo. El ID de creativo de
Innovid no existe hasta que alguien trafica, asi que una TS nunca lo
puede traer: el nombre es el unico identificador que existe en ambos
lados. Se normaliza con norm_creative, el mismo criterio que ya usa el
resto de QA2 para no tener dos definiciones de "mismo creativo".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from core.matching import norm_creative
from core.normalize import norm_compare, normalize_weights

MATCHED = "MATCHED"
MISSING_IN_INNOVID = "MISSING_IN_INNOVID"
EXTRA_IN_INNOVID = "EXTRA_IN_INNOVID"
AMBIGUOUS = "AMBIGUOUS"


@dataclass
class CreativeFlightCheck:
    """Un creativo de la TS frente a su nodo en el decision set."""

    placement_id: str
    creative_name: str = ""
    status: str = MATCHED

    # GREEN / RED / WHITE, tal como lo declara la TS. Los WHITE son
    # contexto: entran a la comparacion para que el resto del decision
    # set no se lea como "extra", pero no generan hallazgos. Sin este
    # campo la regla no puede distinguirlos.
    intent: str = ""

    expected_start: date | None = None
    expected_end: date | None = None
    actual_start: date | None = None
    actual_end: date | None = None

    expected_weight: str = ""
    actual_weight: str = ""

    # Los mismos pesos en porcentaje, ya llevados a la misma escala.
    # La TS guarda 13,33% como 0.1333 y Innovid lo da como 13: sin
    # esto la regla comparaba escalas distintas y la tabla mostraba
    # el 13 de Innovid como 1300%. Se calculan por placement, donde
    # la rotacion reparte el 100%.
    expected_weight_pct: str = ""
    actual_weight_pct: str = ""

    dset_id: str = ""
    dset_name: str = ""

    # Como se encontro el creativo: por nombre de archivo, o por
    # creative id cuando el nombre no coincidia. Un renombrado en
    # Innovid no es un creativo ausente, y darlo por ausente dejaba
    # sin revisar sus fechas y su rotacion.
    matched_by: str = "name"
    actual_name: str = ""

    # Las celdas que la TS pinto en este creativo. La hoja marca el
    # CAMPO que cambia, no la fila: sin esto la regla no puede saber
    # si las fechas eran parte de la solicitud o solo contexto.
    intent_fields: frozenset = frozenset()

    # Cuando un mismo nombre aparece en mas de un nodo del mismo
    # decision set no se elige uno: elegir mal es peor que no elegir.
    candidates: int = 1


@dataclass
class VerificationPartnerCheck:
    placement_id: str
    actual_partner: str = ""
    actual_status: str = ""
    configured: bool = False

    # Los 1x1 site-served no llevan Verification Partner: el sitio
    # sirve el creativo y no hay nada que verificar. Pedir revision
    # por cada uno seria ruido sobre algo que esta bien puesto.
    site_served_1x1: bool = False


@dataclass
class InnovidReconciliation:
    """
    Todo lo que se pudo comparar, y todo lo que no.

    `unchecked` no es un detalle: un placement cuyo decision set no se
    pudo leer no esta bien ni mal, esta sin revisar. Sin esa lista, un
    resultado sin hallazgos se lee como aprobado.
    """

    flights: list[CreativeFlightCheck] = field(default_factory=list)
    partners: list[VerificationPartnerCheck] = field(default_factory=list)
    unchecked: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def checked_placements(self) -> set[str]:
        return {c.placement_id for c in self.flights}


def _dates_differ(left: date | None, right: date | None) -> bool:
    """Solo compara cuando ambos lados existen."""
    return bool(left and right and left != right)


def reconcile(match_result, innovid_result) -> InnovidReconciliation:
    """
    Cruza los placements trabajados de la TS con lo que trajo Innovid.

    Solo mira los placements que la TS pidio: una campana de 200
    placements donde la solicitud toco 6 no debe generar hallazgos de
    los otros 194, que nadie trabajo.
    """
    out = InnovidReconciliation()

    if innovid_result is None:
        return out

    out.errors.extend(innovid_result.errors)

    innovid_by_placement = {
        row.placement_id: row
        for row in innovid_result.placement_rows()
    }

    for pm in match_result.matched:
        pid = str(pm.placement_id)

        innovid_placement = innovid_by_placement.get(pid)
        if innovid_placement is None:
            out.unchecked.append(
                (pid, "Innovid did not return this placement")
            )
            continue

        out.partners.append(VerificationPartnerCheck(
            placement_id=pid,
            actual_partner=innovid_placement.verification_partner,
            actual_status=innovid_placement.verification_status,
            configured=bool(innovid_placement.verification_partner),
            site_served_1x1=_is_site_served_1x1(pm),
        ))

        nodes = [
            n for n in innovid_result.nodes_for_placement(pid)
            if not n.is_default
        ]
        if not nodes:
            out.unchecked.append(
                (pid, "no decision set could be read for this placement")
            )
            continue

        expected = _expected_creatives(pm)
        if not expected:
            # La TS no declara creativos para este placement -- una
            # solicitud de default web ads o de 1x1 de tracking es
            # asi. Sin nada esperado no hay comparacion posible, y
            # marcar como "extra" todo lo que Innovid tenga llenaria
            # el reporte de ruido sobre creativos que nadie pidio
            # revisar.
            out.unchecked.append(
                (pid, "the Traffic Sheet declares no creatives for this "
                      "placement, so there is nothing to compare")
            )
            continue

        _compare_creatives(pid, expected, nodes, out)

    _normalize_weights(out)

    return out


def _normalize_weights(out: InnovidReconciliation) -> None:
    """
    Lleva los pesos de los dos lados a porcentajes, placement por
    placement. Cada rotacion reparte el 100% entre sus creativos, asi
    que el placement es el grupo que revela la escala de cada fuente.
    """
    by_placement: dict[str, list[CreativeFlightCheck]] = {}
    for check in out.flights:
        by_placement.setdefault(check.placement_id, []).append(check)

    for checks in by_placement.values():
        expected = normalize_weights([c.expected_weight for c in checks])
        actual = normalize_weights([c.actual_weight for c in checks])
        for check, exp, act in zip(checks, expected, actual):
            check.expected_weight_pct = exp
            check.actual_weight_pct = act


def _is_site_served_1x1(pm) -> bool:
    """
    Un 1x1 de tracking servido por el sitio.

    Se mira el formato que ya derivo la TS y, como respaldo, las
    dimensiones: un 1x1 puede llegar por cualquiera de los dos y
    equivocarse aqui significa pedir revision de algo correcto.
    """
    expected = getattr(pm, "expected", None)
    if expected is None:
        return False

    if norm_compare(getattr(expected, "fmt", "")) == "1x1":
        return True
    return norm_compare(getattr(expected, "dims", "")) == "1x1"


def _expected_creatives(pm) -> list:
    """
    Los creativos que la TS declara para el placement.

    Se toman de la expectativa, no del export: el export dice lo que
    quedo implementado, y aqui la pregunta es si eso coincide con lo
    que se pidio.
    """
    expected = getattr(pm, "expected", None)
    if expected is None:
        return []
    return [c for c in expected.creatives if c.name]


def _compare_creatives(pid, expected, nodes, out) -> None:
    by_name: dict[str, list] = {}
    for node in nodes:
        key = norm_creative(node.creative_name or node.creative_id)
        if key:
            by_name.setdefault(key, []).append(node)

    # Segundo indice, por creative id. Innovid a veces guarda el
    # creativo con otro nombre que el pedido en la TS -- un
    # "STA-BASE_011_NA-v01" que alla figura como "STA-R1_011_NA" --
    # pero conserva el mismo id. Buscar solo por nombre lo daba por
    # ausente y de paso dejaba sin revisar sus fechas y su rotacion,
    # que era justo lo que habia que mirar. El nombre distinto no se
    # tapa: se reporta aparte.
    by_id: dict[str, list] = {}
    for node in nodes:
        key = str(node.creative_id or "").strip()
        if key:
            by_id.setdefault(key, []).append(node)

    seen: set[str] = set()
    seen_ids: set[str] = set()

    for creative in expected:
        key = norm_creative(creative.name)
        if not key:
            continue
        seen.add(key)

        # El ID manda, el nombre es el respaldo.
        #
        # Dentro del decision set, el creativo se identifica por su
        # creative id: es lo que Innovid usa de verdad. Los nombres
        # llegan con lo que Innovid les pega al mostrarlos y con la
        # descripcion en vez del filename, asi que buscar por nombre
        # primero fallaba en creativos que estaban perfectamente ahi.
        # La Traffic Sheet trae el id en las 878 filas de Dove.
        #
        # El nombre sigue siendo el respaldo, y el unico camino en una
        # TS que no declare ids -- que las hay, y tienen que seguir
        # funcionando.
        creative_id = str(creative.creative_id or "").strip()
        candidates = by_id.get(creative_id, []) if creative_id else []
        matched_by = "creative_id" if candidates else "name"

        if candidates:
            seen_ids.add(creative_id)
        else:
            candidates = by_name.get(key, [])

        if not candidates:
            out.flights.append(CreativeFlightCheck(
                placement_id=pid,
                creative_name=creative.name,
                status=MISSING_IN_INNOVID,
                intent=creative.intent,
                intent_fields=frozenset(
                    getattr(creative, 'intent_fields', None) or ()
                ),
                expected_start=creative.start,
                expected_end=creative.end,
                expected_weight=creative.rotation_weight,
            ))
            continue

        if len(candidates) > 1:
            # Dos nodos con el mismo archivo en el mismo decision set.
            # Se reporta la ambiguedad en vez de comparar contra uno
            # elegido al azar, que daria un veredicto sin fundamento.
            out.flights.append(CreativeFlightCheck(
                placement_id=pid,
                creative_name=creative.name,
                status=AMBIGUOUS,
                intent=creative.intent,
                intent_fields=frozenset(
                    getattr(creative, 'intent_fields', None) or ()
                ),
                expected_start=creative.start,
                expected_end=creative.end,
                expected_weight=creative.rotation_weight,
                dset_id=candidates[0].dtree_id,
                dset_name=candidates[0].dtree_name,
                candidates=len(candidates),
                matched_by=matched_by,
            ))
            continue

        node = candidates[0]
        out.flights.append(CreativeFlightCheck(
            placement_id=pid,
            creative_name=creative.name,
            status=MATCHED,
            intent=creative.intent,
            intent_fields=frozenset(
                getattr(creative, 'intent_fields', None) or ()
            ),
            expected_start=creative.start,
            expected_end=creative.end,
            actual_start=_node_date(node.start_timestamp),
            actual_end=_node_date(node.end_timestamp),
            expected_weight=creative.rotation_weight,
            actual_weight=node.weight,
            dset_id=node.dtree_id,
            dset_name=node.dtree_name,
            matched_by=matched_by,
            actual_name=node.creative_name or "",
        ))

    for key, candidates in by_name.items():
        if key in seen:
            continue
        for node in candidates:
            # Ya se conto: la TS lo encontro por id, con otro nombre.
            if str(node.creative_id or "").strip() in seen_ids:
                continue
            out.flights.append(CreativeFlightCheck(
                placement_id=pid,
                creative_name=node.creative_name or node.creative_id,
                status=EXTRA_IN_INNOVID,
                actual_start=_node_date(node.start_timestamp),
                actual_end=_node_date(node.end_timestamp),
                actual_weight=node.weight,
                dset_id=node.dtree_id,
                dset_name=node.dtree_name,
            ))


def _node_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def flights_by_creative(reconciliation) -> dict[tuple[str, str], CreativeFlightCheck]:
    """
    Indice (placement, nombre normalizado) -> lo que Innovid tiene.

    La tabla de creativos necesita poner lado a lado lo que pide la TS
    y lo que hay en el decision set, fila por fila. Sin este indice
    tendria que recorrer la lista entera por cada creativo, y sobre
    todo tendria que repetir aqui la definicion de "mismo creativo",
    que ya vive en norm_creative -- dos definiciones que se separan
    con el tiempo es justo como aparecen los falsos negativos.

    Cuando el mismo nombre sale en varios nodos, gana el primero pero
    el check conserva `candidates`, para que quien lea sepa que habia
    mas de uno.
    """
    index: dict[tuple[str, str], CreativeFlightCheck] = {}
    if reconciliation is None:
        return index
    for check in reconciliation.flights:
        key = (str(check.placement_id), norm_creative(check.creative_name))
        index.setdefault(key, check)
    return index

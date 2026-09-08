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
from core.normalize import norm_compare

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

    dset_id: str = ""
    dset_name: str = ""

    # Cuando un mismo nombre aparece en mas de un nodo del mismo
    # decision set no se elige uno: elegir mal es peor que no elegir.
    candidates: int = 1


@dataclass
class VerificationPartnerCheck:
    placement_id: str
    actual_partner: str = ""
    actual_status: str = ""
    configured: bool = False


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

    return out


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

    seen: set[str] = set()

    for creative in expected:
        key = norm_creative(creative.name)
        if not key:
            continue
        seen.add(key)

        candidates = by_name.get(key, [])

        if not candidates:
            out.flights.append(CreativeFlightCheck(
                placement_id=pid,
                creative_name=creative.name,
                status=MISSING_IN_INNOVID,
                intent=creative.intent,
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
                expected_start=creative.start,
                expected_end=creative.end,
                expected_weight=creative.rotation_weight,
                dset_id=candidates[0].dtree_id,
                dset_name=candidates[0].dtree_name,
                candidates=len(candidates),
            ))
            continue

        node = candidates[0]
        out.flights.append(CreativeFlightCheck(
            placement_id=pid,
            creative_name=creative.name,
            status=MATCHED,
            intent=creative.intent,
            expected_start=creative.start,
            expected_end=creative.end,
            actual_start=_node_date(node.start_timestamp),
            actual_end=_node_date(node.end_timestamp),
            expected_weight=creative.rotation_weight,
            actual_weight=node.weight,
            dset_id=node.dtree_id,
            dset_name=node.dtree_name,
        ))

    for key, candidates in by_name.items():
        if key in seen:
            continue
        for node in candidates:
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

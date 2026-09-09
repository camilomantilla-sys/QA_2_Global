"""
Agrupado de hallazgos para la revision de QA2.

Un revisor que recibe 100 placements con el mismo "Placement Name
mismatch" esta tomando UNA decision, no cien. Marcarlas de a una solo
gasta su tiempo, y el tiempo gastado en clics es tiempo que no se
dedica a mirar los hallazgos que si son distintos entre si.
"""
from __future__ import annotations

from typing import Iterable


def group_review_findings(findings: Iterable) -> dict[tuple[str, str], list]:
    """
    Agrupa por (regla, mensaje) conservando el orden de aparicion.

    Mismo mensaje y misma regla = mismo motivo. No se agrupa por regla
    a secas: dos hallazgos de PLC-006 pueden decir cosas distintas, y
    aprobarlos juntos seria aprobar a ciegas el que no se leyo.
    """
    groups: dict[tuple[str, str], list] = {}
    for finding in findings:
        groups.setdefault((finding.rule_id, finding.message), []).append(finding)
    return groups


def bulk_groups(findings: Iterable) -> dict[str, list]:
    """
    Los grupos que vale la pena aprobar en bloque, etiquetados para el
    selector.

    Un grupo de uno se queda fuera a proposito: para una sola fila el
    lote no ahorra nada y el selector se llenaria de ruido, tapando
    los grupos donde si hay decenas de clics que ahorrar.
    """
    return {
        f"{rule} · {message} ({len(items)})": items
        for (rule, message), items in group_review_findings(findings).items()
        if len(items) > 1
    }

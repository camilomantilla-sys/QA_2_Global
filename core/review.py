"""
Agrupado de hallazgos para la revision de QA2.

Un revisor que recibe 100 placements con el mismo "Placement Name
mismatch" esta tomando UNA decision, no cien. Marcarlas de a una solo
gasta su tiempo, y el tiempo gastado en clics es tiempo que no se
dedica a mirar los hallazgos que si son distintos entre si.
"""
from __future__ import annotations

import re
from typing import Iterable


def _reason_key(finding) -> str:
    """
    El mensaje sin los nombres que cambian de una fila a otra.

    "Versatility_Get-you-a-bar... flights on other dates" y
    "Superiority_High-Standards... flights on other dates" son el mismo
    motivo dicho sobre dos creativos. Agrupando por el mensaje literal
    salian 95 grupos de uno y el lote no servia para nada; agrupando
    solo por regla se mezclarian motivos distintos de la misma regla,
    que es peor. Se quitan los identificadores y queda el motivo.
    """
    message = str(getattr(finding, "message", "") or "")
    for value in (
        getattr(finding, "creative_name", ""),
        getattr(finding, "placement_name", ""),
        getattr(finding, "creative_id", ""),
        getattr(finding, "placement_id", ""),
    ):
        text = str(value or "").strip()
        if len(text) > 3:
            message = message.replace(text, "")
    # Los nombres de archivo que no vienen en el hallazgo se reconocen
    # por su forma: tramos largos con guiones bajos o extension.
    message = re.sub(r"\S*_\S*\.(zip|jpg|png|gif|html|mp4)\b", "", message)
    message = re.sub(r"\b\d{6,}\b", "", message)
    return " ".join(message.split()).strip(" .:-")


def group_review_findings(findings: Iterable) -> dict[tuple[str, str], list]:
    """
    Agrupa por (regla + estado, motivo) conservando el orden.

    El motivo es el mensaje sin los nombres que cambian de fila a
    fila. Sin eso, cada "<creativo> flights on other dates" era su
    propio grupo y no habia nada que aprobar en bloque. El estado
    entra en la clave porque un FAIL y un REVIEW de la misma regla no
    se firman con el mismo criterio.
    """
    groups: dict[tuple[str, str], list] = {}
    for finding in findings:
        status = getattr(getattr(finding, "status", None), "value", "")
        key = (
            f"{finding.rule_id} [{status}]" if status else finding.rule_id,
            _reason_key(finding) or finding.message,
        )
        groups.setdefault(key, []).append(finding)
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

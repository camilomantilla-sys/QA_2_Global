"""
Orquestador principal del Rule Engine QA2.

Recibe:
  - MatchResult de Traffic Sheet vs Innovid.
  - TagsResult opcional.

Devuelve:
  - FindingsBuffer con todos los resultados QA2.
"""
from __future__ import annotations

from core.findings import FindingsBuffer
from core.tag_matching import match_tags

from rules import attribution
from rules import creatives
from rules import placements
from rules import tags
from rules import urls


def run_rules(
    match_result,
    tags_result=None,
) -> FindingsBuffer:
    """
    Ejecuta las reglas QA2 disponibles.

    El flujo base TS vs Innovid funciona sin archivo de tags.
    Si tags_result está disponible, también ejecuta TAG-001..TAG-011.
    """
    buffer = FindingsBuffer()

    placements.evaluate(match_result, buffer)
    creatives.evaluate(match_result, buffer)
    urls.evaluate(match_result, buffer)
    attribution.evaluate(match_result, buffer)

    if tags_result is not None:
        tag_match_result = match_tags(
            match_result,
            tags_result,
        )

        tags.evaluate(
            tag_match_result,
            buffer,
        )

    return buffer

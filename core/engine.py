"""
Orquestador principal del Rule Engine QA2.

Recibe:
  - MatchResult de Traffic Sheet vs Innovid.
  - TagsResult opcional.

Devuelve:
  - FindingsBuffer con todos los resultados QA2.
"""
from core.findings import FindingsBuffer
from core.tag_matching import match_tags
from rules import attribution
from rules import creatives
from rules import dset
from rules import dtree
from rules import naming
from rules import placements
from rules import tags
from rules import urls
from rules import adobe_pixels  # revisar la firma: recibe `reconciliation`, no `match_result`


def run_rules(match_result, tags_result=None, adobe_pixel_reconciliation=None) -> FindingsBuffer:
    buffer = FindingsBuffer()

    placements.evaluate(match_result, buffer)
    naming.evaluate(match_result, buffer)
    creatives.evaluate(match_result, buffer)
    urls.evaluate(match_result, buffer)
    attribution.evaluate(match_result, buffer)
    dtree.evaluate(match_result, buffer)
    dset.evaluate(match_result, buffer)

    if adobe_pixel_reconciliation is not None:
        adobe_pixels.evaluate(adobe_pixel_reconciliation, buffer)

    if tags_result is not None:
        tag_match_result = match_tags(match_result, tags_result)
        tags.evaluate(tag_match_result, buffer)

    return buffer
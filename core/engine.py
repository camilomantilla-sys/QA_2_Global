from core.findings import FindingsBuffer

from rules import placements
from rules import creatives
from rules import urls
from rules import attribution
from rules import naming


def run_rules(match_result):

    buffer = FindingsBuffer()

    placements.evaluate(match_result, buffer)
    creatives.evaluate(match_result, buffer)
    urls.evaluate(match_result, buffer)
    attribution.evaluate(match_result, buffer)
    naming.evaluate(match_result, buffer)

    return buffer
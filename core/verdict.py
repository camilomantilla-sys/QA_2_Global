from core.findings import Scorecard

def final_verdict(scorecard: Scorecard) -> str:

    if scorecard.blockers:
        return "BLOCKED"

    if scorecard.errors:
        return "FAILED"

    if scorecard.reviews:
        return "NEEDS_REVIEW"

    if scorecard.not_verified:
        return "NEEDS_REVIEW"

    return "PASSED"
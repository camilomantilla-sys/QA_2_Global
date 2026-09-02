from core.findings import Domain
from core.normalize import norm_compare
from parsers.ts_parser import REQ_CREATIVE_REMOVE

_NOT_RUNNING = ("stopped", "disabled", "inactive", "paused")


def _is_retired(pm) -> bool:
    """El placement ya no esta sirviendo, por TS o por Innovid."""
    if pm.expected.request_type == REQ_CREATIVE_REMOVE:
        return True
    status = pm.actual.status if pm.actual else ""
    return norm_compare(status) in _NOT_RUNNING


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        if not pm.actual:
            continue

        expected = (pm.expected.name or "").strip()
        actual = (pm.actual.name_norm or pm.actual.name or "").strip()

        if not expected:
            continue

        if expected == actual:

            buffer.pass_(
                rule_id="PLC-006",
                domain=Domain.IDENTITY,
                message="Placement Name is correct",
                placement_id=pm.placement_id,
            )

        elif _is_retired(pm):

            # El placement ya no corre: o la TS lo pide desasignar por
            # completo, o en Innovid quedo detenido. Como no esta
            # sirviendo, que su nombre no coincida no tiene ninguna
            # consecuencia y no vale la pena ocupar una revision.
            buffer.pass_(
                rule_id="PLC-006",
                domain=Domain.IDENTITY,
                message=(
                    "Placement Name differs, but the placement is no "
                    "longer running, so the naming has no effect."
                ),
                placement_id=pm.placement_id,
                expected=expected,
                actual=actual,
            )

        else:

            # Placement ID already matched at this point (this loop
            # only runs over matched placements), so trafficking is
            # correct. A name mismatch doesn't block implementation
            # -- it's a callout for the digital team to clean up the
            # naming later, not a failure.
            buffer.review(
                rule_id="PLC-006",
                domain=Domain.IDENTITY,
                message=(
                    "Placement Name mismatch (Placement ID matched; "
                    "this does not affect trafficking)."
                ),
                placement_id=pm.placement_id,
                expected=expected,
                actual=actual,
                recommended_action=(
                    "Flag to the digital team as a naming cleanup; "
                    "no re-trafficking required."
                ),
            )
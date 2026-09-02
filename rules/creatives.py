from core.colors import RED
from core.findings import Domain

ROTATION_SHEET = "Creative Rotations"


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        # Creative Rotations declares a pool of rotating variants
        # (Rotation % = EVEN/weighted). One variant not matching in
        # Innovid is normal when the group does a creative swap: it's
        # only a real problem if NONE of the group's variants are
        # running in Innovid.
        rotation_links = [
            cl for cl in pm.creative_links
            if cl.expected.ts_sheet == ROTATION_SHEET
        ]
        rotation_has_match = any(
            cl.actual is not None for cl in rotation_links
        )

        # Adobe Direct & Site-Served 1x1s: Innovid represents these
        # as Placement_Type=Pixel rows (row_type TRACKER), whose
        # "creative" is the account's generic 1x1.gif tracking pixel.
        # The real ad creative is served by the publisher directly
        # and was never going to show up in the export under the
        # TS's stated creative name -- an unmatched expected creative
        # here is the expected, correct state, not a missing creative.
        site_served_pixel = pm.actual is not None and any(
            ac.row_type == "TRACKER" for ac in pm.actual.creatives
        )

        for cl in pm.creative_links:

            # Un creativo en rojo es una REMOCION: la TS pide que quede
            # desasignado. Su ausencia del export no es un problema, es
            # la confirmacion de que se hizo. Las dos cuentas lo dejan
            # distinto y ambas son correctas: Adobe lo conserva en el
            # export con Status=Disabled, y BlackRock, cuando el
            # placement usa Decision Set, lo elimina y desaparece.
            # Lo que si es un fallo real es el caso contrario: que siga
            # ahi y corriendo.
            if cl.expected.intent == RED:

                if cl.actual is None or not cl.actual.running:
                    buffer.pass_(
                        rule_id="CRE-001",
                        domain=Domain.CREATIVE,
                        message=(
                            "Removal confirmed: the creative is no longer "
                            "running on this placement."
                        ),
                        placement_id=pm.placement_id,
                        creative_id=(
                            cl.actual.creative_id
                            if cl.actual
                            else cl.expected.creative_id
                        ),
                        creative_name=cl.expected.name,
                        expected=cl.expected.name,
                    )
                else:
                    buffer.fail(
                        rule_id="CRE-001",
                        domain=Domain.CREATIVE,
                        message=(
                            "The Traffic Sheet asks to remove this creative, "
                            "but it's still running in Innovid."
                        ),
                        placement_id=pm.placement_id,
                        creative_id=cl.actual.creative_id,
                        creative_name=cl.expected.name,
                        expected=cl.expected.name,
                        actual=cl.actual.state_label,
                        recommended_action=(
                            "Unassign the creative from the placement."
                        ),
                    )
                continue

            if cl.actual is None:

                if cl.expected.ts_sheet == ROTATION_SHEET and rotation_has_match:
                    buffer.review(
                        rule_id="CRE-001",
                        domain=Domain.CREATIVE,
                        message=(
                            "Creative Rotations variant with no individual match, "
                            "but the group has other active variants in "
                            "Innovid (possible rotation swap)."
                        ),
                        placement_id=pm.placement_id,
                        creative_id=cl.expected.creative_id,
                        creative_name=cl.expected.name,
                        expected=cl.expected.name,
                        recommended_action=(
                            "Confirm whether this variant was swapped "
                            "out of the rotation intentionally."
                        ),
                    )
                    continue

                if site_served_pixel:
                    buffer.pass_(
                        rule_id="CRE-001",
                        domain=Domain.CREATIVE,
                        message=(
                            "Site-served 1x1: Innovid runs the generic "
                            "1x1.gif tracking pixel here. The creative "
                            "is served by the publisher directly and "
                            "isn't expected to appear in the export."
                        ),
                        placement_id=pm.placement_id,
                        creative_id=cl.expected.creative_id,
                        creative_name=cl.expected.name,
                        expected=cl.expected.name,
                    )
                    continue

                buffer.fail(
                    rule_id="CRE-001",
                    domain=Domain.CREATIVE,
                    message="Creative missing in export",
                    placement_id=pm.placement_id,
                    creative_id=cl.expected.creative_id,
                    creative_name=cl.expected.name,
                    expected=cl.expected.name,
                )

            else:

                buffer.pass_(
                    rule_id="CRE-001",
                    domain=Domain.CREATIVE,
                    message="Creative found",
                    placement_id=pm.placement_id,
                    creative_id=cl.actual.creative_id,
                    creative_name=cl.actual.name,
                )

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

from core.colors import RED, WHITE
from core.findings import Domain, EntityType
from core.matching import is_site_served_1x1

ROTATION_SHEET = "Creative Rotations"


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        _evaluate_site_served_tracker(pm, buffer)

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

            # Los creativos en blanco son contexto del Decision Set: no
            # son parte de lo que se pidio cambiar, asi que se muestran
            # pero no se juzgan.
            if cl.expected.intent == WHITE:
                continue

            # Un creativo en rojo es una REMOCION: la TS pide que quede
            # desasignado. Su ausencia del export no es un problema, es
            # la confirmacion de que se hizo. Las dos cuentas lo dejan
            # distinto y ambas son correctas: Adobe lo conserva en el
            # export con Status=Disabled, y BlackRock, cuando el
            # placement usa Decision Set, lo elimina y desaparece.
            # Lo que si es un fallo real es el caso contrario: que siga
            # ahi y corriendo.
            if cl.expected.intent == RED:

                # Si el placement quedo detenido, lo que tenga asignado
                # ya no corre: la remocion esta cumplida aunque el
                # creativo siga figurando como activo en el export.
                placement_running = pm.actual is None or pm.actual.running

                if (cl.actual is None or not cl.actual.running
                        or not placement_running):
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


def _evaluate_site_served_tracker(pm, buffer) -> None:
    """
    CRE-002 -- el 1x1 de un placement site-served.

    En Adobe, un 1x1 lo sirve el publisher: el creativo de verdad
    nunca pasa por Innovid, asi que la Traffic Sheet escribe "N/A" en
    Creative Names. Eso no es un dato que falte, es que no aplica.

    Pero "N/A" no genera ningun creativo esperado, y sin creativo
    esperado el placement se quedaba sin una sola comprobacion: la
    seccion de creativos salia vacia, nadie confirmaba que el pixel
    estuviera asignado, y el reporte cerraba limpio. Camilo: "en
    adobe los 1x1 en la ts aparecen como N/A porque en innovid se
    asigna un 1x1.gif. No me esta leyendo eso la app".

    Lo que si se puede comprobar es lo unico que Innovid tiene: que el
    pixel este ahi. Es el mismo 1x1.gif para toda la cuenta --
    comparar su nombre no dice nada-- pero que este asignado o no, si.
    """
    expected = pm.expected

    if not is_site_served_1x1(expected):
        return

    # Si la TS SI declaro un creativo, lo juzga el resto de la regla.
    # El default ad no cuenta: se engancha por dimension, no lo pide
    # el placement.
    if [c for c in expected.creatives if not c.is_default]:
        return

    common = dict(
        rule_id="CRE-002",
        domain=Domain.CREATIVE,
        entity_type=EntityType.PLACEMENT,
        placement_id=pm.placement_id,
        placement_name=expected.name,
        expected="A 1x1 tracker assigned in Innovid",
        reason=(
            "Site-served 1x1: the publisher serves the creative, so "
            "the Traffic Sheet declares N/A and there is no creative "
            "name to compare on either side."
        ),
    )

    trackers = getattr(pm, "actual_trackers", None) or []

    if trackers:
        buffer.pass_(
            message="1x1 tracker assigned",
            actual=", ".join(
                t.filename or t.name or t.creative_id for t in trackers
            ),
            **common,
        )
        return

    if pm.actual is None:
        buffer.not_verified(
            message=(
                "The placement did not come back in the export, so "
                "the 1x1 tracker could not be checked."
            ),
            recommended_action=(
                "Re-export the Placement-Creative View including this "
                "placement."
            ),
            **common,
        )
        return

    buffer.fail(
        message="No 1x1 tracker is assigned to this placement",
        actual=(
            f"{len(pm.actual.creatives)} creative row(s), none of them "
            "a tracking pixel"
            if pm.actual.creatives else "no creatives assigned"
        ),
        recommended_action=(
            "Assign the account 1x1 tracking pixel to this placement "
            "in Innovid."
        ),
        **common,
    )

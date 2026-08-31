from core.findings import Domain

ROTATION_SHEET = "Creative Rotations"


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        # Creative Rotations declara un pool de variantes en rotacion
        # (Rotation % = EVEN/weighted). Que una variante puntual no
        # tenga match en Innovid es normal cuando el grupo hace swap
        # de creativos: solo es un problema real si NINGUNA variante
        # del grupo esta corriendo en Innovid.
        rotation_links = [
            cl for cl in pm.creative_links
            if cl.expected.ts_sheet == ROTATION_SHEET
        ]
        rotation_has_match = any(
            cl.actual is not None for cl in rotation_links
        )

        for cl in pm.creative_links:

            if cl.actual is None:

                if cl.expected.ts_sheet == ROTATION_SHEET and rotation_has_match:
                    buffer.review(
                        rule_id="CRE-001",
                        domain=Domain.CREATIVE,
                        message=(
                            "Variante de Creative Rotations sin match individual, "
                            "pero el grupo tiene otras variantes activas en "
                            "Innovid (posible swap de rotacion)."
                        ),
                        placement_id=pm.placement_id,
                        creative_id=cl.expected.creative_id,
                        creative_name=cl.expected.name,
                        expected=cl.expected.name,
                        recommended_action=(
                            "Confirmar si esta variante fue swapeada "
                            "intencionalmente en la rotacion."
                        ),
                    )
                    continue

                buffer.fail(
                    rule_id="CRE-001",
                    domain=Domain.CREATIVE,
                    message="Creative faltante en export",
                    placement_id=pm.placement_id,
                    creative_id=cl.expected.creative_id,
                    creative_name=cl.expected.name,
                    expected=cl.expected.name,
                )

            else:

                buffer.pass_(
                    rule_id="CRE-001",
                    domain=Domain.CREATIVE,
                    message="Creative encontrado",
                    placement_id=pm.placement_id,
                    creative_id=cl.actual.creative_id,
                    creative_name=cl.actual.name,
                )
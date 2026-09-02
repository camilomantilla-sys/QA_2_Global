from core.findings import Domain
from core.urls import TRI_INCOMPLETE


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        for cl in pm.creative_links:

            if cl.triangle is None:
                continue

            if cl.triangle.is_ok:

                buffer.pass_(
                    rule_id="ATR-001",
                    domain=Domain.ATTRIBUTION,
                    message="Attribution is correct",
                    placement_id=pm.placement_id,
                )

            elif cl.triangle.result == TRI_INCOMPLETE:

                # Falta al menos un vertice del triangulo, casi siempre
                # porque la cuenta no maneja CGEN o porque no se cargo el
                # Placement View. No hay nada que revisar: hay algo que
                # no se pudo revisar, que no es lo mismo.
                buffer.not_verified(
                    rule_id="ATR-001",
                    domain=Domain.ATTRIBUTION,
                    message=cl.triangle.note,
                    placement_id=pm.placement_id,
                    reason=(
                        "Missing: " + ", ".join(cl.triangle.missing)
                        if cl.triangle.missing
                        else ""
                    ),
                    recommended_action=(
                        "Confirm whether this account declares a CGEN, "
                        "and upload the Placement View if it applies."
                    ),
                )

            else:

                # Los vertices existen y no coinciden: la medicion queda
                # apuntando al lado equivocado.
                buffer.fail(
                    rule_id="ATR-001",
                    domain=Domain.ATTRIBUTION,
                    message=cl.triangle.note,
                    placement_id=pm.placement_id,
                    expected=cl.triangle.consensus or cl.triangle.ts,
                    actual=cl.triangle.export,
                    recommended_action=(
                        "Align the CGEN in the Traffic Sheet, the "
                        "Third Party ID in Innovid and the sdid in the URL."
                    ),
                )

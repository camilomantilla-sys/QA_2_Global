from core.findings import Domain
from core.urls import TRI_INCOMPLETE


def _declares_cgen(match_result) -> bool:
    """
    ¿Esta cuenta maneja CGEN?

    El triangulo de atribucion se apoya en el CGEN que declara la TS.
    BlackRock, Unilever y Wendy's no lo manejan: no tienen ni la columna.
    Sin esto, cada placement de esas cuentas emitia un NOT_VERIFIED
    pidiendo un dato que nunca va a existir, y el veredicto se quedaba
    en NEEDS_REVIEW aunque todo lo demas estuviera perfecto.
    """
    for pm in match_result.matched:
        if str(pm.expected.cgen or "").strip():
            return True
        for creative in pm.expected.creatives:
            if str(creative.cgen or "").strip():
                return True
    return False


def evaluate(match_result, buffer):

    if not _declares_cgen(match_result):
        if match_result.matched:
            buffer.info(
                rule_id="ATR-001",
                domain=Domain.ATTRIBUTION,
                message=(
                    "Attribution isn't checked: this Traffic Sheet "
                    "declares no CGEN, so the account doesn't use the "
                    "attribution triangle."
                ),
            )
        return

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

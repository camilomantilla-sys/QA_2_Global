from core.findings import Domain
from core.urls import TRI_INCOMPLETE, account_uses_cgen


def _cgen_values(match_result) -> int:
    """Cuantos CGEN con valor trae la TS."""
    found = 0
    for pm in match_result.matched:
        if str(pm.expected.cgen or "").strip():
            found += 1
        for creative in pm.expected.creatives:
            if str(creative.cgen or "").strip():
                found += 1
    return found


def evaluate(match_result, buffer, account: str = ""):
    """
    El triangulo de atribucion se apoya en el CGEN que declara la TS,
    y solo Adobe lo maneja. Quien elige la cuenta en la app manda: si
    dice Unilever, no hay atribucion que revisar aunque la hoja traiga
    un CGEN suelto. Sin cuenta elegida decide la hoja, como antes.
    """
    if not match_result.matched:
        return

    declared = account_uses_cgen(account)
    found = _cgen_values(match_result)

    if declared is False:
        # La cuenta elegida no maneja CGEN. Saltamos, pero si la hoja
        # traia CGEN igual lo decimos: o la cuenta esta mal elegida, o
        # alguien puso un dato que nadie va a revisar. Callarlo seria
        # esconder justo el caso que hay que mirar.
        buffer.info(
            rule_id="ATR-001",
            domain=Domain.ATTRIBUTION,
            message=(
                f"Attribution isn't checked: {account} doesn't use the "
                "attribution triangle."
                + (
                    f" Note: the Traffic Sheet still declares {found} "
                    "CGEN value(s). Check the account is the right one."
                    if found else ""
                )
            ),
        )
        return

    if declared is None and not found:
        buffer.info(
            rule_id="ATR-001",
            domain=Domain.ATTRIBUTION,
            message=(
                "Attribution isn't checked: this Traffic Sheet "
                "declares no CGEN, so the account doesn't use the "
                "attribution triangle."
                + (
                    ""
                    if account
                    else " Pick the Account / Campaign to say so outright."
                )
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
                        "Pick the Account / Campaign in the sidebar if "
                        "this account doesn't use CGEN, and upload the "
                        "Placement View if it applies."
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

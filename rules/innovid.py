"""
Hallazgos de lo que solo Innovid sabe.

Tres cosas que ningun export trae y que hasta ahora se revisaban
abriendo la interfaz a mano:

  INV-001  fechas de vuelo del creativo dentro del decision set
  INV-002  peso de rotacion del creativo
  INV-003  Verification Partner configurado en el placement

Los creativos WHITE entran a la comparacion como contexto pero no
generan hallazgos, igual que en el resto de QA2.
"""
from core.findings import Domain, EntityType
from core.innovid_reconciliation import (
    AMBIGUOUS,
    EXTRA_IN_INNOVID,
    MATCHED,
    MISSING_IN_INNOVID,
)
from core.normalize import norm_compare

WHITE = "WHITE"


def evaluate(reconciliation, buffer):
    _flight_dates(reconciliation, buffer)
    _rotation_weights(reconciliation, buffer)
    _verification_partner(reconciliation, buffer)
    _unchecked(reconciliation, buffer)


def _flight_dates(reconciliation, buffer):
    for check in reconciliation.flights:
        # Contexto, no parte de lo solicitado.
        if check.intent == WHITE:
            continue

        common = dict(
            rule_id="INV-001",
            domain=Domain.DATES,
            entity_type=EntityType.CREATIVE,
            placement_id=check.placement_id,
            reason=f"Innovid decision set · {check.creative_name}",
        )

        if check.status == MISSING_IN_INNOVID:
            buffer.fail(
                message=(
                    f"{check.creative_name} is in the Traffic Sheet but "
                    "not in the decision set"
                ),
                expected=check.creative_name,
                actual="(not in Innovid)",
                recommended_action=(
                    "Add the creative to the decision set, or confirm "
                    "it was dropped from the request."
                ),
                **common,
            )
            continue

        if check.status == EXTRA_IN_INNOVID:
            buffer.review(
                message=(
                    f"{check.creative_name} is in the decision set but "
                    "not in the Traffic Sheet"
                ),
                expected="(not in the Traffic Sheet)",
                actual=check.creative_name,
                recommended_action=(
                    "Confirm whether this creative belongs to an "
                    "earlier request or should be removed."
                ),
                **common,
            )
            continue

        if check.status == AMBIGUOUS:
            # Elegir uno daria un veredicto sin fundamento: si se
            # eligiera el equivocado, un error real pasaria como
            # correcto.
            buffer.not_verified(
                message=(
                    f"{check.creative_name} appears {check.candidates} "
                    "times in the same decision set, so its dates "
                    "could not be checked"
                ),
                recommended_action=(
                    "Check in Innovid which of the duplicates should "
                    "be running."
                ),
                **common,
            )
            continue

        # MATCHED: comparar solo lo que ambos lados declaran.
        if check.expected_start is None and check.expected_end is None:
            buffer.not_verified(
                message=(
                    f"{check.creative_name} has no flight dates in the "
                    "Traffic Sheet, so there is nothing to compare"
                ),
                actual=_span(check.actual_start, check.actual_end),
                **common,
            )
            continue

        start_off = _differs(check.expected_start, check.actual_start)
        end_off = _differs(check.expected_end, check.actual_end)

        if start_off or end_off:
            buffer.fail(
                message=f"{check.creative_name} flights on other dates",
                expected=_span(check.expected_start, check.expected_end),
                actual=_span(check.actual_start, check.actual_end),
                recommended_action=(
                    "Correct the creative's dates in the decision set."
                ),
                **common,
            )
        else:
            buffer.pass_(
                message=f"{check.creative_name} flights as requested",
                expected=_span(check.expected_start, check.expected_end),
                actual=_span(check.actual_start, check.actual_end),
                **common,
            )


def _rotation_weights(reconciliation, buffer):
    for check in reconciliation.flights:
        if check.intent == WHITE or check.status != MATCHED:
            continue

        expected = norm_compare(check.expected_weight)
        actual = norm_compare(check.actual_weight)

        # Sin peso declarado no hay nada que validar. "Even" en la TS
        # es una instruccion de reparto, no un numero comparable con
        # el peso por nodo que devuelve Innovid.
        if not expected or expected in ("even", "n/a", "na"):
            continue

        common = dict(
            rule_id="INV-002",
            domain=Domain.ROTATION,
            entity_type=EntityType.CREATIVE,
            placement_id=check.placement_id,
            reason=f"Innovid decision set · {check.creative_name}",
            expected=check.expected_weight,
            actual=check.actual_weight or "(not set)",
        )

        if not actual:
            buffer.not_verified(
                message=(
                    f"{check.creative_name} has no rotation weight in "
                    "Innovid to compare"
                ),
                **common,
            )
        elif _same_weight(expected, actual):
            buffer.pass_(
                message=f"{check.creative_name} rotates as requested",
                **common,
            )
        else:
            buffer.fail(
                message=f"{check.creative_name} rotates at another weight",
                recommended_action=(
                    "Correct the rotation weight in the decision set."
                ),
                **common,
            )


def _verification_partner(reconciliation, buffer):
    for check in reconciliation.partners:
        common = dict(
            rule_id="INV-003",
            domain=Domain.ATTRIBUTION,
            entity_type=EntityType.PLACEMENT,
            placement_id=check.placement_id,
            reason="Innovid placement",
        )

        if check.configured:
            buffer.pass_(
                message=(
                    f"Verification Partner is set to "
                    f"{check.actual_partner}"
                    + (f" ({check.actual_status})" if check.actual_status else "")
                ),
                actual=check.actual_partner,
                **common,
            )
        else:
            # No se afirma que este mal: muchas campanas no lo llevan.
            # Lo que se afirma es que no esta puesto, que es un hecho.
            buffer.review(
                message="No Verification Partner is set on this placement",
                actual="(not set)",
                recommended_action=(
                    "Confirm whether this campaign is meant to have "
                    "one."
                ),
                **common,
            )


def _unchecked(reconciliation, buffer):
    for placement_id, why in reconciliation.unchecked:
        buffer.not_verified(
            rule_id="INV-001",
            domain=Domain.DATES,
            entity_type=EntityType.PLACEMENT,
            placement_id=placement_id,
            message=f"Creative dates were not checked: {why}",
            reason="Innovid decision set",
            recommended_action=(
                "Review this placement's creative dates in Innovid by "
                "hand."
            ),
        )


def _differs(expected, actual) -> bool:
    """Solo hay diferencia cuando ambos lados declaran una fecha."""
    return bool(expected and actual and expected != actual)


def _span(start, end) -> str:
    if not start and not end:
        return "(no dates)"
    return f"{start or '?'} → {end or 'ongoing'}"


def _same_weight(expected: str, actual: str) -> bool:
    """
    '1x' en Innovid y '1' en la TS son el mismo peso, igual que
    '50%' y '50'.
    """
    def _number(text: str) -> str:
        t = text.replace("x", "").replace("%", "").strip()
        # Solo se recortan los ceros DESPUES del punto: "1.00" es "1",
        # pero "50" no es "5". Recortarlos siempre hacia que un peso
        # del 50% se leyera igual que uno del 5%.
        if "." in t:
            t = t.rstrip("0").rstrip(".")
        return t

    return _number(expected) == _number(actual)

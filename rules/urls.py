from core.findings import Domain
from core.urls import (
    URL_BASE_DIFF,
    URL_BOTH_MISSING,
    URL_MALFORMED,
    URL_MATCH,
    URL_MISSING_ACTUAL,
    URL_MISSING_EXPECTED,
    URL_PARAMS_DIFF,
)


ROTATION_SHEET = "Creative Rotations"


def evaluate(match_result, buffer):

    for pm in match_result.matched:

        # Mismo criterio que CRE-001: una variante de Creative Rotations
        # sin Clicktag en Innovid puede ser un swap normal si el grupo
        # tiene otras variantes activas.
        rotation_links = [
            cl for cl in pm.creative_links
            if cl.expected.ts_sheet == ROTATION_SHEET
        ]
        rotation_has_match = any(
            cl.actual is not None for cl in rotation_links
        )

        for cl in pm.creative_links:

            if cl.url is None:
                continue

            result = cl.url.result

            common = {
                "rule_id": "URL-001",
                "domain": Domain.URL,
                "placement_id": pm.placement_id,
                "placement_name": pm.expected.name,
                "creative_id": (
                    cl.actual.creative_id
                    if cl.actual is not None
                    else cl.expected.creative_id
                ),
                "creative_name": cl.expected.name,
                "expected": cl.url.expected.raw,
                "actual": cl.url.actual.raw,
            }

            if result == URL_MATCH:
                buffer.pass_(
                    message="URL de Traffic Sheet e Innovid coinciden.",
                    **common,
                )

            elif result == URL_MISSING_ACTUAL:
                if cl.expected.ts_sheet == ROTATION_SHEET and rotation_has_match:
                    buffer.review(
                        message=(
                            "TS declara URL para esta variante de rotacion, "
                            "pero el creativo no esta corriendo en Innovid "
                            "(posible swap de rotacion)."
                        ),
                        reason=cl.url.note,
                        recommended_action=(
                            "Confirmar si esta variante fue swapeada "
                            "intencionalmente en la rotacion."
                        ),
                        **common,
                    )
                else:
                    buffer.fail(
                        message="TS declara URL, pero Innovid no tiene Clicktag.",
                        reason=cl.url.note,
                        recommended_action=(
                            "Configurar el Clicktag solicitado y volver a exportar."
                        ),
                        **common,
                    )

            elif result == URL_MISSING_EXPECTED:
                buffer.not_verified(
                    message=(
                        "Innovid contiene URL, pero TS no declara "
                        "una URL verificable para esta entidad."
                    ),
                    reason=cl.url.note,
                    recommended_action=(
                        "Confirmar la fuente de URL aplicable para este "
                        "perfil y tipo de solicitud."
                    ),
                    **common,
                )

            elif result == URL_BOTH_MISSING:
                buffer.not_verified(
                    message="No existe URL declarada en TS ni en Innovid.",
                    reason=cl.url.note,
                    recommended_action=(
                        "Confirmar si la URL aplica a esta implementación."
                    ),
                    **common,
                )

            elif result in (URL_BASE_DIFF, URL_PARAMS_DIFF):
                buffer.fail(
                    message="La URL configurada en Innovid no coincide con la TS.",
                    reason=cl.url.note,
                    recommended_action=(
                        "Corregir destino o parámetros del Clicktag en Innovid."
                    ),
                    **common,
                )

            elif result == URL_MALFORMED:
                buffer.review(
                    message="No fue posible interpretar correctamente la URL.",
                    reason=cl.url.note,
                    recommended_action=(
                        "Revisar manualmente la URL y corregir su formato."
                    ),
                    **common,
                )

            else:
                buffer.review(
                    message=f"Resultado URL no clasificado: {result}.",
                    reason=cl.url.note,
                    **common,
                )

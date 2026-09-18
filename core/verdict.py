"""
El veredicto, y por que hay dos.

Un pixel que llega dos dias despues de que se enviaron los tags no
significa que el trafficking este mal. Camilo: "yo implemento bien
para adobe, pasa el QA y se puede demorar 2 dias en recibir pixels
pero ya envie tags, entonces es diferente la implementacion a los
tags".

Metidos en un solo veredicto, un vendor que todavia no ha mandado su
pixel tiñe de rojo un reporte donde los placements, los creativos, las
fechas y las URLs estan perfectos -- y quien lo recibe no sabe si
tiene que rehacer la implementacion o solo esperar un correo.

Asi que se cuentan por separado:

  * IMPLEMENTACION -- lo que se traficó: placements, creativos,
    fechas, dimensiones, rotacion, URLs, atribucion. Es lo que AdOps
    hizo y lo que AdOps puede arreglar.

  * TAGS Y PIXELES -- lo que se entrega y lo que ponen terceros. Un
    fallo aqui casi nunca se arregla volviendo a Innovid.

El veredicto general sigue siendo el peor de los dos: con los tags mal
el QA no esta aprobado. Lo que cambia es que ahora el reporte dice
CUAL de los dos es el que falla, en vez de dejarlo por averiguar.
"""
from core.findings import Domain, Scorecard

#: Lo que se entrega y lo que ponen terceros.
TAG_DOMAINS = frozenset({Domain.PIXEL.value, Domain.TAG.value})

IMPLEMENTATION = "implementation"
TAGS = "tags"

SCOPE_LABELS = {
    IMPLEMENTATION: "Implementation",
    TAGS: "Tags & pixels",
}

#: Como se escribe cada veredicto donde alguien lo lee. Vive aqui y no
#: en la interfaz porque el Excel y el PDF lo escriben igual, y tres
#: copias de la misma tabla es como terminan diciendo cosas distintas.
VERDICT_LABELS = {
    "PASSED": "PASSED",
    "FAILED": "REQUIRES CORRECTION",
    "BLOCKED": "BLOCKED",
    "NEEDS_REVIEW": "REVIEW REQUIRED",
    "NO_CHECKS": "NO CHECKS RUN",
}

#: De peor a mejor. NO_CHECKS no compite: significa que ahi no habia
#: nada que mirar, no que saliera bien.
_ORDER = ("BLOCKED", "FAILED", "NEEDS_REVIEW", "PASSED", "NO_CHECKS")


def final_verdict(scorecard: Scorecard) -> str:

    if scorecard.blockers:
        return "BLOCKED"

    if scorecard.errors:
        return "FAILED"

    if scorecard.reviews:
        return "NEEDS_REVIEW"

    if scorecard.not_verified:
        return "NEEDS_REVIEW"

    return "PASSED"


def scope_of(finding) -> str:
    """A cual de los dos pertenece un hallazgo."""
    domain = getattr(finding.domain, "value", finding.domain)
    return TAGS if domain in TAG_DOMAINS else IMPLEMENTATION


def split_findings(findings) -> dict[str, list]:
    """Los hallazgos repartidos en los dos alcances."""
    out: dict[str, list] = {IMPLEMENTATION: [], TAGS: []}
    for finding in findings:
        out[scope_of(finding)].append(finding)
    return out


def scorecards_by_scope(findings) -> dict[str, Scorecard]:
    """Un Scorecard por alcance. El que no tiene hallazgos, tampoco."""
    return {
        scope: Scorecard.from_findings(group)
        for scope, group in split_findings(findings).items()
        if group
    }


def verdicts_by_scope(findings) -> dict[str, str]:
    return {
        scope: card.verdict
        for scope, card in scorecards_by_scope(findings).items()
    }


def _worse(left: str, right: str) -> str:
    return min(left, right, key=lambda v: _ORDER.index(v)
               if v in _ORDER else len(_ORDER))


def headline(findings) -> str:
    """
    Una frase que diga cual de los dos hay que mirar.

    Es lo que alguien lee primero y muchas veces lo unico que lee, asi
    que dice que hacer, no cuantos hallazgos hubo.
    """
    verdicts = verdicts_by_scope(findings)
    implementation = verdicts.get(IMPLEMENTATION)
    tags = verdicts.get(TAGS)

    if implementation == "BLOCKED":
        return "The files could not be read, so nothing was checked."

    # Sin tags en la solicitud no hay nada que separar.
    if tags is None:
        return ""

    if implementation is None:
        return _tags_only(tags)

    ok = ("PASSED", "NO_CHECKS")

    if implementation in ok and tags in ok:
        return ""

    if implementation in ok:
        return (
            "The implementation is fine. "
            + _look_at_the_tags(tags)
        )

    if tags in ok:
        return (
            "The tags and pixels are fine -- what needs work is the "
            "implementation."
        )

    return (
        "Both sides need a look: the implementation and the tags and "
        "pixels."
    )


def _look_at_the_tags(tags: str) -> str:
    if tags == "FAILED":
        return "Take a look at the tags and pixels."
    return "Take a look at the tags and pixels before signing off."


def _tags_only(tags: str) -> str:
    if tags in ("PASSED", "NO_CHECKS"):
        return ""
    return "Only the tags and pixels need a look."


def overall(findings) -> str:
    """El peor de los dos, que es el veredicto de la solicitud."""
    verdicts = [v for v in verdicts_by_scope(findings).values()]
    if not verdicts:
        return "NO_CHECKS"
    result = verdicts[0]
    for verdict in verdicts[1:]:
        result = _worse(result, verdict)
    return result

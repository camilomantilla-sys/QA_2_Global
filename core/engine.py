"""
Orquestador principal del Rule Engine QA2.

Recibe:
  - MatchResult de Traffic Sheet vs Innovid.
  - TagsResult opcional.

Devuelve:
  - FindingsBuffer con todos los resultados QA2.
"""
from core.findings import Capability, Domain, FindingsBuffer
from core.tag_matching import match_tags
from rules import attribution
from rules import creatives
from rules import dset
from rules import dtree
from rules import naming
from rules import placements
from rules import rotation
from rules import tags
from rules import urls
from rules import adobe_pixels  # revisar la firma: recibe `reconciliation`, no `match_result`
from rules import adobe_tag_policy  # idem: recibe `reconciliation`
from rules import pixels  # idem: recibe `reconciliation`
from rules import dv_omni  # idem: recibe `reconciliation`
from rules import defaults  # idem: recibe `reconciliation`
from rules import innovid  # idem: recibe `reconciliation`


def _fatal_extraction(ts_result) -> list:
    """
    Las anomalias FATAL de la lectura, de la hoja y de sus pestanas.

    Cada pestana guarda las suyas aparte de las del documento, asi
    que mirar solo `anomalies` de arriba deja fuera justo las que
    dicen que una pestana no se pudo leer.
    """
    if ts_result is None:
        return []

    seen: list = []
    sources = [ts_result]
    for name in ("placements", "rotations", "landing_pages"):
        sheet = getattr(ts_result, name, None)
        if sheet is not None:
            sources.append(sheet)

    for source in sources:
        for anomaly in getattr(source, "anomalies", []):
            if getattr(anomaly, "severity", "") != "FATAL":
                continue
            key = (anomaly.code, anomaly.message)
            if key not in {(a.code, a.message) for a in seen}:
                seen.append(anomaly)
    return seen


def run_rules(
    match_result,
    tags_result=None,
    adobe_pixel_reconciliation=None,
    adobe_tag_policy_reconciliation=None,
    pixel_reconciliation=None,
    dv_omni_reconciliation=None,
    default_ad_reconciliation=None,
    innovid_reconciliation=None,
    account: str = "",
    ts_result=None,
) -> FindingsBuffer:
    buffer = FindingsBuffer()

    # Una lectura que fallo no puede terminar en PASSED.
    #
    # Llego una TS de BlackRock con el encabezado de B1 borrado en
    # "Creative Rotations". El parser lo marco FATAL, leyo cero de
    # sus 384 rotaciones, y el motor -- que no miraba las anomalias
    # de extraccion -- dio PASSED sobre 144 comprobaciones que nunca
    # tocaron un creativo. Verde sobre algo que nadie leyo es el peor
    # resultado posible: la app bloquea antes de llegar aqui, pero
    # esa defensa es de la interfaz y esto lo usan tambien el CLI y
    # los scripts.
    for anomaly in _fatal_extraction(ts_result):
        buffer.blocker(
            "EXT-000",
            Domain.INGESTION,
            "The Traffic Sheet could not be read: "
            + anomaly.message,
        )

    # El peso de rotacion no esta en ningun archivo. Cuando el
    # placement corre por Decision Tree, la columna Rotation del
    # export dice "Decision Tree" y el porcentaje se queda dentro
    # del decision set. Declararlo aqui es lo que hace que una
    # rotacion que nadie pudo comparar salga NOT_VERIFIED en vez
    # de PASS.
    buffer.capabilities.declare(
        Capability.ROTATION_WEIGHT,
        innovid_reconciliation is not None,
        "the rotation weight lives in the Innovid decision set, "
        "not in any export -- connect Innovid to read it",
    )

    placements.evaluate(match_result, buffer)
    naming.evaluate(match_result, buffer)
    creatives.evaluate(match_result, buffer)
    rotation.evaluate(match_result, buffer)
    urls.evaluate(match_result, buffer)
    # La cuenta manda sobre si hay atribucion que revisar: solo
    # Adobe maneja CGEN.
    attribution.evaluate(match_result, buffer, account=account)
    dtree.evaluate(match_result, buffer)
    dset.evaluate(match_result, buffer)

    if adobe_pixel_reconciliation is not None:
        adobe_pixels.evaluate(adobe_pixel_reconciliation, buffer)

    if adobe_tag_policy_reconciliation is not None:
        adobe_tag_policy.evaluate(adobe_tag_policy_reconciliation, buffer)

    if pixel_reconciliation is not None:
        pixels.evaluate(pixel_reconciliation, buffer)

    if dv_omni_reconciliation is not None:
        dv_omni.evaluate(dv_omni_reconciliation, buffer)

    if default_ad_reconciliation is not None:
        defaults.evaluate(default_ad_reconciliation, buffer)

    # Opcional a proposito: Innovid es un servicio externo que tiene
    # dias malos, y un QA que se cae entero porque una API no respondio
    # no sirve. Sin reconciliacion, el resto del QA corre igual y estos
    # chequeos simplemente no se hacen.
    if innovid_reconciliation is not None:
        innovid.evaluate(innovid_reconciliation, buffer)

    if tags_result is not None:
        tag_match_result = match_tags(match_result, tags_result)
        tags.evaluate(tag_match_result, buffer)

    return buffer
"""
El rastro del QA1 dentro del session bundle (FB-18, FB-21).

Quien implementa corre QA, guarda el bundle y se lo pasa a quien hace
el QA2. Antes el bundle llevaba los archivos y el nombre de quien
implemento, pero no lo que el QA1 vio al correrlo, y al abrirlo nada
decia en pantalla "esto lo hizo otra persona". Aqui se arma ese rastro
y la frase que lo cuenta, igual en la app, el PDF y el Excel.
"""
from __future__ import annotations

from core.verdict import VERDICT_LABELS


def result_snapshot(verdict: str, errors: int, reviews: int,
                    not_verified: int, at: str) -> dict:
    """Lo que dio la ultima corrida, para guardarlo en el bundle."""
    return {
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS.get(verdict, verdict),
        "failed": int(errors),
        "review": int(reviews),
        "not_verified": int(not_verified),
        "at": at,
    }


def describe_result(result: dict | None) -> str:
    """'REQUIRES CORRECTION (2 failed, 3 to review)'. Vacio si no hay."""
    if not result or not result.get("verdict_label"):
        return ""
    parts = []
    for key, word in (("failed", "failed"), ("review", "to review"),
                      ("not_verified", "not verified")):
        if result.get(key):
            parts.append(f"{result[key]} {word}")
    detail = f" ({', '.join(parts)})" if parts else ""
    return f"{result['verdict_label']}{detail}"


def describe_origin(manifest: dict) -> str:
    """
    Una frase sobre quien hizo el QA1, para mostrarla al abrir el bundle.

    Solo con lo que el bundle trae: un campo vacio no se inventa.
    """
    who = (manifest.get("implemented_by") or "").strip()
    when = (manifest.get("implementation_date") or "").strip()
    saved = (manifest.get("saved_at") or "").replace("T", " ")[:16]
    wrike = (manifest.get("wrike_id") or "").strip()
    result = describe_result(manifest.get("qa1_result"))

    head = "Implemented (QA1)"
    head += f" by {who}" if who else " by someone not named in the bundle"
    if when:
        head += f" on {when}"
    pieces = [head]
    if wrike:
        pieces.append(f"Wrike {wrike}")
    if saved:
        pieces.append(f"bundle saved {saved}")
    if result:
        pieces.append(f"QA1 result when saved: {result}")
    return " · ".join(pieces) + "."

"""
La hoja QA del entregable: una fila por creativo, TS contra Innovid.

El formato viejo era vertical -- un hallazgo por fila, con el
contexto repartido en varias pestanas -- y para revisar un placement
habia que ir juntando piezas. Este pone los dos lados en columnas
pareadas, que es como se revisa de verdad: se lee una fila y se ve
si lo que se pidio es lo que quedo.

El orden de las columnas es el que definio el equipo. Las de rotacion
y las de fechas de creativo se anadieron despues, porque una rotacion
que no coincide falla el QA entero y las fechas del creativo pueden
diferir de las del placement -- dejarlas fuera del entregable habria
sacado del archivo justo lo que hay que mirar.
"""
from __future__ import annotations

import re

from core.matching import norm_creative
from core.normalize import norm_compare, normalize_weights

# Las columnas, en orden. Cada par (TS, Innovid) se pinta de verde
# cuando los dos lados coinciden.
COLUMNS = [
    "Status",
    "TS Placement ID", "Innovid Placement ID",
    "TS Placement Name", "Innovid Placement Name",
    "TS Start Date", "Innovid Start Date",
    "TS End Date", "Innovid End Date",
    "TS Dset / Dtree", "Innovid Dset / Dtree",
    "TS Dimensions", "Innovid Dimensions",
    "TS Creative ID", "Innovid Creative ID",
    "TS Creative Name", "Innovid Creative Name",
    "TS Creative Dates", "Innovid Creative Dates",
    "TS Rotation", "Innovid Rotation",
    "TS URL", "Innovid URL",
    "Verification Partner",
    # El CGEN va al final: solo Adobe lo maneja, y en las demas
    # cuentas son dos columnas vacias que estorban en medio de lo que
    # si se revisa siempre.
    "CGEN TS (Adobe)", "CGEN Innovid (Adobe)",
    "Notes",
]

# Los pares que se comparan para pintar en verde. Se nombran a mano y
# no por prefijo: "TS URL"/"Innovid URL" y "CGEN TS"/"CGEN Innovid" no
# siguen la misma forma, y adivinarlos por el nombre dejaria pares
# fuera sin que nada lo dijera.
PAIRS = [
    ("TS Placement ID", "Innovid Placement ID"),
    ("TS Placement Name", "Innovid Placement Name"),
    ("TS Start Date", "Innovid Start Date"),
    ("TS End Date", "Innovid End Date"),
    ("TS Dset / Dtree", "Innovid Dset / Dtree"),
    ("TS Dimensions", "Innovid Dimensions"),
    ("TS Creative ID", "Innovid Creative ID"),
    ("TS Creative Name", "Innovid Creative Name"),
    ("TS Creative Dates", "Innovid Creative Dates"),
    ("TS Rotation", "Innovid Rotation"),
    ("CGEN TS (Adobe)", "CGEN Innovid (Adobe)"),
    ("TS URL", "Innovid URL"),
]

_WORST = ["FAIL", "REVIEW", "NOT_VERIFIED", "INFO", "PASS"]


# Innovid solo admite porcentajes enteros en el decision set, asi que
# un 13,33% de la TS se escribe alli como 13%. Es la misma rotacion,
# y exigir el decimal marcaria como diferencia algo que nadie puede
# corregir. El mismo margen que usa INV-002.
ROUNDING_TOLERANCE_PP = 1.0


def _percent(value: str) -> float | None:
    text = value.strip()
    if not text.endswith("%"):
        return None
    try:
        return float(text[:-1])
    except ValueError:
        return None


def cells_agree(left: object, right: object) -> bool:
    """
    ¿Los dos lados dicen lo mismo?

    Vacio contra vacio no es un acuerdo: no hay nada que comparar, y
    pintarlo de verde afirmaria que algo se verifico cuando no se
    miro nada.
    """
    a, b = str(left or "").strip(), str(right or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True

    # Porcentajes: se comparan como numeros, con el margen del
    # redondeo. Como texto, "13.33%" y "13%" no coincidian nunca y la
    # rotacion salia sin pintar en todas las filas.
    left_pct, right_pct = _percent(a), _percent(b)
    if left_pct is not None and right_pct is not None:
        return abs(left_pct - right_pct) <= ROUNDING_TOLERANCE_PP

    # Los nombres se comparan sin lo que Innovid les pega al mostrarlos.
    return _bare(a) == _bare(b) or norm_compare(a) == norm_compare(b)


# El id que Innovid añade al final de lo que muestra:
#   "ACT GM W18+ TTD Display 160X600 UG (34605)"
#   "..._STA-BASE_011_NA-v01.zip (6112823)"
#   "GR_DISP_CRDV_..._W18-160X600 UG ACT (10738914)"
# La Traffic Sheet nunca lo lleva, asi que comparado en crudo el
# nombre no coincidia NUNCA y esas columnas salian siempre en
# naranja. 2226 de los valores del export de Dove lo traen.
_TRAILING_ID = re.compile(r"\s*\(\d+\)\s*$")


def _bare(value: str) -> str:
    """
    El nombre sin el id final ni la extension.

    Se quita primero el "(12345)" y despues la extension, porque
    vienen en ese orden: "....zip (6112823)". norm_creative se
    encarga del resto -- espacios y el sello de subida de Innovid --
    con el mismo criterio que usa el motor, para no tener dos
    definiciones de "mismo nombre".
    """
    return norm_creative(_TRAILING_ID.sub("", str(value or "").strip()))


def _worst_status(statuses) -> str:
    for candidate in _WORST:
        if candidate in statuses:
            return candidate
    return ""


def _span(start, end) -> str:
    if not start and not end:
        return ""
    return f"{start or '?'} → {end or 'ongoing'}"


def _text(value) -> str:
    return "" if value is None else str(value)


def build_qa_rows(match_result, findings=(), innovid_reconciliation=None,
                  ) -> list[dict]:
    """
    Una fila por creativo trabajado, mas una por placement sin
    creativos declarados (una solicitud de landing page o de 1x1 es
    asi, y dejarla fuera borraria del entregable un placement que si
    se trabajo).
    """
    flights = _flights_index(innovid_reconciliation)
    partners = _partners_index(innovid_reconciliation)
    by_row = _findings_index(findings)

    rows: list[dict] = []

    for pm in match_result.matched:
        pid = str(pm.placement_id)
        actual = pm.actual

        base = {
            "TS Placement ID": pid,
            "Innovid Placement ID": _text(
                actual.placement_id if actual else ""
            ),
            "TS Placement Name": _text(pm.expected.name),
            "Innovid Placement Name": _text(actual.name if actual else ""),
            "TS Start Date": _text(pm.expected.start),
            "Innovid Start Date": _text(actual.start if actual else ""),
            "TS End Date": _text(pm.expected.end),
            "Innovid End Date": _text(actual.end if actual else ""),
            "TS Dset / Dtree": _text(pm.expected.group_name),
            "Innovid Dset / Dtree": _text(
                actual.group_name if actual else ""
            ),
            "TS Dimensions": _text(pm.expected.dims),
            "Innovid Dimensions": _text(actual.dims if actual else ""),
            "Verification Partner": _text(
                partners.get(pid, "")
            ),
        }

        links = list(pm.creative_links)

        # La rotacion de la TS se normaliza por placement, que es
        # donde el reparto suma 100.
        ts_weights = normalize_weights(
            [cl.expected.rotation_weight for cl in links]
        )

        if not links:
            rows.append({
                **{column: "" for column in COLUMNS},
                **base,
                "Status": _worst_status(by_row.get((pid, ""), set())),
                "Notes": " | ".join(sorted(_notes(by_row, (pid, "")))),
            })
            continue

        for cl, ts_weight in zip(links, ts_weights):
            key = (pid, norm_creative(cl.expected.name))
            check = flights.get(key)
            creative_actual = cl.actual

            rows.append({
                **{column: "" for column in COLUMNS},
                **base,
                "TS Creative ID": _text(cl.expected.creative_id),
                "Innovid Creative ID": _text(
                    creative_actual.creative_id if creative_actual else ""
                ),
                "TS Creative Name": _text(cl.expected.name),
                "Innovid Creative Name": _text(
                    (creative_actual.filename or creative_actual.name)
                    if creative_actual else ""
                ),
                "TS Creative Dates": _span(cl.expected.start, cl.expected.end),
                "Innovid Creative Dates": (
                    _span(check.actual_start, check.actual_end)
                    if check else ""
                ),
                "TS Rotation": ts_weight,
                "Innovid Rotation": (
                    check.actual_weight_pct if check else ""
                ),
                "CGEN TS (Adobe)": _text(cl.expected.cgen),
                "CGEN Innovid (Adobe)": _text(
                    creative_actual.third_party_id if creative_actual else ""
                ),
                "TS URL": _text(cl.expected.url),
                "Innovid URL": _text(
                    creative_actual.clicktags[0]
                    if creative_actual and creative_actual.clicktags
                    else ""
                ),
                "Status": _worst_status(
                    by_row.get(key, set())
                    | by_row.get((pid, ""), set())
                ),
                "Notes": " | ".join(sorted(
                    _notes(by_row, key) | _notes(by_row, (pid, ""))
                )),
            })

    return rows


def _flights_index(reconciliation) -> dict:
    index: dict = {}
    if reconciliation is None:
        return index
    for check in reconciliation.flights:
        index.setdefault(
            (str(check.placement_id), norm_creative(check.creative_name)),
            check,
        )
    return index


def _partners_index(reconciliation) -> dict[str, str]:
    index: dict[str, str] = {}
    if reconciliation is None:
        return index
    for check in reconciliation.partners:
        if check.site_served_1x1:
            index[str(check.placement_id)] = "N/A (site-served 1x1)"
        else:
            index[str(check.placement_id)] = check.actual_partner or "(not set)"
    return index


def _findings_index(findings) -> dict:
    """
    Hallazgos por (placement, creativo). Los que no nombran creativo
    se guardan bajo "" y alcanzan a todas las filas del placement.
    """
    index: dict = {}
    for finding in findings or ():
        pid = str(getattr(finding, "placement_id", "") or "")
        name = norm_creative(getattr(finding, "creative_name", "") or "")
        key = (pid, name)
        index.setdefault(key, set()).add(finding.status.value)
        # En Notes solo va lo que el color no puede decir: que alguien
        # firmo esto a mano. El resto -- que coincide y que no -- ya
        # esta en el verde y el naranja de las columnas, y volcarlo
        # aqui convertia la celda en un parrafo ilegible.
        reason = str(getattr(finding, "reason", "") or "")
        if "Approved" in reason:
            approval = reason.split("|")[-1].strip() if "|" in reason else reason
            index.setdefault(("notes",) + key, set()).add(
                f"MANUALLY {approval}"
            )
            continue

        # Un hallazgo que sigue abierto si se nombra: un FAIL o un
        # REVIEW no tiene color propio en la fila, y sin esto no
        # habria forma de saber por que la fila esta marcada.
        if finding.status.value in ("FAIL", "REVIEW", "NOT_VERIFIED"):
            index.setdefault(("notes",) + key, set()).add(
                f"{finding.rule_id}: {finding.message}"
            )
    return index


def _notes(index: dict, key: tuple) -> set:
    return index.get(("notes",) + key, set())

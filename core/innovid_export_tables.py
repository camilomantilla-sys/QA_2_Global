"""
Lo que QA2 leyo de Innovid, en tablas para el Excel (FB-17).

La pantalla mostraba el decision set de cada creativo, sus fechas, su
peso y el Verification Partner de cada placement, pero el Excel solo
llevaba lo que cabia en la hoja QA, que es una fila por creativo de la
TS. Lo que Innovid tenia y la TS no pedia, el nombre y el ID del
decision set y lo que no se pudo leer se quedaban en la pantalla. Aqui
va todo, tal cual se leyo.
"""
from __future__ import annotations

import pandas as pd  # type: ignore

from core.innovid_reconciliation import (
    AMBIGUOUS,
    EXTRA_IN_INNOVID,
    MATCHED,
    MISSING_IN_INNOVID,
    ONLY_IN_EXPORT,
)

#: Lo mismo que dice la pantalla para cada resultado.
RESULT_LABELS = {
    MATCHED: "In decision set",
    MISSING_IN_INNOVID: "Not in decision set",
    ONLY_IN_EXPORT: "Assigned, named differently in DS",
    EXTRA_IN_INNOVID: "Not in the Traffic Sheet",
    AMBIGUOUS: "Duplicated in DS",
}


def _date(value) -> str:
    return value.isoformat() if value else ""


def decision_set_table(reconciliation) -> pd.DataFrame:
    """Una fila por creativo leido de cada decision set, mas lo no leido."""
    rows = []
    for check in getattr(reconciliation, "flights", None) or []:
        label = RESULT_LABELS.get(check.status, check.status)
        if check.status == AMBIGUOUS and check.candidates > 1:
            label = f"Duplicated in DS (x{check.candidates})"
        rows.append({
            "Placement ID": check.placement_id,
            "Decision Set ID": check.dset_id,
            "Decision Set Name": check.dset_name,
            "TS Creative": check.creative_name,
            "Creative Name in DS": check.actual_name,
            "Creative Name in Export": check.export_name,
            "Default Ad": "Yes" if check.is_default else "",
            "TS Start": _date(check.expected_start),
            "Innovid Start": _date(check.actual_start),
            "TS End": _date(check.expected_end),
            "Innovid End": _date(check.actual_end) or (
                "ongoing" if check.actual_start else ""
            ),
            "TS Rotation %": check.expected_weight_pct,
            "Innovid Rotation %": check.actual_weight_pct,
            "Innovid Weight": check.actual_weight,
            "Result": label,
        })
    for placement_id, reason in getattr(reconciliation, "unchecked", None) or []:
        rows.append({
            "Placement ID": placement_id,
            "Result": f"Not read from Innovid: {reason}",
        })
    for placement_id in getattr(reconciliation, "site_served", None) or []:
        rows.append({
            "Placement ID": placement_id,
            "Result": "1x1 site-served: no decision set to compare",
        })
    columns = [
        "Placement ID", "Decision Set ID", "Decision Set Name", "TS Creative",
        "Creative Name in DS", "Creative Name in Export", "Default Ad",
        "TS Start", "Innovid Start", "TS End", "Innovid End",
        "TS Rotation %", "Innovid Rotation %", "Innovid Weight", "Result",
    ]
    return pd.DataFrame(rows, columns=columns).fillna("")


def partner_table(reconciliation) -> pd.DataFrame:
    """El Verification Partner de cada placement, como lo devolvio Innovid."""
    rows = []
    for check in getattr(reconciliation, "partners", None) or []:
        rows.append({
            "Placement ID": check.placement_id,
            "Verification Partner": check.actual_partner,
            "Partner Status": check.actual_status,
            "Configured": "Yes" if check.configured else "No",
            "Expected by the TS": "Yes" if check.partner_expected else "No",
            "1x1 Site-Served": "Yes" if check.site_served_1x1 else "",
        })
    columns = ["Placement ID", "Verification Partner", "Partner Status",
               "Configured", "Expected by the TS", "1x1 Site-Served"]
    return pd.DataFrame(rows, columns=columns)

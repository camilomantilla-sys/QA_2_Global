"""
Lo que QA2 entendio de una Traffic Sheet, listo para la pagina.

Parte del mismo resumen que fija las lecturas en las pruebas
(``core.ts_snapshot.summarise_ts``) y le suma lo que la persona
necesita ver para confirmar la lectura: el encabezado real de cada
columna, su letra y unas filas de muestra. Esto no sale del PC: viaja
del servidor local a la pagina local y nada mas.
"""
from __future__ import annotations

import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from core.ts_snapshot import summarise_ts

#: Nombre corporativo de cada perfil. Mismo texto que la interfaz de
#: Streamlit; vive aqui para no importar Streamlit.
PROFILE_LABELS = {
    "adobe_variante_a": "Adobe · Decision Tree Implementation",
    "adobe_variante_b": "Adobe · Direct & Site-Served Implementation",
    "wpp_standard": "WPP Media · Standard Trafficking",
}

#: Como se lee cada campo canonico en pantalla.
FIELD_LABELS = {
    "site": "Site",
    "placement_id": "Placement ID",
    "placement_name": "Placement name",
    "start_date": "Start date",
    "end_date": "End date",
    "dimensions": "Dimensions",
    "group_name": "Creative rotation",
    "creative_names": "Creative names",
    "lp_ref": "Landing page",
    "vendors": "Vendor pixels",
    "rotation_weight": "Rotation weight",
    "cgen": "CGEN",
    "extra_requirements": "Additional requirements",
    "creative_name": "Creative name",
    "universal_ad_id": "Universal Ad-ID",
    "creative_id": "Creative ID",
    "creative_type": "Creative type",
    "dims_or_duration": "Dimensions / duration",
    "sequence": "Sequential",
    "lp_url": "Landing page URL",
    "lp_name": "Landing page name",
    "companion": "Companion banner",
    "companion_id": "Companion banner ID",
    "creative_links": "Creative links",
    "status_of_rotation": "Rotation status",
    "as_campaign": "Campaign (tracking)",
    "as_source": "Source (tracking)",
    "as_content": "Content (tracking)",
    "rich_media_click": "Rich media click-out",
    "io": "IO",
    "fmt": "Format",
}

#: Que pide la solicitud para cada placement.
REQUEST_LABELS = {
    "NEW_PLACEMENT": "New placement",
    "CREATIVE_SWAP": "Creative swap",
    "CREATIVE_ADD": "Creative added",
    "CREATIVE_REMOVE": "Creative removed",
    "URL_SWAP": "URL swap",
    "FIELD_CHANGE": "Field change",
    "REVIEW": "Needs a look",
    "NOT_WORKED": "Not part of this request",
}

#: Intencion de la fila (la que decide el parser) -> tarjeta en pantalla.
#: Verde y rojo a la vez es un cambio; amarillo y gris quedan fuera.
INTENT_GROUP = {
    "GREEN": "new",
    "RED": "remove",
    "SWAP": "swap",
    "SCOPE_EXCLUDED": "out",
    "YELLOW": "out",
    "GREY": "out",
    "REVIEW": "review",
    "WHITE": "context",
    "UNKNOWN": "context",
}

SAMPLE_ROWS = 300


def field_label(name: str) -> str:
    return FIELD_LABELS.get(name, name.replace("_", " ").capitalize())


def _headers(path: Path, sheet: str, header_row: int | None) -> dict[int, str]:
    """Texto real de cada encabezado de la hoja, por numero de columna."""
    if not header_row:
        return {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        book = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = book[sheet]
        for values in ws.iter_rows(min_row=header_row, max_row=header_row,
                                   values_only=True):
            return {i: str(v).strip() for i, v in enumerate(values, start=1)
                    if v is not None and str(v).strip()}
        return {}
    finally:
        book.close()


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%b %d, %Y").replace(" 0", " ")
    return str(value)


def _columns(path: Path, sheet) -> list[dict[str, Any]]:
    """Cada campo que QA2 necesita, en que columna lo encontro y cuan lleno esta."""
    if sheet is None or sheet.cmap is None:
        return []
    headers = _headers(path, sheet.sheet, sheet.header_row)
    out: list[dict[str, Any]] = []
    for name, col in sheet.cmap.single.items():
        out.append({
            "field": name,
            "label": field_label(name),
            "column": get_column_letter(col),
            "header": headers.get(col, ""),
            "filled": round(sheet.fill_rates.get(name, 0.0), 2),
        })
    for name, cols in sheet.cmap.multi.items():
        out.append({
            "field": name,
            "label": field_label(name),
            "column": ", ".join(get_column_letter(c) for c in cols),
            "header": ", ".join(headers.get(c, "") for c in cols),
            "filled": round(sheet.fill_rates.get(name, 0.0), 2),
        })
    out.sort(key=lambda c: c["column"].split(",")[0].rjust(3))
    return out


def _flight(rows) -> dict[str, str]:
    starts = [r.values.get("start_date") for r in rows]
    ends = [r.values.get("end_date") for r in rows]
    starts = [d for d in starts if isinstance(d, (date, datetime))]
    ends = [d for d in ends if isinstance(d, (date, datetime))]
    if not starts or not ends:
        return {}
    first, last = min(starts), max(ends)
    weeks = max(1, round(((last - first).days + 1) / 7))
    return {"start": _text(first), "end": _text(last), "weeks": weeks}


def build_summary(result, path: Path, file_name: str) -> dict[str, Any]:
    """Todo lo que el paso 1 muestra, a partir de la lectura del parser."""
    snap = summarise_ts(result)
    pl = result.placements
    rows = pl.rows if pl else []

    intent = {"new": 0, "remove": 0, "swap": 0, "out": 0, "context": 0, "review": 0}
    for row in rows:
        intent[INTENT_GROUP.get(row.intent, "context")] += 1

    sites = {str(r.values.get("site")).strip() for r in rows
             if r.values.get("site")}
    creatives: set[str] = set()
    if result.rotations is not None:
        creatives = {str(r.values.get("creative_name")).strip()
                     for r in result.rotations.rows
                     if r.values.get("creative_name")}
    if not creatives:
        for r in rows:
            for name in str(r.values.get("creative_names") or "").splitlines():
                if name.strip() and name.strip().upper() != "N/A":
                    creatives.add(name.strip())

    sample = []
    for r in rows[:SAMPLE_ROWS]:
        sample.append({
            "row": r.row,
            "placement_id": _text(r.values.get("placement_id")),
            "placement_name": _text(r.values.get("placement_name")),
            "creative": _text(r.values.get("creative_names")
                              or r.values.get("group_name")),
            "intent": INTENT_GROUP.get(r.intent, "context"),
        })

    sheet_info = None
    if pl is not None:
        sheet_info = {
            "sheet": pl.sheet,
            "header_row": pl.header_row,
            "rows": len(pl.rows),
            "columns": _columns(path, pl),
            "missing_required": [field_label(f) for f in pl.cmap.missing_required] if pl.cmap else [],
            "missing_optional": [field_label(f) for f in pl.cmap.missing_optional] if pl.cmap else [],
            "ignored": [{"column": get_column_letter(c), "header": h}
                        for c, h in (snap["placements"] or {}).get("unmapped_columns", [])],
            "dates": {field_label(k): v.get("order") for k, v in pl.date_diagnostics.items()},
        }

    rotations_info = None
    if result.rotations is not None:
        rotations_info = {
            "sheet": result.rotations.sheet,
            "rows": len(result.rotations.rows),
            "columns": _columns(path, result.rotations),
        }

    return {
        "file": file_name,
        "profile": result.profile,
        "profile_label": PROFILE_LABELS.get(result.profile,
                                            result.profile.replace("_", " ").title()),
        "sheets": snap["sheets"],
        "counts": {
            "placements": len(result.scope),
            "rows": len(rows),
            "creatives": len(creatives),
            "sites": len(sites),
        },
        "flight": _flight(rows),
        "intent": intent,
        "requests": [
            {"key": k, "label": REQUEST_LABELS.get(k, k), "count": v}
            for k, v in sorted(result.request_counts.items(),
                               key=lambda kv: (kv[0] == "NOT_WORKED", -kv[1]))
        ],
        "placements": sheet_info,
        "rotations": rotations_info,
        "rows": sample,
        "rows_total": len(rows),
        "anomalies": [
            {"code": a.code, "severity": a.severity, "message": a.message}
            for a in result.anomalies
        ],
        "fatal": result.fatal,
    }

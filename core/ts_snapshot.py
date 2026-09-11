"""
Lo que QA leyo de una Traffic Sheet, en forma comparable.

Van a seguir llegando TS viejas y nuevas, y el formato volvera a
cambiar. Un resumen estable de la lectura permite dejar fijado lo que
la app entiende hoy de cada formato, y que se note en el acto si un
cambio en el parser rompe uno de los que ya funcionaban.

Solo estructura: perfil, hojas, cabeceras, columnas mapeadas y sin
mapear, conteos y diagnosticos. **Ningun valor de las celdas.** Los
nombres de campana, de placement y de sitio son datos de cliente, y
esto acaba en git.
"""
from __future__ import annotations

from typing import Any


def _plain(value):
    """
    Tuplas a listas, recursivamente.

    JSON no distingue una de otra, asi que una tupla guardada vuelve
    siempre como lista y cada comparacion daria un cambio que no lo
    es. Mejor que no haya tuplas desde el principio.
    """
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def _sheet(sheet) -> dict[str, Any] | None:
    """Como leyo la app una hoja. Nombres de columna, no contenidos."""
    if sheet is None:
        return None

    cmap = sheet.cmap
    return {
        "sheet": sheet.sheet,
        "header_row": sheet.header_row,
        "rows": len(sheet.rows),
        "merged_applied": sheet.merged_applied,
        "mapped_columns": sorted(cmap.single) if cmap else [],
        "multi_columns": sorted(cmap.multi) if cmap else [],
        "unmapped_columns": _plain(sorted(cmap.unmapped)) if cmap else [],
        "missing_required": sorted(cmap.missing_required) if cmap else [],
        "missing_optional": sorted(cmap.missing_optional) if cmap else [],
        "row_class_counts": dict(sorted(sheet.row_class_counts.items())),
        "intent_counts": dict(sorted(sheet.intent_counts.items())),
        "impl_counts": dict(sorted(sheet.impl_counts.items())),
        # El porcentaje de relleno se redondea: un decimal de mas
        # convertiria cada reordenacion de filas en una diferencia.
        "fill_rates": {
            name: round(value, 2)
            for name, value in sorted(sheet.fill_rates.items())
        },
        # De las fechas importa como se leyeron, no que decian.
        "dates": {
            field: {
                "order": diag.get("order"),
                "native": diag.get("native"),
                "text": diag.get("text"),
                "unparsed": diag.get("unparsed"),
            }
            for field, diag in sorted(sheet.date_diagnostics.items())
        },
        "anomalies": sorted({a.code for a in sheet.anomalies}),
    }


def summarise_ts(result) -> dict[str, Any]:
    """El resumen completo de una lectura, listo para comparar."""
    return _plain({
        "profile": result.profile,
        "profile_evidence": result.profile_evidence,
        "sheets": {
            "in_scope": list(result.in_scope_sheets),
            "out_of_scope": list(result.out_of_scope_sheets),
            "hidden": list(result.hidden_sheets),
        },
        # Las claves dicen que campos entendio; los valores son del
        # cliente y no entran.
        "campaign_info_fields": sorted(result.campaign_info),
        "site_contacts": len(result.site_contacts),
        "placements": _sheet(result.placements),
        "rotations": _sheet(result.rotations),
        "landing_pages": _sheet(result.landing_pages),
        "groups": len(result.groups),
        "lp_worked": len(result.lp_worked),
        "scope": len(result.scope),
        "request_counts": dict(sorted(result.request_counts.items())),
        "format_counts": dict(sorted(result.format_counts.items())),
        "source_counts": dict(sorted(result.source_counts.items())),
        "theme_colors": len(result.theme_colors),
        "anomalies": sorted({a.code for a in result.anomalies}),
    })


def differences(expected: dict, actual: dict, path: str = "") -> list[str]:
    """
    En que se diferencian dos lecturas, campo a campo.

    Un diff entero de dos JSON grandes no dice cual es el cambio que
    importa. Esto da una linea por diferencia, con su camino.
    """
    found: list[str] = []

    if type(expected) is not type(actual):
        return [f"{path or 'raiz'}: {type(expected).__name__} -> "
                f"{type(actual).__name__}"]

    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            where = f"{path}.{key}" if path else str(key)
            if key not in actual:
                found.append(f"{where}: desaparecio (era {expected[key]!r})")
            elif key not in expected:
                found.append(f"{where}: nuevo ({actual[key]!r})")
            else:
                found += differences(expected[key], actual[key], where)
        return found

    if isinstance(expected, list):
        if expected != actual:
            gone = [x for x in expected if x not in actual]
            new = [x for x in actual if x not in expected]
            if gone:
                found.append(f"{path}: ya no lee {gone!r}")
            if new:
                found.append(f"{path}: ahora lee ademas {new!r}")
            if not gone and not new:
                found.append(f"{path}: cambio el orden")
        return found

    if expected != actual:
        found.append(f"{path}: {expected!r} -> {actual!r}")
    return found

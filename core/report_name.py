"""
Como se llama el archivo que alguien se descarga.

    2026-09-18_QA_Report_FY26_Q4_AMER_DocumentCloud_Acrobat.xlsx

La fecha primero y en ISO para que la carpeta compartida los ordene
sola: con 18-09-2026 quedan agrupados por dia del mes, que no le sirve
a nadie. Y el nombre de la campana detras, porque "qa_report" y la
hora era lo mismo para todas y en SharePoint no se distinguian.

Los nombres de campana traen caracteres que Windows no acepta en un
nombre de archivo -- \\ / : * ? " < > | -- y de hecho el explorador se
niega a guardar sin decir por que. Se reemplazan por guion bajo.
"""
from __future__ import annotations

import re
from datetime import date, datetime

#: Lo que Windows prohibe, mas los de control.
_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')

#: Un nombre de archivo largo mas la ruta de Descargas se pasa del
#: limite de Windows, y lo que se pierde al recortar es el final: la
#: fecha y "QA_Report" van delante justamente por eso.
MAX_CAMPAIGN = 80


def safe_part(value: str) -> str:
    """Un trozo de nombre de archivo que Windows si acepta."""
    cleaned = _FORBIDDEN.sub("_", str(value or "").strip())
    # Los espacios sobreviven a un correo peor que los guiones bajos.
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("_. ")
    return cleaned[:MAX_CAMPAIGN].strip("_. ")


def report_filename(
    extension: str,
    campaign: str = "",
    when: date | datetime | None = None,
) -> str:
    """
    <fecha>_QA_Report_<campana>.<extension>

    Sin campana se queda en `<fecha>_QA_Report.<extension>`: un nombre
    corto y correcto es mejor que uno con un hueco donde iba el dato.
    """
    when = when or datetime.now()
    stamp = when.strftime("%Y-%m-%d")
    name = safe_part(campaign)
    stem = f"{stamp}_QA_Report_{name}" if name else f"{stamp}_QA_Report"
    return f"{stem}.{extension.lstrip('.')}"

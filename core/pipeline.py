"""
El QA completo, sin interfaz.

La app de Streamlit armaba aqui mismo, en su propio cuerpo, la cadena
que va de los archivos al veredicto: leer cada archivo, decir que es,
cruzar la TS con el export y correr cada familia de reglas. La interfaz
nueva (ui/web) necesita exactamente la misma cadena, y copiarla seria
tener dos QA que con el tiempo dirian cosas distintas sobre la misma
solicitud. Vive aqui y las dos la llaman.

Nada de este modulo sabe de Streamlit ni de HTTP. Recibe bytes y
resultados de los parsers; devuelve resultados del motor.

Orden de uso:

    ts = parse_traffic_sheet(data, name)
    pc = parse_export(data, name)                  # Placement-Creative
    pl = parse_export(data, name)                  # Placement (opcional)
    tags = [(name, parse_tags(data, name)), ...]   # opcional
    dv = parse_dv(files)                           # opcional
    rows, issues = understand_files(...)           # que es cada archivo
    match_result = match(ts, pc, pl)
    checks = run_checks(match_result, ts, pc, pl, tags, dv, account,
                        innovid_reconciliation)
"""
from __future__ import annotations

import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.adobe_pixel_reconciliation import reconcile_adobe_pixels
from core.adobe_tag_policy_reconciliation import reconcile_adobe_tag_policy
from core.default_ads import reconcile_default_ads
from core.dv_omni_reconciliation import reconcile_dv_omni
from core.dv_reconciliation import reconcile_dv_tags
from core.engine import run_rules
from core.pixel_reconciliation import reconcile_pixels
from core.tag_coverage_reconciliation import reconcile_tag_coverage
from core.tag_inventory import TagInventory, build_tag_inventory_from_results
from core.tag_matching import match_tags
from rules import adobe_pixels
from rules import adobe_tag_policy
from rules import defaults as default_rules
from rules import dv_omni as dv_omni_rules
from rules import dv_tags as dv_rules
from rules import pixels as pixel_rules
from rules import tag_coverage as tag_coverage_rules
from rules import tags as tag_rules

ADOBE_PROFILES = ("adobe_variante_a", "adobe_variante_b")

PROFILE_LABELS = {
    "adobe_variante_a": "Adobe · Decision Tree Implementation",
    "adobe_variante_b": "Adobe · Direct & Site-Served Implementation",
    "wpp_standard": "WPP Media · Standard Trafficking",
}


# ------------------------------------------------------------------ lectura

def workbook_path(directory: str, file_name: str, file_bytes: bytes) -> Path:
    """
    Donde escribir un archivo subido, con la extension de lo que ES.

    Innovid exporta sus vistas con nombre .XLS siendo un .xlsx (empieza
    por "PK", un zip). openpyxl los rechaza solo por la extension, asi
    que aqui decide el contenido. El resto del nombre se conserva: los
    parsers lo usan como contexto.
    """
    stem = Path(file_name).stem or "file"
    suffix = Path(file_name).suffix.lower()
    if file_bytes[:2] == b"PK" and suffix not in (".xlsx", ".xlsm", ".zip"):
        suffix = ".xlsx"
    return Path(directory) / f"{stem}{suffix}"


def _parse_bytes(parser: Callable[[Path], Any], file_bytes: bytes, file_name: str):
    """Escribe el archivo en una carpeta temporal, lo lee y la borra."""
    with tempfile.TemporaryDirectory(prefix="qa2_read_") as directory:
        path = workbook_path(directory, file_name, file_bytes)
        path.write_bytes(file_bytes)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return parser(path)


def parse_traffic_sheet(file_bytes: bytes, file_name: str, profile: str | None = None):
    from parsers.ts_parser import parse_ts
    return _parse_bytes(lambda p: parse_ts(p, profile_name=profile), file_bytes, file_name)


def parse_export(file_bytes: bytes, file_name: str):
    from parsers.innovid_export import parse_innovid_export
    return _parse_bytes(parse_innovid_export, file_bytes, file_name)


def parse_tags(file_bytes: bytes, file_name: str):
    from parsers.innovid_tags import parse_innovid_tags
    return _parse_bytes(parse_innovid_tags, file_bytes, file_name)


def parse_dv(files: list[tuple[str, bytes]]):
    """Varios archivos de DV Pinnacle (uno por partner) en uno solo."""
    from parsers.dv_tags import merge_dv_results, parse_dv_tags
    if not files:
        return None
    return merge_dv_results([_parse_bytes(parse_dv_tags, data, name) for name, data in files])


# ------------------------------------------------------------------ que es cada archivo

def is_fatal(result) -> bool:
    return any(a.severity == "FATAL" for a in getattr(result, "anomalies", []))


def anomaly_rows(source_name: str, result) -> list[dict]:
    return [
        {
            "Source": source_name,
            "Severity": anomaly.severity,
            "Code": anomaly.code,
            "Message": anomaly.message,
            "Reference": str(anomaly.ref) if getattr(anomaly, "ref", None) else "",
        }
        for anomaly in getattr(result, "anomalies", [])
    ]


def profile_label(profile: str) -> str:
    return PROFILE_LABELS.get(profile, profile or "Not Recognized")


def understand_files(
    ts_name: str, ts_result,
    pc_name: str, pc_result,
    pl_name: str = "", pl_result=None,
    tags_results: list | None = None,
    dv_result=None,
) -> tuple[list[dict], list[dict]]:
    """
    Que es cada archivo y que problemas trae.

    Devuelve (filas de archivo, anomalias). Una anomalia FATAL bloquea
    el QA: un Placement-Creative que no tiene Creative_ID, o un archivo
    de tags subido donde va el Placement View, no se pueden juzgar.
    """
    tags_results = tags_results or []
    files = [
        {"File": ts_name, "Expected Type": "Traffic Sheet",
         "Detected Type": profile_label(getattr(ts_result, "profile", "")),
         "Status": "FATAL" if is_fatal(ts_result) else "OK",
         "Records": len(ts_result.placements.rows) if getattr(ts_result, "placements", None) else 0},
    ]
    if pc_result is not None:
        files.append({"File": pc_name, "Expected Type": "Placement-Creative View",
                      "Detected Type": pc_result.level or "Not Recognized",
                      "Status": "FATAL" if is_fatal(pc_result) else "OK",
                      "Records": len(pc_result.rows)})
    if pl_result is not None:
        files.append({"File": pl_name, "Expected Type": "Placement View",
                      "Detected Type": pl_result.level or "Not Recognized",
                      "Status": "FATAL" if is_fatal(pl_result) else "OK",
                      "Records": len(pl_result.rows)})
    for name, result in tags_results:
        files.append({"File": name, "Expected Type": "Tags",
                      "Detected Type": f"Tags | sheet {result.sheet}" if result.sheet else "Not Recognized",
                      "Status": "FATAL" if is_fatal(result) else "OK",
                      "Records": len(result.rows)})
    if dv_result is not None:
        for name in (dv_result.sources or ["DV Pinnacle Tags"]):
            rows = [r for r in dv_result.rows if not r.source or r.source == name]
            files.append({"File": name, "Expected Type": "DV Pinnacle Tags",
                          "Detected Type": f"DV Pinnacle | sheet {dv_result.sheet}" if dv_result.sheet else "Not Recognized",
                          "Status": "FATAL" if is_fatal(dv_result) else "OK",
                          "Records": len(rows)})

    issues = anomaly_rows("Traffic Sheet", ts_result)
    if pc_result is not None:
        issues += anomaly_rows("Placement-Creative View", pc_result)
    if pl_result is not None:
        issues += anomaly_rows("Placement View", pl_result)
    for name, result in tags_results:
        issues += anomaly_rows(f"Tags | {name}", result)
    if dv_result is not None:
        issues += anomaly_rows("DV Pinnacle Tags", dv_result)

    if pc_result is not None and not is_fatal(pc_result) and pc_result.level != "placement_creative":
        issues.append({
            "Source": "Placement-Creative View", "Severity": "FATAL",
            "Code": "UI-WRONG-PC-FILE",
            "Message": ("The uploaded file was not recognized as a "
                        "Placement-Creative View. It must contain Creative_ID."),
            "Reference": pc_name,
        })
    if pl_result is not None and not is_fatal(pl_result) and pl_result.level != "placement":
        issues.append({
            "Source": "Placement View", "Severity": "FATAL",
            "Code": "UI-WRONG-PL-FILE",
            "Message": ("The uploaded file was not recognized as a "
                        "Placement View. Do not upload a TAGS file here."),
            "Reference": pl_name,
        })
    return files, issues


# ------------------------------------------------------------------ reglas

@dataclass
class QAChecks:
    """Lo que dejan las reglas: los hallazgos y cada conciliacion que
    la interfaz muestra en sus tablas."""

    findings: Any
    tag_matches: list = field(default_factory=list)
    tag_inventory: Any = None
    adobe_pixel_result: Any = None
    adobe_tag_policy_result: Any = None
    tag_coverage_result: Any = None
    dv_reconciliation: Any = None
    dv_omni_reconciliation: Any = None
    pixel_reconciliation: Any = None
    default_ad_reconciliation: Any = None


def run_checks(
    match_result,
    ts_result,
    pc_result,
    pl_result=None,
    tags_results: list | None = None,
    dv_result=None,
    account: str = "",
    innovid_reconciliation=None,
) -> QAChecks:
    """
    Todas las familias de reglas, en el orden de siempre.

    Innovid se consulta ANTES, fuera de aqui: el motor tiene que saber
    si Innovid contesto para no dar por no verificada cada rotacion.
    """
    tags_results = tags_results or []
    findings = run_rules(
        match_result,
        account=account,
        innovid_reconciliation=innovid_reconciliation,
        ts_result=ts_result,
    )
    out = QAChecks(findings=findings)

    # Cada archivo de tags conserva sus revisiones de estructura.
    for name, result in tags_results:
        tag_match = match_tags(match_result, result)
        tag_rules.evaluate(tag_match, findings)
        out.tag_matches.append((name, result, tag_match))

    # El inventario consolidado: los requisitos de negocio de Adobe se
    # juzgan una vez sobre todos los archivos, no uno por archivo.
    if tags_results:
        out.tag_inventory = build_tag_inventory_from_results(tags_results)
    inventory = out.tag_inventory if out.tag_inventory is not None else TagInventory()

    adobe = getattr(ts_result, "profile", "") in ADOBE_PROFILES

    # PIX-A01 (DISQO/iSpot): los dos perfiles de Adobe.
    if adobe and out.tag_inventory is not None and pl_result is not None:
        out.adobe_pixel_result = reconcile_adobe_pixels(
            ts_result, pl_result, out.tag_inventory, account)
        adobe_pixels.evaluate(out.adobe_pixel_result, findings)

    # TAG-012 (politica de columnas de Adobe) y TAG-013 (cobertura 1x1):
    # solo necesitan los archivos de tags.
    if adobe and out.tag_inventory is not None:
        out.adobe_tag_policy_result = reconcile_adobe_tag_policy(ts_result, out.tag_inventory)
        adobe_tag_policy.evaluate(out.adobe_tag_policy_result, findings)
        out.tag_coverage_result = reconcile_tag_coverage(ts_result, out.tag_inventory)
        tag_coverage_rules.evaluate(out.tag_coverage_result, findings)

    # DV Pinnacle: con inventario vacio si no hay tags, para que un DV
    # que no se puede comprobar salga en REVIEW y no se calle.
    out.dv_reconciliation = reconcile_dv_tags(ts_result, inventory, dv_result)
    dv_rules.evaluate(out.dv_reconciliation, findings)

    # DV-003: DV Omni y Monitoring/Blocking por columna del archivo de tags.
    out.dv_omni_reconciliation = reconcile_dv_omni(ts_result, pl_result, inventory)
    dv_omni_rules.evaluate(out.dv_omni_reconciliation, findings)

    # Pixeles de vendor de "Vendors / Pixels" contra el placement.
    out.pixel_reconciliation = reconcile_pixels(ts_result, pl_result, account)
    pixel_rules.evaluate(out.pixel_reconciliation, findings)

    # El default ad de cada dimension.
    out.default_ad_reconciliation = reconcile_default_ads(ts_result, pc_result)
    default_rules.evaluate(out.default_ad_reconciliation, findings)

    return out

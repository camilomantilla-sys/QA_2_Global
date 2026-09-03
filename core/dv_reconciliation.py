"""
DV Pinnacle site-served tag reconciliation (DV-001).

This is specifically the DV Monitoring, 1x1 check: a wrapped DV
Pinnacle tag file, delivered separately from the regular Innovid tag
export, must exist and make it into the Innovid tag file. DV Omni
doesn't use Pinnacle at all -- it's verified through a column in the
Innovid tag file instead (see core/dv_omni_reconciliation.py, DV-003).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.dv_subtype import MONITORING, dv_subtype, is_dv
from core.normalize import clean_id, norm_dims
from parsers.dv_tags import DVTagsResult
from parsers.ts_parser import REQ_NEW_PLACEMENT


@dataclass
class DVCheck:
    placement_id: str
    placement_name: str = ""
    vendor_raw: str = ""
    in_tag_inventory: bool = False
    in_dv_file: bool = False
    dv_has_content: bool = False
    result: str = "NOT_VERIFIED"
    message: str = ""


@dataclass
class DVReconciliation:
    checks: list[DVCheck] = field(default_factory=list)
    extra_dv_placements: list[str] = field(default_factory=list)


def _worked_dv_data(ts_result) -> dict[str, dict]:
    records: dict[str, dict] = {}
    worked = {s.placement_id: s for s in ts_result.worked}

    for row in ts_result.placements.rows:
        placement_id = clean_id(row.values.get("placement_id"))
        scope = worked.get(placement_id)

        if not placement_id or scope is None:
            continue

        record = records.setdefault(
            placement_id,
            {
                "placement_name": "",
                "vendor_raw": set(),
                "request_type": scope.request_type,
                "dims": "",
            },
        )

        if not record["dims"]:
            record["dims"] = norm_dims(row.values.get("dimensions"))

        if not record["placement_name"]:
            record["placement_name"] = str(
                row.values.get("placement_name") or ""
            ).strip()

        vendor_raw = str(row.values.get("vendors") or "").strip()
        if vendor_raw:
            record["vendor_raw"].add(vendor_raw)

    return records


def reconcile_dv_tags(
    ts_result,
    tag_inventory,
    dv_result: DVTagsResult | None,
) -> DVReconciliation:
    out = DVReconciliation()
    worked_dv = _worked_dv_data(ts_result)

    dv_by_id = {
        row.placement_id: row
        for row in (dv_result.rows if dv_result else [])
    }

    for placement_id in sorted(worked_dv):
        record = worked_dv[placement_id]
        vendor_raw = " | ".join(sorted(record["vendor_raw"]))

        if not is_dv(vendor_raw):
            continue

        # El archivo de DV Pinnacle solo se descarga para placements
        # NUEVOS. Un placement que ya existia y solo cambia creativos o
        # URL conserva el tag de DV que se entrego cuando se implemento,
        # asi que pedirlo otra vez marcaba como no verificado el 100% de
        # la cuenta en vez de los pocos que si lo necesitan.
        if record["request_type"] != REQ_NEW_PLACEMENT:
            continue

        # El wrapping de DV Pinnacle hoy solo se hace para 1x1. Para
        # display y video la exigencia de DV se valida como pixel en el
        # export (PIX-002), no como archivo de Pinnacle.
        if record["dims"] != "1x1":
            continue

        # El archivo de Pinnacle es especificamente la implementacion
        # de DV Monitoring en 1x1. Omni no lo usa: va por columna en
        # el archivo de tags de Innovid (DV-003), no por aqui.
        subtype = dv_subtype(vendor_raw)

        if subtype != MONITORING:
            # OMNI, MONITORING_BLOCKING or UNDETERMINED on 1x1: none
            # of those is this rule's job. DV-003 (dv_omni_reconciliation)
            # owns the fallback "which DV check applies here" finding
            # for every case this rule doesn't handle, so it isn't
            # duplicated across both rules for the same placement.
            continue

        in_inventory = placement_id in tag_inventory.placement_ids
        dv_row = dv_by_id.get(placement_id)
        in_dv_file = dv_row is not None
        has_content = bool(dv_row and dv_row.has_tag)

        check = DVCheck(
            placement_id=placement_id,
            placement_name=record["placement_name"],
            vendor_raw=vendor_raw,
            in_tag_inventory=in_inventory,
            in_dv_file=in_dv_file,
            dv_has_content=has_content,
        )

        if dv_result is None:
            check.result = "NOT_VERIFIED"
            check.message = (
                "DV Pinnacle file not provided; DV tag delivery "
                "cannot be verified."
            )
        elif not in_dv_file:
            check.result = "FAIL"
            check.message = (
                "Placement requires DV but has no row in the "
                "DV Pinnacle file."
            )
        elif not has_content:
            check.result = "FAIL"
            check.message = (
                "Placement is in the DV Pinnacle file but its "
                "tag is empty."
            )
        elif not in_inventory:
            check.result = "REVIEW"
            check.message = (
                "DV tag delivered, but this placement is missing "
                "from the Innovid tag file."
            )
        else:
            check.result = "PASS"
            check.message = (
                "DV tag delivered and present in the Innovid tag file."
            )

        out.checks.append(check)

    if dv_result is not None:
        worked_ids = set(worked_dv)
        out.extra_dv_placements = sorted(
            pid
            for pid in dv_result.placement_ids
            if pid not in worked_ids
        )

    return out

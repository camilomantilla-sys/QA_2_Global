"""
Adobe tag column policy: Ftrack / No Ftrack / Clicktag / Protected.

"Vendors / Pixels" en la Traffic Sheet fija, para 1x1, que columnas del
archivo de tags de Innovid deben tener contenido y cuales no deben
tenerlo. Un placement puede combinar mas de un requisito a la vez
(p.ej. "fTrack, Protected, DISQO"): DISQO/iSpot se validan aparte en
PIX-A01 (son evidencia de pixel, no politica de columnas). Este modulo
cubre las otras cuatro:

    FTRACK      requiere Ftrack impression + Ftrack click
                prohibe  Pixel, Static_Clicktag, Update_Clicktag
    NO_FTRACK   requiere Pixel + Update_Clicktag
                prohibe  Static_Clicktag, Ftrack impression, Ftrack click
    CLICKTAG    requiere Update_Clicktag
                prohibe  Static_Clicktag, Pixel, Ftrack impression, Ftrack click
    PROTECTED   requiere al menos una columna Protected Pixel
                prohibe  nada

Cuando un placement combina requisitos, lo requerido por cualquiera de
ellos gana sobre lo prohibido por otro: se arma primero la union de lo
requerido y luego la union de lo prohibido menos lo ya requerido.

Solo aplica a 1x1. Para video/display la propia regla de negocio dice
que no se analizan estas columnas, solo se cuenta que haya tags
(eso ya lo cubre TAG-010).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.adobe_pixel_reconciliation import (
    PixelRequirement,
    classify_vendor_requirements,
)
from core.normalize import norm_dims
from core.tag_inventory import TagInventory
from parsers.ts_parser import REQ_NOT_WORKED

_COLUMN_POLICY_REQUIREMENTS = {
    PixelRequirement.FTRACK,
    PixelRequirement.NO_FTRACK,
    PixelRequirement.CLICKTAG,
    PixelRequirement.PROTECTED,
}


@dataclass(frozen=True)
class TagPolicyCheck:
    placement_id: str
    placement_name: str = ""
    site: str = ""
    vendor_raw: str = ""
    requirements: tuple[str, ...] = ()

    required_missing: tuple[str, ...] = ()
    forbidden_present: tuple[str, ...] = ()
    columns_found: tuple[str, ...] = ()

    result: str = "NOT_VERIFIED"
    message: str = ""
    recommended_action: str = ""


@dataclass
class TagPolicyReconciliation:
    checks: list[TagPolicyCheck] = field(default_factory=list)


def _normalize_column(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
    return normalized.rstrip("0123456789")


def _is_pixel_column(column: str) -> bool:
    if column in {"pixel", "pixelhtml", "trackingpixel", "impressionpixel"}:
        return True
    return (
        "pixel" in column
        and "protected" not in column
        and "disqo" not in column
        and "ftrack" not in column
        and "ispot" not in column
        and "doubleverify" not in column
    )


def _is_static_clicktag(column: str) -> bool:
    return "staticclicktag" in column


def _is_update_clicktag(column: str) -> bool:
    return "updateclicktag" in column


def _is_ftrack_impression(column: str) -> bool:
    return column.startswith("ftrack") and ("imp" in column or "impression" in column)


def _is_ftrack_click(column: str) -> bool:
    return column.startswith("ftrack") and "click" in column


def _is_protected(column: str) -> bool:
    return "protected" in column


# name -> (detector, human label)
_SLOTS = {
    "pixel": (_is_pixel_column, "Pixel"),
    "static_clicktag": (_is_static_clicktag, "Static_Clicktag"),
    "update_clicktag": (_is_update_clicktag, "Update_Clicktag"),
    "ftrack_impression": (_is_ftrack_impression, "Ftrack impression"),
    "ftrack_click": (_is_ftrack_click, "Ftrack click"),
    "protected": (_is_protected, "Protected Pixel"),
}

# requirement -> (required slots, forbidden slots)
_POLICY: dict[PixelRequirement, tuple[set[str], set[str]]] = {
    PixelRequirement.FTRACK: (
        {"ftrack_impression", "ftrack_click"},
        {"pixel", "static_clicktag", "update_clicktag"},
    ),
    PixelRequirement.NO_FTRACK: (
        {"pixel", "update_clicktag"},
        {"static_clicktag", "ftrack_impression", "ftrack_click"},
    ),
    PixelRequirement.CLICKTAG: (
        {"update_clicktag"},
        {"static_clicktag", "pixel", "ftrack_impression", "ftrack_click"},
    ),
    PixelRequirement.PROTECTED: (
        {"protected"},
        set(),
    ),
}


def _populated_slots(inventory: TagInventory, placement_id: str) -> tuple[set[str], list[str]]:
    present: set[str] = set()
    displayed: set[str] = []

    for source in inventory.by_placement.get(placement_id, []):
        for tag in source.row.tags:
            if not str(tag.raw or "").strip():
                continue

            normalized = _normalize_column(tag.column_name)
            if not normalized:
                continue

            for slot, (detector, _label) in _SLOTS.items():
                if detector(normalized):
                    present.add(slot)

            if tag.column_name not in displayed:
                displayed.append(tag.column_name)

    return present, sorted(displayed)


def _worked_policy_placements(ts_result) -> dict[str, dict]:
    worked_ids = {
        placement_id
        for placement_id, scope in ts_result.scope.items()
        if scope.request_type != REQ_NOT_WORKED
    }

    records: dict[str, dict] = {}

    for row in ts_result.placements.rows:
        placement_id = str(row.values.get("placement_id") or "").strip()

        if not placement_id or placement_id not in worked_ids:
            continue

        # Solo 1x1: para video/display la politica de columnas no aplica.
        if norm_dims(row.values.get("dimensions")) != "1x1":
            continue

        vendor_raw = str(row.values.get("vendors") or "").strip()
        requirements = classify_vendor_requirements(vendor_raw) & _COLUMN_POLICY_REQUIREMENTS

        if not requirements:
            continue

        record = records.setdefault(
            placement_id,
            {
                "placement_name": "",
                "site": "",
                "vendors": set(),
                "requirements": set(),
            },
        )

        if not record["placement_name"]:
            record["placement_name"] = str(row.values.get("placement_name") or "").strip()

        if not record["site"]:
            record["site"] = str(row.values.get("site") or "").strip()

        if vendor_raw:
            record["vendors"].add(vendor_raw)

        record["requirements"] |= requirements

    return records


def reconcile_adobe_tag_policy(ts_result, inventory: TagInventory) -> TagPolicyReconciliation:
    out = TagPolicyReconciliation()

    records = _worked_policy_placements(ts_result)

    for placement_id in sorted(records):
        record = records[placement_id]
        requirements = record["requirements"]

        required_slots: set[str] = set()
        forbidden_slots: set[str] = set()

        for requirement in requirements:
            req, forb = _POLICY[requirement]
            required_slots |= req
            forbidden_slots |= forb

        forbidden_slots -= required_slots

        common = {
            "placement_id": placement_id,
            "placement_name": record["placement_name"],
            "site": record["site"],
            "vendor_raw": " | ".join(sorted(record["vendors"])),
            "requirements": tuple(sorted(r.value for r in requirements)),
        }

        if not inventory.by_placement.get(placement_id):
            out.checks.append(
                TagPolicyCheck(
                    result="NOT_VERIFIED",
                    message="No tag row was found for this placement in the delivered tag file(s).",
                    recommended_action="Upload the tag file that covers this placement.",
                    **common,
                )
            )
            continue

        present, displayed = _populated_slots(inventory, placement_id)

        missing = sorted(_SLOTS[slot][1] for slot in required_slots if slot not in present)
        extra = sorted(_SLOTS[slot][1] for slot in forbidden_slots if slot in present)

        common["columns_found"] = tuple(displayed)
        common["required_missing"] = tuple(missing)
        common["forbidden_present"] = tuple(extra)

        if not missing and not extra:
            out.checks.append(
                TagPolicyCheck(
                    result="PASS",
                    message="Tag columns match the vendor requirement(s) declared in the Traffic Sheet.",
                    **common,
                )
            )
            continue

        problems = []
        if missing:
            problems.append(f"Missing required column(s): {', '.join(missing)}.")
        if extra:
            problems.append(f"Column(s) that should be empty carry content: {', '.join(extra)}.")

        out.checks.append(
            TagPolicyCheck(
                result="FAIL",
                message=" ".join(problems),
                recommended_action="Regenerate the tag file matching the declared vendor requirement(s).",
                **common,
            )
        )

    return out

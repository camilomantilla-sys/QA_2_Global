"""
Tag file coverage (TAG-013).

Camilo: "en ningun caso debes revisar los pixeles como tal, sino que
en la columna de placement ID esten todos los que la solicitud pide."

Every existing TAG-002/003 check reads FROM the delivered tag file's
own rows outward (does this row belong to Innovid, to scope). None of
them check the other direction: does every 1x1 placement the TS
declares a vendor requirement for actually have a row in the delivered
tag file(s) at all. This closes that gap -- coverage, not pixel
content.

Adobe only (1x1 Direct/Site-Served and Decision Tree): that's where
tag files are the deliverable. Only runs once at least one tag file
was uploaded, matching every other TAG rule's gating.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.adobe_pixel_reconciliation import classify_vendor_requirements
from core.normalize import norm_dims
from core.tag_inventory import TagInventory
from parsers.ts_parser import REQ_NOT_WORKED


@dataclass
class TagCoverageCheck:
    placement_id: str
    placement_name: str = ""
    vendor_raw: str = ""
    result: str = "PASS"
    message: str = ""


@dataclass
class TagCoverageReconciliation:
    checks: list[TagCoverageCheck] = field(default_factory=list)


def _worked_1x1_with_vendor(ts_result) -> dict[str, dict]:
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

        if norm_dims(row.values.get("dimensions")) != "1x1":
            continue

        vendor_raw = str(row.values.get("vendors") or "").strip()

        # Sin requisito reconocible no hay nada que exigir en el
        # archivo de tags para este placement.
        if not classify_vendor_requirements(vendor_raw):
            continue

        record = records.setdefault(
            placement_id,
            {"placement_name": "", "vendors": set()},
        )

        if not record["placement_name"]:
            record["placement_name"] = str(row.values.get("placement_name") or "").strip()

        if vendor_raw:
            record["vendors"].add(vendor_raw)

    return records


def reconcile_tag_coverage(ts_result, inventory: TagInventory) -> TagCoverageReconciliation:
    out = TagCoverageReconciliation()

    for placement_id, record in sorted(
        _worked_1x1_with_vendor(ts_result).items()
    ):
        vendor_raw = " | ".join(sorted(record["vendors"]))

        if inventory.by_placement.get(placement_id):
            out.checks.append(
                TagCoverageCheck(
                    placement_id=placement_id,
                    placement_name=record["placement_name"],
                    vendor_raw=vendor_raw,
                    result="PASS",
                    message="Placement is present in the delivered tag file(s).",
                )
            )
        else:
            out.checks.append(
                TagCoverageCheck(
                    placement_id=placement_id,
                    placement_name=record["placement_name"],
                    vendor_raw=vendor_raw,
                    result="REVIEW",
                    message=(
                        "The Traffic Sheet declares a vendor requirement "
                        "for this placement, but it has no row in any "
                        "delivered tag file."
                    ),
                )
            )

    return out

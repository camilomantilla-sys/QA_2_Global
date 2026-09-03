"""
DV Omni / DV Monitoring+Blocking tag-column reconciliation (DV-003).

Unlike DV Monitoring (DV-001: Pinnacle file for 1x1; PIX-002: placement
pixel for Display), DV Omni and DV Monitoring+Blocking are verified by
a column inside the delivered Innovid tag file, not by a placement-
level pixel or a separate Pinnacle file:

    DV Omni, 1x1 or Video
        Innovid tag file column doubleverify_vast must have content.
        No placement-level pixel is expected.

    DV Monitoring/Blocking, Display
        Innovid tag file column doubleverify_html must have content,
        IN ADDITION to the placement pixel PIX-002 already checks.

    DV Monitoring/Blocking, Video
        Camilo: "no deberia salir, es un callout ... se hace la misma
        lectura de DV Omni para video." Unusual combination -- flagged
        as a callout in the message, but read the same way as Omni
        Video (doubleverify_vast column).

Combinations the table doesn't define (Omni+Display, Monitoring-alone
+Video, an undetermined DV sub-type on Video) come back NOT_VERIFIED
instead of a guessed PASS/FAIL.

None of the files reviewed so far actually carry a doubleverify_vast
or doubleverify_html column, so this hasn't been validated against a
real export yet -- treat it as a first pass to confirm against
Camilo's next DV Omni example.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.dv_subtype import MONITORING, MONITORING_BLOCKING, OMNI, dv_subtype, is_dv
from core.normalize import clean_id, norm_compare, norm_dims
from core.tag_inventory import TagInventory
from parsers.ts_parser import REQ_CREATIVE_REMOVE

F_1X1 = "1x1"
F_VIDEO = "video"
F_DISPLAY = "display"
_VIDEO_DIMS = {"640x480", "1920x1080", "1280x720", "0x0"}

_NOT_RUNNING = ("stopped", "disabled", "inactive", "paused")

_DV_VAST = "DV_VAST"
_DV_HTML = "DV_HTML"


def _format_of(dims: object) -> str:
    normalized = norm_dims(dims)
    if normalized == F_1X1:
        return F_1X1
    if normalized in _VIDEO_DIMS:
        return F_VIDEO
    return F_DISPLAY


@dataclass
class DVOmniCheck:
    placement_id: str
    placement_name: str = ""
    vendor_raw: str = ""
    fmt: str = ""
    subtype: str = ""
    expected_column: str = ""
    result: str = "NOT_VERIFIED"
    message: str = ""
    recommended_action: str = ""


@dataclass
class DVOmniReconciliation:
    checks: list[DVOmniCheck] = field(default_factory=list)


def _column_has_content(inventory: TagInventory, placement_id: str, tag_type: str) -> bool:
    for source in inventory.by_placement.get(placement_id, []):
        for tag in source.row.tags:
            if tag.tag_type == tag_type and str(tag.raw or "").strip():
                return True
    return False


def _has_any_row(inventory: TagInventory, placement_id: str) -> bool:
    return bool(inventory.by_placement.get(placement_id))


def reconcile_dv_omni(ts_result, placement_view, tag_inventory: TagInventory) -> DVOmniReconciliation:
    out = DVOmniReconciliation()

    worked = {s.placement_id: s for s in ts_result.worked}
    if not worked or ts_result.placements is None:
        return out

    rows_by_placement = {}
    if placement_view is not None:
        for row in placement_view.rows:
            placement_id = clean_id(row.values.get("placement_id"))
            if placement_id:
                rows_by_placement.setdefault(placement_id, row)

    seen: set[str] = set()

    for ts_row in ts_result.placements.rows:
        placement_id = clean_id(ts_row.values.get("placement_id"))
        if not placement_id or placement_id not in worked or placement_id in seen:
            continue

        if worked[placement_id].request_type == REQ_CREATIVE_REMOVE:
            continue

        status_row = rows_by_placement.get(placement_id)
        if status_row is not None:
            status = norm_compare(status_row.values.get("status"))
            if status in _NOT_RUNNING:
                continue

        vendor_raw = str(ts_row.values.get("vendors") or "").strip()
        if not is_dv(vendor_raw):
            continue

        subtype = dv_subtype(vendor_raw)
        fmt = _format_of(ts_row.values.get("dimensions"))
        placement_name = str(ts_row.values.get("placement_name") or "").strip()

        common = dict(
            placement_id=placement_id,
            placement_name=placement_name,
            vendor_raw=vendor_raw,
            fmt=fmt,
            subtype=subtype or "",
        )

        # DV Monitoring alone: 1x1 goes through DV-001 (Pinnacle file),
        # Display goes through PIX-002 (placement pixel). Neither is
        # this module's job.
        if subtype == MONITORING and fmt in (F_1X1, F_DISPLAY):
            continue

        if subtype == OMNI and fmt in (F_1X1, F_VIDEO):
            tag_type, column_label = _DV_VAST, "doubleverify_vast"
        elif subtype == MONITORING_BLOCKING and fmt == F_DISPLAY:
            tag_type, column_label = _DV_HTML, "doubleverify_html"
        elif subtype == MONITORING_BLOCKING and fmt == F_VIDEO:
            tag_type, column_label = _DV_VAST, "doubleverify_vast"
        else:
            # Combination not covered by the current rules (Omni +
            # Display, Monitoring-alone + Video, or an undetermined
            # sub-type on Video): report it instead of guessing.
            seen.add(placement_id)
            if subtype == "UNDETERMINED":
                message = (
                    "Vendors / Pixels mentions DV but doesn't say "
                    "Omni, Monitoring or Blocking, so it isn't clear "
                    "which DV check applies to this placement."
                )
            else:
                message = (
                    f"DV {subtype or '?'} on {fmt} isn't a combination "
                    "the current rules define yet."
                )
            out.checks.append(
                DVOmniCheck(
                    result="NOT_VERIFIED",
                    message=message,
                    recommended_action=(
                        "Confirm with the team which DV check applies "
                        "to this placement."
                    ),
                    **common,
                )
            )
            continue

        seen.add(placement_id)
        common["expected_column"] = column_label

        callout = ""
        if subtype == MONITORING_BLOCKING and fmt == F_VIDEO:
            callout = (
                "DV Monitoring/Blocking on a Video placement is "
                "unusual -- flagging as a callout. "
            )

        if not _has_any_row(tag_inventory, placement_id):
            out.checks.append(
                DVOmniCheck(
                    result="NOT_VERIFIED",
                    message=(
                        callout
                        + "No tag row was found for this placement in "
                        "the delivered Innovid tag file(s)."
                    ),
                    recommended_action="Upload the tag file that covers this placement.",
                    **common,
                )
            )
            continue

        if _column_has_content(tag_inventory, placement_id, tag_type):
            out.checks.append(
                DVOmniCheck(
                    result="PASS",
                    message=(
                        callout
                        + f"The {column_label} column has content in the tag file."
                    ),
                    **common,
                )
            )
        else:
            out.checks.append(
                DVOmniCheck(
                    result="FAIL",
                    message=(
                        callout
                        + f"The tag file's {column_label} column is missing or empty."
                    ),
                    recommended_action=f"Populate the {column_label} column for this placement.",
                    **common,
                )
            )

    return out

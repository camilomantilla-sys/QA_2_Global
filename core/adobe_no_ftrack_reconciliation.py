"""
Adobe No Ftrack tag reconciliation.

Business requirement:

For each worked placement whose Traffic Sheet declares No Ftrack:

    Pixel populated
    Update_Clicktag populated
    Static_Clicktag empty
    Ftrack impression empty
    Ftrack click empty
    -> PASS

Validation is placement-centric. Workbook-level column presence is ignored.
Only populated cells for the specific Placement ID are evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from core.normalize import norm_compare
from core.tag_inventory import TagInventory
from parsers.ts_parser import REQ_NOT_WORKED


class NoFtrackResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    NOT_VERIFIED = "NOT_VERIFIED"


@dataclass(frozen=True)
class NoFtrackCheck:
    placement_id: str
    placement_name: str = ""
    site: str = ""
    request_type: str = ""
    vendor_raw: str = ""

    columns_found: tuple[str, ...] = ()
    normalized_columns: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    pixel_present: bool = False
    update_clicktag_present: bool = False
    static_clicktag_present: bool = False
    ftrack_impression_present: bool = False
    ftrack_click_present: bool = False

    result: str = NoFtrackResult.NOT_VERIFIED.value
    message: str = ""
    recommended_action: str = ""


@dataclass
class NoFtrackReconciliation:
    checks: list[NoFtrackCheck] = field(default_factory=list)

    @property
    def by_result(self) -> dict[str, int]:
        result = {
            NoFtrackResult.PASS.value: 0,
            NoFtrackResult.FAIL.value: 0,
            NoFtrackResult.REVIEW.value: 0,
            NoFtrackResult.NOT_VERIFIED.value: 0,
        }

        for check in self.checks:
            result[check.result] = (
                result.get(check.result, 0) + 1
            )

        return result

    @property
    def attention(self) -> list[NoFtrackCheck]:
        return [
            check
            for check in self.checks
            if check.result != NoFtrackResult.PASS.value
        ]


def _normalize_column(value: object) -> str:
    """
    Normalize tag column names.

    Examples:
        Update_Clicktag1       -> updateclicktag
        Static_Clicktag1       -> staticclicktag
        ftrack 1x1 imp         -> ftrack1x1imp
        ftrack 1x1 click       -> ftrack1x1click
        Protected Pixel        -> protectedpixel
    """
    normalized = re.sub(
        r"[^a-z0-9]",
        "",
        str(value or "").casefold(),
    )

    return normalized.rstrip("0123456789")


def _is_no_ftrack(value: object) -> bool:
    """
    Detect No Ftrack requirements using normalized business text.

    Accepted examples:
        No Ftrack
        No fTrack
        No F Track
        No-Ftrack
        No_Ftrack
        noFtrack
        Without Ftrack
        Non Ftrack

    A regular Ftrack requirement does not match this function.
    """
    raw = str(value or "").strip()

    if not raw:
        return False

    compact = re.sub(
        r"[^a-z0-9]",
        "",
        raw.casefold(),
    )

    if any(
        signature in compact
        for signature in (
            "noftrack",
            "nonftrack",
            "withoutftrack",
        )
    ):
        return True

    words = re.findall(
        r"[a-z0-9]+",
        raw.casefold(),
    )

    for index, word in enumerate(words):
        if word != "ftrack":
            continue

        previous_words = words[
            max(0, index - 2):index
        ]

        if any(
            previous in {
                "no",
                "non",
                "without",
            }
            for previous in previous_words
        ):
            return True

    return False


def _populated_columns(
    inventory: TagInventory,
    placement_id: str,
) -> tuple[set[str], list[str], list[str]]:
    """
    Return only populated tag cells for one Placement ID.
    """
    normalized_columns: set[str] = set()
    displayed_columns: set[str] = set()
    evidence: list[str] = []

    for source in inventory.by_placement.get(
        placement_id,
        [],
    ):
        for tag in source.row.tags:
            if not str(tag.raw or "").strip():
                continue

            original_name = str(
                tag.column_name or ""
            ).strip()

            normalized_name = _normalize_column(
                original_name
            )

            if not normalized_name:
                continue

            normalized_columns.add(normalized_name)
            displayed_columns.add(original_name)

            evidence.append(
                f"{source.file_name} | "
                f"{source.sheet} | "
                f"row {source.row.row} | "
                f"{original_name}"
            )

    return (
        normalized_columns,
        sorted(displayed_columns),
        sorted(set(evidence)),
    )


def _has_pixel(columns: set[str]) -> bool:
    """
    Detect the operational Pixel column for No Ftrack.

    Protected and DISQO columns do not satisfy the generic Pixel requirement.
    Ftrack impression pixels also do not satisfy it.
    """
    for column in columns:
        if column in {
            "pixel",
            "pixelhtml",
            "trackingpixel",
            "impressionpixel",
        }:
            return True

        if (
            "pixel" in column
            and "protected" not in column
            and "disqo" not in column
            and "ftrack" not in column
            and "ispot" not in column
        ):
            return True

    return False


def _has_update_clicktag(columns: set[str]) -> bool:
    return "updateclicktag" in columns


def _has_static_clicktag(columns: set[str]) -> bool:
    return "staticclicktag" in columns


def _has_ftrack_impression(columns: set[str]) -> bool:
    return any(
        column.startswith("ftrack")
        and (
            "imp" in column
            or "impression" in column
        )
        for column in columns
    )


def _has_ftrack_click(columns: set[str]) -> bool:
    return any(
        column.startswith("ftrack")
        and "click" in column
        for column in columns
    )


def _worked_no_ftrack_placements(
    ts_result,
) -> dict[str, dict]:
    """
    Materialize one record per worked placement that requires No Ftrack.
    """
    worked_ids = {
        placement_id
        for placement_id, scope in ts_result.scope.items()
        if scope.request_type != REQ_NOT_WORKED
    }

    records: dict[str, dict] = {}

    for row in ts_result.placements.rows:
        placement_id = str(
            row.values.get("placement_id") or ""
        ).strip()

        if (
            not placement_id
            or placement_id not in worked_ids
        ):
            continue

        vendor_raw = str(
            row.values.get("vendors") or ""
        ).strip()

        if not _is_no_ftrack(vendor_raw):
            continue

        record = records.setdefault(
            placement_id,
            {
                "placement_name": "",
                "site": "",
                "request_type": "",
                "vendors": set(),
            },
        )

        if not record["placement_name"]:
            record["placement_name"] = str(
                row.values.get("placement_name") or ""
            ).strip()

        if not record["site"]:
            record["site"] = str(
                row.values.get("site") or ""
            ).strip()

        if vendor_raw:
            record["vendors"].add(vendor_raw)

        scope = ts_result.scope.get(placement_id)

        if scope is not None:
            record["request_type"] = str(
                scope.request_type or ""
            )

    return records


def reconcile_adobe_no_ftrack(
    ts_result,
    inventory: TagInventory,
) -> NoFtrackReconciliation:
    result = NoFtrackReconciliation()

    requirements = _worked_no_ftrack_placements(
        ts_result
    )

    for placement_id in sorted(requirements):
        requirement = requirements[placement_id]

        (
            normalized_columns,
            displayed_columns,
            evidence,
        ) = _populated_columns(
            inventory,
            placement_id,
        )

        pixel_present = _has_pixel(
            normalized_columns
        )

        update_present = _has_update_clicktag(
            normalized_columns
        )

        static_present = _has_static_clicktag(
            normalized_columns
        )

        ftrack_imp_present = _has_ftrack_impression(
            normalized_columns
        )

        ftrack_click_present = _has_ftrack_click(
            normalized_columns
        )

        common = {
            "placement_id": placement_id,
            "placement_name": requirement[
                "placement_name"
            ],
            "site": requirement["site"],
            "request_type": requirement[
                "request_type"
            ],
            "vendor_raw": " | ".join(
                sorted(requirement["vendors"])
            ),
            "columns_found": tuple(
                displayed_columns
            ),
            "normalized_columns": tuple(
                sorted(normalized_columns)
            ),
            "evidence": tuple(evidence),
            "pixel_present": pixel_present,
            "update_clicktag_present": (
                update_present
            ),
            "static_clicktag_present": (
                static_present
            ),
            "ftrack_impression_present": (
                ftrack_imp_present
            ),
            "ftrack_click_present": (
                ftrack_click_present
            ),
        }

        problems: list[str] = []
        actions: list[str] = []

        if not inventory.by_placement.get(
            placement_id
        ):
            problems.append(
                "No tag row was found for the placement."
            )
            actions.append(
                "Generate the tag file for this Placement ID."
            )
        else:
            if not pixel_present:
                problems.append(
                    "The required Pixel value is missing."
                )
                actions.append(
                    "Populate the Pixel column."
                )

            if not update_present:
                problems.append(
                    "Update_Clicktag is missing."
                )
                actions.append(
                    "Populate Update_Clicktag."
                )

            if static_present:
                problems.append(
                    "Static_Clicktag is present."
                )
                actions.append(
                    "Remove the populated Static_Clicktag value."
                )

            if ftrack_imp_present:
                problems.append(
                    "Ftrack impression is present."
                )
                actions.append(
                    "Remove the populated Ftrack impression value."
                )

            if ftrack_click_present:
                problems.append(
                    "Ftrack click is present."
                )
                actions.append(
                    "Remove the populated Ftrack click value."
                )

        if problems:
            result.checks.append(
                NoFtrackCheck(
                    result=NoFtrackResult.FAIL.value,
                    message=" ".join(problems),
                    recommended_action=" ".join(
                        actions
                    ),
                    **common,
                )
            )
            continue

        result.checks.append(
            NoFtrackCheck(
                result=NoFtrackResult.PASS.value,
                message=(
                    "Pixel and Update_Clicktag are populated, "
                    "while Static_Clicktag and Ftrack values "
                    "are absent."
                ),
                recommended_action=(
                    "No correction is required."
                ),
                **common,
            )
        )

    return result

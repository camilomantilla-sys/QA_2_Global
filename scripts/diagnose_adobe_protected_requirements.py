"""
PIX-A05 | Adobe Protected diagnostic.

Business rule:

Adobe Site-Served 1x1:
    A populated Protected column in the delivered tag file is required.

Adobe Third Party Display or Video:
    Protected tag validation is not applicable.

Site-Served 1x1 is identified from the delivered tag structure:
    - ftrack 1x1 imp
    - ftrack 1x1 click

Media dimensions alone are not used because a Site-Served 1x1
implementation may retain display or video media dimensions in the
Traffic Sheet.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from core.tag_inventory import build_tag_inventory
from parsers.ts_parser import REQ_NOT_WORKED, parse_ts


CASE_DIR = Path(
    "tests/test_adobe_1x1_3pd_direct"
)

TS_PATH = CASE_DIR / (
    "TS_FY26_Q4_AMER_Creative_STEDiscover_"
    "Awareness_Discover_ASY_C.xlsx"
)


def get_tag_paths() -> list:
    """Return all tag workbooks in the Adobe regression case."""

    return sorted(
        (
            path
            for path in CASE_DIR.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in {
                ".xlsx",
                ".xlsm",
            }
            and path.name.casefold().startswith("tags")
            and not path.name.startswith("~$")
        ),
        key=lambda path: (
            str(path.parent).casefold(),
            path.name.casefold(),
        ),
    )


def normalize_column(value: object) -> str:
    """Normalize tag column names for family detection."""

    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value or "").casefold(),
    )


def requires_protected(value: object) -> bool:
    """Return True when Vendors / Pixels requests Protected."""

    return "protected" in str(value or "").casefold()


def get_worked_ids(ts_result) -> set:
    """Return canonical worked placements, excluding context rows."""

    return {
        str(placement_id).strip()
        for placement_id, scope in ts_result.scope.items()
        if str(placement_id).strip()
        and scope.request_type != REQ_NOT_WORKED
    }


def source_sheet(source) -> str:
    """Read the originating worksheet without assuming one attribute."""

    return (
        getattr(source, "sheet_name", "")
        or getattr(source, "sheet", "")
        or getattr(
            getattr(source, "result", None),
            "sheet",
            "",
        )
        or "Tags"
    )


def populated_columns_for_placement(
    inventory,
    placement_id: str,
) -> tuple[set[str], list[str], list[str]]:
    """
    Return:
      - normalized populated columns
      - original populated column names
      - source evidence
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

            normalized_name = normalize_column(
                original_name
            )

            if not normalized_name:
                continue

            normalized_columns.add(normalized_name)
            displayed_columns.add(original_name)

            evidence.append(
                f"{source.file_name} | "
                f"{source_sheet(source)} | "
                f"row {source.row.row} | "
                f"{original_name}"
            )

    return (
        normalized_columns,
        sorted(displayed_columns),
        sorted(set(evidence)),
    )


def is_ftrack_impression(column: str) -> bool:
    """Identify a populated Ftrack impression column."""

    return (
        column.startswith("ftrack")
        and (
            "imp" in column
            or "impression" in column
        )
    )


def is_ftrack_click(column: str) -> bool:
    """Identify a populated Ftrack click column."""

    return (
        column.startswith("ftrack")
        and "click" in column
    )


def is_protected_column(column: str) -> bool:
    """Identify all supported Protected tag column variants."""

    return "protectedpixel" in column


def main() -> None:
    ts_result = parse_ts(TS_PATH)
    tag_paths = get_tag_paths()
    inventory = build_tag_inventory(tag_paths)

    worked_ids = get_worked_ids(ts_result)

    requirements: dict[str, dict] = {}

    for row in ts_result.placements.rows:
        placement_id = str(
            row.values.get("placement_id")
            or ""
        ).strip()

        if placement_id not in worked_ids:
            continue

        vendor_raw = str(
            row.values.get("vendors")
            or row.values.get("vendor")
            or row.values.get("pixels")
            or ""
        ).strip()

        if not requires_protected(vendor_raw):
            continue

        record = requirements.setdefault(
            placement_id,
            {
                "vendors": set(),
                "placement_name": "",
                "site": "",
                "dimensions": "",
                "request_type": "",
            },
        )

        if vendor_raw:
            record["vendors"].add(vendor_raw)

        if not record["placement_name"]:
            record["placement_name"] = str(
                row.values.get("placement_name")
                or ""
            ).strip()

        if not record["site"]:
            record["site"] = str(
                row.values.get("site")
                or ""
            ).strip()

        if not record["dimensions"]:
            record["dimensions"] = str(
                row.values.get("dimensions")
                or row.values.get("dims")
                or ""
            ).strip()

        scope = ts_result.scope.get(placement_id)

        if scope is not None:
            record["request_type"] = str(
                scope.request_type or ""
            ).strip()

    status_counts: Counter[str] = Counter()
    details: list[dict] = []

    for placement_id in sorted(requirements):
        requirement = requirements[placement_id]

        (
            normalized_columns,
            displayed_columns,
            evidence,
        ) = populated_columns_for_placement(
            inventory,
            placement_id,
        )

        ftrack_impression_present = any(
            is_ftrack_impression(column)
            for column in normalized_columns
        )

        ftrack_click_present = any(
            is_ftrack_click(column)
            for column in normalized_columns
        )

        # The delivered tag structure determines whether this is
        # Site-Served 1x1. Media dimensions are not sufficient.
        is_site_served_1x1 = (
            ftrack_impression_present
            or ftrack_click_present
        )

        protected_columns = sorted(
            original_name
            for original_name in displayed_columns
            if is_protected_column(
                normalize_column(original_name)
            )
        )

        protected_present = bool(protected_columns)

        if not is_site_served_1x1:
            status = "N/A"
            message = (
                "Protected tag validation is not applicable "
                "to Adobe Third Party Display or Video."
            )
            action = "No correction is required."

        elif protected_present:
            status = "PASS"
            message = (
                "Protected is correctly included "
                "in the 1x1 tag file."
            )
            action = "No correction is required."

        else:
            status = "FAIL"
            message = (
                "Protected is required, but no populated "
                "Protected tag column was found."
            )
            action = (
                "Add the required Protected pixel to the "
                "Site-Served 1x1 tag file."
            )

        status_counts[status] += 1

        details.append(
            {
                "status": status,
                "placement_id": placement_id,
                "placement_name": requirement[
                    "placement_name"
                ],
                "site": requirement["site"],
                "dimensions": requirement[
                    "dimensions"
                ],
                "request_type": requirement[
                    "request_type"
                ],
                "vendor": " | ".join(
                    sorted(requirement["vendors"])
                ),
                "all_columns": displayed_columns,
                "protected_columns": protected_columns,
                "ftrack_impression": (
                    ftrack_impression_present
                ),
                "ftrack_click": (
                    ftrack_click_present
                ),
                "message": message,
                "action": action,
                "evidence": evidence,
            }
        )

    print("=" * 105)
    print("PIX-A05 | ADOBE PROTECTED DIAGNOSTIC")
    print("=" * 105)

    print()
    print("INPUTS")
    print(f"Traffic Sheet        : {TS_PATH.name}")
    print(f"Tag files            : {len(tag_paths)}")
    print(
        "Tag inventory rows   : "
        f"{inventory.distinct_placements}"
    )
    print(
        "Fatal tag files      : "
        f"{len(inventory.parse_failures)}"
    )

    print()
    print("COVERAGE")
    print(
        "Worked placements    : "
        f"{len(worked_ids)}"
    )
    print(
        "Protected placements : "
        f"{len(requirements)}"
    )

    print()
    print("STATUS")

    for status in (
        "PASS",
        "FAIL",
        "N/A",
        "REVIEW",
        "NOT_VERIFIED",
    ):
        print(
            f"{status:20}: "
            f"{status_counts.get(status, 0)}"
        )

    print()
    print("DETAIL")

    for item in details:
        print("-" * 105)
        print(
            f"Result              : {item['status']}"
        )
        print(
            f"Placement ID        : "
            f"{item['placement_id']}"
        )
        print(
            f"Placement Name      : "
            f"{item['placement_name']}"
        )
        print(
            f"Site                : {item['site']}"
        )
        print(
            f"Dimensions          : "
            f"{item['dimensions']}"
        )
        print(
            f"Request Type        : "
            f"{item['request_type']}"
        )
        print(
            f"Vendor TS           : {item['vendor']}"
        )
        print(
            f"Ftrack impression   : "
            f"{item['ftrack_impression']}"
        )
        print(
            f"Ftrack click        : "
            f"{item['ftrack_click']}"
        )
        print(
            f"Protected columns   : "
            f"{item['protected_columns']}"
        )
        print(
            f"Message             : {item['message']}"
        )
        print(
            f"Recommended Action  : "
            f"{item['action']}"
        )

        if item["status"] == "PASS":
            for evidence_line in item["evidence"]:
                if "protected" in evidence_line.casefold():
                    print(
                        f"Evidence            : "
                        f"{evidence_line}"
                    )

    print()
    print("ATTENTION REQUIRED")

    attention = [
        item
        for item in details
        if item["status"] in {
            "FAIL",
            "REVIEW",
            "NOT_VERIFIED",
        }
    ]

    if not attention:
        print("None")
    else:
        for item in attention:
            print(
                f"{item['status']:8} | "
                f"{item['placement_id']} | "
                f"{item['message']}"
            )

    print()
    print("=" * 105)


if __name__ == "__main__":
    main()

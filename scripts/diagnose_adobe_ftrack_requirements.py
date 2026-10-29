"""
Adobe Ftrack requirements diagnostic.

Traffic Sheet:
    Vendors / Pixels contains Ftrack.

Tag files:
    Validates populated cells per Placement ID.

This script is diagnostic only and does not affect the QA2 verdict.
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

TS_PATH = (
    CASE_DIR
    / "TS_FY26_Q4_AMER_Creative_STEDiscover_"
    "Awareness_Discover_ASY_C.xlsx"
)


def get_tag_paths() -> list:
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
    normalized = re.sub(
        r"[^a-z0-9]",
        "",
        str(value or "").casefold(),
    )

    return normalized.rstrip("0123456789")


def requires_ftrack(value: object) -> bool:
    """
    Detect a positive Ftrack requirement.

    No Ftrack is explicitly excluded.
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
        return False

    return "ftrack" in compact


def populated_columns_for_placement(
    inventory,
    placement_id: str,
) -> tuple[set[str], list[str], list[str]]:
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
                f"{source.sheet} | "
                f"row {source.row.row} | "
                f"{original_name}"
            )

    return (
        normalized_columns,
        sorted(displayed_columns),
        sorted(set(evidence)),
    )


def is_ftrack_impression(column: str) -> bool:
    return (
        column.startswith("ftrack")
        and (
            "imp" in column
            or "impression" in column
        )
    )


def is_ftrack_click(column: str) -> bool:
    return (
        column.startswith("ftrack")
        and "click" in column
    )


def main() -> None:
    ts_result = parse_ts(TS_PATH)
    tag_paths = get_tag_paths()
    inventory = build_tag_inventory(tag_paths)

    worked_ids = {
        placement_id
        for placement_id, scope in ts_result.scope.items()
        if scope.request_type != REQ_NOT_WORKED
    }

    requirements: dict[str, dict] = {}

    for row in ts_result.placements.rows:
        placement_id = str(
            row.values.get("placement_id") or ""
        ).strip()

        if placement_id not in worked_ids:
            continue

        vendor_raw = str(
            row.values.get("vendors") or ""
        ).strip()

        if not requires_ftrack(vendor_raw):
            continue

        record = requirements.setdefault(
            placement_id,
            {
                "vendors": set(),
                "placement_name": "",
                "site": "",
                "dimensions": "",
            },
        )

        if vendor_raw:
            record["vendors"].add(vendor_raw)

        if not record["placement_name"]:
            record["placement_name"] = str(
                row.values.get("placement_name") or ""
            ).strip()

        if not record["site"]:
            record["site"] = str(
                row.values.get("site") or ""
            ).strip()

        if not record["dimensions"]:
            record["dimensions"] = str(
                row.values.get("dimensions") or ""
            ).strip()

    status_counts: Counter[str] = Counter()
    details = []

    for placement_id in sorted(requirements):
        requirement = requirements[placement_id]

        placement_dimensions = str(
            requirement.get("dimensions") or ""
        ).strip()

        normalized_dimensions = (
            placement_dimensions
            .casefold()
            .replace(" ", "")
            .replace("*", "x")
            .replace("×", "x")
        )

        is_site_served_1x1 = (
            normalized_dimensions == "1x1"
        )

        # Adobe applicability rule:
        #
        # Ftrack impression and click columns are validated only
        # for Site-Served 1x1 placements.
        #
        # Third Party Display and Video placements use their
        # delivered display/video tags and are N/A for PIX-A03.
        if not is_site_served_1x1:
            status_counts["N/A"] += 1

            details.append(
                {
                    "status": "N/A",
                    "placement_id": placement_id,
                    "vendor": " | ".join(
                        sorted(requirement["vendors"])
                    ),
                    "site": requirement["site"],
                    "dimensions": placement_dimensions,
                    "columns": [],
                    "impression": False,
                    "click": False,
                    "message": (
                        "Ftrack 1x1 column validation is not "
                        "applicable to Adobe Third Party Display "
                        "or Video placements."
                    ),
                    "evidence": [],
                }
            )
            continue

        (
            normalized_columns,
            displayed_columns,
            evidence,
        ) = populated_columns_for_placement(
            inventory,
            placement_id,
        )

        impression_present = any(
            is_ftrack_impression(column)
            for column in normalized_columns
        )

        click_present = any(
            is_ftrack_click(column)
            for column in normalized_columns
        )

        has_tag_row = bool(
            inventory.by_placement.get(placement_id)
        )

        problems = []

        if not has_tag_row:
            problems.append(
                "No tag row was found."
            )
        else:
            if not impression_present:
                problems.append(
                    "Ftrack impression is missing."
                )

            if not click_present:
                problems.append(
                    "Ftrack click is missing."
                )

        status = "FAIL" if problems else "PASS"
        status_counts[status] += 1

        details.append(
            {
                "status": status,
                "placement_id": placement_id,
                "vendor": " | ".join(
                    sorted(requirement["vendors"])
                ),
                "site": requirement["site"],
                "dimensions": requirement["dimensions"],
                "columns": displayed_columns,
                "impression": impression_present,
                "click": click_present,
                "message": (
                    " ".join(problems)
                    if problems
                    else (
                        "Ftrack impression and click are "
                        "populated for this placement."
                    )
                ),
                "evidence": evidence,
            }
        )

    print("=" * 105)
    print("PIX-A03 | ADOBE FTRACK TAG DIAGNOSTIC")
    print("=" * 105)

    print()
    print("COVERAGE")
    print(f"Worked placements       : {len(worked_ids)}")
    print(f"Ftrack placements       : {len(requirements)}")
    print(f"Tag files               : {len(tag_paths)}")
    print(
        f"Tag inventory placements: "
        f"{inventory.distinct_placements}"
    )

    print()
    print("STATUS")
    print(
        f"PASS                    : "
        f"{status_counts.get('PASS', 0)}"
    )
    print(
        f"FAIL                    : "
        f"{status_counts.get('FAIL', 0)}"
    )
    print(
        f"N/A                     : "
        f"{status_counts.get('N/A', 0)}"
    )

    print()
    print("DETAIL")

    for item in details:
        print("-" * 105)
        print(
            f"Result              : {item['status']}"
        )
        print(
            f"Placement ID        : {item['placement_id']}"
        )
        print(
            f"Vendor TS           : {item['vendor']}"
        )
        print(
            f"Site                : {item['site']}"
        )
        print(
            f"Dimensions          : {item['dimensions']}"
        )
        print(
            f"Columns found       : {item['columns']}"
        )
        print(
            f"Ftrack impression   : {item['impression']}"
        )
        print(
            f"Ftrack click        : {item['click']}"
        )
        print(
            f"Message             : {item['message']}"
        )

        for evidence in item["evidence"]:
            print(
                f"Evidence            : {evidence}"
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

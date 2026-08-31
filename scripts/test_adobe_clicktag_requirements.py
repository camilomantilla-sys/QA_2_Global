"""
Diagnostic test for Adobe Click tag only requirements.

Business rule:
    Click tag only:
      - Update_Clicktag must be populated.
      - Static_Clicktag must not be present or populated.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from core.tag_inventory import build_tag_inventory
from parsers.ts_parser import parse_ts


CASE_DIR = Path("tests/test_adobe_1x1_3pd_direct")

TS_PATH = CASE_DIR / (
    "TS_FY26_Q4_AMER_Creative_STEDiscover_"
    "Awareness_Discover_ASY_C.xlsx"
)

TAG_DIRS = [
    CASE_DIR / "new_1x1_tags",
    CASE_DIR / "new_3p_tags",
]


def _normalize_tag_column(value: object) -> str:
    """Normalize operational tag column names."""
    normalized = re.sub(
        r"[^a-z0-9]",
        "",
        str(value or "").casefold(),
    )

    return normalized.rstrip("0123456789")


def populated_columns_for_placement(
    inventory,
    placement_id: str,
) -> tuple[set[str], list[str], list[str]]:
    """
    Return populated tag cells for one Placement ID.

    The workbook-level existence of a column is not evidence.
    Only a populated cell on the placement row is included.
    """
    normalized_columns: set[str] = set()
    displayed_columns: set[str] = set()
    evidence: list[str] = []

    for source in inventory.by_placement.get(
        str(placement_id).strip(),
        [],
    ):
        for tag in source.row.tags:
            if not str(tag.raw or "").strip():
                continue

            original_name = str(
                tag.column_name or ""
            ).strip()

            normalized_name = _normalize_tag_column(
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


def _normalized_tag_column_name(value: object) -> str:
    """
    Normalize a tag column without losing its operational meaning.

    Examples:
        Update_Clicktag1  -> updateclicktag
        Update Clicktag   -> updateclicktag
        Static_Clicktag1  -> staticclicktag
        ftrack 1x1 imp    -> ftrack1x1imp
    """
    import re

    normalized = re.sub(
        r"[^a-z0-9]",
        "",
        str(value or "").casefold(),
    )

    return normalized.rstrip("0123456789")


def _populated_tag_columns(
    inventory,
    placement_id: str,
) -> tuple[set[str], list[str]]:
    """
    Return only columns whose cell is populated for this Placement ID.

    Workbook-level column presence is intentionally ignored.
    """
    columns: set[str] = set()
    evidence: list[str] = []

    for source in inventory.by_placement.get(
        placement_id,
        [],
    ):
        for tag in source.row.tags:
            if not str(tag.raw or "").strip():
                continue

            column_key = _normalized_tag_column_name(
                tag.column_name
            )

            columns.add(column_key)

            evidence.append(
                f"{source.file_name} | "
                f"{source.sheet} | "
                f"row {source.row.row} | "
                f"{tag.column_name}"
            )

    return columns, evidence


def normalized_column(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value or "").casefold(),
    )


def get_tag_paths() -> list:
    """
    Find every delivered tag file under the real Adobe test case.

    Recursive discovery avoids dependency on temporary folder names.
    Only files whose names begin with TAGS are included.
    """
    return sorted(
        (
            file_path
            for file_path in CASE_DIR.rglob("*")
            if file_path.is_file()
            and file_path.suffix.casefold() in {".xlsx", ".xlsm"}
            and file_path.name.casefold().startswith("tags")
            and not file_path.name.startswith("~$")
        ),
        key=lambda file_path: (
            str(file_path.parent).casefold(),
            file_path.name.casefold(),
        ),
    )


def is_clicktag_only(value: object) -> bool:
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").casefold(),
    ).strip()

    return normalized in {
        "click tag only",
        "clicktag only",
        "click tag",
        "clicktag",
    }


def main() -> None:
    ts_result = parse_ts(TS_PATH)
    inventory = build_tag_inventory(get_tag_paths())

    vendor_by_placement: dict[str, str] = {}

    for row in ts_result.placements.rows:
        placement_id = str(
            row.values.get("placement_id") or ""
        ).strip()

        vendor = str(
            row.values.get("vendors")
            or row.values.get("vendor")
            or row.values.get("pixels")
            or ""
        ).strip()

        if placement_id and vendor:
            vendor_by_placement[placement_id] = vendor

    results = []
    counts = Counter()

    for placement_id, vendor in sorted(
        vendor_by_placement.items()
    ):
        if not is_clicktag_only(vendor):
            continue

        sources = inventory.by_placement.get(
            placement_id,
            [],
        )

        populated_columns: set[str] = set()
        source_details = []

        for source in sources:
            for tag in source.row.tags:
                if tag.is_empty:
                    continue

                populated_columns.add(
                    tag.column_name
                )

                source_details.append(
                    {
                        "file": source.file_name,
                        "sheet": (
                            getattr(source, "sheet_name", "")
                            or getattr(source, "sheet", "")
                            or getattr(
                                getattr(source, "result", None),
                                "sheet",
                                "",
                            )
                        ),
                        "row": source.row.row,
                        "column": tag.column_name,
                    }
                )

        normalized_columns = {
            normalized_column(column)
            for column in populated_columns
        }

        has_update_clicktag = any(
            "updateclicktag" in column
            for column in normalized_columns
        )

        has_static_clicktag = any(
            "staticclicktag" in column
            for column in normalized_columns
        )

        if (
            has_update_clicktag
            and not has_static_clicktag
        ):
            status = "PASS"
            message = (
                "Update_Clicktag is present and "
                "Static_Clicktag is absent."
            )
            action = "No correction is required."
        else:
            status = "FAIL"

            problems = []

            if not has_update_clicktag:
                problems.append(
                    "Update_Clicktag is missing"
                )

            if has_static_clicktag:
                problems.append(
                    "Static_Clicktag is present"
                )

            message = "; ".join(problems) + "."
            action = (
                "Keep only the populated Update_Clicktag "
                "column for this Click tag only placement."
            )

        counts[status] += 1

        results.append(
            {
                "placement_id": placement_id,
                "vendor": vendor,
                "status": status,
                "message": message,
                "action": action,
                "columns": sorted(populated_columns),
                "sources": source_details,
            }
        )

    print("=" * 100)
    print("PIX-A02 | ADOBE CLICK TAG ONLY DIAGNOSTIC")
    print("=" * 100)

    print()
    print("COVERAGE")
    print(
        f"Click tag only placements : {len(results)}"
    )

    print()
    print("STATUS")

    for status in (
        "PASS",
        "FAIL",
        "REVIEW",
        "NOT_VERIFIED",
    ):
        print(
            f"{status:20}: {counts.get(status, 0)}"
        )

    print()
    print("DETAIL")

    for result in results:
        print("-" * 100)
        print(
            f"Result              : {result['status']}"
        )
        print(
            f"Placement ID        : {result['placement_id']}"
        )
        print(
            f"Vendor TS           : {result['vendor']}"
        )
        print(
            f"Columns found       : {result['columns']}"
        )
        print(
            f"Message             : {result['message']}"
        )
        print(
            f"Recommended Action  : {result['action']}"
        )

        for source in result["sources"]:
            print(
                "Evidence            : "
                f"{source['file']} | "
                f"{source['sheet']} | "
                f"row {source['row']} | "
                f"{source['column']}"
            )

    print()
    print("ATTENTION REQUIRED")

    attention = [
        result
        for result in results
        if result["status"] != "PASS"
    ]

    if not attention:
        print("None")
    else:
        for result in attention:
            print(
                f"{result['status']:8} | "
                f"{result['placement_id']} | "
                f"{result['message']}"
            )

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()

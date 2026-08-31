"""
Diagnostic of Adobe tag requirements.

Compares, at placement level:

Traffic Sheet Vendors / Pixels
vs
columns and tag types found across multiple tag files.

This script is diagnostic only:
- It does not modify files.
- It does not emit QA2 Findings.
- It does not change the final verdict.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from core.normalize import norm_compare
from core.tag_inventory import build_tag_inventory
from parsers.ts_parser import REQ_NOT_WORKED, parse_ts


CASE_DIR = Path("tests/test_adobe_1x1_3pd_direct")

TS_PATH = (
    CASE_DIR
    / "TS_FY26_Q4_AMER_Creative_STEDiscover_Awareness_Discover_ASY_C.xlsx"
)

TAG_DIRS = [
    CASE_DIR / "new_1x1_tags",
    CASE_DIR / "new_3p_tags",
]


def get_tag_paths() -> list[Path]:
    """Return all supported tag files from the configured folders."""

    paths: list[Path] = []

    for directory in TAG_DIRS:
        if not directory.exists():
            continue

        paths.extend(directory.glob("*.xlsx"))
        paths.extend(directory.glob("*.xlsm"))

    return sorted(
        paths,
        key=lambda path: path.name.casefold(),
    )


def classify_vendor(value: object) -> set[str]:
    """
    Classify the Vendors / Pixels text from the Traffic Sheet.

    One placement may contain more than one requirement.

    Recognized Adobe requirements:
    - CLICKTAG
    - FTRACK
    - NO_FTRACK
    - DISQO
    - PROTECTED
    - ISPOT
    """

    text = norm_compare(str(value or ""))
    requirements: set[str] = set()

    if not text:
        return requirements

    compact = (
        text.replace("-", " ")
        .replace("_", " ")
    )

    if "no ftrack" in compact:
        requirements.add("NO_FTRACK")
    elif "ftrack" in compact:
        requirements.add("FTRACK")

    if (
        "clicktag" in compact
        or "click tag" in compact
    ):
        requirements.add("CLICKTAG")

    if "disqo" in compact:
        requirements.add("DISQO")

    if "protected" in compact:
        requirements.add("PROTECTED")

    if (
        "ispot" in compact
        or "i spot" in compact
    ):
        requirements.add("ISPOT")

    return requirements


def main() -> None:
    if not TS_PATH.exists():
        raise SystemExit(
            f"Traffic Sheet not found: {TS_PATH}"
        )

    tag_paths = get_tag_paths()

    if not tag_paths:
        raise SystemExit(
            "No tag files were found in the configured folders."
        )

    ts_result = parse_ts(TS_PATH)
    inventory = build_tag_inventory(tag_paths)

    if ts_result.fatal:
        print("FATAL TRAFFIC SHEET ANOMALIES")

        for anomaly in ts_result.anomalies:
            if anomaly.severity == "FATAL":
                print(
                    f"{anomaly.code} | "
                    f"{anomaly.message}"
                )

        raise SystemExit(
            "The Traffic Sheet could not be parsed."
        )

    if ts_result.placements is None:
        raise SystemExit(
            "The Traffic Sheet has no parsed Placements sheet."
        )

    worked_ids = {
        placement_id
        for placement_id, scope in ts_result.scope.items()
        if scope.request_type != REQ_NOT_WORKED
    }

    placement_rows = defaultdict(list)

    for row in ts_result.placements.rows:
        placement_id = str(
            row.values.get("placement_id") or ""
        ).strip()

        if placement_id in worked_ids:
            placement_rows[placement_id].append(row)

    raw_vendor_counts: Counter[str] = Counter()
    requirement_counts: Counter[str] = Counter()
    tag_column_counts: Counter[str] = Counter()
    tag_type_counts: Counter[str] = Counter()

    unclassified_vendor_values: Counter[str] = Counter()

    placements_without_vendor: list[str] = []
    placements_without_tag_rows: list[str] = []

    detail_rows: list[dict] = []

    for placement_id in sorted(worked_ids):
        rows = placement_rows.get(placement_id, [])

        raw_values = {
            str(row.values.get("vendors") or "").strip()
            for row in rows
            if str(
                row.values.get("vendors") or ""
            ).strip()
        }

        raw_vendor_text = " | ".join(
            sorted(raw_values)
        )

        requirements: set[str] = set()

        for raw_value in raw_values:
            raw_vendor_counts[raw_value] += 1
            requirements |= classify_vendor(raw_value)

        if not raw_values:
            placements_without_vendor.append(
                placement_id
            )

        if raw_values and not requirements:
            for raw_value in raw_values:
                unclassified_vendor_values[
                    raw_value
                ] += 1

        for requirement in requirements:
            requirement_counts[requirement] += 1

        sources = inventory.by_placement.get(
            placement_id,
            [],
        )

        if not sources:
            placements_without_tag_rows.append(
                placement_id
            )

        columns_present: set[str] = set()
        types_present: set[str] = set()
        files_present: set[str] = set()

        for source in sources:
            files_present.add(source.file_name)

            for tag in source.row.tags:
                columns_present.add(
                    tag.column_name
                )

                types_present.add(
                    tag.tag_type
                )

                tag_column_counts[
                    tag.column_name
                ] += 1

                tag_type_counts[
                    tag.tag_type
                ] += 1

        detail_rows.append(
            {
                "placement_id": placement_id,
                "vendor_raw": raw_vendor_text,
                "requirements": sorted(
                    requirements
                ),
                "columns": sorted(
                    columns_present
                ),
                "types": sorted(
                    types_present
                ),
                "files": sorted(
                    files_present
                ),
            }
        )

    print("=" * 110)
    print("ADOBE TAG REQUIREMENTS DIAGNOSTIC")
    print("=" * 110)

    print()
    print("DOCUMENTS")
    print(f"Traffic Sheet                 : {TS_PATH.name}")
    print(f"Implementation model          : {ts_result.profile}")
    print(f"Tag files processed           : {len(tag_paths)}")
    print(
        "Tag files with fatal errors  : "
        f"{len(inventory.parse_failures)}"
    )

    print()
    print("CAMPAIGN")
    campaign_id = str(
        (ts_result.campaign_info or {}).get("campaignid")
        or ""
    ).strip()

    print(
        "Traffic Sheet Campaign ID    : "
        f"{campaign_id or '-'}"
    )
    print(
        "Tag Campaign IDs             : "
        f"{dict(inventory.campaigns)}"
    )

    print()
    print("COVERAGE")
    print(
        "Worked placements            : "
        f"{len(worked_ids)}"
    )
    print(
        "Placements in tag inventory  : "
        f"{len(worked_ids) - len(placements_without_tag_rows)}"
    )
    print(
        "Placements without tag rows  : "
        f"{len(placements_without_tag_rows)}"
    )
    print(
        "Placements without vendor    : "
        f"{len(placements_without_vendor)}"
    )

    print()
    print("CLASSIFIED REQUIREMENTS")

    if requirement_counts:
        for requirement, count in (
            requirement_counts.most_common()
        ):
            print(
                f"{requirement:30}: {count}"
            )
    else:
        print(
            "No classified Adobe requirements found."
        )

    print()
    print("RAW VENDORS / PIXELS VALUES")

    if raw_vendor_counts:
        for value, count in (
            raw_vendor_counts.most_common()
        ):
            print(
                f"{count:4} | {value}"
            )
    else:
        print("None")

    print()
    print("UNCLASSIFIED VENDOR VALUES")

    if unclassified_vendor_values:
        for value, count in (
            unclassified_vendor_values.most_common()
        ):
            print(
                f"{count:4} | {value}"
            )
    else:
        print("None")

    print()
    print("TAG COLUMNS FOUND")

    if tag_column_counts:
        for column, count in (
            tag_column_counts.most_common()
        ):
            print(
                f"{count:4} | {column}"
            )
    else:
        print("None")

    print()
    print("TAG TYPES FOUND")

    if tag_type_counts:
        for tag_type, count in (
            tag_type_counts.most_common()
        ):
            print(
                f"{tag_type:30}: {count}"
            )
    else:
        print("None")

    print()
    print("PLACEMENTS WITHOUT TAG ROWS")

    if placements_without_tag_rows:
        for placement_id in (
            placements_without_tag_rows
        ):
            print(placement_id)
    else:
        print("None")

    print()
    print("PLACEMENTS WITHOUT VENDOR REQUIREMENT")

    if placements_without_vendor:
        for placement_id in (
            placements_without_vendor
        ):
            print(placement_id)
    else:
        print("None")

    print()
    print("PLACEMENT DETAIL")

    for item in detail_rows:
        print("-" * 110)
        print(
            f"Placement ID : "
            f"{item['placement_id']}"
        )
        print(
            f"Vendor TS    : "
            f"{item['vendor_raw'] or '-'}"
        )
        print(
            "Requirements : "
            + (
                ", ".join(
                    item["requirements"]
                )
                or "-"
            )
        )
        print(
            "Tag columns  : "
            + (
                ", ".join(
                    item["columns"]
                )
                or "-"
            )
        )
        print(
            "Tag types    : "
            + (
                ", ".join(
                    item["types"]
                )
                or "-"
            )
        )
        print(
            "Files        : "
            + (
                ", ".join(
                    item["files"]
                )
                or "-"
            )
        )

    if inventory.parse_failures:
        print()
        print("TAG FILE PARSE FAILURES")

        for failure in inventory.parse_failures:
            print("-" * 110)
            print(
                f"File   : {failure['file']}"
            )
            print(
                "Issues : "
                + " | ".join(
                    failure["issues"]
                )
            )

    print()
    print("=" * 110)


if __name__ == "__main__":
    main()

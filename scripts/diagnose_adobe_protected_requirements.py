"""
Adobe Protected requirement diagnostic.

Business rule:
- Protected is identified from Traffic Sheet Vendors / Pixels.
- Protected content is not validated by automated QA2.
- Every worked placement requesting Protected receives N/A.
- N/A does not affect the QA2 verdict.
- Coverage is consolidated by Placement ID.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from core.tag_inventory import build_tag_inventory
from parsers.ts_parser import (
    REQ_NOT_WORKED,
    parse_ts,
)


CASE_DIR = Path(
    "tests/test_adobe_1x1_3pd_direct"
)

TS_PATH = (
    CASE_DIR
    / "TS_FY26_Q4_AMER_Creative_STEDiscover_"
      "Awareness_Discover_ASY_C.xlsx"
)


def get_tag_paths() -> list:
    """
    Find all delivered tag files recursively.

    Temporary Excel lock files beginning with ~$ are excluded.
    """
    return sorted(
        (
            path
            for path in CASE_DIR.rglob("*")
            if path.is_file()
            and path.suffix.casefold()
            in {".xlsx", ".xlsm"}
            and path.name.casefold().startswith("tags")
            and not path.name.startswith("~$")
        ),
        key=lambda path: (
            str(path.parent).casefold(),
            path.name.casefold(),
        ),
    )


def requires_protected(value: object) -> bool:
    """
    Detect Protected in Traffic Sheet Vendors / Pixels.

    Examples:
        ftrack, DISQO, Protected
        fTrack, Protected, DISQO
        Protected
    """
    return "protected" in str(
        value or ""
    ).casefold()


def worked_placement_ids(ts_result) -> set:
    """
    Return only placements worked in the current request.

    ts.scope is the canonical source of QA2 scope.
    """
    return {
        str(placement_id).strip()
        for placement_id, scope
        in ts_result.scope.items()
        if str(placement_id).strip()
        and scope.request_type != REQ_NOT_WORKED
    }


def protected_requirements(
    ts_result,
) -> dict[str, dict]:
    """
    Consolidate Protected requirements by Placement ID.

    A placement may occupy multiple Traffic Sheet rows but is evaluated
    only once.
    """
    worked_ids = worked_placement_ids(
        ts_result
    )

    records: dict[str, dict] = {}

    for row in ts_result.placements.rows:
        placement_id = str(
            row.values.get("placement_id") or ""
        ).strip()

        if placement_id not in worked_ids:
            continue

        vendor_raw = str(
            row.values.get("vendors") or ""
        ).strip()

        if not requires_protected(vendor_raw):
            continue

        record = records.setdefault(
            placement_id,
            {
                "placement_name": "",
                "site": "",
                "dimensions": "",
                "request_type": "",
                "vendors": set(),
            },
        )

        if vendor_raw:
            record["vendors"].add(
                vendor_raw
            )

        if not record["placement_name"]:
            record["placement_name"] = str(
                row.values.get(
                    "placement_name"
                )
                or ""
            ).strip()

        if not record["site"]:
            record["site"] = str(
                row.values.get("site")
                or ""
            ).strip()

        if not record["dimensions"]:
            record["dimensions"] = str(
                row.values.get(
                    "dimensions"
                )
                or ""
            ).strip()

        scope = ts_result.scope.get(
            placement_id
        )

        if scope is not None:
            record["request_type"] = str(
                scope.request_type or ""
            )

    return records


def populated_protected_columns(
    inventory,
    placement_id: str,
) -> tuple[list[str], list[str]]:
    """
    Collect populated Protected columns as informational evidence only.

    Their presence or absence never changes the N/A result.
    """
    columns: set[str] = set()
    evidence: list[str] = []

    for source in inventory.by_placement.get(
        placement_id,
        [],
    ):
        for tag in source.row.tags:
            raw = str(
                tag.raw or ""
            ).strip()

            column_name = str(
                tag.column_name or ""
            ).strip()

            if not raw:
                continue

            if "protected" not in (
                column_name.casefold()
                + " "
                + raw.casefold()
            ):
                continue

            columns.add(column_name)

            evidence.append(
                f"{source.file_name} | "
                f"{source.sheet} | "
                f"row {source.row.row} | "
                f"{column_name}"
            )

    return (
        sorted(columns),
        sorted(set(evidence)),
    )


def main() -> None:
    if not TS_PATH.exists():
        raise SystemExit(
            f"Traffic Sheet not found: "
            f"{TS_PATH}"
        )

    tag_paths = get_tag_paths()

    ts_result = parse_ts(TS_PATH)

    if ts_result.fatal:
        print(
            "FATAL TRAFFIC SHEET ANOMALIES"
        )

        for anomaly in ts_result.anomalies:
            if anomaly.severity == "FATAL":
                print(
                    f"{anomaly.code} | "
                    f"{anomaly.message}"
                )

        raise SystemExit(
            "Traffic Sheet parsing failed."
        )

    if ts_result.placements is None:
        raise SystemExit(
            "Placements sheet was not parsed."
        )

    inventory = build_tag_inventory(
        tag_paths
    )

    worked_ids = worked_placement_ids(
        ts_result
    )

    requirements = protected_requirements(
        ts_result
    )

    status_counts: Counter[str] = (
        Counter()
    )

    details = []

    for placement_id in sorted(
        requirements
    ):
        requirement = requirements[
            placement_id
        ]

        columns, evidence = (
            populated_protected_columns(
                inventory,
                placement_id,
            )
        )

        status = "N/A"
        status_counts[status] += 1

        details.append(
            {
                "status": status,
                "placement_id": (
                    placement_id
                ),
                "placement_name": (
                    requirement[
                        "placement_name"
                    ]
                ),
                "site": requirement["site"],
                "dimensions": (
                    requirement[
                        "dimensions"
                    ]
                ),
                "request_type": (
                    requirement[
                        "request_type"
                    ]
                ),
                "vendor": " | ".join(
                    sorted(
                        requirement[
                            "vendors"
                        ]
                    )
                ),
                "columns": columns,
                "message": (
                    "Protected is declared "
                    "in the Traffic Sheet. "
                    "Protected tag content "
                    "is not evaluated by "
                    "automated QA2."
                ),
                "action": (
                    "No automated correction "
                    "is required."
                ),
                "evidence": evidence,
            }
        )

    print("=" * 105)
    print(
        "PIX-A05 | ADOBE PROTECTED "
        "DIAGNOSTIC"
    )
    print("=" * 105)

    print()
    print("INPUTS")
    print(
        f"Traffic Sheet        : "
        f"{TS_PATH.name}"
    )
    print(
        f"Tag files            : "
        f"{len(tag_paths)}"
    )
    print(
        f"Tag inventory rows   : "
        f"{inventory.distinct_placements}"
    )
    print(
        f"Fatal tag files      : "
        f"{len(inventory.parse_failures)}"
    )

    print()
    print("COVERAGE")
    print(
        f"Worked placements    : "
        f"{len(worked_ids)}"
    )
    print(
        f"Protected placements : "
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
            f"Result              : "
            f"{item['status']}"
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
            f"Vendor TS           : "
            f"{item['vendor']}"
        )
        print(
            f"Site                : "
            f"{item['site']}"
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
            f"Protected columns   : "
            f"{item['columns']}"
        )
        print(
            f"Message             : "
            f"{item['message']}"
        )
        print(
            f"Recommended Action  : "
            f"{item['action']}"
        )

        for evidence in item["evidence"]:
            print(
                f"Evidence            : "
                f"{evidence}"
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

"""
Adobe Protected diagnostic.

Protected is identified from Traffic Sheet Vendors / Pixels.

Business rule:
- Protected is recognized for coverage and traceability.
- Protected tag content is not evaluated by automated QA2.
- Every worked placement requesting Protected returns N/A.
- N/A does not affect the verdict.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from core.tag_inventory import build_tag_inventory
from parsers.ts_parser import REQ_NOT_WORKED, parse_ts


CASE_DIR = Path("tests/test_adobe_1x1_3pd_direct")

TS_PATH = CASE_DIR / (
    "TS_FY26_Q4_AMER_Creative_STEDiscover_"
    "Awareness_Discover_ASY_C.xlsx"
)


def get_tag_paths() -> list:
    """Find all delivered tag files under the test case."""
    return sorted(
        (
            path
            for path in CASE_DIR.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in {".xlsx", ".xlsm"}
            and path.name.casefold().startswith("tags")
            and not path.name.startswith("~$")
        ),
        key=lambda path: (
            str(path.parent).casefold(),
            path.name.casefold(),
        ),
    )


def requires_protected(value: object) -> bool:
    """Return True when Vendors / Pixels requests Protected."""
    return "protected" in str(value or "").casefold()


def get_worked_ids(ts_result) -> set:
    """Use the canonical QA2 scope, excluding context placements."""
    return {
        str(placement_id).strip()
        for placement_id, scope in ts_result.scope.items()
        if str(placement_id).strip()
        and scope.request_type != REQ_NOT_WORKED
    }


def build_protected_records(
    ts_result,
    worked_ids: set[str],
) -> dict[str, dict]:
    """
    Consolidate Protected requirements by Placement ID.

    The same Placement ID may occupy multiple Traffic Sheet rows,
    but is evaluated only once.
    """
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

        scope = ts_result.scope.get(placement_id)

        if scope is not None:
            record["request_type"] = str(
                scope.request_type or ""
            ).strip()

    return records


def protected_tag_evidence(
    inventory,
    placement_id: str,
) -> tuple[list[str], list[str]]:
    """
    Return populated Protected columns as informational evidence.

    Presence or absence does not change the N/A result.
    """
    columns: set[str] = set()
    evidence: set[str] = set()

    for source in inventory.by_placement.get(placement_id, []):
        for tag in source.row.tags:
            raw = str(tag.raw or "").strip()
            column_name = str(tag.column_name or "").strip()

            if not raw:
                continue

            searchable = (
                column_name.casefold()
                + " "
                + raw.casefold()
            )

            if "protected" not in searchable:
                continue

            columns.add(column_name)
            evidence.add(
                f"{source.file_name} | "
                f"{source.sheet} | "
                f"row {source.row.row} | "
                f"{column_name}"
            )

    return sorted(columns), sorted(evidence)


def main() -> None:
    if not TS_PATH.exists():
        raise SystemExit(
            f"Traffic Sheet not found: {TS_PATH}"
        )

    ts_result = parse_ts(TS_PATH)

    if ts_result.fatal:
        for anomaly in ts_result.anomalies:
            if anomaly.severity == "FATAL":
                print(
                    f"{anomaly.code} | {anomaly.message}"
                )

        raise SystemExit(
            "Traffic Sheet parsing failed."
        )

    if ts_result.placements is None:
        raise SystemExit(
            "Placements sheet was not parsed."
        )

    tag_paths = get_tag_paths()
    inventory = build_tag_inventory(tag_paths)

    worked_ids = get_worked_ids(ts_result)

    protected_records = build_protected_records(
        ts_result,
        worked_ids,
    )

    details: list[dict] = []
    status_counts: Counter[str] = Counter()

    for placement_id in sorted(protected_records):
        record = protected_records[placement_id]

        columns, evidence = protected_tag_evidence(
            inventory,
            placement_id,
        )

        status_counts["N/A"] += 1

        details.append(
            {
                "status": "N/A",
                "placement_id": placement_id,
                "placement_name": record["placement_name"],
                "vendor": " | ".join(
                    sorted(record["vendors"])
                ),
                "site": record["site"],
                "dimensions": record["dimensions"],
                "request_type": record["request_type"],
                "columns": columns,
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
        f"Worked placements    : {len(worked_ids)}"
    )
    print(
        f"Protected placements : "
        f"{len(protected_records)}"
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
            f"Vendor TS           : {item['vendor']}"
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
            f"Protected columns   : "
            f"{item['columns']}"
        )
        print(
            "Message             : Protected is declared "
            "in the Traffic Sheet. Protected tag content "
            "is not evaluated by automated QA2."
        )
        print(
            "Recommended Action  : "
            "No automated correction is required."
        )

        for evidence in item["evidence"]:
            print(f"Evidence            : {evidence}")

    print()
    print("ATTENTION REQUIRED")
    print("None")

    print()
    print("=" * 105)


if __name__ == "__main__":
    main()

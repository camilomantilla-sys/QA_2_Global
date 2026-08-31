from __future__ import annotations

from pathlib import Path

from core.adobe_no_ftrack_reconciliation import (
    reconcile_adobe_no_ftrack,
)
from core.tag_inventory import build_tag_inventory
from parsers.ts_parser import parse_ts


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

    Open Excel lock files beginning with ~$ are excluded.
    """
    return sorted(
        (
            path
            for path in CASE_DIR.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in {
                ".xlsx",
                ".xlsm",
            }
            and path.name.casefold().startswith(
                "tags"
            )
            and not path.name.startswith("~$")
        ),
        key=lambda path: (
            str(path.parent).casefold(),
            path.name.casefold(),
        ),
    )


def main() -> None:
    tag_paths = get_tag_paths()

    ts_result = parse_ts(TS_PATH)
    inventory = build_tag_inventory(tag_paths)

    reconciliation = (
        reconcile_adobe_no_ftrack(
            ts_result,
            inventory,
        )
    )

    print("=" * 100)
    print("PIX-A03 | ADOBE NO FTRACK DIAGNOSTIC")
    print("=" * 100)

    print()
    print("INPUTS")
    print(f"Traffic Sheet       : {TS_PATH.name}")
    print(f"Tag files           : {len(tag_paths)}")
    print(
        f"Tag placements      : "
        f"{inventory.distinct_placements}"
    )
    print(
        f"Fatal tag files     : "
        f"{len(inventory.parse_failures)}"
    )

    print()
    print("COVERAGE")
    print(
        "No Ftrack placements : "
        f"{len(reconciliation.checks)}"
    )

    print()
    print("STATUS")

    for status, count in (
        reconciliation.by_result.items()
    ):
        print(f"{status:20}: {count}")

    print()
    print("DETAIL")

    for check in reconciliation.checks:
        print("-" * 100)
        print(
            f"Result              : "
            f"{check.result}"
        )
        print(
            f"Placement ID        : "
            f"{check.placement_id}"
        )
        print(
            f"Placement Name      : "
            f"{check.placement_name}"
        )
        print(
            f"Site                : "
            f"{check.site}"
        )
        print(
            f"Request Type        : "
            f"{check.request_type}"
        )
        print(
            f"Vendor TS           : "
            f"{check.vendor_raw}"
        )
        print(
            f"Columns found       : "
            f"{list(check.columns_found)}"
        )
        print(
            f"Pixel               : "
            f"{check.pixel_present}"
        )
        print(
            f"Update_Clicktag     : "
            f"{check.update_clicktag_present}"
        )
        print(
            f"Static_Clicktag     : "
            f"{check.static_clicktag_present}"
        )
        print(
            f"Ftrack impression   : "
            f"{check.ftrack_impression_present}"
        )
        print(
            f"Ftrack click        : "
            f"{check.ftrack_click_present}"
        )
        print(
            f"Message             : "
            f"{check.message}"
        )
        print(
            f"Recommended Action  : "
            f"{check.recommended_action}"
        )

        for evidence in check.evidence:
            print(
                f"Evidence            : "
                f"{evidence}"
            )

    print()
    print("ATTENTION REQUIRED")

    if not reconciliation.attention:
        print("None")
    else:
        for check in reconciliation.attention:
            print(
                f"{check.result:8} | "
                f"{check.placement_id} | "
                f"{check.message}"
            )

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()

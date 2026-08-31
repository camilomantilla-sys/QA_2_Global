from __future__ import annotations

from pathlib import Path

from core.adobe_pixel_reconciliation import (
    reconcile_adobe_pixels,
)
from core.tag_inventory import build_tag_inventory
from parsers.innovid_export import (
    parse_innovid_export,
)
from parsers.ts_parser import parse_ts


CASE_DIR = Path(
    "tests/test_adobe_1x1_3pd_direct"
)

TS_PATH = (
    CASE_DIR
    / "TS_FY26_Q4_AMER_Creative_STEDiscover_"
      "Awareness_Discover_ASY_C.xlsx"
)

PLACEMENT_VIEW_PATH = (
    CASE_DIR / "placement view.xlsm"
)

TAG_DIRECTORIES = [
    CASE_DIR / "new_1x1_tags",
    CASE_DIR / "new_3p_tags",
]


def get_tag_paths() -> list[Path]:
    paths: list[Path] = []

    for directory in TAG_DIRECTORIES:
        paths.extend(directory.glob("*.xlsx"))
        paths.extend(directory.glob("*.xlsm"))

    return sorted(
        paths,
        key=lambda path: path.name.casefold(),
    )


def main() -> None:
    ts_result = parse_ts(TS_PATH)

    placement_result = parse_innovid_export(
        PLACEMENT_VIEW_PATH
    )

    inventory = build_tag_inventory(
        get_tag_paths()
    )

    reconciliation = reconcile_adobe_pixels(
        ts_result,
        placement_result,
        inventory,
    )

    print("=" * 110)
    print("ADOBE PIXEL RECONCILIATION")
    print("=" * 110)

    print()
    print("INPUTS")
    print(f"Traffic Sheet       : {TS_PATH.name}")
    print(
        f"Placement View      : "
        f"{PLACEMENT_VIEW_PATH.name}"
    )
    print(
        f"Tag files           : "
        f"{len(inventory.files)}"
    )

    print()
    print("RESULTS")

    for status, total in (
        reconciliation.by_result.items()
    ):
        print(f"{status:20}: {total}")

    print()
    print("DISQO EVIDENCE SUMMARY")

    disqo_required_checks = [
        check
        for check in reconciliation.checks
        if check.disqo_required
    ]

    pass_by_tags = sum(
        1
        for check in disqo_required_checks
        if check.result == "PASS"
        and check.tags_disqo
    )

    pass_by_innovid = sum(
        1
        for check in disqo_required_checks
        if check.result == "PASS"
        and not check.tags_disqo
        and check.innovid_disqo
    )

    evidence_in_both = sum(
        1
        for check in disqo_required_checks
        if check.tags_disqo
        and check.innovid_disqo
    )

    without_evidence = sum(
        1
        for check in disqo_required_checks
        if not check.tags_disqo
        and not check.innovid_disqo
    )

    print(
        f"PASS supported by Tags       : "
        f"{pass_by_tags}"
    )
    print(
        f"PASS supported by Innovid    : "
        f"{pass_by_innovid}"
    )
    print(
        f"Evidence found in both       : "
        f"{evidence_in_both}"
    )
    print(
        f"No valid evidence            : "
        f"{without_evidence}"
    )

    print()
    print("DISQO REQUIRED")

    disqo_checks = [
        check
        for check in reconciliation.checks
        if check.disqo_required
    ]

    print(
        f"Placements          : "
        f"{len(disqo_checks)}"
    )

    for check in disqo_checks:
        print("-" * 110)
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
            f"Innovid DISQO       : "
            f"{check.innovid_disqo}"
        )
        print(
            f"Tags DISQO          : "
            f"{check.tags_disqo}"
        )
        print(
            f"Message             : "
            f"{check.message}"
        )
        print(
            f"Recommended Action  : "
            f"{check.recommended_action or '-'}"
        )

        if check.innovid_evidence:
            print("Innovid Evidence")

            for evidence in (
                check.innovid_evidence
            ):
                print(f"  - {evidence}")

        if check.tag_evidence:
            print("Tag Evidence")

            for evidence in check.tag_evidence:
                print(f"  - {evidence}")

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
    print("=" * 110)


if __name__ == "__main__":
    main()

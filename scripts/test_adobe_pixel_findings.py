from __future__ import annotations

from collections import Counter
from pathlib import Path

from core.adobe_pixel_reconciliation import (
    reconcile_adobe_pixels,
)
from core.findings import FindingsBuffer
from core.tag_inventory import build_tag_inventory
from parsers.innovid_export import parse_innovid_export
from parsers.ts_parser import parse_ts
from rules import adobe_pixels


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

    buffer = FindingsBuffer()

    adobe_pixels.evaluate(
        reconciliation,
        buffer,
    )

    findings = [
        finding
        for finding in buffer.findings
        if finding.rule_id == "PIX-A01"
    ]

    status_counts = Counter(
        finding.status.value
        for finding in findings
    )

    print("=" * 100)
    print("PIX-A01 | ADOBE DISQO FINDINGS")
    print("=" * 100)

    print()
    print("RECONCILIATION COVERAGE")
    print(
        f"All worked placement checks : "
        f"{len(reconciliation.checks)}"
    )
    print(
        f"DISQO-required placements   : "
        f"{sum(check.disqo_required for check in reconciliation.checks)}"
    )
    print(
        f"Canonical PIX-A01 findings  : "
        f"{len(findings)}"
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
            f"{status:20}: "
            f"{status_counts.get(status, 0)}"
        )

    print()
    print("SAMPLE")

    for finding in findings[:20]:
        print("-" * 100)
        print(
            f"{finding.status.value:15} | "
            f"{finding.placement_id:12} | "
            f"{finding.message}"
        )
        print(f"Expected : {finding.expected}")
        print(f"Actual   : {finding.actual}")
        print(f"Reason   : {finding.reason}")

    problems = [
        finding
        for finding in findings
        if finding.status.value != "PASS"
    ]

    print()
    print("ATTENTION REQUIRED")

    if not problems:
        print("None")
    else:
        for finding in problems:
            print(
                f"{finding.status.value:15} | "
                f"{finding.placement_id:12} | "
                f"{finding.message}"
            )

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()

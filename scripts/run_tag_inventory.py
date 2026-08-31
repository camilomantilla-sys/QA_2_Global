from __future__ import annotations

from collections import Counter
from pathlib import Path

from core.matching import build_expected
from core.tag_inventory import build_tag_inventory
from parsers.innovid_export import parse_innovid_export
from parsers.ts_parser import parse_ts


CASE_DIR = Path("tests/test_adobe_1x1_3pd_direct")

TS_PATH = (
    CASE_DIR
    / "TS_FY26_Q4_AMER_Creative_STEDiscover_Awareness_Discover_ASY_C.xlsx"
)

EXPORT_PC_PATH = CASE_DIR / "placement creative view.xlsm"
EXPORT_PL_PATH = CASE_DIR / "placement view.xlsm"

TAG_DIRS = [
    CASE_DIR / "new_1x1_tags",
    CASE_DIR / "new_3p_tags",
]


def tag_paths() -> list:
    paths = []
    for directory in TAG_DIRS:
        paths.extend(directory.glob("*.xlsx"))
        paths.extend(directory.glob("*.xlsm"))

    return sorted(paths, key=lambda item: item.name.casefold())


def main() -> None:
    paths = tag_paths()

    print("=" * 100)
    print("QA2 MULTI-FILE TAG INVENTORY")
    print("=" * 100)

    print(f"Traffic Sheet              : {TS_PATH.name}")
    print(f"Placement-Creative View    : {EXPORT_PC_PATH.name}")
    print(f"Placement View             : {EXPORT_PL_PATH.name}")
    print(f"Tag files                  : {len(paths)}")

    ts = parse_ts(TS_PATH)
    pc = parse_innovid_export(EXPORT_PC_PATH)
    pl = parse_innovid_export(EXPORT_PL_PATH)

    inventory = build_tag_inventory(paths)
    expected = build_expected(ts)

    expected_ids = set(expected)
    tag_ids = inventory.placement_ids

    tags_in_scope = expected_ids & tag_ids
    missing_tags = expected_ids - tag_ids
    tags_outside_scope = tag_ids - expected_ids

    pc_ids = {
        str(row.values.get("placement_id") or "")
        for row in pc.rows
        if row.values.get("placement_id")
    }

    pl_ids = {
        str(row.values.get("placement_id") or "")
        for row in pl.rows
        if row.values.get("placement_id")
    }

    tags_missing_pc = tag_ids - pc_ids
    tags_missing_pl = tag_ids - pl_ids

    print()
    print("CAMPAIGN IDS")
    ts_campaign_id = (
        ts.campaign_info.get("campaignid")
        or ts.campaign_info.get("campaign_id")
        or ts.campaign_info.get("Campaign ID")
        or "-"
    )

    print(f"Traffic Sheet              : {ts_campaign_id}")
    print(
        "Placement-Creative View  : "
        f"{pc.metadata.get('campaignid', '-')}"
    )
    print(
        "Placement View           : "
        f"{pl.metadata.get('campaignid', '-')}"
    )
    print(f"Tag files                  : {dict(inventory.campaigns)}")

    print()
    print("TAG INVENTORY")
    print(f"Files processed            : {len(inventory.files)}")
    print(f"Files with fatal errors    : {len(inventory.parse_failures)}")
    print(f"Unique tag placements      : {inventory.distinct_placements}")
    print(f"Tag rows                   : {inventory.total_rows}")
    print(f"Materialized tags          : {inventory.total_tags}")

    print()
    print("SCOPE COVERAGE")
    print(f"Worked placements          : {len(expected_ids)}")
    print(f"Worked placements with tag : {len(tags_in_scope)}")
    print(f"Worked placements no tag   : {len(missing_tags)}")
    print(f"Tag placements out of scope: {len(tags_outside_scope)}")
    print(f"Tags missing in PC View    : {len(tags_missing_pc)}")
    print(f"Tags missing in PL View    : {len(tags_missing_pl)}")

    print()
    print("TAG TYPES")

    for tag_type, count in inventory.tag_types.most_common():
        print(f"{tag_type:25}: {count}")

    print()
    print("FILES")

    for result in inventory.results:
        status = "FATAL" if result.fatal else "OK"

        print(
            f"{status:7} | "
            f"{Path(result.path).name} | "
            f"placements={result.distinct_placements} | "
            f"tags={result.total_tags} | "
            f"campaign={result.campaign_id or '-'}"
        )

    if inventory.parse_failures:
        print()
        print("PARSE FAILURES")

        for failure in inventory.parse_failures:
            print(f"{failure['file']}: {failure['issues']}")

    print()
    print("MISSING TAGS IN WORKED SCOPE")

    if missing_tags:
        for placement_id in sorted(missing_tags):
            placement = expected[placement_id]

            print(
                f"{placement_id} | "
                f"{placement.site} | "
                f"{placement.dims} | "
                f"{placement.request_type} | "
                f"{placement.name}"
            )
    else:
        print("None")

    print()
    print("TAG PLACEMENTS OUTSIDE WORKED SCOPE")

    if tags_outside_scope:
        for placement_id in sorted(tags_outside_scope):
            sources = inventory.by_placement[placement_id]
            files = sorted({source.file_name for source in sources})

            print(
                f"{placement_id} | "
                f"files={', '.join(files)}"
            )
    else:
        print("None")

    print()
    print("PLACEMENTS PRESENT IN MULTIPLE TAG FILES")

    duplicate_files = {}

    for placement_id, sources in inventory.by_placement.items():
        files = {source.file_name for source in sources}

        if len(files) > 1:
            duplicate_files[placement_id] = sorted(files)

    if duplicate_files:
        for placement_id, files in sorted(duplicate_files.items()):
            print(
                f"{placement_id} | "
                f"{len(files)} files | "
                f"{', '.join(files)}"
            )
    else:
        print("None")

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()

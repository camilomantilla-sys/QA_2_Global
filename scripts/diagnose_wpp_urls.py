"""
Diagnóstico de resolución URL para Traffic Sheets WPP.

Flujo esperado:
Placement
-> Creative Rotation
-> Landing Page Name
-> Landing Page URL
"""
from __future__ import annotations

import re
from pathlib import Path

from parsers.ts_parser import parse_ts


CASE_DIR = Path("tests/test_unilever1_3p")

_URL_PATTERN = re.compile(
    r'https?://[^\s"\'<>]+',
    re.IGNORECASE,
)


def extract_first_url(value: object) -> str:
    text = str(value or "").strip()

    if not text:
        return ""

    match = _URL_PATTERN.search(text)

    if not match:
        return ""

    return (
        match.group(0)
        .replace("&amp;", "&")
        .rstrip("'\"),")
    )


def find_traffic_sheet() -> Path:
    candidates = sorted(
        path
        for path in CASE_DIR.glob("*.xlsx")
        if not path.name.startswith("~$")
    )

    for path in candidates:
        name = path.name.casefold()

        if (
            "traffic" in name
            or "t sheet" in name
            or "wpp" in name
        ):
            return path

    if candidates:
        return candidates[0]

    raise SystemExit(
        f"No Traffic Sheet found in {CASE_DIR}"
    )


def main() -> None:
    ts_path = find_traffic_sheet()

    print("=" * 110)
    print("WPP URL RESOLUTION DIAGNOSTIC")
    print("=" * 110)
    print(f"FILE    : {ts_path}")
    print()

    ts = parse_ts(ts_path)

    print(f"PROFILE : {ts.profile}")
    print(f"WORKED  : {len(ts.worked)}")
    print()

    if ts.placements is None:
        raise SystemExit("Placements sheet was not parsed.")

    if ts.rotations is None:
        raise SystemExit("Creative Rotations sheet was not parsed.")

    if ts.landing_pages is None:
        raise SystemExit("Landing Pages sheet was not parsed.")

    print("PARSED ROW COUNTS")
    print(f"Placements         : {len(ts.placements.rows)}")
    print(f"Creative Rotations : {len(ts.rotations.rows)}")
    print(f"Landing Pages      : {len(ts.landing_pages.rows)}")
    print()

    landing_page_lookup: dict[str, str] = {}

    for row in ts.landing_pages.rows:
        lp_name = str(
            row.values.get("lp_name") or ""
        ).strip()

        lp_raw = row.values.get("lp_url")
        lp_url = extract_first_url(lp_raw)

        if lp_name and lp_url:
            landing_page_lookup[lp_name.casefold()] = lp_url

    rotations_by_group: dict[str, list[dict]] = {}

    current_group = ""

    for row in ts.rotations.rows:
        row_group = str(
            row.values.get("group_name") or ""
        ).strip()

        if row_group:
            current_group = row_group

        creative_name = str(
            row.values.get("creative_name") or ""
        ).strip()

        lp_name = str(
            row.values.get("lp_url") or ""
        ).strip()

        effective_group = row_group or current_group

        if not effective_group:
            continue

        resolved_url = landing_page_lookup.get(
            lp_name.casefold(),
            "",
        )

        rotations_by_group.setdefault(
            effective_group.casefold(),
            [],
        ).append(
            {
                "group": effective_group,
                "creative": creative_name,
                "landing_page_name": lp_name,
                "resolved_url": resolved_url,
                "row": row.row,
            }
        )

    print("LOOKUP COVERAGE")
    print(
        f"Landing Page URLs indexed : "
        f"{len(landing_page_lookup)}"
    )
    print(
        f"Rotation groups indexed   : "
        f"{len(rotations_by_group)}"
    )
    print()

    print("=" * 110)
    print("FIRST 15 PLACEMENT RESOLUTIONS")
    print("=" * 110)

    unresolved_groups = 0
    unresolved_landing_pages = 0
    resolved_creatives = 0

    for placement_row in ts.placements.rows[:15]:
        placement_id = str(
            placement_row.values.get("placement_id") or ""
        ).strip()

        placement_name = str(
            placement_row.values.get("placement_name") or ""
        ).strip()

        group_name = str(
            placement_row.values.get("group_name") or ""
        ).strip()

        lp_ref = str(
            placement_row.values.get("lp_ref") or ""
        ).strip()

        group_creatives = rotations_by_group.get(
            group_name.casefold(),
            [],
        )

        print()
        print("-" * 110)
        print(f"PLACEMENT ID     : {placement_id}")
        print(f"PLACEMENT NAME   : {placement_name}")
        print(f"CREATIVE ROTATION: {group_name}")
        print(f"PLACEMENT LP CELL: {lp_ref}")
        print(f"CREATIVES FOUND  : {len(group_creatives)}")

        if not group_creatives:
            print("RESULT            : GROUP NOT RESOLVED")
            unresolved_groups += 1
            continue

        for creative in group_creatives[:10]:
            resolved_url = creative["resolved_url"]

            print(
                f"  ROW {creative['row']:04} | "
                f"LP NAME={creative['landing_page_name']} | "
                f"URL={'FOUND' if resolved_url else 'NOT FOUND'}"
            )

            if resolved_url:
                resolved_creatives += 1
                print(f"    {resolved_url}")
            else:
                unresolved_landing_pages += 1

    print()
    print("=" * 110)
    print("SUMMARY")
    print("=" * 110)
    print(f"Resolved creatives          : {resolved_creatives}")
    print(f"Unresolved groups           : {unresolved_groups}")
    print(
        f"Unresolved landing page refs: "
        f"{unresolved_landing_pages}"
    )

    print()
    print("EXPECTED RESULT")
    print(
        "Groups must resolve from Placements.Creative Rotation "
        "to Creative Rotations column 1."
    )
    print(
        "URLs must resolve from Creative Rotations.Landing Page Name "
        "to Landing Pages.Landing Page URL."
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections import Counter
from pathlib import Path

from parsers.innovid_tags import parse_innovid_tags


TAGS_DIR = Path("data/tags")


def main() -> None:
    files = sorted(
        list(TAGS_DIR.glob("*.xlsx"))
        + list(TAGS_DIR.glob("*.xlsm"))
    )

    if not files:
        print("No se encontraron archivos de tags.")
        return

    total_issues = 0
    issue_types: Counter[str] = Counter()

    for path in files:
        result = parse_innovid_tags(path)

        print()
        print("=" * 100)
        print(f"ARCHIVO      : {path.name}")
        print(f"HOJA         : {result.sheet or '-'}")
        print(f"CAMPAIGN ID  : {result.campaign_id or '-'}")
        print(f"PLACEMENTS   : {result.distinct_placements}")
        print(f"TAGS         : {result.total_tags}")
        print("=" * 100)

        if result.fatal:
            for anomaly in result.anomalies:
                print(
                    f"{anomaly.severity} | "
                    f"{anomaly.code} | "
                    f"{anomaly.message}"
                )
            continue

        file_issues = 0

        for row in result.rows:
            for tag in row.tags:
                issues = []

                if (
                    tag.campaign_ids
                    and result.campaign_id
                    and result.campaign_id not in tag.campaign_ids
                ):
                    issues.append(
                        f"CAMPAIGN_ID esperado={result.campaign_id} "
                        f"embebido={tag.campaign_ids}"
                    )
                    issue_types["CAMPAIGN_ID"] += 1

                if (
                    tag.placement_ids
                    and row.placement_id not in tag.placement_ids
                ):
                    issues.append(
                        f"PLACEMENT_ID esperado={row.placement_id} "
                        f"embebido={tag.placement_ids}"
                    )
                    issue_types["PLACEMENT_ID"] += 1

                # Los píxeles auxiliares pueden usar width=0 height=0.
                check_dimensions = tag.tag_type not in {
                    "PIXEL",
                    "PIXEL_HTML",
                    "1X1_IMPRESSION",
                }

                if (
                    check_dimensions
                    and tag.widths
                    and row.width
                    and row.width not in tag.widths
                ):
                    issues.append(
                        f"WIDTH esperado={row.width} "
                        f"embebido={tag.widths}"
                    )
                    issue_types["WIDTH"] += 1

                if (
                    check_dimensions
                    and tag.heights
                    and row.height
                    and row.height not in tag.heights
                ):
                    issues.append(
                        f"HEIGHT esperado={row.height} "
                        f"embebido={tag.heights}"
                    )
                    issue_types["HEIGHT"] += 1

                if not issues:
                    continue

                file_issues += 1
                total_issues += 1

                print()
                print(f"PLACEMENT ID : {row.placement_id}")
                print(f"PLACEMENT    : {row.placement_name}")
                print(f"DIMENSION    : {row.dimensions}")
                print(f"THIRD PARTY  : {row.third_party_id}")
                print(f"TAG COLUMN   : {tag.column_name}")
                print(f"TAG TYPE     : {tag.tag_type}")
                print(f"HOSTS        : {tag.hosts}")
                print(f"ISSUES       : {' | '.join(issues)}")
                print(f"MACROS       : {tag.macros}")
                print(f"RAW SAMPLE   : {tag.raw[:300]}")

        if file_issues:
            print()
            print(f"RESULTADO: {file_issues} POSIBLES INCONSISTENCIAS")
        else:
            print()
            print("RESULTADO: SIN INCONSISTENCIAS INTERNAS")

    print()
    print("=" * 100)
    print("RESUMEN GLOBAL")
    print("=" * 100)
    print(f"ARCHIVOS PROCESADOS : {len(files)}")
    print(f"TOTAL ISSUES        : {total_issues}")

    for issue_type, count in sorted(issue_types.items()):
        print(f"{issue_type:20}: {count}")


if __name__ == "__main__":
    main()
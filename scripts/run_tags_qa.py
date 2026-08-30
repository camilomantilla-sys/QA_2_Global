from __future__ import annotations

from collections import Counter
from pathlib import Path

from core.matching import match
from core.engine import run_rules
from core.tag_matching import match_tags
from parsers.innovid_export import parse_innovid_export
from parsers.innovid_tags import parse_innovid_tags
from parsers.ts_parser import parse_ts


TS_PATH = Path(
    "data/ts/TS Adobe Variante B.xlsx"
)

EXPORT_PC_PATH = Path(
    "data/exports/"
    "Export 1x1_3P directo placement creative.xlsm"
)

EXPORT_PL_PATH = Path(
    "data/exports/"
    "Export 1x1_3P directo placement.xlsm"
)

TAGS_PATH = Path(
    "data/tags/"
    "TAGS_Learnverse_VIDEO_DISPLAY_FY26_Q4_AMER_"
    "Creative_STEDiscover.xlsx"
)


def main() -> None:
    print("Parseando Traffic Sheet...")
    ts_result = parse_ts(TS_PATH)

    print("Parseando Placement-Creative export...")
    pc_result = parse_innovid_export(EXPORT_PC_PATH)

    print("Parseando Placement export...")
    pl_result = parse_innovid_export(EXPORT_PL_PATH)

    print("Parseando archivo de tags...")
    tags_result = parse_innovid_tags(TAGS_PATH)

    print("Ejecutando matching...")
    match_result = match(
        ts_result,
        pc_result,
        pl_result,
    )

    tag_match_result = match_tags(
        match_result,
        tags_result,
    )

    print("Ejecutando reglas...")
    findings = run_rules(
        match_result,
        tags_result=tags_result,
    )

    scorecard = findings.scorecard()

    print()
    print("=" * 100)
    print("QA2 INTEGRADO · TS + INNOVID + TAGS")
    print("=" * 100)

    print()
    print(f"Perfil TS              : {ts_result.profile}")
    print(f"Campaign ID TS         : {match_result.ts_campaign_id or '-'}")
    print(f"Campaign ID Innovid    : {match_result.export_campaign_id or '-'}")
    print(f"Campaign ID Tags       : {tags_result.campaign_id or '-'}")

    print()
    print(f"Placements TS scope    : {match_result.expected_total}")
    print(f"Placements en Tags     : {tags_result.distinct_placements}")
    print(
        "Tags dentro del scope  : "
        f"{len(tag_match_result.matched_to_scope)}"
    )
    print(
        "Tags fuera del scope   : "
        f"{len(tag_match_result.outside_scope)}"
    )
    print(
        "Tags sin match Innovid : "
        f"{len(tag_match_result.missing_in_innovid)}"
    )

    print()
    print(f"VERDICT                : {scorecard.verdict}")
    print(f"TOTAL FINDINGS         : {scorecard.total_findings}")

    print()
    print("STATUS")

    for status, total in scorecard.by_status.items():
        print(f"{status:20}: {total}")

    print()
    print("RULE BREAKDOWN")

    counter = Counter(
        (
            finding.rule_id,
            finding.status.value,
        )
        for finding in findings.findings
    )

    for (rule_id, status), total in sorted(counter.items()):
        print(
            f"{rule_id:12} "
            f"{status:15} "
            f"{total}"
        )

    print()
    print("PROBLEMAS")

    problems = [
        finding
        for finding in findings.findings
        if finding.status.value
        in {
            "FAIL",
            "REVIEW",
            "NOT_VERIFIED",
        }
    ]

    if not problems:
        print("Sin problemas.")
    else:
        for finding in problems[:100]:
            print(
                f"{finding.status.value:15} | "
                f"{finding.rule_id:10} | "
                f"{finding.placement_id:12} | "
                f"{finding.message} | "
                f"expected={finding.expected} | "
                f"actual={finding.actual}"
            )

    print()
    print("=" * 100)


if __name__ == "__main__":
    main()
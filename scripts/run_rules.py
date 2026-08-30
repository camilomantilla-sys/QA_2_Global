from collections import Counter
from pathlib import Path

from parsers.ts_parser import parse_ts
from parsers.innovid_export import parse_innovid_export

from core.matching import match
from core.engine import run_rules


TS = Path("data/ts/TS Adobe Variante 1.xlsx")

EXPORT_PC = Path("data/exports/Export 3p con Dtree sin url.xlsx")


def main():

    ts = parse_ts(TS)

    pc = parse_innovid_export(EXPORT_PC)

    result = match(ts, pc)

    findings = run_rules(result)

    scorecard = findings.scorecard()

    print()
    print("=" * 80)
    print("QA2 REPORT")
    print("=" * 80)

    print()
    print("PROFILE")
    print(ts.profile)

    print()
    print("VERDICT")
    print(scorecard.verdict)

    print()
    print("MATCH COVERAGE")
    print(f"Placements trabajados : {result.expected_total}")
    print(f"Placements encontrados: {len(result.matched)}")

    print()
    print("RULE RESULTS")

    for k, v in scorecard.by_status.items():
        print(f"{k:15} {v}")

    print()
    print("SEVERITY")

    for k, v in scorecard.by_severity.items():
        print(f"{k:15} {v}")

    print()
    print("DOMAINS")

    if scorecard.by_domain:
        for k, v in scorecard.by_domain.items():
            print(f"{k:15} {v}")
    else:
        print("Sin hallazgos negativos")

    print()
    print("TOTAL FINDINGS")
    print(scorecard.total_findings)

    print()
    print("RULE BREAKDOWN")

    rule_counter = Counter()

    for f in findings.findings:
        rule_counter[f.rule_id] += 1

    for rule, total in sorted(rule_counter.items()):
        print(f"{rule:15} {total}")

    print()
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
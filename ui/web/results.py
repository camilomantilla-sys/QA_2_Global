"""
Los resultados del QA, listos para la pagina.

Cada hallazgo lleva lo que dijo la regla y el porque: que mira esa
regla, que esperaba, que encontro y que hacer. La pagina no inventa
texto: todo sale del hallazgo o de RULE_TITLES.
"""
from __future__ import annotations

from typing import Any

from core.verdict import (
    SCOPE_LABELS, VERDICT_LABELS, headline, overall, verdicts_by_scope,
)

from core.rule_titles import RULE_TITLES  # noqa: E402,F401  (aqui se leia antes)

STATUS_ORDER = {"FAIL": 0, "REVIEW": 1, "NOT_VERIFIED": 2, "INFO": 3, "PASS": 4}
STATUS_LABELS = {
    "FAIL": "Fail",
    "REVIEW": "Review",
    "NOT_VERIFIED": "Not checked",
    "INFO": "Info",
    "PASS": "Pass",
}


def _value(value) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def finding_row(finding) -> dict[str, Any]:
    status = _value(finding.status)
    return {
        "id": finding.finding_id,
        "rule": finding.rule_id,
        "rule_title": RULE_TITLES.get(finding.rule_id, ""),
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "severity": _value(finding.severity),
        "domain": _value(finding.domain),
        "placement_id": _value(finding.placement_id),
        "placement_name": _value(finding.placement_name),
        "creative": _value(finding.creative_name) or _value(finding.creative_id),
        "message": _value(finding.message),
        "expected": _value(finding.expected),
        "actual": _value(finding.actual),
        "reason": _value(finding.reason),
        "action": _value(finding.recommended_action),
        "count": max(int(finding.count or 1), 1),
    }


def build_results(findings, placement_names: dict[str, str] | None = None,
                  innovid: dict | None = None) -> dict[str, Any]:
    """Veredicto, conteos, y los hallazgos agrupados por placement."""
    placement_names = placement_names or {}
    items = list(findings.findings)
    rows = sorted((finding_row(f) for f in items),
                  key=lambda r: (STATUS_ORDER.get(r["status"], 9), r["placement_id"], r["rule"]))

    counts = {label: 0 for label in STATUS_LABELS}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    by_placement: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["placement_id"] or "(campaign)"
        entry = by_placement.setdefault(key, {
            "placement_id": row["placement_id"],
            "placement_name": row["placement_name"] or placement_names.get(row["placement_id"], ""),
            "worst": row["status"],
            "counts": {},
        })
        entry["counts"][row["status"]] = entry["counts"].get(row["status"], 0) + 1
        if STATUS_ORDER.get(row["status"], 9) < STATUS_ORDER.get(entry["worst"], 9):
            entry["worst"] = row["status"]

    verdict = overall(items)
    return {
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS.get(verdict, verdict),
        "headline": headline(items),
        "scopes": [
            {"key": k, "label": SCOPE_LABELS.get(k, k), "verdict": v,
             "verdict_label": VERDICT_LABELS.get(v, v)}
            for k, v in verdicts_by_scope(items).items()
        ],
        "counts": counts,
        "placements": sorted(by_placement.values(),
                             key=lambda p: (STATUS_ORDER.get(p["worst"], 9), p["placement_id"])),
        "findings": rows,
        "innovid": innovid or {"used": False},
    }

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

#: Que revisa cada regla, en una frase. Es lo primero del "porque".
RULE_TITLES = {
    "EXT-000": "The Traffic Sheet could be read",
    "EXT-001": "A required column is not empty",
    "PLC-001": "The placement in the Traffic Sheet exists in Innovid",
    "PLC-002": "A full disassignment left the placement stopped",
    "PLC-006": "The placement name matches",
    "PLC-007": "The rotation the placement declares has creatives of its size",
    "CRE-001": "The creative is assigned as the Traffic Sheet asks",
    "CRE-002": "The 1x1 pixel is assigned on a site-served placement",
    "CRE-008": "Creative rotation",
    "ROT-001": "The requested rotation change was applied",
    "URL-001": "The landing page matches the click tag in Innovid",
    "URL-002": "The new landing page is live in Innovid",
    "URL-003": "Landing pages of directly assigned placements",
    "ATR-001": "Attribution (CGEN) on each creative",
    "ATR-002": "Attribution (CGEN) on the placement",
    "TRK-001": "The decision tree is the right one",
    "TRK-002": "The decision set is the right one",
    "INV-001": "Creative flight dates inside the decision set",
    "INV-002": "Creative rotation weight inside the decision set",
    "INV-003": "Verification partner on the placement",
    "INV-004": "The creative name in the decision set",
    "INV-005": "The placement is active in Innovid",
    "TAG-001": "The tag file declares the right Campaign ID",
    "TAG-002": "The tag's placement exists in Innovid",
    "TAG-003": "The tag's placement is part of this request",
    "TAG-004": "The tag's placement name matches",
    "TAG-008": "The Campaign ID inside the tag",
    "TAG-009": "The dimensions inside the tag",
    "TAG-010": "The tag is not empty",
    "TAG-011": "The placement appears once in the tag file",
    "TAG-012": "Adobe tag columns (Ftrack, Clicktag, Protected)",
    "TAG-013": "Every 1x1 with a vendor has a row in the tag file",
    "TAG-014": "The landing page inside the 1x1 click tag",
    "DV-001": "DV Pinnacle tag delivered for the placement",
    "DV-002": "DV Pinnacle tags outside this request",
    "DV-003": "DoubleVerify column in the Innovid tag file",
    "PIX-002": "Vendor pixels on the placement",
    "PIX-A01": "Adobe vendor pixels (DISQO, iSpot)",
    "DEF-001": "The default ad is consistent",
}

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

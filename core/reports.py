"""
Los informes del QA (PDF y Excel) y las firmas de QA2 Review, sin
interfaz.

Las dos interfaces (Streamlit y la nueva) firman y descargan lo mismo:
si cada una armara sus informes, tarde o temprano dirian cosas
distintas sobre la misma solicitud. Por eso la cadena que va de los
hallazgos a los bytes del PDF y del Excel vive aqui, como la de las
reglas vive en core.pipeline.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore

from core.findings import Scorecard, Severity, Status
from core.pdf_report import ReportMeta, build_pdf_report
from core.excel_report import build_excel_report
from core.qa_export import build_qa_rows
from core.tag_analysis import analyse_tags, dv_table, import_table
from core.verdict import VERDICT_LABELS, headline as scope_headline, verdicts_by_scope

PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Lo que se puede firmar en QA2 Review. Un PASS ya esta bien.
REVIEWABLE = ("REVIEW", "FAIL", "NOT_VERIFIED")

STATUS_PRIORITY = {"FAIL": 5, "REVIEW": 4, "NOT_VERIFIED": 3, "INFO": 2, "PASS": 1}

_LOGO_CANDIDATES = ("wpp-media-logo.png", "wpp-media-logo.svg", "wpp-media-logo.png.png")


def logo_path() -> Path | None:
    for name in _LOGO_CANDIDATES:
        candidate = PROJECT_ROOT / "ui" / "assets" / name
        if candidate.exists():
            return candidate
    return None


# ------------------------------------------------------------ firmas

def apply_review_overrides(findings, overrides: dict, approved_by: str = ""):
    """
    Turns an approved REVIEW, FAIL or NOT_VERIFIED finding into PASS,
    carrying the QA's observation forward as the reason a human can
    read later.

    A FAIL is signed off, not silenced: the observation is what makes
    it acceptable, and it stays on the record in the report and in
    the Excel as "MANUALLY Approved by ...".

    `overrides` is {finding_id: {"approved": bool, "note": str}} from
    the sign-off panel. A REVIEW finding not in `overrides` (or not
    approved) passes through unchanged -- only an explicit approval
    flips the status. The finding's identity (rule, placement,
    creative, expected/actual) is untouched, so its finding_id stays
    stable across reruns.
    """
    out = []

    for finding in findings:
        entry = overrides.get(finding.finding_id)

        if (
            not entry
            or not entry.get("approved")
            or finding.status.value not in REVIEWABLE
        ):
            out.append(finding)
            continue

        note = entry.get("note", "").strip()
        stamp = f"Approved by {approved_by}" if approved_by else "Approved"
        approval_text = f"{stamp}: {note}" if note else stamp

        out.append(
            replace(
                finding,
                status=Status.PASS,
                severity=Severity.NONE,
                reason=(
                    f"{finding.reason} | {approval_text}"
                    if finding.reason
                    else approval_text
                ),
            )
        )

    return out


# ------------------------------------------------------------ tablas

def _items(findings) -> list:
    return list(getattr(findings, "findings", findings) or [])


def findings_dataframe(findings) -> pd.DataFrame:
    rows = [
        {
            "Status": finding.status.value,
            "Severity": finding.severity.value,
            "Rule": finding.rule_id,
            "Domain": finding.domain.value,
            "Placement ID": finding.placement_id,
            "Placement Name": finding.placement_name,
            "Creative ID": finding.creative_id,
            "Creative Name": finding.creative_name,
            "Message": finding.message,
            "Expected": finding.expected,
            "Found": finding.actual,
            "Reason": finding.reason,
            "Recommended Action": finding.recommended_action,
            "Confidence": finding.confidence.value,
            "Count": finding.count,
        }
        for finding in _items(findings)
    ]
    return pd.DataFrame(rows)


def rule_summary_dataframe(findings) -> pd.DataFrame:
    grouped: dict[str, Counter] = defaultdict(Counter)
    for finding in _items(findings):
        grouped[finding.rule_id][finding.status.value] += max(finding.count, 1)

    rows = []
    for rule_id in sorted(grouped):
        counts = grouped[rule_id]
        rows.append({
            "Rule": rule_id,
            "PASS": counts.get("PASS", 0),
            "FAIL": counts.get("FAIL", 0),
            "REVIEW": counts.get("REVIEW", 0),
            "NOT_VERIFIED": counts.get("NOT_VERIFIED", 0),
            "INFO": counts.get("INFO", 0),
            "Total": sum(counts.values()),
        })
    return pd.DataFrame(rows)


def placement_status(placement_id: str, findings) -> str:
    statuses = [f.status.value for f in _items(findings) if f.placement_id == placement_id]
    if not statuses:
        return "NOT_VERIFIED"
    return max(statuses, key=lambda status: STATUS_PRIORITY.get(status, 0))


def placement_rows(match_result, findings, tag_matches) -> list[dict]:
    """Una fila por placement trabajado: lo que va en 'Worked Placements'."""
    tag_rows: Counter = Counter()
    for _name, _result, tag_match in tag_matches or []:
        for link in tag_match.links:
            tag_rows[link.placement_id] += 1

    matched = {pm.placement_id: pm for pm in match_result.matched}
    missing = {ep.placement_id: ep for ep in match_result.only_expected}
    rows = []
    for placement_id in sorted(set(matched) | set(missing)):
        pm = matched.get(placement_id)
        expected = pm.expected if pm is not None else missing[placement_id]
        actual = pm.actual if pm is not None else None
        rows.append({
            "Status": placement_status(placement_id, findings),
            "Placement ID": placement_id,
            "Placement Name": expected.name,
            "Request Type": expected.request_type or "-",
            "Dimensions": expected.dims or "-",
            "Creatives": len(pm.creative_links) if pm is not None else 0,
            "Tag Rows": tag_rows.get(placement_id, 0),
            "Found in Innovid": "Yes" if actual else "No",
        })
    return rows


def tag_coverage_rows(tag_matches) -> list[dict]:
    return [
        {
            "File": file_name,
            "Campaign ID": tags_result.campaign_id,
            "Sheet": tags_result.sheet,
            "Placements": tags_result.distinct_placements,
            "Materialized Tags": tags_result.total_tags,
            "Rows In Scope": len(tag_match.matched_to_scope),
            "Rows Out of Scope": len(tag_match.outside_scope),
            "No Innovid Match": len(tag_match.missing_in_innovid),
        }
        for file_name, tags_result, tag_match in tag_matches or []
    ]


def tag_family_rows(tag_analysis) -> list[dict]:
    """El panel de arriba de la hoja Tags: una linea por tipo de placement."""
    return [
        {
            "Status": family.status,
            "Placement Type": family.family,
            "Rows": family.rows,
            "Placements": family.placements,
            "Tags": family.tags,
            "Complete": family.complete,
            "To Look At": family.incomplete,
            "Tag Columns": ", ".join(family.columns) or "-",
        }
        for family in tag_analysis.families
    ]


def tag_coverage_counts(tag_analysis, tag_files: int) -> dict:
    counts: dict = {}
    if not tag_analysis.rows:
        return counts
    counts["Tag files"] = tag_files
    counts["Tag rows"] = len(tag_analysis.rows)
    counts["Placements in the tag files"] = tag_analysis.placements
    counts["Tags delivered"] = tag_analysis.total_tags
    if tag_analysis.coverage_known:
        counts["Worked placements in the Traffic Sheet"] = tag_analysis.ts_worked
        counts["Of those, found in the tag files"] = tag_analysis.ts_covered
        counts["Missing from the tag files"] = len(tag_analysis.missing_from_tags)
    counts["Rows to look at"] = len(tag_analysis.incomplete)
    return counts


# ------------------------------------------------------------ informes

@dataclass
class ReportInputs:
    """Todo lo que necesitan los dos informes de una corrida."""

    ts_result: Any
    match_result: Any
    findings: list
    profile_used: str
    detected_profile: str
    detection_evidence: str
    file_rows: list[dict]
    tags_results: list = field(default_factory=list)
    tag_matches: list = field(default_factory=list)
    tag_analysis: Any = None
    dv_result: Any = None
    innovid_reconciliation: Any = None
    evidence_images: list[tuple[str, bytes]] = field(default_factory=list)
    # Implementation Record
    campaign: str = ""
    request_type: str = ""
    wrike_id: str = ""
    implemented_by: str = ""
    qa1_result: str = ""
    implementation_date: date | None = None
    qa2_by: str = ""
    qa2_date: date | None = None
    qa3_by: str = ""
    qa3_date: date | None = None
    notes: str = ""


def report_meta(inputs: ReportInputs) -> ReportMeta:
    findings = inputs.findings
    scorecard = Scorecard.from_findings(findings)
    verdict = scorecard.verdict
    match_result = inputs.match_result
    return ReportMeta(
        verdict=verdict,
        verdict_label=VERDICT_LABELS.get(verdict, verdict),
        # El veredicto partido en dos, igual que en pantalla: el reporte
        # que se reparte tiene que decir lo mismo que vio quien lo genero.
        scope_verdicts=verdicts_by_scope(findings),
        scope_summary=scope_headline(findings),
        profile_used=inputs.profile_used,
        detected_profile=inputs.detected_profile,
        detection_evidence=inputs.detection_evidence,
        scope_guard=match_result.scope_guard or "UNKNOWN",
        scope_evidence=match_result.scope_evidence,
        ts_campaign_id=match_result.ts_campaign_id,
        export_campaign_id=match_result.export_campaign_id,
        metrics={
            "Worked Placements": match_result.expected_total,
            "Found": len(match_result.matched),
            "Missing": len(match_result.only_expected),
            "Tag Files": len(inputs.tags_results),
            "Errors": scorecard.errors,
            "Reviews": scorecard.reviews,
            "Not Verified": scorecard.not_verified,
        },
        source_files=[row["File"] for row in inputs.file_rows],
        campaign=inputs.campaign,
        request_type=inputs.request_type,
        wrike_id=inputs.wrike_id,
        implemented_by=inputs.implemented_by,
        qa1_result=inputs.qa1_result,
        implementation_date=inputs.implementation_date,
        qa2_by=inputs.qa2_by,
        qa2_date=inputs.qa2_date,
        qa3_by=inputs.qa3_by,
        qa3_date=inputs.qa3_date,
        notes=inputs.notes,
    )


def build_pdf(inputs: ReportInputs) -> bytes:
    findings = inputs.findings
    return build_pdf_report(
        report_meta(inputs),
        findings_df=findings_dataframe([f for f in findings if f.status.value != "PASS"]),
        rules_df=rule_summary_dataframe(findings),
        files_df=pd.DataFrame(inputs.file_rows),
        placements_df=pd.DataFrame(
            placement_rows(inputs.match_result, findings, inputs.tag_matches)
        ),
        evidence_images=inputs.evidence_images,
        logo_path=logo_path(),
    )


def build_excel(inputs: ReportInputs) -> bytes:
    findings = inputs.findings
    tag_analysis = inputs.tag_analysis
    if tag_analysis is None:
        tag_analysis = analyse_tags(inputs.tags_results, inputs.ts_result)
    coverage = tag_coverage_rows(inputs.tag_matches)
    dv_rows = dv_table(inputs.dv_result)
    return build_excel_report(
        report_meta(inputs),
        findings_df=findings_dataframe(findings),
        rules_df=rule_summary_dataframe(findings),
        files_df=pd.DataFrame(inputs.file_rows),
        placements_df=pd.DataFrame(
            placement_rows(inputs.match_result, findings, inputs.tag_matches)
        ),
        tag_coverage_df=pd.DataFrame(coverage) if coverage else None,
        tags_df=pd.DataFrame(import_table(tag_analysis)) if tag_analysis.rows else None,
        tag_summary_rows=tag_family_rows(tag_analysis),
        tag_coverage_counts=tag_coverage_counts(tag_analysis, len(inputs.tags_results)),
        dv_tags_df=pd.DataFrame(dv_rows) if dv_rows else None,
        evidence_images=inputs.evidence_images,
        innovid_reconciliation=inputs.innovid_reconciliation,
        logo_path=logo_path(),
        qa_rows=build_qa_rows(inputs.match_result, findings, inputs.innovid_reconciliation),
    )

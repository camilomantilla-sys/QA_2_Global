"""
Branded PDF export of a QA2 run.

Mirrors what the Streamlit UI shows (verdict, metrics, findings) so a
QA2 result can be saved and shared as a record of what was analyzed,
without needing the app running.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd  # type: ignore
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PAGE_W, PAGE_H = letter

WPP_INDIGO = HexColor("#4B5EEA")
WPP_INDIGO_DARK = HexColor("#2C36A8")
WPP_CYAN = HexColor("#17B4DE")
WPP_MINT = HexColor("#0FA97C")
WPP_INK = HexColor("#171B2E")
WPP_MUTED = HexColor("#64748B")
WPP_BORDER = HexColor("#E2E6FB")
WPP_BG = HexColor("#F5F7FD")

STATUS_COLORS = {
    "PASS": WPP_MINT,
    "FAIL": HexColor("#DC2626"),
    "REVIEW": HexColor("#D97706"),
    "NOT_VERIFIED": WPP_MUTED,
    "INFO": WPP_CYAN,
}

VERDICT_COLORS = {
    "PASSED": WPP_MINT,
    "FAILED": HexColor("#DC2626"),
    "BLOCKED": HexColor("#991B1B"),
    "NEEDS_REVIEW": HexColor("#D97706"),
    "NO_CHECKS": WPP_MUTED,
}


@dataclass
class ReportMeta:
    """Everything needed to render the report header/summary."""

    verdict: str
    verdict_label: str
    profile_used: str
    detected_profile: str
    detection_evidence: str
    scope_guard: str
    scope_evidence: str
    ts_campaign_id: str
    export_campaign_id: str
    metrics: dict[str, int] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    source_files: list[str] = field(default_factory=list)

    # Implementation record -- filled from the sidebar, or left blank
    # for the reviewer to fill by hand on a printed copy.
    campaign: str = ""
    request_type: str = ""
    wrike_id: str = ""
    implemented_by: str = ""
    implementation_date: date | None = None
    qa2_by: str = ""
    qa2_date: date | None = None
    qa3_by: str = ""
    qa3_date: date | None = None
    notes: str = ""


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "QA2Title", parent=base["Title"], textColor=colors.white,
            fontSize=20, leading=24, alignment=0,
        ),
        "subtitle": ParagraphStyle(
            "QA2Subtitle", parent=base["Normal"], textColor=colors.white,
            fontSize=9.5, leading=13, alignment=0,
        ),
        "h2": ParagraphStyle(
            "QA2H2", parent=base["Heading2"], textColor=WPP_INK,
            fontSize=13, spaceBefore=14, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "QA2Body", parent=base["Normal"], textColor=WPP_INK,
            fontSize=9, leading=13,
        ),
        "muted": ParagraphStyle(
            "QA2Muted", parent=base["Normal"], textColor=WPP_MUTED,
            fontSize=8, leading=11,
        ),
        "cell": ParagraphStyle(
            "QA2Cell", parent=base["Normal"], textColor=WPP_INK,
            fontSize=7.6, leading=10,
        ),
        "cell_head": ParagraphStyle(
            "QA2CellHead", parent=base["Normal"], textColor=colors.white,
            fontSize=7.8, leading=10, fontName="Helvetica-Bold",
        ),
    }


def _header_flowables(meta: ReportMeta, styles, logo_path: Path | None):
    row = []
    if logo_path is not None and logo_path.exists():
        img = Image(str(logo_path), width=42 * mm, height=23.6 * mm)
        row.append(img)

    title_block = [
        Paragraph("INNOVID QA2 AUTOMATION", styles["title"]),
        Paragraph(
            "QA2 Report &mdash; Traffic Sheet vs Innovid validation",
            styles["subtitle"],
        ),
    ]
    row.append(title_block)

    header_table = Table(
        [row],
        colWidths=[46 * mm, None] if len(row) == 2 else None,
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WPP_INDIGO_DARK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    return [header_table, Spacer(1, 14)]


def _verdict_flowable(meta: ReportMeta, styles):
    color = VERDICT_COLORS.get(meta.verdict, WPP_MUTED)
    data = [
        [Paragraph("OVERALL QA2 RESULT", styles["muted"])],
        [
            Paragraph(
                f'<font color="{color.hexval()}"><b>{meta.verdict_label}</b>'
                f"</font>",
                ParagraphStyle(
                    "verdictValue", parent=styles["body"], fontSize=17,
                    leading=21,
                ),
            )
        ],
    ]
    t = Table(data, colWidths=[170 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, WPP_BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 4, color),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def _info_flowable(meta: ReportMeta, styles):
    lines = [
        f"<b>Profile used:</b> {meta.profile_used}",
        f"<b>Detected profile:</b> {meta.detected_profile}",
        f"<b>Evidence:</b> {meta.detection_evidence}",
        f"<b>Scope Guard:</b> {meta.scope_guard} "
        f"&mdash; {meta.scope_evidence}",
        f"<b>Campaign ID (TS / Innovid):</b> "
        f"{meta.ts_campaign_id or '-'} / {meta.export_campaign_id or '-'}",
        f"<b>Generated:</b> "
        f"{meta.generated_at.strftime('%Y-%m-%d %H:%M')}",
    ]
    if meta.source_files:
        lines.append(f"<b>Source files:</b> {', '.join(meta.source_files)}")

    para = Paragraph("<br/>".join(lines), styles["body"])
    t = Table([[para]], colWidths=[170 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, WPP_BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), WPP_BG),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def _esc(text: str) -> str:
    """Escape user-typed text before it goes into reportlab markup."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _blank(value: str | None, width: int = 28) -> str:
    """Render a filled value, or an underscored blank line to fill by hand."""
    if value:
        return _esc(value)
    return "_" * width


def _blank_date(value: date | None) -> str:
    if value:
        return value.strftime("%Y-%m-%d")
    return "_" * 14


def _record_flowable(meta: ReportMeta, styles):
    left = [
        f"<b>Campaign:</b> {_blank(meta.campaign, 34)}",
        f"<b>Request Type:</b> {_blank(meta.request_type, 34)}",
        f"<b>Wrike ID:</b> {_blank(meta.wrike_id, 20)}",
        f"<b>Implemented By:</b> {_blank(meta.implemented_by, 24)}",
        f"<b>Implementation Date:</b> "
        f"{_blank_date(meta.implementation_date)}",
    ]
    right = [
        f"<b>QA2 By:</b> {_blank(meta.qa2_by, 24)}",
        f"<b>QA2 Date:</b> {_blank_date(meta.qa2_date)}",
        f"<b>QA3 By:</b> {_blank(meta.qa3_by, 24)}",
        f"<b>QA3 Date:</b> {_blank_date(meta.qa3_date)}",
    ]

    left_para = Paragraph("<br/><br/>".join(left), styles["body"])
    right_para = Paragraph("<br/><br/>".join(right), styles["body"])

    t = Table([[left_para, right_para]], colWidths=[85 * mm, 85 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, WPP_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, WPP_BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    caption = Paragraph(
        "IMPLEMENTATION RECORD &mdash; fill in the app or by hand",
        styles["muted"],
    )
    flowables = [caption, Spacer(1, 4), t]

    if meta.notes:
        notes_para = Paragraph(
            _esc(meta.notes).replace("\n", "<br/>"), styles["body"]
        )
        notes_table = Table([[notes_para]], colWidths=[170 * mm])
        notes_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.75, WPP_BORDER),
                    ("BACKGROUND", (0, 0), (-1, -1), WPP_BG),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        flowables += [
            Spacer(1, 8),
            Paragraph("NOTES / CALLOUTS", styles["muted"]),
            Spacer(1, 4),
            notes_table,
        ]

    return flowables


def _metrics_flowable(meta: ReportMeta, styles):
    items = list(meta.metrics.items())
    cells = []
    for label, value in items:
        cell_style = ParagraphStyle(
            "metricValue", parent=styles["body"], fontSize=15,
            fontName="Helvetica-Bold", textColor=WPP_INDIGO_DARK,
        )
        cells.append(
            [
                Paragraph(label, styles["muted"]),
                Paragraph(str(value), cell_style),
            ]
        )

    row = [
        Table(
            [[c[0]], [c[1]]],
            colWidths=[170 * mm / len(cells)],
            style=TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.75, WPP_BORDER),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        )
        for c in cells
    ]
    wrapper = Table([row], colWidths=None)
    wrapper.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return wrapper


def _df_to_table(df: pd.DataFrame, styles, col_widths=None,
                  status_col: str | None = None, max_rows: int = 400):
    if df.empty:
        return Paragraph("No rows.", styles["muted"])

    shown = df.head(max_rows)
    header = [Paragraph(str(c), styles["cell_head"]) for c in shown.columns]
    rows = [header]

    for _, row in shown.iterrows():
        cells = []
        for col in shown.columns:
            text = str(row[col]) if pd.notna(row[col]) else ""
            text = text.replace("&", "&amp;").replace("<", "&lt;")
            if col == status_col and text in STATUS_COLORS:
                color = STATUS_COLORS[text].hexval()
                text = f'<font color="{color}"><b>{text}</b></font>'
            cells.append(Paragraph(text[:400], styles["cell"]))
        rows.append(cells)

    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), WPP_INDIGO),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, WPP_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, WPP_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(style))

    flowables = [t]
    if len(df) > max_rows:
        flowables.append(Spacer(1, 4))
        flowables.append(
            Paragraph(
                f"Showing the first {max_rows} of {len(df)} rows. "
                "Download the CSV for the full list.",
                styles["muted"],
            )
        )
    return flowables


def _evidence_flowables(
    evidence_images: list[tuple[str, bytes]], styles
):
    if not evidence_images:
        return [
            Paragraph(
                "No evidence screenshots were attached to this run.",
                styles["muted"],
            )
        ]

    max_w, max_h = 170 * mm, 150 * mm
    flowables = []

    for name, raw_bytes in evidence_images:
        try:
            reader = ImageReader(io.BytesIO(raw_bytes))
            iw, ih = reader.getSize()
        except Exception:
            continue

        scale = min(max_w / iw, max_h / ih, 1.0) if iw and ih else 1.0
        w, h = iw * scale, ih * scale

        img = Image(io.BytesIO(raw_bytes), width=w, height=h)
        caption = Paragraph(name, styles["muted"])
        frame = Table(
            [[img], [caption]],
            colWidths=[170 * mm],
        )
        frame.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.75, WPP_BORDER),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        flowables.append(KeepTogether([frame, Spacer(1, 12)]))

    return flowables


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(WPP_MUTED)
    canvas.drawString(
        20 * mm, 10 * mm, "WPP Media · Innovid QA2 Automation"
    )
    canvas.drawRightString(
        PAGE_W - 20 * mm, 10 * mm, f"Page {doc.page}"
    )
    canvas.setStrokeColor(WPP_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 13 * mm, PAGE_W - 20 * mm, 13 * mm)
    canvas.restoreState()


def build_pdf_report(
    meta: ReportMeta,
    findings_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    files_df: pd.DataFrame,
    placements_df: pd.DataFrame | None = None,
    evidence_images: list[tuple[str, bytes]] | None = None,
    logo_path: Path | None = None,
) -> bytes:
    """Render the full branded QA2 report and return it as PDF bytes."""
    styles = _styles()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title="Innovid QA2 Automation Report",
    )

    story = []
    story += _header_flowables(meta, styles, logo_path)
    story.append(_verdict_flowable(meta, styles))
    story.append(Spacer(1, 10))
    story.append(_info_flowable(meta, styles))
    story.append(Spacer(1, 10))
    story.append(_metrics_flowable(meta, styles))
    story.append(Spacer(1, 14))
    story += _record_flowable(meta, styles)

    story.append(Spacer(1, 6))
    story.append(PageBreak())

    story.append(Paragraph("Worked Placements — Scope", styles["h2"]))
    story.append(
        Paragraph(
            "Every placement in the worked scope, with its match "
            "status against Innovid. The app's collapsible detail "
            "per placement (creatives, URLs, attribution, tags) is "
            "in the Findings table below.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 6))
    placements_df = (
        placements_df if placements_df is not None else pd.DataFrame()
    )
    story.append(
        Paragraph(
            f"Total placements: {len(placements_df)}", styles["muted"]
        )
    )
    story.append(Spacer(1, 4))
    placements_cols = [
        c for c in [
            "Status", "Placement ID", "Placement Name", "Request Type",
            "Dimensions", "Creatives", "Tag Rows", "Found in Innovid",
        ]
        if c in placements_df.columns
    ]
    placements_widths = None
    if placements_cols:
        weights = {
            "Status": 0.08, "Placement ID": 0.10,
            "Placement Name": 0.34, "Request Type": 0.13,
            "Dimensions": 0.10, "Creatives": 0.08, "Tag Rows": 0.08,
            "Found in Innovid": 0.09,
        }
        total = 170 * mm
        placements_widths = [
            total * weights.get(c, 1 / len(placements_cols))
            for c in placements_cols
        ]
    result = _df_to_table(
        placements_df[placements_cols]
        if placements_cols else placements_df,
        styles, col_widths=placements_widths, status_col="Status",
    )
    story += result if isinstance(result, list) else [result]

    story.append(PageBreak())
    story.append(Paragraph("Findings", styles["h2"]))
    story.append(
        Paragraph(
            "All non-PASS findings from this run.", styles["muted"]
        )
    )
    story.append(Spacer(1, 6))
    findings_cols = [
        c for c in [
            "Status", "Rule", "Placement ID", "Placement Name",
            "Message", "Expected", "Found", "Reason",
        ]
        if c in findings_df.columns
    ]
    display_df = findings_df[findings_cols] if findings_cols else findings_df
    col_widths = None
    if findings_cols:
        weights = {
            "Status": 0.09, "Rule": 0.09, "Placement ID": 0.10,
            "Placement Name": 0.15, "Message": 0.20, "Expected": 0.13,
            "Found": 0.13, "Reason": 0.11,
        }
        total = 170 * mm
        col_widths = [
            total * weights.get(c, 1 / len(findings_cols))
            for c in findings_cols
        ]
    story.append(
        Paragraph(f"Total findings: {len(display_df)}", styles["muted"])
    )
    story.append(Spacer(1, 4))
    result = _df_to_table(
        display_df, styles, col_widths=col_widths, status_col="Status"
    )
    story += result if isinstance(result, list) else [result]

    story.append(PageBreak())
    story.append(Paragraph("Rule Execution Coverage", styles["h2"]))
    story.append(Spacer(1, 4))
    result = _df_to_table(rules_df, styles)
    story += result if isinstance(result, list) else [result]

    story.append(Spacer(1, 14))
    story.append(Paragraph("Files & Extraction", styles["h2"]))
    story.append(Spacer(1, 4))
    result = _df_to_table(files_df, styles, status_col="Status")
    story += result if isinstance(result, list) else [result]

    story.append(PageBreak())
    story.append(Paragraph("Implementation Evidence", styles["h2"]))
    story.append(
        Paragraph(
            "Screenshots attached in the app as evidence of the "
            "Innovid implementation.",
            styles["muted"],
        )
    )
    story.append(Spacer(1, 8))
    story += _evidence_flowables(evidence_images or [], styles)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()

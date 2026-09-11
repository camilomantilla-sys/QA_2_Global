"""
Branded multi-tab Excel export of a QA2 run.

Meant as the detailed working record analysts filter/pivot on day to
day; the PDF report is the print-and-sign record for QA3. Both are
built from the same underlying dataframes so they never disagree.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd  # type: ignore
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from core.pdf_report import ReportMeta
from core.qa_export import COLUMNS as QA_COLUMNS, PAIRS, cells_agree

# WPP Media Brand Guidelines 2025 v1.0 (openpyxl wants RRGGBB, no #).
WPP_NAVY = "000050"
WPP_LIME = "B0F467"
WPP_PANTONE_629 = "93DFE3"
WPP_CORNFLOWER = "5465FF"

WPP_INDIGO = WPP_CORNFLOWER
WPP_INDIGO_DARK = WPP_NAVY
WPP_INK = WPP_NAVY
WPP_MUTED = "6B7194"
WPP_BG = "F6F8FC"

# Verde de acuerdo: la TS y lo que Innovid tiene dicen lo mismo.
# Deliberadamente suave -- son cientos de celdas, y un verde fuerte
# taparia las pocas que no coinciden, que son las que hay que ver.
AGREE_FILL = PatternFill("solid", start_color="E8F8E4", end_color="E8F8E4")

# Naranja de desacuerdo: los dos lados traen dato y no dicen lo mismo.
# Estas son las celdas que hay que mirar, asi que llevan mas color que
# el verde. Un par donde falta uno de los dos lados no se pinta de
# ninguno: no es un desacuerdo, es que no hay con que comparar, y
# teñirlo mandaria a revisar algo que nadie ha contradicho.
DISAGREE_FILL = PatternFill("solid", start_color="FFE0B2", end_color="FFE0B2")

# Lo que no coincide PERO alguien firmo a mano. En naranja se
# confundia con lo que sigue abierto, y justo eso -- que se aprobo por
# decision de una persona y no porque cuadrara -- es lo que hay que
# poder ver de un vistazo al abrir el archivo.
SIGNED_OFF_FILL = PatternFill("solid", start_color="D9CCF0", end_color="D9CCF0")

STATUS_FILLS = {
    "PASS": "D9F7EC",
    "FAIL": "FDE2E2",
    "REVIEW": "FDECD2",
    "NOT_VERIFIED": "E9EBF3",
    "INFO": "D9F2FA",
}

STATUS_FONT_COLORS = {
    "PASS": "0FA97C",
    "FAIL": "DC2626",
    "REVIEW": "B45309",
    "NOT_VERIFIED": "475569",
    "INFO": "0E7490",
}

HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
HEADER_FILL = PatternFill(
    start_color=WPP_INDIGO, end_color=WPP_INDIGO, fill_type="solid"
)
TITLE_FONT = Font(color=WPP_INDIGO_DARK, bold=True, size=15)
LABEL_FONT = Font(color=WPP_MUTED, bold=True, size=9)
VALUE_FONT = Font(color=WPP_INK, size=10)
BODY_FONT = Font(color=WPP_INK, size=9.5)


def _write_table(
    ws: Worksheet, df: pd.DataFrame, start_row: int = 1,
    status_col: str | None = None,
) -> int:
    """Write a dataframe as a styled, filterable table. Returns next free row."""
    if df.empty:
        ws.cell(
            row=start_row, column=1, value="No rows."
        ).font = BODY_FONT
        return start_row + 2

    for col_idx, col_name in enumerate(df.columns, start=1):
        cell = ws.cell(row=start_row, column=col_idx, value=str(col_name))
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    status_idx = (
        list(df.columns).index(status_col) + 1
        if status_col and status_col in df.columns
        else None
    )

    for row_offset, (_, row) in enumerate(df.iterrows(), start=1):
        row_num = start_row + row_offset
        for col_idx, col_name in enumerate(df.columns, start=1):
            value = row[col_name]
            if pd.isna(value):
                value = ""
            cell = ws.cell(row=row_num, column=col_idx, value=value)
            cell.font = BODY_FONT
            cell.alignment = Alignment(
                vertical="top", wrap_text=(col_idx != status_idx)
            )
            if (
                status_idx
                and col_idx == status_idx
                and str(value) in STATUS_FILLS
            ):
                cell.fill = PatternFill(
                    start_color=STATUS_FILLS[str(value)],
                    end_color=STATUS_FILLS[str(value)],
                    fill_type="solid",
                )
                cell.font = Font(
                    color=STATUS_FONT_COLORS[str(value)],
                    bold=True,
                    size=9.5,
                )

    last_row = start_row + len(df)
    last_col = len(df.columns)
    ws.auto_filter.ref = (
        f"A{start_row}:{get_column_letter(last_col)}{last_row}"
    )
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1).coordinate

    for col_idx, col_name in enumerate(df.columns, start=1):
        max_len = max(
            [len(str(col_name))]
            + [
                len(str(v)) for v in df[col_name].head(300).tolist()
            ]
        )
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            max(max_len + 2, 10), 60
        )

    return last_row + 2


def _blank(value, fallback: str = "") -> str:
    return str(value) if value else fallback


def _summary_sheet(wb: Workbook, meta: ReportMeta, logo_path: Path | None):
    ws = wb.active
    ws.title = "Summary"

    row = 1
    if logo_path is not None and logo_path.exists():
        img = XLImage(str(logo_path))
        # Proporcion real: un ancho fijo con un alto fijo deforma
        # cualquier logo que no sea el banner original.
        ratio = (img.height / img.width) if img.width else 0.56
        img.width = 180
        img.height = round(180 * ratio)
        ws.add_image(img, "A1")
        row = max(2, round(img.height / 20) + 2)

    ws.cell(row=row, column=1, value="INNOVID QA AUTOMATION").font = (
        TITLE_FONT
    )
    row += 1
    ws.cell(
        row=row, column=1,
        value=f"Overall result: {meta.verdict_label}",
    ).font = Font(
        color=STATUS_FONT_COLORS.get(
            "FAIL"
            if meta.verdict in ("FAILED", "BLOCKED")
            else "REVIEW" if meta.verdict == "NEEDS_REVIEW" else "PASS",
            WPP_INK,
        ),
        bold=True, size=12,
    )
    # El desplegable de aprobacion, al lado del veredicto. Excel de
    # verdad usa un control de formulario para esto, que openpyxl no
    # sabe escribir; una celda con lista desplegable se marca igual de
    # rapido, viaja dentro del propio .xlsx y no necesita macros.
    approval_cell = ws.cell(row=row, column=2, value="PENDING")
    approval_cell.font = Font(color=WPP_INK, bold=True, size=12)
    approval_cell.alignment = Alignment(horizontal="center")
    approval_cell.border = Border(*(Side(style="thin", color=WPP_MUTED),) * 4)

    approval = DataValidation(
        type="list",
        formula1='"APPROVED,NOT APPROVED,PENDING"',
        allow_blank=False,
        showDropDown=False,   # False = SI muestra la flecha (Excel lo
                              # nombra al reves: es "ocultar" invertido)
    )
    approval.error = "Pick APPROVED, NOT APPROVED or PENDING."
    approval.prompt = "QA2 sign-off for this campaign."
    ws.add_data_validation(approval)
    approval.add(approval_cell)

    # Se pinta sola al elegir: el color tiene que seguir a lo que
    # quede escrito en el archivo, no a lo que hubiera cuando QA2 lo
    # genero.
    target = f"{approval_cell.coordinate}:{approval_cell.coordinate}"
    for value, key in (("APPROVED", "PASS"), ("NOT APPROVED", "FAIL")):
        ws.conditional_formatting.add(target, CellIsRule(
            operator="equal",
            formula=[f'"{value}"'],
            fill=PatternFill("solid", start_color=STATUS_FILLS[key],
                             end_color=STATUS_FILLS[key]),
            font=Font(color=STATUS_FONT_COLORS[key], bold=True, size=12),
        ))

    row += 1

    # Quien firmo y cuando ya viven en el Implementation Record, unas
    # filas mas abajo. Aqui habia ademas una celda de texto libre que
    # repetia lo mismo y pedia editarla a mano: dos sitios donde
    # escribir la misma firma es un sitio de mas.

    info_rows = [
        ("Profile used", meta.profile_used),
        ("Detected profile", meta.detected_profile),
        ("Evidence", meta.detection_evidence),
        ("Scope Guard", f"{meta.scope_guard} — {meta.scope_evidence}"),
        (
            "Campaign ID (TS / Innovid)",
            f"{meta.ts_campaign_id or '-'} / "
            f"{meta.export_campaign_id or '-'}",
        ),
        ("Generated", meta.generated_at.strftime("%Y-%m-%d %H:%M")),
        ("Source files", ", ".join(meta.source_files)),
    ]
    for label, value in info_rows:
        ws.cell(row=row, column=1, value=label).font = LABEL_FONT
        ws.cell(row=row, column=2, value=value).font = VALUE_FONT
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Metrics").font = Font(
        color=WPP_INDIGO_DARK, bold=True, size=11
    )
    row += 1
    for label, value in meta.metrics.items():
        ws.cell(row=row, column=1, value=label).font = LABEL_FONT
        ws.cell(row=row, column=2, value=value).font = Font(
            color=WPP_INDIGO_DARK, bold=True, size=11
        )
        row += 1

    row += 1
    ws.cell(
        row=row, column=1, value="Implementation Record"
    ).font = Font(color=WPP_INDIGO_DARK, bold=True, size=11)
    row += 1
    record_rows = [
        ("Campaign", meta.campaign),
        ("Request Type", meta.request_type),
        ("Wrike ID", meta.wrike_id),
        ("Implemented By", meta.implemented_by),
        (
            "Implementation Date",
            meta.implementation_date.isoformat()
            if meta.implementation_date else "",
        ),
        ("QA2 By", meta.qa2_by),
        ("QA2 Date", meta.qa2_date.isoformat() if meta.qa2_date else ""),
        ("QA3 By", meta.qa3_by),
        ("QA3 Date", meta.qa3_date.isoformat() if meta.qa3_date else ""),
    ]
    for label, value in record_rows:
        ws.cell(row=row, column=1, value=label).font = LABEL_FONT
        ws.cell(row=row, column=2, value=_blank(value, "—")).font = (
            VALUE_FONT
        )
        row += 1

    if meta.notes:
        row += 1
        ws.cell(row=row, column=1, value="Notes / Callouts").font = Font(
            color=WPP_INDIGO_DARK, bold=True, size=11
        )
        row += 1
        cell = ws.cell(row=row, column=1, value=meta.notes)
        cell.font = BODY_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(
            start_row=row, start_column=1, end_row=row + 3, end_column=6
        )

    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 60



def _qa_sheet(wb: Workbook, qa_rows: list[dict]) -> None:
    """
    El entregable en horizontal: una fila por creativo, los dos lados
    en columnas pareadas.
    """
    ws = wb.create_sheet("QA")

    if not qa_rows:
        _write_table(ws, pd.DataFrame(columns=QA_COLUMNS), status_col="Status")
        return

    df = pd.DataFrame(qa_rows, columns=QA_COLUMNS)
    _write_table(ws, df, status_col="Status")

    index = {name: pos for pos, name in enumerate(QA_COLUMNS, start=1)}

    # Verde donde los dos lados coinciden, naranja donde no. Se pintan
    # LAS DOS celdas del par: pintar solo la de Innovid haria pensar
    # que el color es un veredicto sobre Innovid y no sobre el acuerdo
    # entre ambos.
    for offset, row in enumerate(qa_rows, start=2):
        signed_off = "MANUALLY" in str(row.get("Notes") or "")
        for left, right in PAIRS:
            left_value = str(row.get(left) or "").strip()
            right_value = str(row.get(right) or "").strip()

            if not left_value or not right_value:
                # Falta un lado: no hay acuerdo ni desacuerdo, hay una
                # comparacion que no se pudo hacer. Sin color.
                continue

            if cells_agree(left_value, right_value):
                fill = AGREE_FILL
            elif signed_off:
                # La fila es un creativo, y la nota dice que alguien
                # firmo lo que aqui no cuadra -- las fechas que
                # arrancan antes para testear, casi siempre. Si una
                # fila llevara dos discrepancias y solo una firmada,
                # las dos saldrian de este color: la nota, al lado,
                # dice cual se firmo.
                fill = SIGNED_OFF_FILL
            else:
                fill = DISAGREE_FILL

            for column in (left, right):
                ws.cell(row=offset, column=index[column]).fill = fill

    _colour_legend(ws, len(qa_rows) + 3)


def _colour_legend(ws, row: int) -> None:
    """
    Que significa cada color, debajo de la tabla.

    Tres colores sin leyenda son tres colores que cada quien
    interpreta a su manera, y el morado -- "no cuadra pero se firmo"
    -- es justo el que nadie adivina.
    """
    ws.cell(row=row, column=1, value="Colours").font = Font(
        color=WPP_INK, bold=True, size=10
    )
    entries = (
        (AGREE_FILL, "Traffic Sheet and Innovid agree"),
        (DISAGREE_FILL, "They differ, and it is still open"),
        (SIGNED_OFF_FILL,
         "They differ, and a reviewer signed it off by hand "
         "-- see Notes for who and why"),
    )
    for offset, (fill, text) in enumerate(entries, start=1):
        swatch = ws.cell(row=row + offset, column=1, value="")
        swatch.fill = fill
        swatch.border = Border(*(Side(style="thin", color=WPP_MUTED),) * 4)
        ws.cell(row=row + offset, column=2, value=text).font = Font(
            color=WPP_MUTED, size=9
        )


def build_excel_report(
    meta: ReportMeta,
    findings_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    files_df: pd.DataFrame,
    placements_df: pd.DataFrame | None = None,
    tag_coverage_df: pd.DataFrame | None = None,
    logo_path: Path | None = None,
    qa_rows: list[dict] | None = None,
) -> bytes:
    """Render the full branded QA2 workbook and return it as XLSX bytes."""
    wb = Workbook()

    _summary_sheet(wb, meta, logo_path)

    # Primero la hoja QA: es la que se revisa. Las demas son el
    # detalle al que se baja cuando una fila no cuadra.
    _qa_sheet(wb, qa_rows or [])

    ws = wb.create_sheet("Worked Placements")
    _write_table(
        ws, placements_df if placements_df is not None else pd.DataFrame(),
        status_col="Status",
    )

    ws = wb.create_sheet("Findings")
    _write_table(ws, findings_df, status_col="Status")

    ws = wb.create_sheet("Rules Executed")
    _write_table(ws, rules_df)

    ws = wb.create_sheet("Files & Extraction")
    _write_table(ws, files_df, status_col="Status")

    if tag_coverage_df is not None:
        ws = wb.create_sheet("Tag Coverage")
        _write_table(ws, tag_coverage_df)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

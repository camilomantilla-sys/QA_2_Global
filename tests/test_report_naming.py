"""
Como se llama el archivo que alguien se descarga, y que pestanas del
Excel se ven.

Se llamaban todos `qa_report_20260918_1734.xlsx`. En la carpeta
compartida del equipo eso es una lista de archivos identicos donde hay
que abrirlos para saber cual es cual. Camilo: "que el excel se exporte
con el siguiente nombre: Fecha_QA_Report_CampaignName".

La fecha va en ISO y delante para que la carpeta los ordene sola. Y
los nombres de campana traen `|`, `/` y `:`, que Windows no acepta en
un nombre de archivo -- el explorador se niega a guardar y no dice por
que.

Run with pytest, or directly:
    python tests/test_report_naming.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.report_name import report_filename, safe_part  # noqa: E402

DIA = date(2026, 9, 18)


def test_the_date_comes_first_and_sorts():
    name = report_filename("xlsx", "Acrobat", DIA)
    assert name.startswith("2026-09-18_")
    assert name == "2026-09-18_QA_Report_Acrobat.xlsx"


def test_the_campaign_is_in_the_name():
    name = report_filename(
        "xlsx",
        "FY26_Q4_AMER_DocumentCloud_Acrobat_Awareness_Discover",
        DIA,
    )
    assert "DocumentCloud_Acrobat" in name


def test_windows_forbidden_characters_are_replaced():
    r"""\ / : * ? " < > | -- el explorador no guarda y no explica."""
    name = report_filename("xlsx", 'BRK|BLK/188: Q2 *test* <a>?', DIA)
    assert not (set(name) & set('\\/:*?"<>|'))
    assert name.endswith(".xlsx")


def test_no_campaign_still_gives_a_correct_name():
    # Un nombre corto y correcto es mejor que uno con un hueco donde
    # iba el dato.
    assert report_filename("pdf", "", DIA) == "2026-09-18_QA_Report.pdf"
    assert report_filename("pdf", "   ", DIA) == "2026-09-18_QA_Report.pdf"


def test_a_very_long_campaign_is_trimmed():
    name = report_filename("xlsx", "A" * 400, DIA)
    assert len(name) < 120


def test_spaces_and_runs_of_underscores_collapse():
    assert safe_part("  Q4   AMER  ") == "Q4_AMER"
    assert safe_part("a///b") == "a_b"


def test_the_extension_can_be_given_with_or_without_a_dot():
    assert report_filename(".pdf", "x", DIA).endswith(".pdf")
    assert report_filename("pdf", "x", DIA).endswith(".pdf")


# ── las pestanas de auditoria del Excel ──────────────────────────────

def test_the_audit_tabs_are_hidden_not_removed():
    """
    Oculta: el dato sigue ahi y vuelve con clic derecho > Mostrar.
    "Muy oculta" no, porque entonces solo se ve desde VBA.
    """
    source = (
        Path(__file__).resolve().parents[1] / "core" / "excel_report.py"
    ).read_text(encoding="utf-8")
    assert 'ws.sheet_state = "hidden"' in source
    assert "veryHidden" not in source

    def _block(sheet: str) -> str:
        """Lo que se hace con esa hoja, hasta que empieza la siguiente."""
        start = source.index(f'create_sheet("{sheet}")')
        nxt = source.find("create_sheet(", start + 20)
        return source[start:nxt if nxt != -1 else len(source)]

    # Y las dos que se ocultan son las de auditoria, no las que se leen.
    for sheet in ("Rules Executed", "Tag Coverage"):
        assert "_audit_tab(ws)" in _block(sheet), sheet

    for sheet in ("Findings", "Worked Placements", "Evidence"):
        assert "_audit_tab(ws)" not in _block(sheet), sheet


def test_the_signed_off_legend_says_what_it_means():
    source = (
        Path(__file__).resolve().parents[1] / "core" / "excel_report.py"
    ).read_text(encoding="utf-8")
    assert "reviewed and accepted" in source
    # La redaccion vieja: "on Status, whatever the row shows; on a
    # pair, where that is what was signed".
    assert "whatever the row shows" not in source


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

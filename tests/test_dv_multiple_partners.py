"""
Una campana puede tener mas de un partner, y DV entrega un archivo por
cada uno.

El uploader de DV Pinnacle aceptaba uno solo. Camilo, probando la
solicitud de BlackRock: "solo deja subir un archivo de dv pinnacle y
hay casos que puede ser mas de un partner entonces solo pude subir 1,
pero eran dos."

Los dos archivos de esa solicitud son Bloomberg (18 placements) y The
New York Times (6). Subiendo solo el primero, los 6 del segundo salian

    DV-001 FAIL: Placement requires DV but has no row in the DV
                 Pinnacle file

seis hallazgos falsos sobre trabajo que estaba bien hecho -- y, peor,
indistinguibles de un tag que de verdad no se entrego.

merge_dv_results lee los que hagan falta como si fueran uno. Cada fila
recuerda de que archivo vino, para que un hallazgo se pueda rastrear
hasta el archivo que lo trajo.

Run with pytest, or directly:
    python tests/test_dv_multiple_partners.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.dv_tags import (  # noqa: E402
    DVTagRow,
    DVTagsResult,
    merge_dv_results,
)

BLOOMBERG = "DV_Tags_..._Bloomberg L.P._08.26.2026.xlsx"
NYT = "DV_Tags_..._The New York Times Company_08.26.2026.xlsx"


def partner(name: str, first_id: int, count: int) -> DVTagsResult:
    return DVTagsResult(
        path=f"/downloads/{name}",
        sheet="Site-Served Tags",
        sources=[name],
        rows=[
            DVTagRow(
                row=2 + n,
                placement_id=str(first_id + n),
                placement_name=f"{name[:9]} placement {n}",
                display_tag=f"<script src='dv/{first_id + n}'></script>",
            )
            for n in range(count)
        ],
    )


def both_partners() -> DVTagsResult:
    return merge_dv_results([
        partner(BLOOMBERG, 11084394, 18),
        partner(NYT, 11084412, 6),
    ])


# ── los dos archivos se leen como uno ────────────────────────────────

def test_every_placement_of_every_partner_is_there():
    merged = both_partners()
    assert len(merged.placement_ids) == 24


def test_the_second_partner_is_no_longer_missing():
    """Los 6 que salian FAIL por no haber podido subir su archivo."""
    merged = both_partners()
    for n in range(6):
        assert str(11084412 + n) in merged.placement_ids


def test_each_row_remembers_its_file():
    merged = both_partners()
    counts: dict[str, int] = {}
    for row in merged.rows:
        counts[row.source] = counts.get(row.source, 0) + 1
    assert counts == {BLOOMBERG: 18, NYT: 6}


def test_the_files_are_listed_in_order():
    assert both_partners().sources == [BLOOMBERG, NYT]


def test_the_sheet_survives_the_merge():
    assert both_partners().sheet == "Site-Served Tags"


# ── el caso de siempre no cambia ─────────────────────────────────────

def test_one_file_is_handed_back_untouched():
    """Lo normal sigue siendo un archivo, y no debe pagar nada."""
    only = partner(BLOOMBERG, 11084394, 18)
    assert merge_dv_results([only]) is only


def test_nothing_uploaded_is_nothing_to_read():
    assert merge_dv_results([]) is None
    assert merge_dv_results([None]) is None


# ── un placement en dos archivos ─────────────────────────────────────

def test_the_same_placement_twice_is_one_row():
    """Que aparezca en dos archivos no es un hallazgo."""
    a = partner(BLOOMBERG, 11084394, 2)
    b = partner(NYT, 11084394, 2)
    merged = merge_dv_results([a, b])
    assert len(merged.rows) == 2
    assert len(merged.placement_ids) == 2


def test_the_copy_that_carries_the_tag_wins():
    """
    Si un archivo trae el placement vacio y el otro con su tag, lo que
    importa es que el tag existe.
    """
    empty = DVTagsResult(
        sheet="Site-Served Tags", sources=["empty.xlsx"],
        rows=[DVTagRow(row=2, placement_id="11084394")],
    )
    filled = DVTagsResult(
        sheet="Site-Served Tags", sources=["filled.xlsx"],
        rows=[DVTagRow(row=2, placement_id="11084394",
                       display_tag="<script></script>")],
    )
    merged = merge_dv_results([empty, filled])
    assert len(merged.rows) == 1
    assert merged.rows[0].has_tag
    assert merged.rows[0].source == "filled.xlsx"


def test_every_anomaly_is_kept():
    from core.extraction import Anomaly

    a = partner(BLOOMBERG, 11084394, 1)
    b = partner(NYT, 11084412, 1)
    b.anomalies.append(Anomaly("DV-NO-DATA", "FATAL", "empty"))
    merged = merge_dv_results([a, b])
    assert merged.fatal


# ── la interfaz deja subir varios ────────────────────────────────────

def test_the_uploader_accepts_more_than_one_file():
    app = (Path(__file__).resolve().parents[1] / "ui" / "app_v2.py").read_text(
        encoding="utf-8"
    )
    block = app[app.index('"6. Upload DV Pinnacle Tags"'):][:300]
    assert "accept_multiple_files=True" in block


def test_the_build_badge_is_not_drawn():
    """
    Se quita antes del lanzamiento: al equipo no le dice nada. La
    version sigue yendo al log, que es donde hace falta.
    """
    app = (Path(__file__).resolve().parents[1] / "ui" / "app_v2.py").read_text(
        encoding="utf-8"
    )
    assert "QA build:" not in app
    assert "running_version()" in app


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))

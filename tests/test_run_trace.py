"""
El rastro en disco de cada pasada.

Cuando una pasada no termina, la pagina se queda con el render
anterior y la app no puede contar nada de si misma: lo que se dibuja
solo llega cuando el script acaba. Por eso el rastro va a un archivo.

Este test existe porque el fallo que costo una semana -- "el boton de
firmar no hace nada" -- resulto ser que la pasada de Run QA no
terminaba en su maquina. Sin un archivo, eso no se puede ver.

Run with pytest, or directly:
    python tests/test_run_trace.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")

STAGES = (
    "SCRIPT RUN starts",
    "sidebar drawn",
    "parsing traffic sheet",
    "parsing placement-creative view",
    "matching",
    "running rules",
    "building the review panel",
    "building the PDF",
    "building the Excel",
    "SCRIPT RUN finished",
)


def test_every_stage_of_a_run_is_traced():
    for stage in STAGES:
        assert f'trace("{stage}")' in SOURCE or f'trace(f"{stage}' in SOURCE, stage


def _where(stage: str) -> int:
    """
    Donde se traza una etapa, escrita como cadena o como f-string.

    "SCRIPT RUN starts" lleva el build detras desde que se quito de la
    barra lateral, asi que buscar la cadena cerrada no la encontraba.
    """
    for form in (f'"{stage}"', f'f"{stage}'):
        at = SOURCE.find(form)
        if at != -1:
            return at
    raise AssertionError(f"la etapa {stage!r} no se traza")


def test_the_stages_are_traced_in_order():
    at = [_where(stage) for stage in STAGES]
    assert at == sorted(at), "las etapas no van en el orden de la pasada"


def test_a_failed_run_says_so():
    # Un `except Exception` mudo fue parte del problema.
    assert 'trace(f"SCRIPT RUN failed:' in SOURCE


def test_innovid_is_traced_on_both_sides():
    # Es la etapa que puede tardar minutos: hay que poder ver si
    # entro y no salio.
    assert 'trace(f"reading Innovid campaign' in SOURCE
    assert 'trace("Innovid answered")' in SOURCE


def test_tracing_never_breaks_the_app():
    body = SOURCE[SOURCE.index("def trace(stage: str)"):]
    body = body[:body.index("def sign_findings(")]
    assert "except Exception:" in body
    assert "pass" in body


def test_the_log_does_not_grow_for_ever():
    body = SOURCE[SOURCE.index("def trace(stage: str)"):]
    body = body[:body.index("def sign_findings(")]
    assert "st_size >" in body


def test_the_log_is_not_committed():
    # Puede llevar nombres de campana y de cliente dentro.
    assert "logs/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


# ------------------------------------------------------------------
# Lo que cuesta una pasada
# ------------------------------------------------------------------

APP = Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"
APP_SOURCE = APP.read_text(encoding="utf-8")


def test_only_the_chosen_section_is_drawn():
    """
    st.tabs dibuja el cuerpo de TODAS las pestanas en cada pasada.

    En una solicitud de 72 placements con Innovid conectado eso son
    seis secciones enteras cada vez que se toca cualquier cosa --
    setenta y dos desplegables con sus tablas de fechas y rotacion, la
    lista de tags, la de DV. La pasada no terminaba, y mientras no
    termina Streamlit no atiende el clic siguiente: se pulsaba firmar
    y no pasaba nada, sin que llegara una sola pasada al servidor.
    """
    assert "st.tabs(" not in APP_SOURCE
    assert "st.segmented_control(" in APP_SOURCE
    for label in (
        "Worked Placements", "Findings",
        "Files & Extraction", "Tags", "DV Pinnacle Tags",
    ):
        assert f'if _section == "{label}":' in APP_SOURCE, label


def test_rules_executed_is_not_a_section_of_its_own():
    """
    Es la constancia de que se reviso: util el dia que alguien
    pregunte "¿esto si comprobo X?", ruido el resto de los dias.
    Vive dentro de "Files & Extraction", en un desplegable cerrado.
    Camilo: "ocultar rules executed en la interfaz".

    Oculta, no borrada: se sigue llegando a ella con un clic.
    """
    assert 'if _section == "Rules Executed":' not in APP_SOURCE
    assert '"Rule Execution Coverage"' in APP_SOURCE
    assert "rule_summary_dataframe(" in APP_SOURCE


def test_every_section_says_when_it_starts():
    # Para que el log diga cual es la cara, y no haya que adivinarlo.
    assert APP_SOURCE.count('trace("section ') == 5


def test_signing_lives_in_the_body():
    """
    Camilo: "a mi me gustaba firmar en el panel central".

    Estuvo al pie de la pagina y luego como seccion aparte, las dos
    veces para esquivar un coste que no era suyo -- lo que dejaba la
    pagina pintando para siempre eran los 44 placements desplegados a
    la vez.
    """
    assert 'if _section == "QA2 Review":' not in APP_SOURCE
    assert 'key="qa2_panel_sign_all"' in APP_SOURCE
    # y antes del veredicto, que se calcula con lo firmado
    assert (
        APP_SOURCE.index('key="qa2_panel_sign_all"')
        < APP_SOURCE.index("scorecard = findings_buffer.scorecard()")
    )


def test_the_reports_can_be_downloaded_from_the_top():
    # Camilo: "que el descargable del excel este arriba como antes".
    assert (
        APP_SOURCE.index("download_columns = st.columns(2)")
        < APP_SOURCE.index("SECTIONS = [")
    )


def test_the_reports_are_not_rebuilt_on_every_pass():
    # Cinco segundos por pasada en una solicitud grande, aunque nadie
    # hubiera tocado el boton de descargar.
    assert 'reuse("pdf"' in APP_SOURCE
    assert 'reuse("excel"' in APP_SOURCE


def test_signing_changes_what_the_reports_say():
    # Y por eso la firma entra en la firma del estado: el informe
    # tiene que reflejar lo que se acaba de aprobar.
    body = APP_SOURCE[APP_SOURCE.index("_report_signature = ("):]
    body = body[:body.index("trace(\"building the PDF\")")]
    assert "scorecard.verdict" in body
    assert "review_overrides" in body


def test_only_one_placement_is_opened_at_a_time():
    """
    El servidor termina; el que no puede es el navegador.

    Cada placement desplegado son decenas de elementos -- creativos,
    fechas, rotacion, URLs, tags -- y cuarenta y cuatro de golpe dejan
    la pagina pintando para siempre: el indicador no para y no se
    llega a firmar, con un log que dice SCRIPT RUN finished a los 53
    segundos. Camilo: "lo que no me gustaba era el desplegable de
    todos los placements trabajados".

    La tabla los trae todos; el desplegable abre uno.
    """
    assert 'f"qa2_row_{placement_id}"' in APP_SOURCE
    assert 'st.session_state["qa2_open_placement"]' in APP_SOURCE
    assert "if not _is_open:" in APP_SOURCE
    assert "DETAIL_CHOICES" not in APP_SOURCE


def test_the_list_is_back_and_the_table_is_gone():
    # Camilo: "me gusta mas cuando podia desplegar todos los
    # placements... ese panel de status, placement, placement name,
    # es muy invasivo".
    assert "overview_rows" not in APP_SOURCE
    assert "_overview_slot" not in APP_SOURCE
    assert 'f"{placement_id}  |  "' in APP_SOURCE


def test_the_panel_says_what_it_did_last():
    # Un clic durante una pasada que aun corre se pierde. Sin rastro,
    # "no registro el clic" y "lo registro y no paso nada" se ven
    # igual desde fuera.
    assert 'st.caption(f"Last action: {_last_action}")' in APP_SOURCE


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
        else:
            passed += 1
            print(f"ok   {name}")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

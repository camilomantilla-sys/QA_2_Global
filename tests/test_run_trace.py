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


def test_the_stages_are_traced_in_order():
    at = [SOURCE.index(f'"{stage}"') for stage in STAGES]
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
        "Worked Placements", "Findings", "Rules Executed",
        "Files & Extraction", "Tags", "DV Pinnacle Tags",
    ):
        assert f'if _section == "{label}":' in APP_SOURCE, label


def test_every_section_says_when_it_starts():
    # Para que el log diga cual es la cara, y no haya que adivinarlo.
    assert APP_SOURCE.count('trace("section ') == 7


def test_signing_is_a_section_of_its_own():
    """
    Al final de la pagina el orden era el correcto y el resultado no:
    el boton de firmar era lo ultimo en dibujarse, asi que en una
    solicitud de 44 placements con su detalle no aparecia hasta que
    el navegador terminaba de pintarlo todo. Camilo: "ni termino de
    cargar, ni me salio el boton para firma".

    Como seccion se dibuja sola, y se sigue llegando a ella despues de
    haber mirado el resto.
    """
    assert '"QA2 Review",' in APP_SOURCE
    assert 'if _section == "QA2 Review":' in APP_SOURCE
    # y la ultima, que es el orden de trabajo
    assert APP_SOURCE.index('"DV Pinnacle Tags",') < APP_SOURCE.index('"QA2 Review",')


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


def test_the_placement_detail_is_always_drawn():
    """
    Camilo lo pidio al derecho: "me parece mejor que se muestren todos
    de una apenas corro el QA asi toque esperar un poquito mas".

    La casilla que lo apagaba en solicitudes grandes se fue. Lo que
    sostiene el coste ahora es el orden: firmar esta al final, y para
    llegar alli la pasada ya ha terminado.
    """
    assert "qa2_show_detail" not in APP_SOURCE
    assert "if not show_detail:" not in APP_SOURCE


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

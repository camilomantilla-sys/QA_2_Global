"""
Como se firma el QA2, y por que ya no es un boton.

En la maquina de Camilo, Run QA llega siempre al servidor y los
botones de firmar no llegaban nunca -- ni el del panel ni el de la
barra lateral, ni leyendo el valor de retorno ni por `on_click`. El
rastro de logs/qa_run.log lo zanjo: tras pulsar firmar no arranca
ninguna pasada del script, y tras Run QA si. Aqui, con sus mismos
archivos, ese boton firma los 24 a la primera, asi que no es el
codigo.

Lo que si le responde, ademas de Run QA, son las casillas y los
desplegables. Asi que firmar es una casilla. Destildar limpia, de
modo que tampoco hace falta boton de limpiar.

Run with pytest, or directly:
    python tests/test_review_approve_buttons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

APP = Path(__file__).resolve().parents[1] / "ui" / "app_v2.py"
SOURCE = APP.read_text(encoding="utf-8")

RESULTS_TRY = SOURCE.index("\nif True:\n    try:")


def test_the_results_section_never_asks_for_another_pass():
    """
    Un st.rerun() aqui se come el clic que lo provoco.

    La barra lateral se dibuja antes de que exista un solo hallazgo,
    asi que para poner el numero en el rotulo de su boton pedia una
    pasada mas desde la seccion de resultados. Esa pasada DESCARTA la
    que esta corriendo -- y con ella el boton de firmar, que se evalua
    doscientas lineas mas abajo. Se pulsaba firmar, el script volvia a
    empezar, y en la pasada nueva el boton ya devolvia False: nada
    firmado, sin error y sin rastro.

    Camilo, sobre tres solicitudes distintas: "no me deja aprobarlos
    el boton de firma".
    """
    called = [
        line.strip() for line in SOURCE.splitlines()
        if line.strip().startswith("st.rerun()")
    ]
    assert not called, called


def test_there_is_one_place_to_sign_and_it_is_the_panel():
    # Los controles de la barra lateral dependian de esa pasada de
    # mas. Un solo sitio, donde el numero ya se sabe.
    for gone in (
        "sign_all = st.checkbox(",
        "sign_groups = st.multiselect(",
        "qa2_sign_all_was",
    ):
        assert gone not in SOURCE, gone


def test_the_old_broken_sign_off_buttons_are_gone():
    # Los de entonces, con sus mismas keys, no volvieron.
    for gone in (
        "sign_all_clicked",
        "sign_group_clicked",
        "clear_all_clicked",
        'key="qa2_review_approve_all"',
        'key="qa2_sidebar_sign_all"',
    ):
        assert gone not in SOURCE, gone


def test_the_sidebar_only_says_how_many_are_pending():
    # Un rotulo, no un widget: sin widget no hace falta que la barra
    # lateral este al dia, y sin eso no hace falta la pasada de mas.
    assert "to sign off, " in SOURCE


def test_the_panel_can_sign_without_waiting_for_another_pass():
    """
    Los mismos controles, dentro del panel.

    La casilla de la barra lateral se dibuja ANTES de que exista un
    solo hallazgo, asi que para saber cuantos hay depende de que el
    script se vuelva a correr entero. Con Innovid conectado y casi
    doscientos hallazgos esa segunda pasada tarda, y mientras tanto se
    ven los resultados y no hay con que firmarlos -- que se lee igual
    que un boton roto. Dentro del panel el numero ya se sabe.
    """
    for marker in (
        'key="qa2_panel_sign_all"',
        'key="qa2_panel_clear"',
        'key="qa2_panel_groups"',
    ):
        assert marker in SOURCE, marker


def test_the_panel_controls_come_before_the_table():
    # Si se dibujaran despues, la tabla saldria sin lo que se acaba
    # de firmar y habria que volver a correr para verlo.
    assert (
        SOURCE.index('key="qa2_panel_sign_all"')
        < SOURCE.index("key=_editor_key,")
    )


def test_no_callbacks_anywhere():
    assert "on_click=" not in SOURCE


def test_clearing_is_its_own_button_and_nothing_else_clears():
    """
    Limpiar se pide, no se deduce.

    Antes, destildar la casilla de la barra lateral limpiaba -- y la
    casilla no llevaba key, asi que bastaba con que su rotulo cambiara
    de numero para que Streamlit la diera por nueva y sin tildar. Eso
    borraba las firmas sin que nadie lo hubiera pedido.
    """
    assert 'key="qa2_panel_clear"' in SOURCE
    assert "elif _was_all:" not in SOURCE


def test_the_sidebar_label_comes_from_the_last_run():
    # Arriba todavia no existe ningun hallazgo.
    assert 'st.session_state["qa2_review_pending"] = len(review_findings)' in SOURCE
    assert 'st.session_state.get("qa2_review_pending", 0)' in SOURCE


def test_run_qa_still_remembers_that_it_ran():
    # Un reemplazo por bloque se llevo por delante estas cuatro
    # lineas y el QA dejo de correr entero: st.button solo devuelve
    # True en la pasada del clic, asi que sin esto cualquier otra
    # interaccion vuelve a la pantalla de inicio.
    assert 'if "qa2_has_run" not in st.session_state:' in SOURCE
    assert "st.session_state.qa2_has_run = False" in SOURCE
    assert "if analyze_button:" in SOURCE
    assert "st.session_state.qa2_has_run = True" in SOURCE
    # y en ese orden, antes de que alguien la lea
    assert (SOURCE.index("st.session_state.qa2_has_run = False")
            < SOURCE.index("if not st.session_state.qa2_has_run:"))


def test_signing_leaves_a_trace():
    body = SOURCE[SOURCE.index("def sign_findings("):SOURCE.index("def clear_signatures(")]
    assert "qa2_review_last_action" in body
    assert "qa2_click_beacon" in body
    assert 'entry["approved"] = True' in body


def test_the_script_run_counter_is_drawn_outside_the_results_try():
    assert SOURCE.index('st.session_state["qa2_script_runs"] = _runs') < RESULTS_TRY


def test_nothing_is_signed_off_before_the_run():
    assert "qa2_preapprove" not in SOURCE


# ------------------------------------------------------------------
# Dos hallazgos distintos no pueden compartir firma
# ------------------------------------------------------------------

def test_two_findings_on_the_same_placement_have_different_ids():
    """
    El id de un hallazgo incluye el nombre del creativo.

    Sin eso, dos creativos del mismo placement sin Creative ID en la
    TS y con los mismos valores comparados daban el MISMO id. Firmar
    uno tildaba los dos, pero el contador de aprobados solo subia una
    -- las claves de un diccionario no se repiten -- asi que quedaba
    siempre algo pendiente y el boton parecia no funcionar.
    """
    from core.findings import FindingsBuffer as _Buffer
    from core.findings import Domain as _Domain

    buffer = _Buffer()
    for name in ("banner_a.jpg", "banner_b.jpg"):
        buffer.review(
            rule_id="URL-001",
            domain=_Domain.URL,
            message="The landing page differs",
            placement_id="10738901",
            creative_name=name,
        )

    ids = {finding.finding_id for finding in buffer.findings}
    assert len(ids) == 2, [f.finding_id for f in buffer.findings]


def test_the_same_finding_keeps_the_same_id():
    # Lo que hace util el id: la firma sobrevive a volver a correr el
    # QA sobre los mismos datos.
    from core.findings import FindingsBuffer as _Buffer
    from core.findings import Domain as _Domain

    def build():
        buffer = _Buffer()
        buffer.review(
            rule_id="URL-001",
            domain=_Domain.URL,
            message="The landing page differs",
            placement_id="10738901",
            creative_name="banner_a.jpg",
        )
        return buffer.findings[0].finding_id

    assert build() == build()


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
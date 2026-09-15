"""
La landing page viaja dentro del click tag de un 1x1.

Idea del equipo de Camilo: "en el static clicktag para 1x1 siempre va a
estar la lp que viene en la ts, esa puede ser una forma de validar los
tags".

Es cierto, y mejor de como se contaba: no esta "al final" sin mas, va
en `&url=` y ocupa el resto de la cadena -- con sus propios `?` y `&`
dentro, asi que no se puede leer como un parametro cualquiera.

    .../click/8/328665;11103057;6403794;211;0/?gdpr=${GDPR}
    &us_privacy=${US_PRIVACY}&force_transparent=true
    &url=https://www.martinsfoods.com/?999=SplashPage&997=adrm-...

Y `Update_Clicktag1` usa el mismo parametro para otra cosa --
`&url=45754586`, un identificador -- asi que la regla solo cuenta
cuando detras hay de verdad una URL. Eso deja esa columna fuera sin
nombrarla.

Es la unica comprobacion que mira el DESTINO dentro del archivo
entregado: las demas miran campaign id, placement id y dimensiones.

Run with pytest, or directly:
    python tests/test_tag_landing_page.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.findings import FindingsBuffer  # noqa: E402
from core.matching import ExpectedPlacement  # noqa: E402
from parsers.innovid_tags import TagRow, _parse_tag_value  # noqa: E402
from rules.tags import _clicked_url, _landing_page_in_click_tag  # noqa: E402

LANDING = (
    "https://www.martinsfoods.com/?999=SplashPage"
    "&997=adrm-unilever-hellmans-q3-q4-flight1-2026&996=id&001=10012"
)
CLICK = (
    "https://servedby.flashtalking.com/click/8/328665;11103057;6403794;"
    "211;0/?gdpr=${GDPR}&gdpr_consent=${GDPR_CONSENT_78}"
    "&us_privacy=${US_PRIVACY}&force_transparent=true&url=" + LANDING
)
UPDATE = (
    "https://servedby.flashtalking.com/click/8/328665;11103057;6403794;"
    "211;0/?gdpr=${GDPR}&us_privacy=${US_PRIVACY}&url=45754586"
)


class _Link:
    def __init__(self, tags: dict, ts_url: str = LANDING):
        self.tag_row = TagRow(
            row=12,
            placement_id="11103057",
            tags=[_parse_tag_value(name, raw) for name, raw in tags.items()],
        )
        self.expected = (
            ExpectedPlacement(placement_id="11103057", url=ts_url)
            if ts_url is not None
            else None
        )


def run(link) -> list:
    buffer = FindingsBuffer()
    _landing_page_in_click_tag(link, buffer)
    return [f for f in buffer.findings if f.rule_id == "TAG-014"]


# ------------------------------------------------- leer la cola

def test_the_landing_page_is_the_tail_after_url():
    assert _clicked_url(CLICK) == LANDING


def test_its_own_query_string_survives_whole():
    # Se lee como cola, no como parametro: si se cortara en el primer
    # `&` se perderia medio destino y todo saldria en fallo.
    assert _clicked_url(CLICK).endswith("&001=10012")


def test_an_update_clicktag_carries_an_id_and_is_left_alone():
    assert _clicked_url(UPDATE) == ""


def test_a_tag_without_the_parameter_says_nothing():
    assert _clicked_url("https://servedby.flashtalking.com/imp/8/1;2;3") == ""
    assert _clicked_url("") == ""


# ------------------------------------------------- el veredicto

def test_the_declared_landing_page_passes():
    found = run(_Link({"Static_Clicktag1": CLICK}))
    assert found and found[0].status.value == "PASS", found
    assert "Static_Clicktag1" in found[0].message


def test_another_landing_page_fails():
    other = CLICK.replace("martinsfoods.com", "giantfoodstores.com")
    found = run(_Link({"Static_Clicktag1": other}))
    assert found and found[0].status.value == "FAIL", found
    assert "another landing page" in found[0].message


def test_the_update_clicktag_produces_no_verdict():
    found = run(_Link({"Update_Clicktag1": UPDATE}))
    assert not found, found


def test_both_columns_together_judge_only_the_static_one():
    found = run(_Link({
        "Static_Clicktag1": CLICK,
        "Update_Clicktag1": UPDATE,
    }))
    assert len(found) == 1, [f.message for f in found]
    assert found[0].status.value == "PASS"


def test_no_landing_page_in_the_traffic_sheet_is_not_a_failure():
    found = run(_Link({"Static_Clicktag1": CLICK}, ts_url=""))
    assert found and found[0].status.value == "NOT_VERIFIED", found
    assert "declares none" in found[0].message


def test_a_pixel_row_has_nothing_to_judge():
    impression = (
        '<img src="https://servedby.flashtalking.com/imp/8/328665;'
        '11103057;201;pixel;AholdDelhaizeUSA;P3K87R5" />'
    )
    assert not run(_Link({"pixel": impression}))


def test_an_adobe_click_tag_without_a_destination_says_nothing():
    """
    Camilo: "en adobe muchas veces no se envia el static".

    Cierto, y la regla ya lo aguanta sin excepciones por cuenta: habla
    solo cuando el tag trae destino. En sus archivos reales, Chegg y
    Duolingo mandan `ftrack 1x1 click` sin `&url=` -- 93 filas, ni un
    hallazgo -- y Brainly manda ademas `Static_Clicktag1` con la
    landing page dentro, que si se comprueba y pasa.
    """
    ftrack = (
        "https://servedby.flashtalking.com/click/8/326319;11038749;"
        "50126;211;0/?ft_width=1&ft_height=1&gdpr=${GDPR}"
        "&us_privacy=${US_PRIVACY}&gpp=${GPP_STRING}"
    )
    assert _clicked_url(ftrack) == ""
    assert not run(_Link({"ftrack 1x1 click": ftrack}))


def test_the_rule_is_gated_on_evidence_not_on_the_account():
    # Sin lista de cuentas que mantener: si el tag lleva destino se
    # compara, y si no, no existe el hallazgo.
    source = Path(__file__).resolve().parents[1] / "rules" / "tags.py"
    body = source.read_text(encoding="utf-8")
    body = body[body.index("def _clicked_url"):]
    for account in ("adobe", "unilever", "blackrock", "wendy"):
        assert account not in body.lower(), account


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

"""
El color de la celda del grupo no decide el de un creativo.

Camilo, mirando el detalle de un placement de BlackRock: "me sigue
leyendo creativos en rojo como si fueran verdes".

En su Traffic Sheet, el decision set "AV Display Unit 300x600" lleva
dos filas -- una ROJA con el creativo que sale y una VERDE con el que
entra -- y la celda del nombre del grupo esta fusionada entre las dos,
pintada de verde.

El intent de la fila se calculaba mirando TODOS los colores, incluida
esa celda compartida:

    fams = {GREEN, RED}   ->   intent = "SWAP"

y "SWAP" se resuelve como GREEN mas adelante. Asi que el creativo que
habia que QUITAR se leia como uno que se queda. Tres veces en esa
solicitud, las tres al reves.

La celda del grupo habla del grupo. Esta fusionada: es literalmente la
misma celda para todas las filas del decision set. No puede decir nada
sobre un creativo en concreto.

Camilo, sobre esa celda: "ahi el ds puede estar en verde o blanco".
Las dos formas tienen que dar lo mismo.

Run with pytest, or directly:
    python tests/test_group_colour_does_not_decide.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, GREY, RED, WHITE, YELLOW  # noqa: E402
from parsers.ts_parser import _row_own  # noqa: E402


def intent_of(colors: dict) -> str:
    """
    La decision que toma el parser, con los mismos colores.

    Se replica aqui en vez de montar una hoja entera: lo que se prueba
    es la regla, y una hoja de Excel de mentira solo añadiria ruido
    entre el color y el veredicto.
    """
    own = _row_own(colors)
    if not own:
        heredado = colors.get("group_name")
        own = {heredado} if heredado in (GREEN, RED) else set()

    if GREEN in own and RED in own:
        return "SWAP"
    if GREEN in own:
        return GREEN
    if RED in own:
        return RED
    if own and own <= {YELLOW, GREY}:
        return "SCOPE_EXCLUDED"
    return WHITE


def creative_row(group: str, creative: str) -> dict:
    """Una fila de Creative Rotations: el grupo y las celdas propias."""
    return {
        "group_name": group,
        "creative_name": creative,
        "creative_id": creative,
        "rotation_weight": creative,
        "start_date": creative,
        "end_date": creative,
    }


# ── el caso de Camilo ────────────────────────────────────────────────

def test_a_red_creative_inside_a_green_group_is_red():
    """El que se leia verde. Tres veces en su solicitud."""
    assert intent_of(creative_row(group=GREEN, creative=RED)) == RED


def test_a_red_creative_inside_a_white_group_is_also_red():
    """"el ds puede estar en verde o blanco" -- da igual."""
    assert intent_of(creative_row(group=WHITE, creative=RED)) == RED


def test_the_green_creative_beside_it_stays_green():
    """Es un swap: uno sale y otro entra. Los dos tienen que leerse."""
    assert intent_of(creative_row(group=GREEN, creative=GREEN)) == GREEN


def test_the_group_colour_never_turns_a_row_into_a_swap():
    """
    "SWAP" tiene que salir de que la FILA lleve verde y rojo a la vez,
    no de sumar el color del grupo al del creativo.
    """
    row = creative_row(group=GREEN, creative=RED)
    assert intent_of(row) != "SWAP"

    de_verdad = dict(row, creative_name=GREEN, creative_id=RED)
    assert intent_of(de_verdad) == "SWAP"


# ── lo que no se puede romper al arreglarlo ──────────────────────────

def test_a_new_decision_set_paints_the_group_and_leaves_creatives_white():
    """
    Sin color propio, el grupo si habla: un decision set nuevo va en
    verde con sus creativos en blanco, y esos son parte del pedido.
    """
    assert intent_of(creative_row(group=GREEN, creative=WHITE)) == GREEN


def test_a_group_being_removed_takes_its_white_creatives():
    assert intent_of(creative_row(group=RED, creative=WHITE)) == RED


def test_a_grey_group_does_not_put_white_creatives_out_of_scope():
    """
    En la TS de Dove hay placements con SOLO la celda de grupo en gris
    y el resto en blanco. Tomar ese gris dejaba cuatro fuera de alcance
    sin que nadie lo pidiera -- y el guard de snapshots lo atrapo al
    primer intento de arreglar esto.
    """
    assert intent_of(creative_row(group=GREY, creative=WHITE)) == WHITE


def test_a_grey_creative_is_still_out_of_scope():
    assert intent_of(creative_row(group=WHITE, creative=GREY)) == "SCOPE_EXCLUDED"


def test_a_grey_creative_inside_a_green_group_is_still_out_of_scope():
    """El caso del default viejo de BlackRock."""
    assert intent_of(creative_row(group=GREEN, creative=GREY)) == "SCOPE_EXCLUDED"


def test_an_untouched_row_is_context():
    assert intent_of(creative_row(group=WHITE, creative=WHITE)) == WHITE


# ── y la regla, escrita donde vive ───────────────────────────────────

def test_the_parser_decides_on_the_rows_own_colours():
    source = (
        Path(__file__).resolve().parents[1] / "parsers" / "ts_parser.py"
    ).read_text(encoding="utf-8")
    bloque = source[source.index("own = _row_own(colors)"):]
    bloque = bloque[:bloque.index("intent = WHITE")]
    # Nada de esa decision puede volver a mirar todos los colores.
    assert "fams" not in bloque


def test_the_group_cell_is_excluded_from_a_rows_own_colours():
    assert _row_own({"group_name": RED, "creative_name": WHITE}) == set()
    assert _row_own({"group_name": GREEN, "creative_name": RED}) == {RED}


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))

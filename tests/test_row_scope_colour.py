"""
Que color deja una fila fuera de alcance, y cual no.

Gris y amarillo son "esto no se toca". Pero decidirlo mirando todos
los colores de la fila falla por los dos lados, y hay un caso real de
cada uno:

  BlackRock  cada grupo "... Default Web Ad" trae dos filas, y la del
             default viejo va entera en gris MENOS la celda del nombre
             del grupo, compartida por las dos, que va en blanco.
             Exigiendo que todo fuera gris, ese blanco bastaba para
             que la fila pasara por contexto normal y el creativo gris
             se colara en el decision set.

  Dove       al reves: placements con SOLO la celda de grupo en gris y
             el resto en blanco. Mirando cualquier color pintado, esos
             cuatro se habrian quedado fuera de alcance sin que nadie
             lo pidiera.

Asi que decide lo que se pinto sobre la fila misma: ni el blanco, que
es "sin pintar", ni la celda del grupo, que habla del grupo.

Run with pytest, or directly:
    python tests/test_row_scope_colour.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.ts_parser import _row_own  # noqa: E402


def test_the_blackrock_grey_default_row_is_out_of_scope():
    colors = {
        "group_name": "WHITE",
        "creative_name": "GREY",
        "rotation_weight": "GREY",
        "start_date": "GREY",
        "end_date": "GREY",
        "lp_url": "GREY",
    }
    own = _row_own(colors)
    assert own == {"GREY"}
    assert own and own <= {"YELLOW", "GREY"}


def test_a_grey_group_cell_alone_leaves_the_row_alone():
    # Los cuatro de Dove.
    colors = {
        "placement_id": "WHITE",
        "placement_name": "WHITE",
        "group_name": "GREY",
        "lp_ref": "WHITE",
    }
    assert _row_own(colors) == set()


def test_white_is_not_a_colour():
    assert _row_own({"a": "WHITE", "b": "WHITE"}) == set()


def test_a_painted_row_keeps_its_colours():
    assert _row_own({"group_name": "WHITE", "creative_name": "GREEN"}) == {"GREEN"}


def test_a_green_cell_beats_a_grey_one():
    # Que la fila lleve algo gris no la saca de alcance si tambien
    # pide un cambio.
    own = _row_own({"creative_name": "GREEN", "start_date": "GREY"})
    assert not (own <= {"YELLOW", "GREY"})


def test_yellow_counts_the_same_as_grey():
    own = _row_own({"group_name": "WHITE", "creative_name": "YELLOW"})
    assert own and own <= {"YELLOW", "GREY"}


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

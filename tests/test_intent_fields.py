"""
La celda pintada manda: se valida lo que se pidio.

La Traffic Sheet pinta el CAMPO que cambia, no la fila. En la
solicitud real de Dove, 355 de las 382 filas verdes tenian pintada
solo la celda de Rotation (%): eran cambios de rotacion sobre
creativos que ya existian. QA2 las leia como creativos nuevos y
validaba nombre, fechas y URL de creativos que nadie pidio tocar.

Run with pytest, or directly:
    python tests/test_intent_fields.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.intent import ASPECTS, requested, rotation_only  # noqa: E402


@dataclass
class _Creative:
    intent_fields: frozenset = field(default_factory=frozenset)


def _painted(*fields):
    return _Creative(intent_fields=frozenset(fields))


def test_a_rotation_change_asks_about_the_rotation():
    assert requested(_painted("rotation_weight"), "rotation")


def test_a_rotation_change_does_not_ask_about_the_dates():
    # El caso de Camilo: creativos que arrancan un dia antes para
    # poder testearlos salian como fallo de fechas en una solicitud
    # que solo cambiaba pesos.
    assert not requested(_painted("rotation_weight"), "dates")


def test_a_rotation_change_does_not_ask_about_the_url():
    assert not requested(_painted("rotation_weight"), "url")


def test_a_brand_new_creative_asks_about_everything_it_paints():
    new = _painted(
        "creative_name", "creative_id", "start_date", "end_date",
        "lp_url", "rotation_weight", "universal_ad_id",
    )
    for aspect in ("rotation", "dates", "url", "name", "identity"):
        assert requested(new, aspect), aspect


def test_one_painted_date_is_enough_to_ask_about_dates():
    # Se pinta la que cambia; la otra se deja como estaba.
    assert requested(_painted("start_date"), "dates")
    assert requested(_painted("end_date"), "dates")


def test_a_sheet_with_no_colour_is_asked_about_everything():
    # TS viejas, hojas sin pintar, filas que el parser no clasifico.
    # Validar de mas nunca deja pasar un error; callar por no saber,
    # si. Y esta app tiene que seguir leyendo formatos que cambian.
    blank = _Creative()
    for aspect in ("rotation", "dates", "url", "name", "identity"):
        assert requested(blank, aspect), aspect


def test_an_unmapped_aspect_is_validated():
    # Mismo criterio: preguntar de mas antes que callar por no saber.
    assert requested(_painted("rotation_weight"), "something_new")


def test_rotation_only_is_exactly_that():
    assert rotation_only(_painted("rotation_weight"))
    assert not rotation_only(_painted("rotation_weight", "start_date"))
    assert not rotation_only(_painted("creative_name"))
    assert not rotation_only(_Creative())


def test_an_ad_id_fix_still_asks_about_the_rotation():
    # 9 filas de la solicitud real: rotacion + Universal Ad-ID.
    both = _painted("rotation_weight", "universal_ad_id")
    assert requested(both, "rotation")
    assert requested(both, "identity")
    assert not requested(both, "dates")


def test_every_aspect_maps_to_real_sheet_fields():
    # Una errata aqui apagaria una validacion sin que nada lo dijera.
    from core.ts_schema import TS_ROTATIONS
    known = {spec.name for spec in TS_ROTATIONS.fields}
    for aspect, fields in ASPECTS.items():
        for name in fields:
            assert name in known, f"{aspect} -> {name} no existe en la hoja"


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

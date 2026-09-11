"""
Un peso de rotacion es relativo, y cada fuente lo guarda a su manera.

  Traffic Sheet   0.13333333333333333   (Excel guarda 13,33% asi)
  Innovid         13                    (el porcentaje)
  Innovid         1, 2, 1               (a veces cuotas: 1x, 2x)

Camilo lo vio en la tabla: la TS decia 13.33% y al lado Innovid decia
1300%, porque se multiplicaba por 100 sin mirar la escala. Su regla:
"lo ideal es que siempre sume 100".

Run with pytest, or directly:
    python tests/test_weight_normalization.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.normalize import normalize_weights  # noqa: E402


def _total(labels: list[str]) -> float:
    return round(sum(float(x.rstrip("%")) for x in labels if x), 2)


def test_excels_fractions_become_percentages():
    assert normalize_weights(["0.25", "0.75"]) == ["25%", "75%"]


def test_innovids_whole_percent_is_left_as_recorded():
    # Este es el bug: 13 salia como 1300%.
    assert normalize_weights([13, 13, 74]) == ["13%", "13%", "74%"]


def test_a_percentage_group_that_rounds_to_99_is_not_redistributed():
    # Repartirlo otra vez convertiria un 13 exacto en 13,13%.
    assert normalize_weights([13, 13, 7, 13, 13, 7, 13, 13, 7])[0] == "13%"


def test_innovids_shares_become_percentages():
    assert normalize_weights([1, 2, 1]) == ["25%", "50%", "25%"]


def test_even_across_the_whole_group_is_the_equal_share():
    # "Even" es que roten por igual: cada uno 100/N.
    assert normalize_weights(["EVEN"] * 4) == ["25%"] * 4


def test_even_mixed_with_numbers_is_left_alone():
    # Su parte no se puede deducir sin inventarla.
    assert normalize_weights(["EVEN", "0.5", "0.5"])[0] == "EVEN"


def test_the_dove_rotation_sums_to_100():
    # El grupo real: 6 creativos al 13,33% y 3 al 6,67%.
    labels = normalize_weights(
        ["0.13333333333333333"] * 6 + ["0.06666666666666667"] * 3
    )
    assert labels[0] == "13.33%"
    assert labels[-1] == "6.67%"
    assert abs(_total(labels) - 100) < 0.1


def test_the_two_sides_of_the_dove_rotation_line_up():
    ts = normalize_weights(
        ["0.13333333333333333"] * 6 + ["0.06666666666666667"] * 3
    )
    innovid = normalize_weights([13] * 6 + [7] * 3)
    # Innovid solo admite enteros, asi que no son identicos, pero
    # tienen que quedar a menos de un punto.
    for left, right in zip(ts, innovid):
        assert abs(float(left.rstrip("%")) - float(right.rstrip("%"))) <= 1


def test_a_zero_weight_survives():
    # str(0 or "") es "": un peso de cero desaparecia por ser falsy.
    assert normalize_weights([0, 50, 50])[0] == "0%"


def test_an_all_zero_group_is_left_alone():
    # No hay reparto que repartir, y dividir seria inventarlo.
    assert normalize_weights([0, 0]) == ["0", "0"]


def test_an_empty_group_gives_nothing():
    assert normalize_weights([]) == []


def test_free_text_passes_through():
    assert normalize_weights(["TBD"]) == ["TBD"]


def test_a_lone_creative_takes_everything():
    # Deliberado: sin con quien repartir, se lleva el 100%.
    assert normalize_weights(["0.5"]) == ["100%"]


def test_even_with_one_creative_left_is_one_hundred():
    # Caso real de BlackRock: un grupo de cuatro donde dos se van y
    # uno es el default. El unico asignado se lleva el 100%, no el
    # 25% que salia de repartir entre los cuatro.
    assert normalize_weights(
        ["Even", "Even", "Even"], removed=[True, True, False]
    ) == ["", "", "100%"]


def test_a_creative_being_removed_gets_no_share():
    labels = normalize_weights(["Even"] * 4, removed=[True, False, False, False])
    assert labels[0] == ""
    assert labels[1:] == ["33.33%"] * 3


def test_an_empty_rotation_does_not_take_a_share():
    # El default de BlackRock viene sin rotacion porque se trafica en
    # el decision set oficial de su dimension. Contarlo daba el 50%.
    assert normalize_weights(["", "Even"]) == ["", "100%"]


def test_numbers_are_rescaled_without_the_removed_ones():
    assert normalize_weights(
        [50, 50, 50], removed=[True, False, False]
    ) == ["", "50%", "50%"]


def test_without_removed_nothing_changes():
    # La firma crecio; el comportamiento de siempre, no.
    assert normalize_weights(["EVEN"] * 4) == ["25%"] * 4
    assert normalize_weights([13, 13, 74]) == ["13%", "13%", "74%"]
    assert normalize_weights([1, 2, 1]) == ["25%", "50%", "25%"]


def test_removing_every_creative_leaves_no_shares():
    assert normalize_weights(["Even", "Even"], removed=[True, True]) == ["", ""]


def test_the_default_is_marked_so_it_can_be_left_out():
    # Quien lo deja fuera del reparto es el llamador, y para eso
    # necesita distinguirlo.
    import dataclasses

    from core.matching import ExpectedCreative

    names = {f.name for f in dataclasses.fields(ExpectedCreative)}
    assert "is_default" in names


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

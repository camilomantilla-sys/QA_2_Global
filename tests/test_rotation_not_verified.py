"""
Una rotacion que nadie comparo no puede salir en verde.

El peso de rotacion no viaja en ningun export: cuando el placement
corre por Decision Tree, la columna Rotation del export dice
literalmente "Decision Tree" en TODAS sus filas y el porcentaje se
queda dentro del decision set.

En la solicitud real de Dove eso significaba 382 cambios de rotacion
pedidos y cero comparados, con el reporte cerrando en verde porque
CRE-001 habia encontrado los creativos. Encontrar el creativo es
verdad; que la rotacion quedo como se pidio, no se sabia.

Run with pytest, or directly:
    python tests/test_rotation_not_verified.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.findings import Capability, FindingsBuffer, Status  # noqa: E402
from rules import rotation  # noqa: E402
from core.normalize import normalize_weights  # noqa: E402


@dataclass
class _Expected:
    name: str = "creative_a"
    intent: str = "GREEN"
    rotation_weight: str = ""
    intent_fields: frozenset = frozenset()
    creative_id: str = ""
    # El default ad se engancha por dimension y tiene su propio
    # decision set: no reparte el 100% con los que el placement
    # declara.
    is_default: bool = False


@dataclass
class _Link:
    expected: _Expected = field(default_factory=_Expected)


@dataclass
class _Matched:
    placement_id: str = "PL-1"
    creative_links: list = field(default_factory=list)


@dataclass
class _MatchResult:
    matched: list = field(default_factory=list)


def _creative(weight="0.25", fields=("rotation_weight",), intent="GREEN",
              name="creative_a"):
    return _Link(_Expected(
        name=name, intent=intent, rotation_weight=weight,
        intent_fields=frozenset(fields),
    ))


def _run(links, innovid_connected=False):
    buffer = FindingsBuffer()
    buffer.capabilities.declare(
        Capability.ROTATION_WEIGHT, innovid_connected,
        "the rotation weight lives in the Innovid decision set",
    )
    rotation.evaluate(
        _MatchResult(matched=[_Matched(creative_links=links)]), buffer,
    )
    return [f for f in buffer.findings if f.rule_id == "ROT-001"]


def test_a_requested_rotation_is_reported_as_not_verified():
    findings = _run([_creative()])
    assert len(findings) == 1
    assert findings[0].status == Status.NOT_VERIFIED


def test_it_never_passes():
    # El bug: 382 PASS sobre 382 comparaciones que no ocurrieron.
    assert all(f.status != Status.PASS for f in _run([_creative()]))


def test_the_count_is_the_number_of_rotations_requested():
    findings = _run([_creative(), _creative(name="b"), _creative(name="c")])
    assert len(findings) == 1, "un hallazgo por placement, no por creativo"
    assert findings[0].count == 3


def test_innovid_connected_hands_the_check_to_inv_002():
    # Con la API conectada quien compara de verdad es INV-002.
    # Repetirlo aqui duplicaria el hallazgo.
    assert _run([_creative()], innovid_connected=True) == []


def test_a_creative_with_no_painted_rotation_is_not_reported():
    # Solo se reporta lo que la TS pidio cambiar.
    assert _run([_creative(fields=("creative_name",))]) == []


def test_a_white_creative_is_context_not_a_request():
    assert _run([_creative(intent="WHITE")]) == []


def test_a_brand_new_creative_also_declares_a_weight_nobody_compared():
    # Las filas de creativo nuevo traen la rotacion pintada junto con
    # el resto. Esa rotacion tampoco se comparo.
    links = [_creative(fields=("creative_name", "creative_id",
                               "rotation_weight", "start_date"))]
    assert len(_run(links)) == 1


def test_the_reason_says_where_the_weight_lives():
    # Sin esto el usuario no sabe que le falta conectar Innovid.
    assert "decision set" in _run([_creative()])[0].reason


def test_weights_are_shown_as_percentages():
    # Excel guarda 13,33% como 0.13333333333333333.
    links = [_creative(weight="0.13333333333333333", name=f"c{i}")
             for i in range(6)]
    links += [_creative(weight="0.06666666666666667", name=f"d{i}")
              for i in range(3)]
    assert _run(links)[0].expected == "13.33%, 6.67%"


def test_free_text_mixed_with_numbers_is_left_alone():
    # No se puede deducir que parte le toca sin inventarla.
    assert normalize_weights(["TBD", "0.5", "0.5"])[0] == "TBD"


def test_a_group_already_in_percentages_is_left_as_recorded():
    # Unos porcentajes reales suman 99 o 101 por redondeo; volver a
    # repartirlos convertiria un 13 exacto de Innovid en 13,13%.
    assert normalize_weights(["13%", "13%", "74%"]) == ["13%", "13%", "74%"]


def test_distinct_weights_are_listed_once_each():
    links = [_creative(weight="0.25"), _creative(weight="0.25", name="b"),
             _creative(weight="0.5", name="c")]
    assert _run(links)[0].expected == "25%, 50%"


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

"""
Que filas de Creative Rotations se descartan.

La hoja trae ejemplos de la plantilla mezclados con el trabajo real, y
se descartan por nombre. Un patron demasiado amplio se llevaba por
delante rotaciones reales: la TS quedaba sin creativos, QA2 informaba
que no habia nada que revisar, y los hallazgos de una solicitud de
default web ads caian a la mitad sin que nada lo dijera.

Run with pytest, or directly:
    python tests/test_ts_rotation_filters.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ts_schema import TS_ROTATIONS  # noqa: E402


def _ignored(value: str) -> bool:
    return any(
        re.search(pattern, value)
        for pattern in TS_ROTATIONS.ignore_row_patterns
    )


# Nombres reales, de TS_3360_UNIC_US_MDS.
REAL_ROTATIONS = (
    "160x600 Default Web Ad",
    "300x250 Default Web Ad",
    "728x90 Default Web Ad",
    "970x250 Default Web Ad",
)

# Filas de la plantilla, que si deben descartarse.
TEMPLATE_ROWS = (
    "Default In-stream Ad",
    "Example Display Rotation",
    "Options to denote a swap",
    "[object Object]",
    "09.03.2026 UPDATE",
)

# Estas no las descarta ningun patron: llegan y las excluye el color /
# el scope, que es otro mecanismo. Se listan para que quede claro que
# su ausencia de arriba no es un olvido.
HANDLED_BY_COLOUR = (
    "Example Video Rotation 15s",
    "Placement Tracking Creative",
    "Generic Tracking Creative",
)


def test_real_default_web_ad_rotations_survive():
    for name in REAL_ROTATIONS:
        assert not _ignored(name), f"{name} es una rotacion real"


def test_the_templates_own_rows_are_ignored():
    for name in TEMPLATE_ROWS:
        assert _ignored(name), f"{name} es una fila de plantilla"


def test_rows_left_to_the_colour_system_are_not_pattern_matched():
    for name in HANDLED_BY_COLOUR:
        assert not _ignored(name), (
            f"{name} lo excluye el color, no un patron"
        )


def test_the_default_pattern_is_anchored():
    """
    La diferencia entre las dos listas de arriba.

    "Default In-stream Ad" empieza con Default; "160x600 Default Web
    Ad" solo lo contiene. Sin el ancla, un nombre real que termine en
    "Default ... Ad" desaparece.
    """
    assert _ignored("Default In-stream Ad")
    assert not _ignored("160x600 Default Web Ad")


def test_a_rotation_named_after_its_size_is_never_ignored():
    # Las cuentas nombran las rotaciones por dimension; ningun patron
    # deberia tocar eso.
    for size in ("160x600", "300x250", "728x90", "970x250", "300x600"):
        for suffix in ("Default Web Ad", "Rotation", "Web Ad"):
            name = f"{size} {suffix}"
            assert not _ignored(name), name


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

"""
Que se guarda en el cache de Innovid y que no.

Cada interaccion en la app vuelve a correr el script entero, asi que
sin cache un clic relanza el navegador y relee la campana. La regla
vieja exigia CERO errores; los 400 de placementDecisionSetId salen en
todas las campanas de esta cuenta, asi que no guardaba nunca y cada
clic costaba una descarga completa. Desde fuera se ve como que el
boton no hace nada.

Run with pytest, or directly:
    python tests/test_innovid_cache_policy.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass
class _Result:
    placements: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def _worth_caching(result) -> bool:
    """
    La regla, aislada de Streamlit: se guarda lo que trajo datos.

    Se copia aqui a proposito en vez de importar la app, que arranca
    Streamlit entera al importarse. Si la de la app cambia, este test
    deja de representarla -- por eso la regla es de una linea y esta
    escrita igual en los dos sitios.
    """
    return bool(result.placements)


DSET_400 = (
    "3 of 88 decision set(s) could not be read. "
    "placementDecisionSetId returned HTTP 400"
)


def test_a_partial_answer_is_kept():
    # El caso real de Camilo: 88 decision sets, 3 fallaron. Los datos
    # sirven y volver a preguntar no arregla esos 3.
    assert _worth_caching(_Result(placements=[1, 2, 3], errors=[DSET_400]))


def test_a_clean_answer_is_kept():
    assert _worth_caching(_Result(placements=[1], errors=[]))


def test_an_empty_answer_is_not():
    # Sin placements no hay nada que reutilizar, y suele ser sesion
    # caducada: eso si merece reintento.
    assert not _worth_caching(_Result(placements=[], errors=["HTTP 401"]))


def test_an_empty_answer_with_no_errors_is_not_kept_either():
    # Campaign id equivocado, por ejemplo. Guardarlo condenaria los
    # siguientes quince minutos a la misma respuesta vacia.
    assert not _worth_caching(_Result(placements=[], errors=[]))


def test_errors_alone_never_decide():
    # Lo que decide es si trajo datos, no cuantos errores trae.
    assert _worth_caching(_Result(placements=[1], errors=["a", "b", "c"]))


def test_the_app_still_uses_this_rule():
    # Guardia contra que la app se separe de este test sin que nada
    # lo diga.
    source = (Path(__file__).resolve().parents[1] / "ui" / "app_v2.py").read_text()
    assert "if result.placements:" in source, (
        "la regla del cache cambio en la app y este test ya no la representa"
    )


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

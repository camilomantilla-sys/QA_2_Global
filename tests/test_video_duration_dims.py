"""
"Dims or Duration" a veces trae la duracion, y eso no es una dimension.

El caso: un swap de creativos de video de Unilever sobre dos decision
sets que ya existian. Se quitaba un placeholder y entraban tres
creativos reales. QA2 leyo la Traffic Sheet bien -- los dos placements,
el rojo, los tres verdes -- y luego no valido nada:

    creative_links: 0
    extra_running:  ['6398878', '6398876', '6398881']

Los tres creativos que Innovid SI tenia asignados salian como "extra
creative". Sin link no hay comparacion, asi que no se miraban las
fechas, no se miraba la rotacion, y sobre todo no se podia confirmar
que el placeholder que habia que desasignar se hubiera ido.

La causa es una linea de build_expected:

    if not dims_match(ep.dims, c.dims):
        continue

El filtro por dimension existe por Adobe, donde un grupo trae los
creativos de los cinco tamanos y un placement de 160x600 solo sirve
los suyos. Pero el placement de video mide 1920x1080 y la columna
"Dims or Duration" de sus creativos dice "15s". Eso no es un tamano;
no hay forma de que haga match, y el filtro se llevaba por delante el
grupo entero.

dims_match ya toleraba la otra forma de escribir video -- 0x0 contra
el tamano real -- pero no esta. Ahora solo opina cuando los dos lados
son de verdad un ancho por alto: dejar pasar un creativo de mas es
visible y comparable, descartarlo lo vuelve invisible.

En esa Traffic Sheet, 78 de 225 filas de rotacion declaran duracion.

Run with pytest, or directly:
    python tests/test_video_duration_dims.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.colors import GREEN, RED, WHITE  # noqa: E402
from core.matching import build_expected  # noqa: E402
from core.normalize import dims_match, is_dimensions  # noqa: E402


# ── lo que dims_match puede y no puede decir ─────────────────────────

def test_a_duration_is_not_a_dimension():
    assert not is_dimensions("15s")
    assert not is_dimensions("30s")
    assert not is_dimensions(":15")
    assert is_dimensions("1920x1080")
    assert is_dimensions("160 x 600")
    assert is_dimensions("0x0")


def test_the_filter_says_nothing_about_a_duration():
    """No es que coincidan: es que este filtro no puede opinar."""
    assert dims_match("1920x1080", "15s")
    assert dims_match("15s", "1920x1080")
    assert dims_match("160x600", "30s")


def test_the_filter_still_does_its_job_between_real_dimensions():
    """Lo que existe por Adobe sigue igual: 160x600 no sirve 300x250."""
    assert not dims_match("160x600", "300x250")
    assert not dims_match("1920x1080", "728x90")


def test_zero_by_zero_still_matches_anything():
    assert dims_match("0x0", "1920x1080")
    assert dims_match("300x250", "0x0")


def test_the_same_duration_still_matches_itself():
    assert dims_match("15s", "15s")


# ── el caso real, con la forma de la Traffic Sheet ───────────────────

class _Row:
    def __init__(self, row, intent, **values):
        self.row = row
        self.intent = intent
        self.values = values
        self.intent_fields = ()
        self.impl_type = ""
        self.fmt = ""


class _Sheet:
    def __init__(self, rows, sheet="Placements"):
        self.rows = rows
        self.sheet = sheet


class _Scope:
    def __init__(self, request_type, groups):
        self.request_type = request_type
        self.groups = set(groups)
        self.visual_review = False
        self.source = ""


class _TS:
    def __init__(self, placements, rotations=None, scope=None):
        self.profile = "wpp_standard"
        self.placements = _Sheet(placements)
        self.rotations = _Sheet(rotations or [], sheet="Creative Rotations")
        self.landing_pages = None
        self.scope = scope or {}
        self.groups = {}
        self.lp_worked = set()


PLACEMENT = "10874808"
GROUP = "OLV USH Cognitiv"
PLACEHOLDER = "5772770"
SWAPPED_IN = ("6398881", "6398878", "6398876")


def video_swap_sheet():
    """
    El placement 10874808 de uni_shopper_creative_swap_lp_swap, tal
    cual: 1920x1080, y sus creativos declarados en segundos.
    """
    placements = [
        _Row(97, GREEN,
             placement_id=PLACEMENT,
             placement_name="P3H9KT0_UUT_DD_024_THE TRADE DESK INC_1920 x 1080_",
             dimensions="1920x1080", group_name=GROUP,
             start_date="2026-07-01", end_date="2026-09-30"),
    ]
    rotations = [
        _Row(215, RED, group_name=GROUP,
             creative_name="2026_UL_PLACEHOLDER_CREATIVE_15s_VIDEO_MUST_SWAP",
             creative_id=PLACEHOLDER, dims_or_duration="15s",
             rotation_weight="EVEN"),
    ] + [
        _Row(216 + n, GREEN, group_name=GROUP,
             creative_name=f"72h_protection_Testimonial_{n}.mp4",
             creative_id=cid, dims_or_duration="15s",
             rotation_weight="EVEN")
        for n, cid in enumerate(SWAPPED_IN)
    ]
    scope = {PLACEMENT: _Scope("CREATIVE_SWAP", {GROUP.casefold()})}
    return _TS(placements, rotations, scope)


def test_the_video_creatives_reach_the_placement():
    """Lo que fallaba: el placement se quedaba con cero creativos."""
    ep = build_expected(video_swap_sheet())[PLACEMENT]
    assert len(ep.creatives) == 4, [c.creative_id for c in ep.creatives]


def test_the_three_swapped_in_creatives_are_expected():
    ep = build_expected(video_swap_sheet())[PLACEMENT]
    green = {c.creative_id for c in ep.creatives if c.intent == GREEN}
    assert green == set(SWAPPED_IN)


def test_the_placeholder_is_expected_to_be_gone():
    """
    Sin esta fila no habia forma de confirmar la desasignacion, que es
    justo lo que hay que revisar en un swap.
    """
    ep = build_expected(video_swap_sheet())[PLACEMENT]
    red = [c for c in ep.creatives if c.intent == RED]
    assert [c.creative_id for c in red] == [PLACEHOLDER]


def test_a_display_group_is_still_filtered_by_size():
    """
    La proteccion de Adobe no se perdio: un grupo con cinco tamanos
    sobre un placement de 160x600 sigue aportando solo los suyos.
    """
    placements = [
        _Row(2, WHITE, placement_id="999", placement_name="Banner",
             dimensions="160x600", group_name="Concepts"),
    ]
    rotations = [
        _Row(10 + n, WHITE, group_name="Concepts",
             creative_name=f"concept_{size}.jpg", creative_id=f"c{n}",
             dims_or_duration=size)
        for n, size in enumerate(
            ("160x600", "300x250", "728x90", "300x600", "970x250")
        )
    ]
    scope = {"999": _Scope("NEW_PLACEMENT", {"concepts"})}
    ep = build_expected(_TS(placements, rotations, scope))["999"]
    assert [c.dims for c in ep.creatives] == ["160x600"]


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))

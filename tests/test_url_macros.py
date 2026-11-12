"""
Las macros de Innovid se resuelven en el tag, y eso no es otra URL.

Caso real (FB-27, Unilever): la TS declara la landing page con
utm_term=[%placementID%]_[%creativeID%]&utm_source=[%siteName%] y el
tag de 1x1 que entrega Innovid trae utm_term=11269660_6567795 y
utm_source=CondeNast. TAG-014 marcaba "clicks through to another
landing page" en los 9 placements nuevos, con la misma URL.

Run with pytest, or directly:
    python tests/test_url_macros.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.urls import URL_MATCH, URL_PARAMS_DIFF, compare_urls  # noqa: E402

TS = ("https://shop.example/dp/X1?ref_=a&utm_campaign=DEMO_006"
      "&utm_term=[%placementID%]_[%creativeID%]&utm_source=[%siteName%]"
      "&utm_medium=Social")
TAG = ("https://shop.example/dp/X1?ref_=a&utm_campaign=DEMO_006"
       "&utm_term=900100_500100&utm_source=DemoSite&utm_medium=Social")


def test_resolved_macros_are_the_same_url():
    assert compare_urls(TS, TAG).result == URL_MATCH


def test_a_known_placement_id_must_be_the_right_one():
    assert compare_urls(TS, TAG, {"placementID": "900100"}).result == URL_MATCH
    wrong = compare_urls(TS, TAG, {"placementid": "900999"})
    assert wrong.result == URL_PARAMS_DIFF
    assert "utm_term" in wrong.note


def test_the_literal_parts_still_count():
    other = TAG.replace("utm_term=900100_500100", "utm_term=900100-500100")
    assert compare_urls(TS, other).result == URL_PARAMS_DIFF
    other = TAG.replace("utm_campaign=DEMO_006", "utm_campaign=DEMO_007")
    assert compare_urls(TS, other).result == URL_PARAMS_DIFF


def test_an_empty_value_is_not_a_resolved_macro():
    empty = TAG.replace("utm_source=DemoSite", "utm_source=")
    assert compare_urls(TS, empty).result == URL_PARAMS_DIFF


def test_works_in_either_direction():
    assert compare_urls(TAG, TS).result == URL_MATCH


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

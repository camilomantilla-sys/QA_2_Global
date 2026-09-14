"""
Donde se espera el pixel de DISQO depende de como se trafica.

Camilo: "disqo en third party impression 1 column solo aplica para 3p,
no 1x1; en 1x1 se anade la columna en los tags y pues se adjunta cuando
el vendor lo provee."

Un 1x1 es site-served: lo pone el sitio, asi que el pixel llega como
una columna mas del archivo de tags. Un third-party se sirve desde
Innovid, y alli el pixel va en Third_Party_Impression. Antes los dos se
juzgaban igual, con el mismo mensaje: un display de 300x250 con el
pixel solo en los tags pasaba el QA diciendo "correctly included in the
1x1 tag file".

Run with pytest, or directly:
    python tests/test_disqo_by_placement_type.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adobe_pixel_reconciliation import (  # noqa: E402
    PixelResult,
    reconcile_adobe_pixels,
)
from core.tag_inventory import TagInventory, TagSourceRow  # noqa: E402
from parsers.innovid_tags import TagRow, _parse_tag_value  # noqa: E402

PLACEMENT = "11096219"


class _Scope:
    def __init__(self):
        self.placement_id = PLACEMENT
        self.request_type = "NEW_PLACEMENT"


class _Row:
    def __init__(self, values):
        self.values = values
        self.multi = {}
        self.row = 11


class _Sheet:
    def __init__(self, rows):
        self.rows = rows


class _TS:
    def __init__(self, dimensions: str):
        scope = _Scope()
        self.scope = {PLACEMENT: scope}
        self.worked = [scope]
        self.placements = _Sheet([
            _Row({
                "placement_id": PLACEMENT,
                "placement_name": "HBOMax_FY26Acrobat",
                "site": "Discovery.com",
                "dimensions": dimensions,
                "vendors": "DISQO, fTrack",
            })
        ])


class _Export:
    """Placement View, con o sin DISQO en Third_Party_Impression."""

    def __init__(self, has_disqo: bool):
        row = _Row({"placement_id": PLACEMENT})
        if has_disqo:
            row.multi = {
                "third_party_impression": [
                    "https://track.activemetering.com/pixel?id=1"
                ]
            }
        self.rows = [row]


def inventory(has_disqo: bool) -> TagInventory:
    columns = {"ftrack 1x1 imp": "<imp>", "ftrack 1x1 click": "<click>"}
    if has_disqo:
        columns["DISQO"] = "https://ad-score.com/l?l1=1&l3=2"

    row = TagRow(
        row=12,
        placement_id=PLACEMENT,
        tags=[_parse_tag_value(name, raw) for name, raw in columns.items()],
    )
    tags = TagInventory()
    tags.by_placement = {
        PLACEMENT: [
            TagSourceRow(
                file_name="TAGS_Discovery_1x1.xlsx",
                sheet="Tags",
                campaign_id="327816",
                row=row,
            )
        ]
    }
    return tags


def check(dimensions: str, innovid: bool, tags: bool):
    result = reconcile_adobe_pixels(
        _TS(dimensions), _Export(innovid), inventory(tags)
    )
    assert len(result.checks) == 1, result.checks
    return result.checks[0]


# --------------------------------------------------------------- 1x1

def test_a_1x1_with_disqo_in_the_tag_file_passes():
    found = check("1x1", innovid=False, tags=True)
    assert found.result == PixelResult.PASS.value, found.message
    assert "tag file" in found.message


def test_a_1x1_says_innovid_is_not_needed():
    found = check("1x1", innovid=False, tags=True)
    assert "Third_Party_Impression" in found.recommended_action


def test_a_1x1_with_no_disqo_anywhere_is_a_review():
    found = check("1x1", innovid=False, tags=False)
    assert found.result == PixelResult.REVIEW.value
    assert "pending from the vendor" in found.message


def test_a_1x1_with_disqo_only_in_innovid_is_a_review():
    # La medicion existe, pero no por donde se trafica un 1x1.
    found = check("1x1", innovid=True, tags=False)
    assert found.result == PixelResult.REVIEW.value
    assert "site-served 1x1 carries it in the tag file" in found.message


def test_a_1x1_with_disqo_on_both_sides_is_a_review():
    found = check("1x1", innovid=True, tags=True)
    assert found.result == PixelResult.REVIEW.value
    assert "in both" in found.message


# -------------------------------------------------------- third party

def test_a_display_with_disqo_in_innovid_passes():
    found = check("300x250", innovid=True, tags=False)
    assert found.result == PixelResult.PASS.value, found.message
    assert "Innovid" in found.message


def test_a_display_with_disqo_only_in_the_tags_is_a_review():
    # Este es el que pasaba antes, y encima diciendo "1x1 tag file".
    found = check("300x250", innovid=False, tags=True)
    assert found.result == PixelResult.REVIEW.value, found.message
    assert "third-party placement" in found.message
    assert "1x1" not in found.message


def test_a_display_with_no_disqo_anywhere_is_a_review():
    found = check("300x250", innovid=False, tags=False)
    assert found.result == PixelResult.REVIEW.value


def test_a_video_is_judged_like_a_display():
    found = check("1920x1080", innovid=True, tags=False)
    assert found.result == PixelResult.PASS.value


def test_the_dimensions_travel_with_the_check():
    assert check("1x1", innovid=False, tags=True).dimensions == "1x1"
    assert check("300x250", innovid=True, tags=False).dimensions == "300x250"


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

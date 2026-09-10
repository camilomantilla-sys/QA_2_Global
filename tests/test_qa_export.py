"""
La hoja QA del entregable: una fila por creativo, TS contra Innovid.

El formato viejo era vertical -- un hallazgo por fila, el contexto
repartido en varias pestanas -- y revisar un placement obligaba a ir
juntando piezas. Este pone los dos lados en columnas pareadas.

Run with pytest, or directly:
    python tests/test_qa_export.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.findings import Domain, FindingsBuffer  # noqa: E402
from core.matching import ExpectedCreative, ExpectedPlacement  # noqa: E402
from core.qa_export import (  # noqa: E402
    COLUMNS,
    PAIRS,
    build_qa_rows,
    cells_agree,
)


@dataclass
class _ActualCreative:
    creative_id: str = ""
    filename: str = ""
    name: str = ""
    third_party_id: str = ""
    clicktags: list = field(default_factory=list)


@dataclass
class _ActualPlacement:
    placement_id: str = ""
    name: str = ""
    start: date | None = None
    end: date | None = None
    group_name: str = ""


@dataclass
class _Link:
    expected: ExpectedCreative
    actual: object = None


@dataclass
class _Match:
    placement_id: str
    expected: ExpectedPlacement
    actual: object = None
    creative_links: list = field(default_factory=list)


@dataclass
class _MatchResult:
    matched: list = field(default_factory=list)


def _case(creative_name="banner_300x250", innovid_name=None,
          rotation="0.5", creatives=2):
    links = []
    for index in range(creatives):
        name = creative_name if index == 0 else f"other_{index}"
        links.append(_Link(
            expected=ExpectedCreative(
                name=name, creative_id=f"600{index}", intent="GREEN",
                rotation_weight=rotation, url="https://example.com/a",
                start=date(2026, 4, 22), end=date(2026, 12, 31),
            ),
            actual=_ActualCreative(
                creative_id=f"600{index}",
                filename=(innovid_name if index == 0 and innovid_name
                          else name),
                clicktags=["https://example.com/a"],
            ),
        ))
    return _MatchResult(matched=[_Match(
        placement_id="10738901",
        expected=ExpectedPlacement(
            placement_id="10738901", name="P3G1_TTD_300x250",
            start=date(2026, 4, 22), end=date(2026, 12, 31),
            group_name="ACT DL TTD Display 300x250",
            creatives=[link.expected for link in links],
        ),
        actual=_ActualPlacement(
            placement_id="10738901", name="P3G1_TTD_300x250",
            start=date(2026, 4, 22), end=date(2026, 12, 31),
            group_name="ACT DL TTD Display 300x250",
        ),
        creative_links=links,
    )])


def test_one_row_per_creative():
    assert len(build_qa_rows(_case(creatives=3))) == 3


def test_every_column_is_present_on_every_row():
    # Un esquema estable: una columna que a veces falta rompe los
    # filtros y las tablas dinamicas de quien recibe el archivo.
    for row in build_qa_rows(_case()):
        assert list(row.keys()) == COLUMNS


def test_the_placement_block_repeats_on_each_creative_row():
    rows = build_qa_rows(_case(creatives=3))
    assert {row["TS Placement ID"] for row in rows} == {"10738901"}
    assert {row["Innovid Placement Name"] for row in rows} == {
        "P3G1_TTD_300x250"
    }


def test_a_placement_with_no_creatives_still_gets_a_row():
    # Una solicitud de landing page o de 1x1 no declara creativos.
    # Dejarla fuera borraria del entregable un placement trabajado.
    result = _case()
    result.matched[0].creative_links = []
    result.matched[0].expected.creatives = []
    rows = build_qa_rows(result)
    assert len(rows) == 1
    assert rows[0]["TS Placement ID"] == "10738901"


def test_rotation_is_normalised_across_the_placement():
    # 0.5 y 0.5 son 50% y 50%, no 50% sueltos.
    rows = build_qa_rows(_case(rotation="0.5", creatives=2))
    assert {row["TS Rotation"] for row in rows} == {"50%"}


def test_findings_land_on_their_own_row():
    buffer = FindingsBuffer()
    buffer.fail("URL-001", Domain.URL, "URL mismatch",
                placement_id="10738901", creative_name="banner_300x250")
    rows = build_qa_rows(_case(creatives=2), buffer.findings)
    hit = [r for r in rows if r["TS Creative Name"] == "banner_300x250"][0]
    other = [r for r in rows if r["TS Creative Name"] != "banner_300x250"][0]
    assert hit["Status"] == "FAIL"
    assert "URL-001" in hit["Notes"]
    assert other["Status"] == ""


def test_a_placement_level_finding_reaches_every_row():
    buffer = FindingsBuffer()
    buffer.review("PLC-006", Domain.IDENTITY, "Placement Name mismatch",
                  placement_id="10738901")
    rows = build_qa_rows(_case(creatives=3), buffer.findings)
    assert {row["Status"] for row in rows} == {"REVIEW"}


def test_the_worst_status_on_a_row_wins():
    # Una fila con un FAIL y un PASS no es un PASS.
    buffer = FindingsBuffer()
    buffer.pass_("CRE-001", Domain.CREATIVE, "Creative found",
                 placement_id="10738901", creative_name="banner_300x250")
    buffer.fail("URL-001", Domain.URL, "URL mismatch",
                placement_id="10738901", creative_name="banner_300x250")
    rows = build_qa_rows(_case(), buffer.findings)
    hit = [r for r in rows if r["TS Creative Name"] == "banner_300x250"][0]
    assert hit["Status"] == "FAIL"


# --- el verde de acuerdo -----------------------------------------

def test_two_sides_that_agree_are_green():
    assert cells_agree("10738901", "10738901")


def test_two_sides_that_differ_are_not():
    assert not cells_agree("13.33%", "20%")


def test_empty_against_empty_is_not_an_agreement():
    # Pintarlo de verde afirmaria que algo se verifico cuando no se
    # miro nada. Es la distincion que este proyecto lleva defendiendo.
    assert not cells_agree("", "")
    assert not cells_agree("6079260", "")
    assert not cells_agree("", "not returned")


def test_innovids_upload_stamp_still_counts_as_agreement():
    # El sello que Innovid pega al subir no es una diferencia.
    base = "banner_300x250"
    stamped = base + "__38383730-3934-5731-b931-623638616639__145194828.zip"
    assert cells_agree(base, stamped)


def test_a_renamed_creative_is_not_green():
    # STA-BASE contra STA-R1 es un callout, no un acuerdo.
    assert not cells_agree("creative_STA-BASE_011_NA-v01",
                           "creative_STA-R1_011_NA")


def test_every_pair_names_real_columns():
    # Los pares se nombran a mano; una errata dejaria un par sin
    # pintar y nada lo diria.
    for left, right in PAIRS:
        assert left in COLUMNS, left
        assert right in COLUMNS, right


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

"""
Que se ve de un archivo de tags.

El QA de tags no es leer los cientos que se entregan -- eso no lo hace
nadie. Camilo: "realmente todos se envian, entonces es muy dificil
analizarlos todos, por eso validamos con los screenshots que algunos
sirvan y ya que esten todos los placements que dice la ts en esos tags."

Asi que lo que esto fija es la cobertura, no el contenido: que no falte
una fila, que a una fila no le falte una columna que sus hermanas si
tienen, y que ningun tipo de placement se quede sin lo minimo que lo
hace servir -- un 1x1 sin tag de impresion no cuenta impresiones.

Los dos casos que dieron pie a esto son reales:
  - TAGS_Brainly_1x1: 10 filas, 8 con "ftrack 1x1 imp" y 2 solo con
    clicktags.
  - TAGS_CheggUS_VIDEO: 18 filas, 6 con VAST y 12 con nada mas que un
    Placement ID debajo.

Run with pytest, or directly:
    python tests/test_tag_analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.tag_analysis import (  # noqa: E402
    AUDIO,
    DISPLAY,
    ONE_BY_ONE,
    VIDEO,
    analyse_tags,
    dv_table,
    import_table,
)
from parsers.innovid_tags import TagRow, TagsResult, TagValue  # noqa: E402


def tag(column: str, raw: str = "https://servedby.example/x") -> TagValue:
    from parsers.innovid_tags import _parse_tag_value

    return _parse_tag_value(column, raw)


def row(number: int, placement_id: str, dims: str, columns: dict) -> TagRow:
    width, _, height = dims.partition("x")
    return TagRow(
        row=number,
        width=width,
        height=height,
        placement_id=placement_id,
        placement_name=f"Placement {placement_id}",
        tags=[tag(name, raw) for name, raw in columns.items()],
    )


def tags_file(name: str, columns: list[str], rows: list[TagRow]) -> tuple:
    result = TagsResult(
        path=name,
        sheet="Import",
        tag_columns={column: index for index, column in enumerate(columns, 1)},
        rows=rows,
    )
    return (name, result)


DISPLAY_COLUMNS = ["js_https", "if_https", "async_https", "ins"]
ONE_BY_ONE_COLUMNS = ["ftrack 1x1 imp", "ftrack 1x1 click"]


def full_display(number: int, placement_id: str) -> TagRow:
    return row(
        number, placement_id, "300x250",
        {column: f"<tag {column}>" for column in DISPLAY_COLUMNS},
    )


def test_a_display_file_reads_as_display():
    analysis = analyse_tags([
        tags_file("display.xlsx", DISPLAY_COLUMNS,
                  [full_display(2, "111"), full_display(3, "222")])
    ])
    assert [f.family for f in analysis.families] == [DISPLAY]
    assert analysis.families[0].rows == 2
    assert analysis.families[0].incomplete == 0


def test_a_1x1_without_an_impression_tag_fails():
    # El caso Brainly, tal cual.
    rows = [
        row(number, str(number), "1x1",
            {"ftrack 1x1 imp": "<imp>", "ftrack 1x1 click": "<click>"})
        for number in range(2, 10)
    ]
    rows.append(row(10, "10", "1x1", {"ftrack 1x1 click": "<click>"}))

    analysis = analyse_tags([
        tags_file("1x1.xlsx", ONE_BY_ONE_COLUMNS, rows)
    ])
    bad = [r for r in analysis.rows if r.placement_id == "10"]
    assert bad[0].status == "FAIL", bad[0].note
    assert "impression tag" in bad[0].note
    assert analysis.families[0].family == ONE_BY_ONE


def test_a_1x1_without_a_click_tag_fails():
    analysis = analyse_tags([
        tags_file("1x1.xlsx", ONE_BY_ONE_COLUMNS,
                  [row(2, "1", "1x1", {"ftrack 1x1 imp": "<imp>"})])
    ])
    assert analysis.rows[0].status == "FAIL"
    assert "click tag" in analysis.rows[0].note


def test_a_row_with_a_placement_id_and_no_tags_fails():
    # El caso CheggUS: doce filas listadas debajo de la tabla, con ID y
    # nada mas. Sin tipo reconocible, pero igual de vacias.
    analysis = analyse_tags([
        tags_file("video.xlsx", ["preroll_https"], [
            row(2, "111", "640x480", {"preroll_https": "<vast>"}),
            row(3, "222", "", {}),
        ])
    ])
    empty = [r for r in analysis.rows if r.placement_id == "222"][0]
    assert empty.status == "FAIL"
    assert "not a single tag" in empty.note


def test_a_column_every_sibling_fills_but_one_is_a_review():
    rows = [full_display(number, str(number)) for number in range(2, 8)]
    rows.append(
        row(8, "8", "300x250",
            {column: "<tag>" for column in DISPLAY_COLUMNS if column != "ins"})
    )
    analysis = analyse_tags([
        tags_file("display.xlsx", DISPLAY_COLUMNS, rows)
    ])
    odd = [r for r in analysis.rows if r.placement_id == "8"][0]
    assert odd.status == "REVIEW", odd.note
    assert odd.missing_columns == ["ins"]


def test_a_column_only_some_rows_carry_is_not_a_hole():
    # DV no va en todos los placements, y hay cuentas que mandan un
    # archivo con dos formatos revueltos. Que falte donde la mitad no
    # la lleva no es un hueco.
    rows = [full_display(number, str(number)) for number in range(2, 8)]
    rows[0].tags.append(tag("doubleverify_html", "<dv>"))
    rows[1].tags.append(tag("doubleverify_html", "<dv>"))
    analysis = analyse_tags([
        tags_file("display.xlsx", DISPLAY_COLUMNS + ["doubleverify_html"], rows)
    ])
    assert not analysis.incomplete, [r.note for r in analysis.incomplete]


def test_a_single_row_file_is_not_compared_against_itself():
    analysis = analyse_tags([
        tags_file("display.xlsx", DISPLAY_COLUMNS, [full_display(2, "111")])
    ])
    assert analysis.rows[0].missing_columns == []


def test_video_and_audio_are_told_apart():
    analysis = analyse_tags([
        tags_file("v.xlsx", ["preroll_https"],
                  [row(2, "1", "1920x1080", {"preroll_https": "<vast>"})]),
        tags_file("a.xlsx", ["vastAudio"],
                  [row(2, "2", "0x0", {"vastAudio": "<vast>"})]),
    ])
    assert {f.family for f in analysis.families} == {VIDEO, AUDIO}


def test_the_import_table_carries_every_tag_column_whole():
    analysis = analyse_tags([
        tags_file("display.xlsx", DISPLAY_COLUMNS,
                  [full_display(2, "111"), full_display(3, "222")])
    ])
    table = import_table(analysis)
    assert list(table[0])[:4] == ["Status", "File", "Row", "Placement ID"]
    for column in DISPLAY_COLUMNS:
        assert table[0][column] == "<tag %s>" % column


def test_the_same_column_spelled_two_ways_is_one_column():
    # Una cuenta escribe "DISQO" y otra "disqo". Dos columnas en la
    # tabla serian dos huecos donde no hay ninguno.
    analysis = analyse_tags([
        tags_file("a.xlsx", DISPLAY_COLUMNS + ["DISQO"],
                  [full_display(2, "1")]),
        tags_file("b.xlsx", DISPLAY_COLUMNS + ["disqo"],
                  [full_display(2, "2")]),
    ])
    assert len([c for c in analysis.columns if c.casefold() == "disqo"]) == 1


class _Scope:
    def __init__(self, request_type="NEW_PLACEMENT"):
        self.request_type = request_type


class _Row:
    def __init__(self, values):
        self.values = values


class _Sheet:
    def __init__(self, rows):
        self.rows = rows


class _TS:
    def __init__(self, ids):
        self.scope = {placement_id: _Scope() for placement_id in ids}
        self.placements = _Sheet([
            _Row({"placement_id": placement_id,
                  "placement_name": f"Placement {placement_id}"})
            for placement_id in ids
        ])


def test_a_placement_the_ts_asks_for_and_the_tags_do_not_carry():
    # La mitad de la validacion que se hace a mano.
    analysis = analyse_tags(
        [tags_file("display.xlsx", DISPLAY_COLUMNS, [full_display(2, "111")])],
        ts_result=_TS(["111", "222"]),
    )
    assert analysis.ts_worked == 2
    assert analysis.ts_covered == 1
    assert [m["Placement ID"] for m in analysis.missing_from_tags] == ["222"]


def test_a_tag_row_outside_the_traffic_sheet_is_a_review():
    analysis = analyse_tags(
        [tags_file("display.xlsx", DISPLAY_COLUMNS,
                   [full_display(2, "111"), full_display(3, "999")])],
        ts_result=_TS(["111"]),
    )
    stray = [r for r in analysis.rows if r.placement_id == "999"][0]
    assert stray.status == "REVIEW"
    assert "not in the Traffic Sheet" in stray.note


def test_without_a_traffic_sheet_nothing_is_claimed_about_coverage():
    analysis = analyse_tags(
        [tags_file("display.xlsx", DISPLAY_COLUMNS, [full_display(2, "111")])]
    )
    assert not analysis.coverage_known
    assert analysis.missing_from_tags == []
    assert analysis.rows[0].in_ts is None


class _DVRow:
    def __init__(self, row, placement_id, display="", video=""):
        self.row = row
        self.placement_id = placement_id
        self.placement_name = f"Placement {placement_id}"
        self.display_tag = display
        self.video_tag = video

    @property
    def has_tag(self):
        return bool(self.display_tag.strip() or self.video_tag.strip())


class _DV:
    def __init__(self, rows):
        self.rows = rows


def test_the_dv_table_is_its_own_thing():
    table = dv_table(_DV([
        _DVRow(2, "111", display="<dv html>", video="<dv vast>"),
        _DVRow(3, "222"),
    ]))
    assert table[0]["Status"] == "PASS"
    assert table[0]["Display Site-Served Tag"] == "<dv html>"
    assert table[1]["Status"] == "FAIL"
    assert "no DV tag" in table[1]["QA Note"]


def test_no_dv_file_is_an_empty_table_not_a_crash():
    assert dv_table(None) == []


def test_no_tag_files_at_all_is_an_empty_analysis():
    analysis = analyse_tags([])
    assert analysis.rows == []
    assert analysis.families == []
    assert import_table(analysis) == []


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

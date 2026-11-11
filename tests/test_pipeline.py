"""
Una sola cadena de QA para las dos interfaces.

La app de Streamlit armaba en su propio cuerpo la cadena que va de los
archivos al veredicto. La interfaz nueva necesita la misma, y dos
copias terminan diciendo cosas distintas sobre la misma solicitud. Por
eso vive en core.pipeline y Streamlit la llama.

Run with pytest, or directly:
    python tests/test_pipeline.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import pipeline  # noqa: E402
from core.matching import match  # noqa: E402
from tests import made_up_files as made_up  # noqa: E402


def read_both():
    ts = pipeline.parse_traffic_sheet(made_up.traffic_sheet(), "DEMO_TS.xlsx")
    pc = pipeline.parse_export(made_up.placement_creative(), "DEMO_PC.xlsx")
    return ts, pc


def test_streamlit_runs_the_shared_chain():
    source = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")
    assert "run_checks(" in source
    # Las familias que vivian en el cuerpo de la app ya no se llaman ahi.
    for name in ("reconcile_dv_omni(", "reconcile_pixels(", "reconcile_default_ads("):
        assert name not in source, name


def test_each_file_says_what_it_is():
    ts, pc = read_both()
    files, issues = pipeline.understand_files("DEMO_TS.xlsx", ts, "DEMO_PC.xlsx", pc)
    assert [f["Expected Type"] for f in files] == ["Traffic Sheet", "Placement-Creative View"]
    assert files[1]["Records"] == 10
    assert not [i for i in issues if i["Severity"] == "FATAL"]


def test_a_traffic_sheet_dropped_as_an_export_blocks_the_run():
    ts, _ = read_both()
    wrong = pipeline.parse_export(made_up.traffic_sheet(), "DEMO_TS.xlsx")
    files, issues = pipeline.understand_files("ts", ts, "pc", wrong)
    assert files[1]["Status"] == "FATAL"
    assert [i for i in issues if i["Severity"] == "FATAL"]


def test_the_chain_reaches_a_verdict():
    ts, pc = read_both()
    checks = pipeline.run_checks(match(ts, pc, None), ts, pc, account="Unilever")
    got = Counter((f.rule_id, f.status.value) for f in checks.findings.findings)
    # Los 5 verdes existen; los 2 rojos (desasignacion completa) no
    # estan en el export y PLC-001 lo dice.
    assert got[("PLC-001", "PASS")] == 5
    assert got[("PLC-001", "FAIL")] == 2
    assert got[("CRE-001", "PASS")] == 5
    assert checks.dv_reconciliation is not None
    assert checks.default_ad_reconciliation is not None


def test_an_xls_that_is_really_an_xlsx_is_read():
    _, pc = read_both()
    renamed = pipeline.parse_export(made_up.placement_creative(), "Innovid Export.XLS")
    assert renamed.level == pc.level == "placement_creative"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

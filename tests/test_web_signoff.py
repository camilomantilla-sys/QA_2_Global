"""
Paso 5 de la interfaz nueva: firmar los Review, el Implementation
Record, las capturas y las descargas (PDF, Excel, session bundle).

Usa la misma cadena que Streamlit (core.reports, core.session_bundle):
estas pruebas miran que la pagina llegue a ella y que lo firmado cambie
el veredicto y los informes.

Run with pytest, or directly:
    python tests/test_web_signoff.py
"""
from __future__ import annotations

import http.client
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from tests.test_web_steps import call, loaded, port, post, send  # noqa: E402,F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def raw_get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    conn.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    res = conn.getresponse()
    data = res.read()
    headers = dict(res.getheaders())
    conn.close()
    return res.status, headers, data


@pytest.fixture()
def ran(port):
    loaded(port)
    status, d = post(port, "/api/run", {"account": ""})
    assert status == 200, d
    return port, d


def test_reviews_can_be_signed_and_undone(ran):
    port, d = ran
    reviewable = [f for f in d["findings"] if f["reviewable"]]
    assert reviewable, "the made-up request leaves something to review"
    assert d["review"] == {"total": len(reviewable), "signed": 0}

    one = reviewable[0]["id"]
    status, d = post(port, "/api/review", {"ids": [one], "approved": True, "note": "checked"})
    assert status == 200
    row = next(f for f in d["findings"] if f["id"] == one)
    assert row["signed"] and row["status"] == "PASS" and row["note"] == "checked"
    assert d["review"]["signed"] == 1

    status, d = post(port, "/api/review", {"ids": [one], "approved": False})
    row = next(f for f in d["findings"] if f["id"] == one)
    assert not row["signed"] and row["status"] != "PASS"


def test_signing_everything_moves_the_verdict(ran):
    port, d = ran
    before = d["verdict"]
    ids = [f["id"] for f in d["findings"] if f["reviewable"]]
    _, d = post(port, "/api/review", {"ids": ids, "approved": True, "note": "ok"})
    assert d["review"]["signed"] == len(ids)
    assert d["counts"]["FAIL"] == d["counts"]["REVIEW"] == d["counts"]["NOT_VERIFIED"] == 0
    assert before != "PASSED" and d["verdict"] == "PASSED"


def test_a_pass_cannot_be_signed(ran):
    port, d = ran
    passed = next(f["id"] for f in d["findings"] if f["status"] == "PASS")
    _, d = post(port, "/api/review", {"ids": [passed], "approved": True})
    assert d["review"]["signed"] == 0


def test_the_record_keeps_known_fields_and_real_dates(ran):
    port, _ = ran
    _, d = post(port, "/api/record", {"qa2_by": "Demo QA", "qa3_date": "not a date",
                                      "evil": "x"})
    rec = d["record"]
    assert rec["qa2_by"] == "Demo QA" and rec["qa3_date"] == "" and "evil" not in rec
    assert rec["qa2_date"], "running the QA dates the QA2"


def test_screenshots_are_images_only(ran):
    port, _ = ran
    status, d = send(port, "/api/evidence", b"not an image", "notes.txt")
    assert status == 400
    status, d = send(port, "/api/evidence", PNG, "shot.png")
    assert status == 200 and d["evidence"] == ["shot.png"]
    status, d = send(port, "/api/evidence", PNG, "shot.png")
    assert d["evidence"] == ["shot.png", "shot_2.png"]
    status, headers, body = raw_get(port, "/api/evidence/image?name=shot.png")
    assert status == 200 and body == PNG
    _, d = post(port, "/api/evidence/remove", {"name": "shot.png"})
    assert d["evidence"] == ["shot_2.png"]


def test_the_reports_download(ran):
    port, d = ran
    ids = [f["id"] for f in d["findings"] if f["reviewable"]][:1]
    post(port, "/api/review", {"ids": ids, "approved": True, "note": "seen in Innovid"})
    post(port, "/api/record", {"qa2_by": "Demo QA"})

    status, headers, pdf = raw_get(port, "/api/download/pdf")
    assert status == 200 and pdf.startswith(b"%PDF")
    assert "attachment" in headers["Content-Disposition"]

    status, headers, xlsx = raw_get(port, "/api/download/xlsx")
    assert status == 200 and xlsx[:2] == b"PK"
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(xlsx))
    reasons = [str(c.value) for row in wb["Findings"].iter_rows() for c in row if c.value]
    assert any("Approved by Demo QA: seen in Innovid" in r for r in reasons)


def test_the_session_bundle_carries_files_record_and_screenshots(ran):
    port, _ = ran
    post(port, "/api/record", {"wrike_id": "123456"})
    send(port, "/api/evidence", PNG, "shot.png")
    status, headers, data = raw_get(port, "/api/download/bundle")
    assert status == 200
    archive = zipfile.ZipFile(io.BytesIO(data))
    names = archive.namelist()
    assert "files/ts/DEMO_TS.xlsx" in names and "files/pc/DEMO_PC.xlsx" in names
    assert "files/evidence/1_shot.png" in names
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["wrike_id"] == "123456" and manifest["qa1_result"]["verdict"]

    # Y se vuelve a abrir en el paso 1.
    status, d = send(port, "/api/bundle", data, "qa2_session_bundle.zip")
    assert status == 200 and d["bundle"]["evidence"] == 1


def test_downloads_wait_for_a_run(port):
    status, _, _ = raw_get(port, "/api/download/pdf")
    assert status == 409


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

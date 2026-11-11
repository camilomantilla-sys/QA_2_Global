"""
Pasos 2 a 5 de la interfaz nueva: exports, Innovid, correr y resultados.

Todo con archivos inventados (tests/made_up_files.py). Innovid no se
toca: la prueba del paso 3 solo mira que la pagina sepa si hay sesion.

Run with pytest, or directly:
    python tests/test_web_steps.py
"""
from __future__ import annotations

import http.client
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from tests import made_up_files as made_up  # noqa: E402
from ui.web import server as web  # noqa: E402
from ui.web.session import SESSION  # noqa: E402


@pytest.fixture()
def port():
    SESSION.reset()
    srv = web.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_port
    srv.shutdown()
    srv.server_close()
    SESSION.reset()


def call(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    sent = {"Host": f"127.0.0.1:{port}", "X-QA2": "1"}
    sent.update(headers or {})
    conn.request(method, path, body=body, headers=sent)
    res = conn.getresponse()
    data = res.read()
    conn.close()
    return res.status, json.loads(data or b"{}")


def send(port, path, data, name):
    return call(port, "POST", path, data, {"X-File-Name": name,
                                           "Content-Type": "application/octet-stream"})


def post(port, path, body=None):
    return call(port, "POST", path, json.dumps(body or {}),
                {"Content-Type": "application/json"})


def loaded(port):
    send(port, "/api/traffic-sheet", made_up.traffic_sheet(), "DEMO_TS.xlsx")
    return send(port, "/api/file?slot=pc", made_up.placement_creative(), "DEMO_PC.xlsx")


def test_exports_wait_for_the_traffic_sheet(port):
    status, body = send(port, "/api/file?slot=pc", made_up.placement_creative(), "pc.xlsx")
    assert status == 409
    assert "step 1" in body["error"]


def test_the_export_says_what_it_is_and_what_it_found(port):
    status, d = loaded(port)
    assert status == 200
    [pc] = d["slots"]["pc"]
    assert pc["Detected Type"] == "Placement-Creative View" and pc["Records"] == 10
    assert d["coverage"] == {"worked": 7, "found": 5, "missing": ["900105", "900106"],
                             "missing_total": 2}
    assert d["ready"] is True


def test_a_wrong_file_blocks_and_can_be_removed(port):
    loaded(port)
    _, d = send(port, "/api/file?slot=pl", made_up.traffic_sheet(), "wrong.xlsx")
    assert d["ready"] is False and d["blocked_by"]
    _, d = post(port, "/api/remove", {"slot": "pl", "name": "wrong.xlsx"})
    assert d["ready"] is True and d["slots"]["pl"] == []


def test_run_gives_the_verdict_and_the_why(port):
    loaded(port)
    status, d = post(port, "/api/run", {"account": "Unilever"})
    assert status == 200
    assert d["verdict"] == "FAILED"
    assert d["verdict_label"] == "REQUIRES CORRECTION"
    assert d["counts"]["FAIL"] == 2
    first = d["findings"][0]
    assert first["status"] == "FAIL" and first["rule"] == "PLC-001"
    assert first["rule_title"] == "The placement in the Traffic Sheet exists in Innovid"
    assert first["placement_name"] == "DEMO_Placement_5"
    assert d["innovid"] == {"used": False}
    _, again = call(port, "GET", "/api/results")
    assert again["verdict"] == "FAILED"


def test_run_needs_the_files(port):
    status, body = post(port, "/api/run", {})
    assert status == 409


def test_start_over_forgets_everything(port):
    loaded(port)
    post(port, "/api/run", {})
    _, d = post(port, "/api/reset")
    assert d["has_ts"] is False and d["slots"]["pc"] == []
    _, results = call(port, "GET", "/api/results")
    assert results == {}


def test_the_innovid_step_knows_the_sign_in_state(port):
    status, d = call(port, "GET", "/api/innovid")
    assert status == 200
    assert set(d) >= {"saved", "expired", "hours_left"}


def test_a_new_file_clears_the_old_results(port):
    loaded(port)
    post(port, "/api/run", {})
    send(port, "/api/file?slot=pc", made_up.placement_creative(), "DEMO_PC.xlsx")
    _, results = call(port, "GET", "/api/results")
    assert results == {}


def test_actions_from_another_page_are_refused(port):
    status, _ = call(port, "POST", "/api/reset", b"{}", {"X-QA2": ""})
    assert status == 403
    status, _ = call(port, "POST", "/api/run", b"{}", {"Origin": "https://attacker.example"})
    assert status == 403


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

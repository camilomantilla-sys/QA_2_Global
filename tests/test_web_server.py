"""
La interfaz nueva (ui/web) cumple las mismas promesas que la de Streamlit.

Solo escucha en este PC, no le responde a una pagina de otro sitio, no
sirve nada fuera de su lista, y lee la Traffic Sheet con el parser de
siempre. Todo con una TS inventada: ninguna celda de cliente.

Run with pytest, or directly:
    python tests/test_web_server.py
"""
from __future__ import annotations

import datetime
import http.client
import json
import re
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import PatternFill  # noqa: E402

from ui.web import server as web  # noqa: E402

HEADERS = [
    "Site Name", "Placement ID", "Placement Name", "Start Date", "End Date",
    "Dimensions", "Creative Names", "Landing Page", "Vendors / Pixels",
    "Creative Rotation %", "CGEN", "Notes",
]
FILLS = {
    "green": PatternFill("solid", fgColor="FF00FF00"),
    "red": PatternFill("solid", fgColor="FFFF0000"),
    "yellow": PatternFill("solid", fgColor="FFFFFF00"),
}


def made_up_traffic_sheet() -> bytes:
    """5 verdes, 2 rojas, 1 amarilla y 2 blancas. Todo inventado."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    for col, name in enumerate(HEADERS, start=1):
        ws.cell(1, col, name)
    for i in range(10):
        values = [
            f"Site{'ABC'[i % 3]}", 900100 + i, f"DEMO_Placement_{i}",
            datetime.date(2027, 1, 6), datetime.date(2027, 3, 30), "1x1",
            f"DEMO_Creative_{i}", "https://landing.example", "", 100, "ABCD", "",
        ]
        colour = "green" if i < 5 else "red" if i < 7 else "yellow" if i < 8 else None
        for col, value in enumerate(values, start=1):
            cell = ws.cell(i + 2, col, value)
            if colour:
                cell.fill = FILLS[colour]
    wb.create_sheet("Campaign Information")
    target = Path(tempfile.mkdtemp()) / "ts.xlsx"
    wb.save(target)
    return target.read_bytes()


@pytest.fixture(scope="module")
def running():
    srv = web.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_port
    srv.shutdown()
    srv.server_close()


def call(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    sent = {"Host": f"127.0.0.1:{port}"}
    sent.update(headers or {})
    conn.request(method, path, body=body, headers=sent)
    res = conn.getresponse()
    data = res.read()
    conn.close()
    return res.status, data


def upload(port, data, name="DEMO_TrafficSheet.xlsx", **extra):
    headers = {"X-QA2": "1", "X-File-Name": name,
               "Content-Type": "application/octet-stream"}
    headers.update(extra)
    return call(port, "POST", "/api/traffic-sheet", data, headers)


def test_the_new_interface_listens_on_this_computer_only():
    assert web.HOST == "127.0.0.1"
    srv = web.make_server(0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def test_a_request_for_another_host_is_refused(running):
    status, _ = call(running, "GET", "/", headers={"Host": "attacker.example:8502"})
    assert status == 403


def test_another_site_cannot_send_a_file(running):
    data = made_up_traffic_sheet()
    status, _ = call(running, "POST", "/api/traffic-sheet", data,
                     {"X-File-Name": "ts.xlsx"})
    assert status == 403, "without the X-QA2 header"
    status, _ = upload(running, data, Origin="https://attacker.example")
    assert status == 403, "from a foreign page"


def test_only_the_listed_assets_are_served(running):
    for path in ("/assets/../../config/innovid_session.json",
                 "/assets/fonts/README.md",
                 "/config/innovid_credentials.env",
                 "/static/../server.py"):
        status, _ = call(running, "GET", path)
        assert status == 404, path
    status, _ = call(running, "GET", "/assets/logo.png")
    assert status == 200


def test_the_page_loads_nothing_from_outside():
    page = (ROOT / "ui" / "web" / "static" / "index.html").read_text(encoding="utf-8")
    hosts = set(re.findall(r"https?://([A-Za-z0-9._-]+)", page))
    assert hosts <= {"localhost"}, hosts


def test_the_answers_tell_the_browser_to_stay_local(running):
    conn = http.client.HTTPConnection("127.0.0.1", running, timeout=10)
    conn.request("GET", "/", headers={"Host": f"127.0.0.1:{running}"})
    res = conn.getresponse()
    res.read()
    csp = res.getheader("Content-Security-Policy")
    conn.close()
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp


def test_the_traffic_sheet_is_read_like_in_the_current_app(running):
    status, body = upload(running, made_up_traffic_sheet())
    assert status == 200
    d = json.loads(body)
    assert d["counts"]["placements"] == 10
    assert d["counts"]["sites"] == 3
    assert d["intent"]["new"] == 5
    assert d["intent"]["remove"] == 2
    assert d["intent"]["out"] == 1
    assert d["flight"]["weeks"] == 12
    columns = {c["field"]: c for c in d["placements"]["columns"]}
    assert columns["placement_id"]["column"] == "B"
    assert columns["placement_id"]["header"] == "Placement ID"
    assert {"column": "L", "header": "Notes"} in d["placements"]["ignored"]
    assert d["fatal"] is False


def test_the_workbook_does_not_stay_on_disk(running):
    upload(running, made_up_traffic_sheet())
    left = list(Path(tempfile.gettempdir()).glob("qa2_web_ts_*"))
    assert not left, left


def test_a_file_that_is_not_a_workbook_gets_a_clear_message(running):
    status, body = upload(running, b"not a spreadsheet", name="notes.txt")
    assert status == 400
    assert "xlsx" in json.loads(body)["error"]
    status, body = upload(running, b"not a spreadsheet", name="broken.xlsx")
    assert status == 422
    assert "could not read" in json.loads(body)["error"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

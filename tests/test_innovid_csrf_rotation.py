"""
Un token que rota: el capturado al inicio queda viejo enseguida.

Tambien comprueba que la corrida vaya a la direccion que abre la
propia interfaz, /{id}/summary/, y no a /campaign/{id}.
"""
import json, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
sys.path.insert(0, "/home/user/QA_2_Global")
from playwright.sync_api._generated import BrowserType  # noqa: E402
_real = BrowserType.launch
BrowserType.launch = lambda self, **kw: _real(self, **{
    **kw, "args": ["--no-sandbox"],
    "executable_path": "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"})
import core.innovid_api as api  # noqa: E402
from core.innovid_api import fetch_campaign  # noqa: E402

state = {"token": "tok-1", "issued": 0, "paths": []}

def app_page():
    return ("<!doctype html><body><h1>Campaign</h1><script>"
            f"sessionStorage.setItem('csrf', '{state['token']}');"
            "</script></body>")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _s(self, body, code=200, ctype="text/html"):
        b = body.encode(); self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        state["paths"].append(self.path)
        if "/dset/" in self.path:
            self._s(json.dumps({"id": 1, "name": "d",
                                "servingMethod": "Rotation", "nodes": []}),
                    200, "application/json")
        elif self.path.startswith("/favicon"):
            self._s("", 404)
        else:
            # Cada carga de la campana entrega un token nuevo, como
            # Innovid. El favicon no cuenta: rotarlo ahi era un
            # artefacto de esta prueba, no del comportamiento real.
            state["issued"] += 1
            state["token"] = f"tok-{state['issued']}"
            self._s(app_page())
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        if self.headers.get("X-Csrf-Token") == state["token"]:
            self._s(json.dumps({"page": 1, "totalPages": 1, "items": [
                {"placementId": 11102553, "level": "PLACEMENT",
                 "startDate": "2026-09-10", "endDate": "2026-12-31"}]}),
                200, "application/json")
        else:
            self._s("Invalid CSRF Token", 403, "text/plain")

srv = HTTPServer(("127.0.0.1", 0), H)
base = f"http://127.0.0.1:{srv.server_port}"
threading.Thread(target=srv.serve_forever, daemon=True).start()
api.APP_ORIGIN = base; api.CM_BASE = f"{base}/cm/v1/ui"
api.DT_BASE = f"{base}/dt/v1/ui"; api._API_HOST = "127.0.0.1"

sess = Path(tempfile.mkdtemp()) / "s.json"
sess.write_text(json.dumps({"cookies": [], "origins": []}))

fails = []
def check(label, got, want=True):
    if got != want: fails.append(label); print(f"  FAIL {label}: {got!r}")
    else: print(f"  ok   {label}")

res = fetch_campaign("328634", credentials=None, headless=True,
                     timeout_ms=25_000, session_path=sess)

print("it opens the address the interface itself uses")
check("went to /328634/summary/",
      any(p.startswith("/328634/summary") for p in state["paths"]))
check("not /campaign/328634",
      any(p.startswith("/campaign/") for p in state["paths"]), False)

print("\na rotating token doesn't stop the run")
check("no errors", res.errors, [])
check("the campaign was read", len(res.placements), 1)

srv.shutdown()
print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("Rotation and campaign URL verified.")

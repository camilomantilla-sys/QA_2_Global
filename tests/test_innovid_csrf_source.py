"""
La situacion real de Camilo: la sesion trae DOS tokens csrf.

  _csrf  en uam-login.mediaocean.com  -> el de Auth0, valido para
                                         iniciar sesion, no para la API
  csrf   en sessionStorage            -> el que Innovid quiere

Mandar el primero produce exactamente "Invalid CSRF Token".
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
from core.innovid_api import _csrf_from_cookies, fetch_campaign  # noqa: E402

INNOVID_TOKEN = "innovid-real-token"
AUTH0_TOKEN = "auth0-wrong-token"

# La pagina repone el token en sessionStorage al cargar, y no llama a
# la API por su cuenta -- asi no hay cabecera que copiar.
APP = """<!doctype html><body><h1>Campaign Manager</h1><script>
sessionStorage.setItem('csrf', '%s');
</script></body>""" % INNOVID_TOKEN

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _s(self, body, code=200, ctype="text/html", cookie=None):
        b = body.encode(); self.send_response(code)
        self.send_header("Content-Type", ctype)
        if cookie: self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        if "/dset/" in self.path:
            self._s(json.dumps({"id": 1, "name": "d",
                                "servingMethod": "Rotation", "nodes": []}),
                    200, "application/json")
        else:
            self._s(APP)
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        token = self.headers.get("X-Csrf-Token")
        if token == INNOVID_TOKEN:
            self._s(json.dumps({"page": 1, "totalPages": 1, "items": [
                {"placementId": 11102546, "level": "PLACEMENT",
                 "startDate": "2026-09-10", "endDate": "2026-12-31"}]}),
                200, "application/json")
        else:
            self._s("Invalid CSRF Token", 403, "text/plain")

srv = HTTPServer(("127.0.0.1", 0), H)
base = f"http://127.0.0.1:{srv.server_port}"
threading.Thread(target=srv.serve_forever, daemon=True).start()
api.APP_ORIGIN = base; api.CM_BASE = f"{base}/cm/v1/ui"
api.DT_BASE = f"{base}/dt/v1/ui"; api._API_HOST = "127.0.0.1"

# Una sesion guardada con la cookie del proveedor de identidad dentro.
sess = Path(tempfile.mkdtemp()) / "s.json"
sess.write_text(json.dumps({"cookies": [
    {"name": "_csrf", "value": AUTH0_TOKEN,
     "domain": "uam-login.mediaocean.com", "path": "/",
     "expires": -1, "httpOnly": False, "secure": False,
     "sameSite": "Lax"},
], "origins": []}))

fails = []
def check(label, got, want=True):
    if got != want: fails.append(label); print(f"  FAIL {label}: {got!r}")
    else: print(f"  ok   {label}")

print("the token comes from sessionStorage, where Innovid keeps it")
res = fetch_campaign("328634", credentials=None, headless=True,
                     timeout_ms=25_000, session_path=sess)
check("no errors", res.errors, [])
check("the campaign was read", len(res.placements), 1)

print("\nthe identity provider's token is never used")
from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(storage_state=str(sess))
    check("_csrf from mediaocean is ignored", _csrf_from_cookies(ctx), "")
    b.close()

srv.shutdown()
print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("CSRF source verified.")

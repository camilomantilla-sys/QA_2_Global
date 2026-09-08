"""
El 403 que le salio a Camilo: sesion valida, token ausente.
"""
import json, sys, threading
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

COOKIE_TOKEN = "tok-from-cookie-123"
mode = {"csrf_in_cookie": True}

# La app NO llama a su API al cargar, asi que la cabecera nunca aparece.
APP = "<!doctype html><body><h1>Campaign Manager</h1></body>"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, body, code=200, ctype="text/html", cookie=None):
        b = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        if cookie: self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        if "/ui/" in self.path:
            self._send("{}", 200, "application/json")
        else:
            c = f"XSRF-TOKEN={COOKIE_TOKEN}; Path=/" if mode["csrf_in_cookie"] else None
            self._send(APP, cookie=c)
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        if self.headers.get("X-Csrf-Token") == COOKIE_TOKEN:
            self._send(json.dumps({"page":1,"totalPages":1,"items":[
                {"placementId": 11102546, "level": "PLACEMENT",
                 "startDate": "2026-09-10", "endDate": "2026-12-31"}]}),
                200, "application/json")
        else:
            self._send('{"error":"forbidden"}', 403, "application/json")

srv = HTTPServer(("127.0.0.1", 0), H)
base = f"http://127.0.0.1:{srv.server_port}"
threading.Thread(target=srv.serve_forever, daemon=True).start()
api.APP_ORIGIN = base; api.CM_BASE = f"{base}/cm/v1/ui"
api.DT_BASE = f"{base}/dt/v1/ui"; api._API_HOST = "127.0.0.1"

sess = Path("csrf.json"); sess.write_text(json.dumps({"cookies": [], "origins": []}))
fails = []
def check(label, got, want):
    if got != want: fails.append(label); print(f"  FAIL {label}: {got!r} != {want!r}")
    else: print(f"  ok   {label}")

print("the token is taken from the cookie when no request carries it")
res = fetch_campaign("328634", credentials=None, headless=True,
                     timeout_ms=25_000, session_path=sess)
check("no errors", res.errors, [])
check("the campaign was read", len(res.placements), 1)

print("\nwithout any token, the run says so before it fails")
mode["csrf_in_cookie"] = False
res2 = fetch_campaign("328634", credentials=None, headless=True,
                      timeout_ms=25_000, session_path=sess)
joined = " ".join(res2.errors)
check("warns about the missing token", "never handed over" in joined, True)
check("403 blames the token, not the sign-in",
      "refused the request (HTTP 403)" in joined, True)
check("does not tell them the session is invalid",
      "no longer valid" in joined, False)

srv.shutdown()
print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("CSRF handling verified.")

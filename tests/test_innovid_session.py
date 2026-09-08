"""
El 401 que le salio a Camilo con una sesion guardada.

Dos cosas: que el mensaje diga que hacer, y que --login no guarde una
sesion que no sirve.
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
from core.innovid_api import InnovidAuthError, fetch_campaign  # noqa: E402

APP = """<!doctype html><body><h1>Campaign Manager</h1><script>
fetch('/cm/v1/ui/ping', {headers:{'X-Csrf-Token':'t'}, credentials:'include'});
</script></body>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, body, code=200, ctype="text/html"):
        b = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        if "/ui/" in self.path: self._send('{"error":"no"}', 401, "application/json")
        else: self._send(APP)
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        self._send('{"error":"unauthorized"}', 401, "application/json")

srv = HTTPServer(("127.0.0.1", 0), H)
base = f"http://127.0.0.1:{srv.server_port}"
threading.Thread(target=srv.serve_forever, daemon=True).start()
api.APP_ORIGIN = base; api.CM_BASE = f"{base}/cm/v1/ui"
api.DT_BASE = f"{base}/dt/v1/ui"; api._API_HOST = "127.0.0.1"

# Un temporal, no la raiz del repo: un test no debe dejar
# basura en el arbol de trabajo.
sess = Path(tempfile.mkdtemp()) / "s401.json"; sess.write_text(json.dumps({"cookies": [], "origins": []}))

fails = []
def check(label, got, want):
    if got != want: fails.append(label); print(f"  FAIL {label}: {got!r} != {want!r}")
    else: print(f"  ok   {label}")

print("a 401 says what to do about it")
res = fetch_campaign("328634", credentials=None, headless=True,
                     timeout_ms=25_000, session_path=sess)
msg = " ".join(res.errors)
check("reports an error", bool(res.errors), True)
check("names the cause", "no longer valid" in msg, True)
check("says to run --login", "--login" in msg, True)
check("does not dump the whole URL", "fields=status,siteName" in msg, False)
print(f"       {res.errors[0].splitlines()[0]}")

print("\n--login refuses to save a session the API never accepted")
missing = Path("never_saved.json")
if missing.exists(): missing.unlink()
try:
    api.establish_session(session_path=missing, login_url=base, timeout_ms=8_000)
    check("raises", "no error", "InnovidAuthError")
except InnovidAuthError as exc:
    check("explains the API never answered", "never answered" in str(exc), True)
check("nothing was written", missing.exists(), False)

srv.shutdown()
print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("Session-401 handling verified.")

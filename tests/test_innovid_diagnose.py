"""El diagnostico debe informar sin exponer nada."""
import json, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _browser import fail, patch_launch, require_browser  # noqa: E402

require_browser()
patch_launch()
import core.innovid_api as api  # noqa: E402

SECRET = "super-secret-cookie-value"
APP = """<!doctype html><body><h1>Campaign Manager</h1><script>
localStorage.setItem('ft.user','someone'); sessionStorage.setItem('ft.csrf','tok');
</script></body>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _s(self, body, code=200, ctype="text/html", cookie=None):
        b = body.encode(); self.send_response(code)
        self.send_header("Content-Type", ctype)
        if cookie: self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        self._s(APP, cookie=f"ftsession={SECRET}; Path=/")
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        self._s('{"name":"Forbidden","description":"Invalid CSRF token"}',
                403, "application/json")

srv = HTTPServer(("127.0.0.1", 0), H)
base = f"http://127.0.0.1:{srv.server_port}"
threading.Thread(target=srv.serve_forever, daemon=True).start()
# These modules are scripts: everything below runs at import, so the
# rebinding is on the real module and stays there. Under `pytest
# tests/` that leaked -- a later module asked redact_url() about a
# genuine api.flashtalking.net URL and got "" back, because by then
# _API_HOST said 127.0.0.1. The originals are kept here and put back
# once the fake server is down.
_REAL_ENDPOINTS = (api.APP_ORIGIN, api.CM_BASE, api.DT_BASE, api._API_HOST)
api.APP_ORIGIN = base; api.CM_BASE = f"{base}/cm/v1/ui"
api.DT_BASE = f"{base}/dt/v1/ui"; api._API_HOST = "127.0.0.1"

sess = Path(tempfile.mkdtemp()) / "d.json"
sess.write_text(json.dumps({"cookies": [], "origins": []}))

lines = api.diagnose_session("328634", session_path=sess, headless=True)
report = "\n".join(lines)
fails = []
def check(label, got, want=True):
    if got != want: fails.append(label); print(f"  FAIL {label}")
    else: print(f"  ok   {label}")

check("reports where it landed", "Landed on:" in report)
check("lists cookie names", "ftsession" in report)
check("never prints a cookie value", SECRET in report, False)
check("reports storage keys", "ft.user" in report and "ft.csrf" in report)
check("says whether the app sent a token", "X-Csrf-Token itself" in report)
check("quotes Innovid's own error", "Invalid CSRF token" in report)
check("shows the status", "HTTP 403" in report)

srv.shutdown()
(api.APP_ORIGIN, api.CM_BASE, api.DT_BASE, api._API_HOST) = _REAL_ENDPOINTS
print("\n--- sample output ---")
print(report[:600])
print()
fail(fails, "Diagnostic")

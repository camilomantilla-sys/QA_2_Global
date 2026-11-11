"""
El servidor local de la interfaz nueva.

Usa ``http.server`` de la libreria estandar de Python: nada que
instalar y nada nuevo que aprobar. Las reglas de seguridad son las
mismas que ya cumple la app de Streamlit, y aqui estan escritas en
codigo en vez de en un archivo de configuracion:

- Escucha solo en 127.0.0.1. ``HOST`` no se puede cambiar desde fuera.
- Rechaza cualquier peticion cuyo ``Host`` no sea este PC. Asi una
  pagina de internet no puede alcanzarlo apuntando un dominio propio a
  127.0.0.1 (DNS rebinding).
- Las peticiones que hacen algo (POST) exigen la cabecera ``X-QA2`` y
  un ``Origin`` local. Un navegador no deja que otra pagina mande esa
  cabecera sin preguntar primero, y aqui nadie responde esa pregunta.
- Cada archivo se escribe en una carpeta temporal solo mientras se lee,
  y se borra al terminar. La solicitud en curso vive en memoria
  (ui/web/session.py) hasta Start over o hasta cerrar la ventana; no se
  guarda en disco ni se registra su contenido.
- Sin telemetria: el servidor no habla con nadie.
"""
from __future__ import annotations

import json
import mimetypes
import sys
import tempfile
import threading
import warnings
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: Solo este PC. No es configurable a proposito.
HOST = "127.0.0.1"
#: Streamlit usa 8501; la interfaz nueva va al lado para que convivan.
PORT = 8502
#: Una Traffic Sheet grande ronda los 10 MB; esto deja margen de sobra.
MAX_UPLOAD = 60 * 1024 * 1024
TS_SUFFIXES = (".xlsx", ".xlsm", ".xls")

STATIC = Path(__file__).resolve().parent / "static"

from ui.web.session import SESSION, SLOTS, WORKBOOK_SUFFIXES, account_options  # noqa: E402
ASSETS = ROOT / "ui" / "assets"

#: Lo unico que se sirve desde ui/assets. Nada mas de esa carpeta sale.
ASSET_FILES = {
    "/assets/logo.png": ASSETS / "wpp-media-logo.png.png",
    "/assets/fonts/WPP-Regular.woff2": ASSETS / "fonts" / "WPP-Regular.woff2",
    "/assets/fonts/WPP-Medium.woff2": ASSETS / "fonts" / "WPP-Medium.woff2",
    "/assets/fonts/WPP-Bold.woff2": ASSETS / "fonts" / "WPP-Bold.woff2",
}

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def allowed_hosts(port: int) -> set[str]:
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def allowed_origins(port: int) -> set[str]:
    return {f"http://{h}" for h in allowed_hosts(port)}


def read_traffic_sheet(data: bytes, file_name: str, keep: bool = True) -> dict:
    """Lee la TS con el parser de siempre y devuelve el resumen del paso 1.

    Con ``keep`` la lectura queda en la sesion para los pasos siguientes."""
    from parsers.ts_parser import parse_ts
    from ui.web.summary import build_summary

    suffix = Path(file_name).suffix.lower()
    if suffix not in TS_SUFFIXES:
        # Un .xlsx renombrado sigue siendo un zip; se respeta lo que es.
        suffix = ".xlsx" if data[:2] == b"PK" else suffix
    with tempfile.TemporaryDirectory(prefix="qa2_web_ts_") as folder:
        path = Path(folder) / f"traffic_sheet{suffix}"
        path.write_bytes(data)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = parse_ts(path)
            summary = build_summary(result, path, file_name)
    if keep:
        SESSION.set_traffic_sheet(file_name, data, result)
    return summary


class Handler(BaseHTTPRequestHandler):
    server_version = "QA2"
    sys_version = ""

    # ------------------------------------------------------------ helpers
    def log_message(self, format, *args):  # noqa: A002 - firma de la base
        """Sin registro por peticion: las rutas no dicen nada util y asi
        no queda ni el nombre de un archivo en ninguna consola."""

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in allowed_hosts(self.server.server_port)

    # ------------------------------------------------------------ GET
    def do_GET(self):  # noqa: N802 - nombre de la base
        if not self._host_ok():
            return self._json(HTTPStatus.FORBIDDEN, {"error": "QA2 only answers on this computer."})
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            body = (STATIC / "index.html").read_bytes()
            return self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
        if path == "/api/health":
            from core.release import qa2_version
            return self._json(HTTPStatus.OK, {"ok": True, "version": qa2_version()})
        if path == "/api/files":
            return self._json(HTTPStatus.OK, SESSION.overview())
        if path == "/api/accounts":
            return self._json(HTTPStatus.OK, {"accounts": account_options(),
                                              "selected": SESSION.account})
        if path == "/api/innovid":
            return self._json(HTTPStatus.OK, innovid_status())
        if path == "/api/results":
            return self._json(HTTPStatus.OK, SESSION.last_run or {})
        if path in ASSET_FILES and ASSET_FILES[path].is_file():
            target = ASSET_FILES[path]
            kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".woff2":
                kind = "font/woff2"
            return self._send(HTTPStatus.OK, target.read_bytes(), kind)
        return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    do_HEAD = do_GET

    # ------------------------------------------------------------ POST
    def do_POST(self):  # noqa: N802 - nombre de la base
        if not self._host_ok():
            return self._json(HTTPStatus.FORBIDDEN, {"error": "QA2 only answers on this computer."})
        origin = self.headers.get("Origin")
        if self.headers.get("X-QA2") != "1" or (
            origin is not None and origin not in allowed_origins(self.server.server_port)
        ):
            return self._json(HTTPStatus.FORBIDDEN, {"error": "Request refused."})

        from urllib.parse import parse_qs, unquote, urlsplit
        parts = urlsplit(self.path)
        path, query = parts.path, parse_qs(parts.query)

        if path == "/api/reset":
            SESSION.reset()
            return self._json(HTTPStatus.OK, SESSION.overview())
        if path == "/api/remove":
            body = self._read_json()
            slot = str(body.get("slot", ""))
            if slot not in SLOTS:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "Unknown file slot."})
            SESSION.remove_file(slot, str(body.get("name", "")))
            return self._json(HTTPStatus.OK, SESSION.overview())
        if path == "/api/run":
            return self._run(self._read_json())
        if path == "/api/innovid/sign-in":
            return self._json(HTTPStatus.OK, innovid_sign_in())
        if path not in ("/api/traffic-sheet", "/api/file", "/api/bundle"):
            return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

        slot = (query.get("slot") or [""])[0]
        if path == "/api/file" and slot not in SLOTS:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "Unknown file slot."})
        if path == "/api/file" and SESSION.ts is None:
            return self._json(HTTPStatus.CONFLICT,
                              {"error": "Load the Traffic Sheet in step 1 first."})

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "The file arrived empty. Try dropping it again."})
        if length > MAX_UPLOAD:
            return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                              {"error": "That file is over 60 MB. Check it is the right file."})

        file_name = Path(unquote(self.headers.get("X-File-Name", "file.xlsx"))).name[:200]
        if path == "/api/bundle":
            return self._bundle(self.rfile.read(length))
        if Path(file_name).suffix.lower() not in WORKBOOK_SUFFIXES:
            return self._json(HTTPStatus.BAD_REQUEST,
                              {"error": "QA2 reads .xlsx, .xlsm or .xls files. Save the file in one of those formats and drop it again."})

        data = self.rfile.read(length)
        if path == "/api/file":
            try:
                SESSION.add_file(slot, file_name, data)
            except Exception as exc:  # el detalle va a la pagina, no a un log
                return self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                    "error": f"QA2 could not read {file_name}. If Excel opens it, save a copy as .xlsx and try again.",
                    "detail": type(exc).__name__,
                })
            return self._json(HTTPStatus.OK, SESSION.overview())

        try:
            summary = read_traffic_sheet(data, file_name)
        except Exception as exc:  # el detalle va a la pagina, no a un log
            return self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                "error": "QA2 could not read this workbook. If Excel opens it, save a copy as .xlsx and try again.",
                "detail": type(exc).__name__,
            })
        return self._json(HTTPStatus.OK, summary)

    def _bundle(self, data: bytes):
        """Un session bundle: la TS va al paso 1 y el resto al paso 2."""
        from core.qa1_trail import describe_origin
        from core.session_bundle import BundleError, read_bundle
        try:
            bundle = read_bundle(data)
        except BundleError as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        ts = bundle.one("ts")
        if ts is None:
            return self._json(HTTPStatus.BAD_REQUEST,
                              {"error": "This bundle has no Traffic Sheet inside."})
        SESSION.reset()
        try:
            summary = read_traffic_sheet(ts[1], ts[0])
        except Exception as exc:  # noqa: BLE001
            return self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                "error": "QA2 could not read the Traffic Sheet inside this bundle.",
                "detail": type(exc).__name__,
            })
        unreadable = []
        for slot in SLOTS:
            for name, content in bundle.files.get(slot, []):
                try:
                    SESSION.add_file(slot, name, content)
                except Exception:  # noqa: BLE001 - se dice, no tumba la carga
                    unreadable.append(name)
        manifest = bundle.manifest
        account = str(manifest.get("account") or "")
        if account in account_options():
            SESSION.account = account
        origin = {k: manifest.get(k) for k in (
            "implemented_by", "implementation_date", "wrike_id", "saved_at", "qa1_result")}
        summary["bundle"] = {
            "origin": describe_origin(origin),
            "account": SESSION.account,
            "evidence": len(bundle.files.get("evidence", [])),
            "unreadable": unreadable,
        }
        summary["files"] = SESSION.overview()
        return self._json(HTTPStatus.OK, summary)

    def _read_json(self) -> dict:
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 64 * 1024)
            body = json.loads(self.rfile.read(length) or b"{}")
            return body if isinstance(body, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    def _run(self, body: dict):
        account = str(body.get("account") or "")[:80]
        if account == "All / unknown":
            account = ""
        use_innovid = bool(body.get("innovid"))
        SESSION.check_innovid = use_innovid
        try:
            payload = SESSION.run(account, fetch_innovid if use_innovid else None)
        except ValueError as exc:
            return self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - se dice en la pagina
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {
                "error": "The QA stopped before finishing. Run it again; if it keeps "
                         "failing, use the current QA2 window for this request.",
                "detail": type(exc).__name__,
            })
        return self._json(HTTPStatus.OK, payload)


# ------------------------------------------------------------------ Innovid

def innovid_status() -> dict:
    """Si hay una sesion de Innovid guardada en este PC y hasta cuando sirve."""
    from datetime import datetime, timezone
    from core.innovid_api import session_expires_at, session_has_expired, session_is_saved
    saved = session_is_saved()
    expired = saved and session_has_expired()
    hours = None
    if saved and not expired:
        expiry = session_expires_at()
        if expiry is not None:
            hours = max(0, int((expiry - datetime.now(timezone.utc)).total_seconds() // 3600))
    return {"saved": saved, "expired": expired, "hours_left": hours,
            "checking": SESSION.check_innovid}


def innovid_sign_in() -> dict:
    """Abre la ventana de inicio de sesion de Innovid en este PC."""
    from core.innovid_login import start_innovid_login
    outcome = start_innovid_login()
    return {"ok": outcome.ok, "message": outcome.message or (
        "A browser window is opening. Sign in, open a campaign so Innovid "
        "finishes loading, then close the window and come back here.")}


def fetch_innovid(campaign_id: str, placement_ids: tuple[str, ...]):
    """La campana desde Innovid. Nunca lanza: un fallo vuelve en ``errors``."""
    from types import SimpleNamespace
    from core.innovid_api import fetch_campaign, load_credentials
    try:
        return fetch_campaign(
            campaign_id=campaign_id,
            credentials=load_credentials(),
            placement_ids=set(placement_ids) or None,
            headless=True,
        )
    except Exception as exc:  # noqa: BLE001
        return SimpleNamespace(placements=[], errors=[f"Innovid could not be read: {type(exc).__name__}"])


def make_server(port: int = PORT) -> ThreadingHTTPServer:
    """El servidor, ligado solo a este PC. ``port=0`` toma uno libre (pruebas)."""
    server = ThreadingHTTPServer((HOST, port), Handler)
    server.daemon_threads = True
    return server


def main(open_browser: bool = True) -> None:
    try:
        server = make_server()
    except OSError:
        url = f"http://{HOST}:{PORT}/"
        print(f"QA2 is already running. Opening {url}")
        if open_browser:
            webbrowser.open(url)
        return
    url = f"http://{HOST}:{server.server_port}/"
    print(f"QA2 is running on this computer only: {url}")
    print("Close this window to stop it.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

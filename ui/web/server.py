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
- La Traffic Sheet se escribe en una carpeta temporal solo mientras se
  lee, y se borra al terminar. No se guarda ni se registra su contenido.
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


def read_traffic_sheet(data: bytes, file_name: str) -> dict:
    """Lee la TS con el parser de siempre y devuelve el resumen del paso 1."""
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
            return build_summary(result, path, file_name)


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

        path = self.path.split("?", 1)[0]
        if path != "/api/traffic-sheet":
            return self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "The file arrived empty. Try dropping it again."})
        if length > MAX_UPLOAD:
            return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                              {"error": "That file is over 60 MB. A Traffic Sheet is usually under 10 MB; check it is the right file."})

        from urllib.parse import unquote
        file_name = unquote(self.headers.get("X-File-Name", "traffic_sheet.xlsx"))[:200]
        if Path(file_name).suffix.lower() not in TS_SUFFIXES:
            return self._json(HTTPStatus.BAD_REQUEST,
                              {"error": "QA2 reads Traffic Sheets as .xlsx, .xlsm or .xls. Save the file in one of those formats and drop it again."})

        data = self.rfile.read(length)
        try:
            summary = read_traffic_sheet(data, file_name)
        except Exception as exc:  # el detalle va a la pagina, no a un log
            return self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                "error": "QA2 could not read this workbook. If Excel opens it, save a copy as .xlsx and try again.",
                "detail": type(exc).__name__,
            })
        return self._json(HTTPStatus.OK, summary)


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

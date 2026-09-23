"""
Arranca QA2: anota su PID, abre el navegador, y avisa si no levanta.

Sin ventana cuando lo lanza pythonw.exe, que es como lo abre el equipo
-- "yo no quiero que mi amiga tenga que abrir ninguna terminal".

Eso deja un problema conocido, y es el que hundio al lanzador .vbs que
habia antes: sin consola, un fallo no se ve por ningun lado y la
persona espera a una ventana que no va a llegar. Aqui no. Un hilo
vigila el puerto; si el servidor responde abre el navegador, y si no
responde lo dice en un cuadro de dialogo --con ctypes, sin Windows
Script Host, que la directiva de IT bloquea-- y apunta al log.

El PID se anota antes de ceder el control, y en el MISMO proceso:
cli.main() no lanza otro, asi que el numero escrito es exactamente el
que "Stop QA2.bat" tiene que matar. Estaba dentro de app_v2.py y no
servia: ese codigo corre en la primera sesion, o sea cuando alguien
abre la pagina, y hasta entonces el servidor estaba arriba sin que
nadie pudiera encontrarlo.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# NADA de QA2 se importa aqui arriba, a proposito.
#
# Este archivo lo arranca pythonw.exe, que NO TIENE CONSOLA: si algo
# falla antes de que el log este abierto, el mensaje no va a ninguna
# parte. Doble clic y no pasa nada, sin un solo rastro -- que es
# exactamente lo que le paso al jefe de Camilo con el paquete 1.0.1:
# "solo me dice que no le abre nada".
#
# Asi que lo primero que hace main() es abrir el log, y TODO lo demas
# --incluidos los imports de core-- va dentro de un try que escribe
# ahi lo que pase y lo enseña en un cuadro de dialogo.

DEFAULT_PORT = 8501

#: Cuanto se le da al servidor. Un paquete levanta en segundos; una
#: copia de desarrollo que aun instala librerias tarda bastante mas.
STARTUP_TIMEOUT = 120


def _answers(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _tell(message: str) -> None:
    """
    Un aviso que se ve aunque no haya consola.

    ctypes y no un .vbs: Windows Script Host esta bloqueado por
    directiva en las maquinas del equipo.
    """
    print(message)
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "QA2", 0x10)
    except Exception:
        pass


#: Cuantos puertos se prueban despues del suyo antes de rendirse.
PORT_TRIES = 20


def _free_port(start: int) -> int | None:
    """
    El primer puerto que nadie tenga, a partir del siguiente al suyo.

    Se comprueba intentando ATARLO, no preguntando si contesta: un
    puerto tomado por algo que no responde se ve libre desde fuera y
    Streamlit se estrellaria contra el.
    """
    for candidate in range(start + 1, start + 1 + PORT_TRIES):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                continue
        return candidate
    return None


def _watch(port: int, log: Path) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if _answers(port):
            webbrowser.open(f"http://localhost:{port}")
            return
        time.sleep(0.5)

    _tell(
        f"QA2 no arranco en {STARTUP_TIMEOUT} segundos.\n\n"
        f"Lo que paso quedo escrito en:\n{log}\n\n"
        "Mandale ese archivo a quien te compartio QA2."
    )


def _open_log(log: Path):
    """
    El log, abierto ANTES que nada.

    Si no hay consola --pythonw.exe, que es como arranca el equipo--
    ademas se le manda stdout y stderr: de otro modo un fallo de
    arranque no deja rastro en ningun sitio.
    """
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        handle = log.open("w", encoding="utf-8", errors="replace")
    except OSError:
        return None

    if sys.stdout is None or not sys.stdout.isatty():
        sys.stdout = handle
        sys.stderr = handle
    return handle


def _note(handle, text: str) -> None:
    """Al log siempre; y a la consola tambien, si la hay."""
    try:
        print(text)
    except Exception:
        pass
    if handle is not None and sys.stdout is not handle:
        try:
            handle.write(text + "\n")
            handle.flush()
        except OSError:
            pass


def _header(handle, port: int) -> None:
    """
    Lo que hace falta saber para entender un arranque fallido, sin
    tener que pedirlo por chat.
    """
    try:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        version = "(sin VERSION)"

    _note(handle, "-" * 60)
    _note(handle, f"QA2 {version} arrancando  {datetime.now():%Y-%m-%d %H:%M:%S}")
    _note(handle, f"  carpeta      {ROOT}")
    _note(handle, f"  interprete   {sys.executable}")
    _note(handle, f"  python       {sys.version.split()[0]}")
    _note(handle, f"  python\\      {'si' if (ROOT / 'python').is_dir() else 'NO'}")
    _note(handle, f"  browsers\\    {'si' if (ROOT / 'browsers').is_dir() else 'NO'}")
    _note(handle, f"  puerto       {port}")
    _note(handle, "-" * 60)


def main() -> int:
    port = DEFAULT_PORT
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    log = ROOT / "logs" / "qa2_startup.log"
    handle = _open_log(log)
    _header(handle, port)

    try:
        return _start(port, log, handle)
    except BaseException:
        # Cualquier cosa: un import que falta, un permiso, un archivo
        # que no llego en el .zip. Sin esto, con pythonw.exe no se ve
        # nada de nada y la app "no abre" sin mas.
        _note(handle, "")
        _note(handle, traceback.format_exc())
        _tell(
            "QA2 no pudo arrancar.\n\n"
            f"Lo que paso quedo escrito en:\n{log}\n\n"
            "Mandale ese archivo a quien te compartio QA2."
        )
        return 1
    finally:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass


def _start(port: int, log: Path, handle) -> int:
    from core.innovid_login import ensure_browser_path
    from core.pidfile import clear_pid, is_running, write_pid

    # El navegador del paquete. El chequeo contra Innovid abre
    # Chromium dentro de ESTE proceso, asi que la variable tiene que
    # quedar puesta aqui: pasarsela a un subproceso no alcanza.
    ensure_browser_path(ROOT)

    if _answers(port):
        # Hay algo en el puerto. La pregunta es de QUIEN.
        #
        # Si es el QA2 de ESTA carpeta, se abre el navegador sobre el
        # en vez de pelear por el puerto: sin eso Streamlit se iba al
        # 8502 y cada vuelta dejaba un proceso mas vivo.
        if is_running(ROOT):
            _note(handle, "Ya habia un QA2 de esta carpeta abierto.")
            webbrowser.open(f"http://localhost:{port}")
            return 0

        # Pero si es OTRO --la carpeta de una version vieja que
        # alguien conservo, y la gente las conserva-- abrir ahi
        # enseñaba una version distinta de la que se habia abierto,
        # sin decir nada. Camilo: "intenté correr esa version vieja y
        # me corre la mas reciente". Esta arranca en su propio puerto.
        libre = _free_port(port)
        if libre is None:
            _tell(
                "QA2 no encontro un puerto libre.\n\n"
                "Cierra las otras copias de QA2 que tengas abiertas "
                'con "Stop QA2.bat" y vuelve a intentarlo.'
            )
            return 1
        _note(
            handle,
            f"El puerto {port} lo tiene otra copia de QA2. "
            f"Esta arranca en el {libre}.",
        )
        port = libre

    write_pid(ROOT)

    threading.Thread(target=_watch, args=(port, log), daemon=True).start()

    try:
        from streamlit.web import cli
    except ImportError:
        clear_pid(ROOT)
        _tell(
            "A esta copia de QA2 le falta Streamlit.\n\n"
            "Si es el paquete que te compartieron, la descarga quedo "
            "incompleta: vuelve a extraer el .zip."
        )
        return 1

    sys.argv = [
        "streamlit", "run", str(ROOT / "ui" / "app_v2.py"),
        "--server.port", str(port),
    ]
    try:
        return cli.main(standalone_mode=False) or 0
    finally:
        # Que no quede un PID apuntando a un proceso muerto: el
        # siguiente arranque lo leeria y creeria que QA2 sigue abierto.
        clear_pid(ROOT)


if __name__ == "__main__":
    sys.exit(main())

"""
Arrancar el inicio de sesion de Innovid, y saber si arranco.

La app lanzaba el proceso y anunciaba "se esta abriendo una ventana"
sin mirar si seguia vivo. Cuando moria al instante -- que es lo que
pasa si el paquete se quedo sin Chromium -- el usuario veia ese mensaje
y esperaba una ventana que no iba a llegar nunca. Sin error, sin log,
sin nada que explicara por que.

Aqui se espera unos segundos: un navegador que va a abrirse, se abre en
ese tiempo, y un fallo tambien ocurre en ese tiempo. Si el proceso
sigue vivo, se le deja seguir -- el inicio de sesion es interactivo y
puede tardar minutos.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

#: Cuanto se espera antes de dar por bueno que arranco. Playwright
#: tarda un segundo largo en levantar Chromium; cuatro da margen sin
#: que la app se sienta colgada.
SETTLE_SECONDS = 4.0


@dataclass
class LoginStart:
    ok: bool
    message: str = ""
    detail: str = ""


def bundled_browser_dir(root: Path) -> Path | None:
    """La carpeta de navegadores del paquete, si este es un paquete."""
    browsers = root / "browsers"
    if browsers.is_dir() and any(browsers.glob("chromium*")):
        return browsers
    return None


def ensure_browser_path(root: Path | None = None) -> Path | None:
    """
    Pone PLAYWRIGHT_BROWSERS_PATH en ESTE proceso, si el paquete trae
    navegador propio.

    El lanzador sin ventana --el que usa el equipo-- no lo ponia: solo
    lo hacia run_qa2.bat, la version con consola. Y como el chequeo
    contra Innovid abre Chromium DENTRO del proceso de la app, y no en
    un subproceso al que se le pueda pasar el entorno, un paquete
    completo abierto con doble clic no encontraba su propio navegador:
    Playwright lo buscaba en la carpeta del usuario, donde no hay nada.

    Se arregla aqui y no en el .bat porque la ruta se deduce sola de la
    carpeta del proyecto, y asi vale igual para el .bat, para el CLI y
    para quien lo arranque de otra manera. Una variable ya puesta a
    mano manda: quien la declara sabe lo que hace.
    """
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip():
        return None
    root = root or Path(__file__).resolve().parents[1]
    browsers = bundled_browser_dir(root)
    if browsers is None:
        return None
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
    return browsers


def missing_browser_reason(root: Path) -> str:
    """
    Por que no hay navegador, dicho para quien lo va a leer.

    Se distingue el paquete de una copia de desarrollo porque el
    remedio no es el mismo, y mandarle a alguien un `pip install` a la
    cara cuando lo que tiene es un zip incompleto no ayuda a nadie.
    """
    if (root / "python" / "python.exe").exists() or (root / "python").is_dir():
        if not (root / "browsers").is_dir():
            return (
                "This QA2 package was built without the browser, so the "
                "Innovid sign-in cannot run. Everything else works. Ask "
                "for a package built with Innovid included."
            )
        return (
            "The browser folder in this package looks incomplete. Ask "
            "for the package to be built again."
        )
    # Ni paquete ni copia de desarrollo: lo que hay es el zip de
    # actualizacion extraido por su cuenta.
    #
    # Ese zip es un parche, no una aplicacion: trae el codigo y nada
    # mas, para caer encima de una instalacion que ya existe. Abierto
    # solo, arranca --hay Python en la maquina de quien lo intenta--
    # pero sin interprete propio ni navegador, y lo unico que se veia
    # era un "corre pip install" que no tiene nada que ver.
    es_desarrollo = (root / ".git").exists() or (root / ".venv").is_dir()
    if not es_desarrollo and (root / "ACTUALIZAR QA2.bat").exists():
        return (
            "This folder is the QA2 update, not QA2 itself: it carries "
            "the code and nothing else. Extract it over your existing "
            'QA2 folder and run "ACTUALIZAR QA2.bat" from there, or '
            "ask for the full package."
        )

    return (
        "Playwright has no browser on this machine. In the project "
        "folder run:\n\n    python -m playwright install chromium"
    )


def start_innovid_login(
    root: Path | None = None,
    settle: float = SETTLE_SECONDS,
) -> LoginStart:
    """
    Lanza check_innovid_connection.py --login y mira si sobrevivio.

    Devuelve ok=True si sigue corriendo pasados unos segundos, que es
    lo que significa que el navegador se abrio de verdad.
    """
    root = root or Path(__file__).resolve().parents[1]

    environment = dict(os.environ)
    browsers = bundled_browser_dir(root)
    if browsers is not None:
        # El paquete trae el suyo. Se dice explicitamente en vez de
        # confiar en que el lanzador lo heredara: quien arranca QA2 de
        # otra manera se quedaba sin navegador y sin explicacion.
        environment["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)

    script = root / "check_innovid_connection.py"
    if not script.exists():
        return LoginStart(
            False,
            "check_innovid_connection.py is missing from this QA2 "
            "folder. The download may be incomplete -- extract the "
            ".zip again.",
        )

    try:
        process = subprocess.Popen(
            [sys.executable, str(script), "--login"],
            cwd=str(root),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        return LoginStart(
            False, f"The sign-in could not be started: {error}"
        )

    deadline = time.monotonic() + settle
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        time.sleep(0.2)

    if process.poll() is None:
        return LoginStart(True)

    output = ""
    try:
        output = (process.stdout.read() or "").strip() if process.stdout else ""
    except OSError:
        pass

    lowered = output.lower()
    if "executable doesn't exist" in lowered or "playwright install" in lowered:
        return LoginStart(
            False, missing_browser_reason(root), output
        )

    return LoginStart(
        False,
        "The Innovid sign-in stopped before the browser opened.",
        output or "(it printed nothing)",
    )

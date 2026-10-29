"""
Como lanzan Chromium las pruebas que necesitan un navegador.

Seis archivos traian esta linea, copiada de uno a otro:

    "executable_path": "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

Esa es la ruta del contenedor donde se escribio el codigo. En Windows
no existe, asi que Playwright fallaba con "executable doesn't exist at
\\opt\\pw-browsers\\..." -- y como esos archivos son scripts que
terminan en sys.exit(1), pytest se caia entero durante la recoleccion.
No es que fallaran unas pruebas: NINGUNA corria. `pytest tests/`, que
es el paso que protege lo que se le entrega al equipo, nunca habia
funcionado fuera de esa maquina.

Ahora no se le dice a Playwright donde esta el navegador: Playwright lo
sabe, y honra PLAYWRIGHT_BROWSERS_PATH cuando esta puesto. Y si no hay
navegador instalado, el archivo se salta con un motivo en vez de tumbar
la corrida.
"""
from __future__ import annotations

import pytest

#: Lo unico que de verdad hace falta pasarle. --no-sandbox porque
#: muchos contenedores corren como root y Chromium se niega.
LAUNCH_ARGS = ["--no-sandbox"]


def patch_launch() -> None:
    """
    Le pone --no-sandbox a todo BrowserType.launch de esta corrida.

    Los scripts que prueban innovid_api no llaman a launch() ellos: lo
    llama el codigo de la aplicacion, por dentro. Esta es la unica
    forma de alcanzarlo sin cambiar la aplicacion para las pruebas.
    """
    from playwright.sync_api._generated import BrowserType

    if getattr(BrowserType.launch, "_qa2_patched", False):
        return

    original = BrowserType.launch

    def launch(self, **kwargs):
        return original(self, **{**kwargs, "args": LAUNCH_ARGS})

    launch._qa2_patched = True
    BrowserType.launch = launch


def require_browser() -> None:
    """
    Salta el archivo entero si no hay Chromium instalado.

    Se llama al principio, antes de levantar servidores falsos y de
    importar la aplicacion, para que saltar sea limpio.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright is not installed", allow_module_level=True)
        return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=LAUNCH_ARGS)
            browser.close()
    except Exception as error:
        pytest.skip(
            "no Chromium for Playwright here -- run "
            f"`python -m playwright install chromium` ({type(error).__name__})",
            allow_module_level=True,
        )


def fail(failures: list[str], subject: str) -> None:
    """
    Como termina un script de estos cuando algo no cuadra.

    Antes era sys.exit(1), y bajo pytest un SystemExit durante la
    recoleccion no es un fallo: es un INTERNALERROR que se lleva por
    delante la corrida completa, incluidos los otros cuatrocientos
    tests que no tenian nada que ver. Un AssertionError se reporta como
    lo que es y deja correr al resto.
    """
    if failures:
        raise AssertionError(f"{len(failures)} FAILURE(S): {failures}")
    print(f"{subject} verified.")

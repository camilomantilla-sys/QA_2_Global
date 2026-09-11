"""
La app debe darse cuenta de que corre codigo viejo.

Se simula lo que le paso a Camilo: el archivo cambia en disco
DESPUES de que el proceso lo cargo, y recargar la pagina no basta.

Levanta la app de verdad, asi que tambien vale como prueba de que
arranca. Run directly:
    python tests/test_ui_stale_modules.py
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core" / "innovid_api.py"
PYTHON = ROOT / ".venv" / "bin" / "python"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for(url: str, timeout: int = 90) -> bool:
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    return False


def sidebar_text(page):
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("[data-testid='stSidebar']", timeout=60_000)
    page.wait_for_timeout(4000)
    page.get_by_text("Check against Innovid", exact=False).first.click()
    page.wait_for_timeout(1500)
    return page.inner_text("[data-testid='stSidebar']")


fails = []


def check(label, got, want=True):
    if got != want:
        fails.append(label)
        print(f"  FAIL {label}: {got!r}")
    else:
        print(f"  ok   {label}")


port = _free_port()
server = subprocess.Popen(
    [
        str(PYTHON), "-m", "streamlit", "run", "ui/app_v2.py",
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ],
    cwd=str(ROOT),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
app = f"http://127.0.0.1:{port}"

try:
    if not _wait_for(app):
        print("FAILURE: la app no arranco")
        sys.exit(1)

    with sync_playwright() as p:
        b = p.chromium.launch(
            args=["--no-sandbox"],
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
        )
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(app, wait_until="domcontentloaded")

        before = sidebar_text(page)
        print("with the loaded code matching disk")
        check("the app booted", "Run QA" in before)
        check("no restart warning", "Restart QA" in before, False)
        check("build is shown", "QA build" in before)
        # El testigo del clic y el contador de pasadas: sin ellos no
        # se puede distinguir "el clic no llego" de "llego y no hizo
        # nada", que costo una semana.
        check("script runs is shown", "Script runs" in before)

        # Ahora el archivo cambia despues de haber sido cargado.
        CORE.touch()
        time.sleep(2)

        after = sidebar_text(page)
        print("\nafter the file changes under the running app")
        check("it says to restart", "Restart QA" in after)
        check("it names the module", "innovid_api" in after)
        check("it says reloading is not enough", "not enough" in after)

        b.close()
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()

print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    sys.exit(1)
print("Stale-code warning verified.")

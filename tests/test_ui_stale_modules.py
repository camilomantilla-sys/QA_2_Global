"""
La app debe darse cuenta de que corre codigo viejo.

Se simula lo que le paso a Camilo: el archivo cambia en disco
DESPUES de que el proceso lo cargo.
"""
import subprocess, sys, time
from playwright.sync_api import sync_playwright

APP = "http://127.0.0.1:8520"
CORE = "/home/user/QA_2_Global/core/innovid_api.py"

def sidebar_text(page):
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("[data-testid='stSidebar']", timeout=60_000)
    page.wait_for_timeout(4000)
    page.get_by_text("Check against Innovid", exact=False).first.click()
    page.wait_for_timeout(1500)
    return page.inner_text("[data-testid='stSidebar']")

fails = []
def check(label, got, want=True):
    if got != want: fails.append(label); print(f"  FAIL {label}: {got!r}")
    else: print(f"  ok   {label}")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"],
        executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    page = b.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(APP, wait_until="domcontentloaded")

    before = sidebar_text(page)
    print("with the loaded code matching disk")
    check("no restart warning", "Restart QA2" in before, False)
    check("build is shown", "QA2 build" in before)

    # Ahora el archivo cambia despues de haber sido cargado.
    subprocess.run(["touch", CORE], check=True)
    time.sleep(2)

    after = sidebar_text(page)
    print("\nafter the file changes under the running app")
    check("it says to restart", "Restart QA2" in after)
    check("it names the module", "innovid_api" in after)
    check("it says reloading is not enough", "not enough" in after)

    page.screenshot(path="stale_warning.png")
    b.close()

print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("Stale-code warning verified.")

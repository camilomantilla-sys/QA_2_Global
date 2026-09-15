"""
El paquete que se entrega trae su propio Python.

    "yo no voy a poner a descargar python a 30 personas"

Y en una maquina corporativa probablemente ni podrian. Asi que el
Python viaja dentro del zip: se extrae, se hace doble clic, y no hay
nada que instalar.

Estas pruebas fijan lo que no se puede romper sin que alguien lo note
tarde, cuando el paquete ya esta en manos de otros:

  - el lanzador usa el Python del paquete si esta, y el del sistema si
    no -- el mismo .bat sirve para el equipo y para quien desarrolla;
  - Chromium solo se copia si es la revision EXACTA que pide el
    Playwright del paquete. Una distinta produce un paquete que
    arranca y falla al abrir el navegador, que es el peor momento;
  - el paquete no lleva credenciales, y eso se comprueba antes de
    comprimir.

Run with pytest, or directly:
    python tests/test_bundle.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
BAT = (ROOT / "run_qa2.bat").read_text(encoding="utf-8")
SILENT = (ROOT / "run_qa2_silent.bat").read_text(encoding="utf-8")


# ── el lanzador ──────────────────────────────────────────────────────

def test_the_launcher_prefers_the_bundled_python():
    assert 'if exist "python\\python.exe"' in BAT
    assert "%CD%\\python\\python.exe" in BAT


def test_the_launcher_points_playwright_at_the_bundled_browser():
    """Sin esto busca en la carpeta del usuario, donde no hay nada."""
    assert "PLAYWRIGHT_BROWSERS_PATH=%CD%\\browsers" in BAT
    assert "PLAYWRIGHT_BROWSERS_PATH=%CD%\\browsers" in SILENT


def test_the_launcher_still_works_for_a_development_copy():
    assert ".venv" in BAT
    assert "requirements.txt" in BAT


def test_the_bundle_never_runs_pip():
    """
    Las librerias ya estan. Si el paquete intentara instalarlas,
    necesitaria llegar a PyPI -- que es justo lo que no se puede
    asumir en la red donde va a correr.
    """
    bundled = BAT[BAT.index('if exist "python\\python.exe"'):]
    bundled = bundled[:bundled.index("goto :run")]
    assert "pip" not in bundled


def test_someone_who_did_not_extract_the_zip_is_told_so():
    """El error que parece que el programa esta roto."""
    assert "Extract All" in BAT


def test_the_silent_launcher_has_no_pause():
    """No hay ventana donde verlo, asi que esperaria para siempre."""
    commands = [
        line.strip().lower()
        for line in SILENT.splitlines()
        if not line.strip().upper().startswith("REM")
    ]
    assert "pause" not in commands


# ── que revisiones del navegador se copian ───────────────────────────

def test_only_the_revision_playwright_asks_for_is_reused():
    from scripts.build_bundle import install_chromium

    source = install_chromium.__doc__ or ""
    code = (ROOT / "scripts" / "build_bundle.py").read_text(encoding="utf-8")
    body = code[code.index("def install_chromium"):]
    body = body[:body.index("\ndef ", 1)] if "\ndef " in body[1:] else body
    # La copia local solo ocurre cuando estan TODAS las que pide.
    assert "len(available) == len(needed)" in body
    assert "required_browsers" in body


def test_the_needed_revisions_come_from_playwright_itself():
    from scripts.build_bundle import required_browsers

    code = (ROOT / "scripts" / "build_bundle.py").read_text(encoding="utf-8")
    body = code[code.index("def required_browsers"):]
    assert "--dry-run" in body
    assert "Install location:" in body
    assert callable(required_browsers)


def test_a_cache_is_found_on_every_platform():
    from scripts.build_bundle import local_browser_cache

    code = (ROOT / "scripts" / "build_bundle.py").read_text(encoding="utf-8")
    body = code[code.index("def local_browser_cache"):]
    for marker in ("AppData", ".cache", "Library"):
        assert marker in body
    assert callable(local_browser_cache)


# ── lo que nunca entra ───────────────────────────────────────────────

def test_the_bundle_would_refuse_to_ship_the_sign_in():
    from scripts.build_bundle import guard
    from core.paths import LOCAL_ONLY_FILES
    import pytest

    import tempfile

    fake = Path(tempfile.mkdtemp())
    (fake / "config").mkdir()
    (fake / "config" / LOCAL_ONLY_FILES[0]).write_text("SECRET=1")
    with pytest.raises(SystemExit):
        guard(fake)


def test_a_clean_bundle_passes_the_guard():
    from scripts.build_bundle import guard
    import tempfile

    fake = Path(tempfile.mkdtemp())
    (fake / "ui").mkdir()
    (fake / "ui" / "app_v2.py").write_text("# app")
    guard(fake)  # no levanta


def test_the_builder_does_not_package_its_own_output():
    """
    dist/ contiene el paquete a medio armar. Sin excluirlo, el paquete
    se copia a si mismo: 158 archivos pasaron a 12.630 y el zip a
    1,3 GB antes de que alguien mirara el numero.
    """
    from scripts.package_release import SKIP_DIRS

    assert "dist" in SKIP_DIRS
    assert "browsers" in SKIP_DIRS


def test_the_project_files_are_the_same_list_for_both_packagers():
    """
    Que es un secreto se decide en un sitio. Si el paquete grande
    tuviera sus propias reglas, tarde o temprano se separarian.
    """
    code = (ROOT / "scripts" / "build_bundle.py").read_text(encoding="utf-8")
    assert "from scripts.package_release import" in code
    assert "app_files" in code


# ── las versiones quedan fijadas ─────────────────────────────────────

def test_the_build_pins_what_it_installed():
    """
    requirements.txt dice `pandas>=2.2.0`. Bien para desarrollar, mal
    para un paquete: armarlo dos meses despues trae otras versiones y
    el equipo corre algo que nunca paso las pruebas, en silencio.
    """
    code = (ROOT / "scripts" / "build_bundle.py").read_text(encoding="utf-8")
    assert "pip\", \"freeze" in code.replace("'", '"')
    assert "requirements-lock-" in code


def test_a_lock_is_used_when_it_exists():
    from scripts.build_bundle import lock_path

    code = (ROOT / "scripts" / "build_bundle.py").read_text(encoding="utf-8")
    body = code[code.index("def install_requirements"):]
    assert "if lock.exists():" in body
    assert lock_path("windows").name == "requirements-lock-windows.txt"


# ── el trim no deja huerfanos ────────────────────────────────────────

def test_removing_setuptools_also_removes_its_pth():
    """
    setuptools deja un .pth que importa _distutils_hack al arrancar.
    Quitar el modulo y dejar el .pth hacia que el interprete escupiera
    ModuleNotFoundError antes de ejecutar una sola linea.
    """
    from scripts.build_bundle import TRIM, TRIM_PTH

    assert "setuptools" in TRIM
    assert "_distutils_hack" in TRIM
    assert "distutils-precedence.pth" in TRIM_PTH



# ── el update se descomprime DENTRO de una instalacion ───────────────

def test_the_update_zip_has_no_folder_inside_it():
    """
    El zip completo trae una carpeta porque se extrae en un sitio
    nuevo. El de update NO, porque se extrae dentro de uno que ya
    existe.

    Con carpeta no se superponia con nada: la instalada se llama
    QA2-1.0.0-windows y el zip traia QA2-1.0.0, asi que extraerlo
    dejaba una carpeta nueva al lado y la aplicacion sin actualizar, y
    sin dar ningun error -- que es la peor forma de fallar, porque
    parece que funciono.
    """
    import tempfile
    import zipfile

    from scripts.package_release import build_update

    target = Path(tempfile.mkdtemp()) / "update.zip"
    build_update(target)
    names = zipfile.ZipFile(target).namelist()

    assert "core/excel_report.py" in names
    assert not [n for n in names if n.startswith("QA2-")]


def test_applying_the_update_leaves_the_interpreter_alone():
    """
    Lo que de verdad importa al actualizar: nadie pierde su Python, su
    navegador, ni su sesion de Innovid.
    """
    import tempfile
    import zipfile

    from scripts.package_release import build_update

    install = Path(tempfile.mkdtemp()) / "QA2-1.0.0-windows"
    (install / "python" / "bin").mkdir(parents=True)
    (install / "browsers").mkdir()
    (install / "config").mkdir()
    (install / "core").mkdir()
    (install / "python" / "bin" / "python3").write_text("interpreter")
    (install / "browsers" / "chromium").write_text("browser")
    (install / "config" / "innovid_credentials.env").write_text("SECRET")
    (install / "core" / "excel_report.py").write_text("old")

    target = Path(tempfile.mkdtemp()) / "update.zip"
    build_update(target)
    with zipfile.ZipFile(target) as zf:
        zf.extractall(install)

    assert (install / "python" / "bin" / "python3").read_text() == "interpreter"
    assert (install / "browsers" / "chromium").read_text() == "browser"
    assert (install / "config" / "innovid_credentials.env").read_text() == "SECRET"
    assert (install / "core" / "excel_report.py").read_text() != "old"


def test_the_full_package_still_has_its_folder():
    """El completo se extrae en un sitio nuevo: ahi la carpeta si va."""
    import tempfile
    import zipfile

    from scripts.package_release import build

    target = Path(tempfile.mkdtemp()) / "full.zip"
    build(target)
    names = zipfile.ZipFile(target).namelist()
    assert all(n.startswith("QA2-") for n in names), names[:3]


def test_pytest_is_a_development_dependency_not_a_shipped_one():
    """
    `pytest tests/` fallaba en una copia recien clonada: pytest no
    esta en requirements.txt, y no debe estarlo -- el paquete del
    equipo corre QA2, no las pruebas. Va en su propio archivo.
    """
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    shipped = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "pytest" in dev
    assert "pytest" not in shipped.lower()


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))

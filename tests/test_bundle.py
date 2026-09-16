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


# ── el lanzador ──────────────────────────────────────────────────────

def test_the_launcher_prefers_the_bundled_python():
    assert 'if exist "python\\python.exe"' in BAT
    assert "%CD%\\python\\python.exe" in BAT


def test_the_launcher_points_playwright_at_the_bundled_browser():
    """Sin esto busca en la carpeta del usuario, donde no hay nada."""
    assert "PLAYWRIGHT_BROWSERS_PATH=%CD%\\browsers" in BAT


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
    (fake / "config" / LOCAL_ONLY_FILES[0]).write_text("SECRET=1", encoding="utf-8")
    with pytest.raises(SystemExit):
        guard(fake)


def test_a_clean_bundle_passes_the_guard():
    from scripts.build_bundle import guard
    import tempfile

    fake = Path(tempfile.mkdtemp())
    (fake / "ui").mkdir()
    (fake / "ui" / "app_v2.py").write_text("# app", encoding="utf-8")
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
    (install / "python" / "bin" / "python3").write_text("interpreter", encoding="utf-8")
    (install / "browsers" / "chromium").write_text("browser", encoding="utf-8")
    (install / "config" / "innovid_credentials.env").write_text("SECRET", encoding="utf-8")
    (install / "core" / "excel_report.py").write_text("old", encoding="utf-8")

    target = Path(tempfile.mkdtemp()) / "update.zip"
    build_update(target)
    with zipfile.ZipFile(target) as zf:
        zf.extractall(install)

    assert (install / "python" / "bin" / "python3").read_text(encoding="utf-8") == "interpreter"
    assert (install / "browsers" / "chromium").read_text(encoding="utf-8") == "browser"
    assert (install / "config" / "innovid_credentials.env").read_text(encoding="utf-8") == "SECRET"
    assert (install / "core" / "excel_report.py").read_text(encoding="utf-8") != "old"


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


# ── el que aplica la actualizacion ───────────────────────────────────

def test_the_folder_the_team_opens_is_not_a_junk_drawer():
    """
    Trece archivos en la raiz donde tres importan. No estorbaba hasta
    el dia que alguien abrio el lanzador equivocado.
    """
    import tempfile
    import zipfile

    from scripts.package_release import build_update

    target = Path(tempfile.mkdtemp()) / "update.zip"
    build_update(target)
    root = {n for n in zipfile.ZipFile(target).namelist() if "/" not in n}

    assert "QA2.bat" in root
    assert "Stop QA2.bat" in root
    for noise in (".gitignore", "requirements-dev.txt"):
        assert noise not in root, noise
    assert not [n for n in root if n.startswith("requirements-lock-")]


def test_the_update_carries_something_that_applies_it():
    """
    "Abre el zip y arrastra el contenido" no es lo que hace la gente.
    Le dan a Extraer todo, que crea una carpeta con el nombre del zip,
    y la actualizacion se queda ahi sin aplicarse -- sin ningun error,
    porque la carpeta existe y los archivos estan. Paso en la primera
    entrega real.
    """
    import tempfile
    import zipfile

    from scripts.package_release import build_update

    target = Path(tempfile.mkdtemp()) / "update.zip"
    build_update(target)
    assert "ACTUALIZAR QA2.bat" in zipfile.ZipFile(target).namelist()


def test_the_applier_refuses_to_copy_over_a_running_qa2():
    """Con QA2 abierto, Windows no deja reemplazar sus archivos."""
    bat = (ROOT / "scripts" / "update_template.bat").read_text(encoding="utf-8")
    assert "tasklist" in bat
    assert "python.exe" in bat


def test_the_applier_checks_it_found_qa2_before_copying():
    bat = (ROOT / "scripts" / "update_template.bat").read_text(encoding="utf-8")
    assert "ui\\app_v2.py" in bat


def test_the_applier_never_touches_what_must_survive():
    """
    El interprete, el navegador y la sesion de Innovid no estan en el
    zip, asi que copiar encima no puede tocarlos -- y el .bat lo dice
    antes de preguntar, que es lo que hace que alguien se atreva.
    """
    bat = (ROOT / "scripts" / "update_template.bat").read_text(encoding="utf-8")
    for kept in ("python\\", "browsers\\", "config\\", "logs\\"):
        assert kept in bat, kept


def test_the_applier_asks_before_doing_anything():
    bat = (ROOT / "scripts" / "update_template.bat").read_text(encoding="utf-8")
    assert "set /p CONFIRM" in bat
    assert "Cancelado" in bat


def test_robocopy_success_is_not_zero():
    """
    robocopy devuelve 0-7 cuando fue bien y 8+ cuando fallo, al reves
    que todo lo demas. Tratarlo como un comando normal daria el update
    por fallido siempre que copiara algo.
    """
    bat = (ROOT / "scripts" / "update_template.bat").read_text(encoding="utf-8")
    assert "GEQ 8" in bat


# ── QA2 no se multiplica, y se le puede parar ────────────────────────
#
# Camilo llego a once python.exe vivos despues de un dia de pruebas, y
# con ellos abiertos Windows no dejaba ni borrar la carpeta.
#
# Encontrar QA2 fue el problema de verdad. Por puerto fallaba en cuanto
# arrancaba en otro; con wmic no sirve, que Windows 11 ya no lo trae; y
# desde un .vbs se topa con la directiva de IT de WPP que bloquea
# Windows Script Host -- "This script is blocked by IT policy", que es
# donde se quedo su companera.
#
# Ahora la app deja su PID escrito y los .bat lo leen con tasklist y
# taskkill, que son parte de Windows y no los bloquea nadie.

STOP = (ROOT / "Stop QA2.bat").read_text(encoding="utf-8")


def test_nothing_is_launched_or_stopped_with_a_script_host():
    """
    Los .vbs estan bloqueados por directiva en las maquinas del
    equipo. No pueden volver.
    """
    assert not list(ROOT.glob("*.vbs"))


def test_stopping_qa2_does_not_depend_on_the_port():
    """El 8501 es donde arranca, no donde esta."""
    code = [
        line for line in STOP.splitlines()
        if line.strip() and not line.strip().upper().startswith("REM")
    ]
    assert "8501" not in "\n".join(code)


def test_nothing_depends_on_wmic():
    """Microsoft lo quito de Windows 11."""
    for name in ("run_qa2.bat", "Stop QA2.bat"):
        bat = (ROOT / name).read_text(encoding="utf-8")
        code = [
            line for line in bat.splitlines()
            if line.strip() and not line.strip().upper().startswith("REM")
        ]
        assert "wmic" not in "\n".join(code).lower(), name


def test_the_app_writes_down_its_pid():
    app = (ROOT / "ui" / "app_v2.py").read_text(encoding="utf-8")
    assert "write_pid()" in app


def test_stopping_qa2_checks_the_pid_is_still_python():
    """
    Un PID viejo puede estar reutilizado por otra cosa. Matarlo a
    ciegas seria matar lo que Windows le haya dado ese numero.
    """
    assert "IMAGENAME eq python.exe" in STOP
    assert "tasklist" in STOP


def test_the_running_check_does_the_same():
    bat = (ROOT / "run_qa2.bat").read_text(encoding="utf-8")
    assert "IMAGENAME eq python.exe" in bat


def test_a_stale_pid_file_is_cleared():
    assert 'del "logs\\qa2.pid"' in STOP


def test_the_pid_file_stays_next_to_the_app():
    """
    Si siguiera a QA2_OUTPUT_DIR, los .bat no sabrian donde buscarlo
    y dos personas escribirian su PID en el mismo archivo.
    """
    source = (ROOT / "core" / "pidfile.py").read_text(encoding="utf-8")
    assert "parents[1]" in source
    assert "output_dir" not in source


# ── el que aplica la actualizacion ───────────────────────────────────

# ── QA2 no se multiplica, y se le puede parar ────────────────────────
#
# Camilo llego a once python.exe vivos despues de un dia de pruebas, y
# con ellos abiertos Windows no dejaba ni borrar la carpeta.
#
# Encontrar QA2 fue el problema de verdad. Por puerto fallaba en cuanto
# arrancaba en otro; con wmic no sirve, que Windows 11 ya no lo trae; y
# desde un .vbs se topa con la directiva de IT de WPP que bloquea
# Windows Script Host -- "This script is blocked by IT policy", que es
# donde se quedo su companera.
#
# Ahora la app deja su PID escrito y los .bat lo leen con tasklist y
# taskkill, que son parte de Windows y no los bloquea nadie.

STOP = (ROOT / "Stop QA2.bat").read_text(encoding="utf-8")


# ── el que aplica la actualizacion ───────────────────────────────────

def test_the_launcher_refuses_to_start_a_second_one():
    bat = (ROOT / "run_qa2.bat").read_text(encoding="utf-8")
    assert "qa2.pid" in bat
    assert "ya esta abierto" in bat


def test_the_second_launch_opens_the_one_already_running():
    """Que no arranque otro no puede significar que no pase nada."""
    bat = (ROOT / "run_qa2.bat").read_text(encoding="utf-8")
    assert "start \"\" http://localhost:8501" in bat


# ── Streamlit no puede preguntar nada por consola ────────────────────
#
# La primera vez pide un correo y SE QUEDA BLOQUEADO:
#
#     Welcome to Streamlit!
#     ... please enter your email address below.
#     Email: _
#
# En la ventana negra se ve y confunde; en el lanzador silencioso no
# hay ventana donde escribir y QA2 no arranca nunca. Es la causa de
# los diez minutos que espero la companera de Camilo, y habria
# afectado a los treinta la primera vez que abrieran QA2.

CONFIG = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
MAIN_BAT = (ROOT / "run_qa2.bat").read_text(encoding="utf-8")


def test_streamlit_never_asks_for_an_email():
    """
    En la configuracion y no en los lanzadores: asi lo salta tambien
    quien arranque `streamlit run ui/app_v2.py` a mano.
    """
    assert "headless = true" in CONFIG


def test_the_launcher_opens_the_browser_since_streamlit_will_not():
    """headless significa que ya no lo abre solo. Alguien tiene que."""
    assert "http://localhost:8501" in MAIN_BAT


def test_the_launcher_pins_the_port():
    """Si Streamlit se mueve de puerto, la URL que abrimos no sirve."""
    assert "start_qa2.py 8501" in MAIN_BAT
    assert "start_qa2.py\" 8501" in (ROOT / "QA2.bat").read_text(encoding="utf-8")
    starter = (ROOT / "scripts" / "start_qa2.py").read_text(encoding="utf-8")
    assert '"--server.port", str(port)' in starter


def test_the_pid_is_written_by_the_process_that_serves():
    """
    Estaba en app_v2.py, que corre en la primera sesion -- o sea
    cuando alguien abre la pagina. Hasta entonces el servidor estaba
    arriba y "Stop QA2.bat" no encontraba a quien parar.
    """
    starter = (ROOT / "scripts" / "start_qa2.py").read_text(encoding="utf-8")
    # Sin el docstring de arriba, que nombra cli.main() al explicarlo.
    code = starter.split('"""', 2)[-1]
    assert code.index("write_pid(ROOT)") < code.index("cli.main(")


def test_the_starter_does_not_spawn_a_second_process():
    """
    Si lanzara otro, el PID escrito seria el del envoltorio y matarlo
    dejaria Streamlit corriendo.
    """
    starter = (ROOT / "scripts" / "start_qa2.py").read_text(encoding="utf-8")
    assert "subprocess" not in starter
    assert "cli.main(" in starter


def test_the_pid_file_goes_away_when_qa2_stops():
    """Si no, el siguiente arranque cree que QA2 sigue abierto."""
    starter = (ROOT / "scripts" / "start_qa2.py").read_text(encoding="utf-8")
    assert "clear_pid(ROOT)" in starter
    assert "finally:" in starter


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))



"""
Construye el paquete que se le entrega al equipo: QA2 con Python
adentro.

    python scripts/build_bundle.py

Sale una carpeta y un .zip que no necesitan que nadie instale nada.
Quien lo recibe extrae y hace doble clic en run_qa2.bat. Sin Python,
sin pip, sin permisos de administrador, sin llegar a PyPI.

POR QUE

    "yo no voy a poner a descargar python a 30 personas"

Y en una maquina corporativa probablemente ni podrian. Asi que el
Python viaja dentro. No es el instalador de python.org ni el embeddable
zip: es python-build-standalone, la distribucion reubicable que usa uv.
Vive en la carpeta de QA2, no toca el registro, no toca el PATH, y se
borra borrando la carpeta.

COMO SE USA

    python scripts/build_bundle.py                 # para esta maquina
    python scripts/build_bundle.py --no-innovid    # sin Playwright
    python scripts/build_bundle.py --keep-folder   # no borra dist/

EL PAQUETE SE ARMA EN LA MISMA PLATAFORMA A LA QUE VA

Las ruedas de pandas y numpy son binarias y Chromium es un ejecutable:
las dos cosas las tiene que poner el Python del destino. Asi que el
paquete de Windows se construye EN Windows. Es una vez por version, y
el script lo dice en vez de armar algo que no arranca.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.package_release import ROOT, SKIP_FILES, app_files  # noqa: E402

# python-build-standalone. Fijado a proposito: un paquete que se arma
# dos veces tiene que dar lo mismo las dos veces.
PBS_TAG = "20250818"
PBS_PYTHON = "3.11.13"
PBS_BASE = (
    "https://github.com/astral-sh/python-build-standalone/releases/download"
)

TRIPLES = {
    "windows": "x86_64-pc-windows-msvc",
    "linux": "x86_64-unknown-linux-gnu",
    "macos": "aarch64-apple-darwin",
}

# Lo que no hace falta una vez instalado. pip y setuptools solo sirven
# para instalar, y aqui ya no se instala nada.
TRIM = ("pip", "setuptools", "pkg_resources", "wheel", "_distutils_hack")

# setuptools deja un .pth que importa _distutils_hack en cada arranque.
# Quitar el modulo y dejar el .pth hacia que el interprete escupiera
# ModuleNotFoundError antes de ejecutar nada.
TRIM_PTH = ("distutils-precedence.pth",)


def host_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def python_exe(bundle: Path, target: str) -> Path:
    if target == "windows":
        return bundle / "python" / "python.exe"
    return bundle / "python" / "bin" / "python3"


def version() -> str:
    path = ROOT / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "dev"


def fetch_python(bundle: Path, target: str) -> None:
    """Descarga y extrae el interprete dentro del paquete."""
    triple = TRIPLES[target]
    url = (
        f"{PBS_BASE}/{PBS_TAG}/cpython-{PBS_PYTHON}+{PBS_TAG}"
        f"-{triple}-install_only.tar.gz"
    )
    print(f"  Python {PBS_PYTHON} for {target}")
    print(f"    {url}")

    with urllib.request.urlopen(url, timeout=300) as response:
        payload = response.read()
    print(f"    {len(payload) / 1_048_576:.0f} MB downloaded")

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
        # El tar trae todo bajo python/, que es justo donde va.
        tar.extractall(bundle)

    target_exe = python_exe(bundle, target)
    if not target_exe.exists():
        raise SystemExit(f"the interpreter is not where expected: {target_exe}")
    if target != "windows":
        target_exe.chmod(0o755)


def lock_path(target: str) -> Path:
    return ROOT / f"requirements-lock-{target}.txt"


def install_requirements(bundle: Path, target: str, innovid: bool) -> None:
    """
    Instala las librerias, y fija cuales.

    requirements.txt dice `pandas>=2.2.0`, que esta bien para
    desarrollar y mal para un paquete: armarlo dos meses despues trae
    otras versiones y el equipo termina corriendo algo que nunca paso
    las pruebas -- en silencio, porque nadie mira una version menor.

    Asi que la primera vez se instala desde requirements.txt y se
    escribe un lock con lo que quedo; a partir de ahi se instala desde
    el lock. El lock es por plataforma porque las dependencias no son
    las mismas en Windows y en Linux.
    """
    exe = python_exe(bundle, target)
    lock = lock_path(target)

    if lock.exists():
        print(f"  installing the pinned libraries ({lock.name})")
        source = lock
        scratch = None
    else:
        print("  installing the libraries into it")
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        if not innovid:
            requirements = "\n".join(
                line
                for line in requirements.splitlines()
                if not line.strip().lower().startswith("playwright")
            )
        scratch = bundle / "_requirements.txt"
        scratch.write_text(requirements, encoding="utf-8")
        source = scratch

    subprocess.run(
        [str(exe), "-m", "pip", "install", "--no-warn-script-location",
         "--disable-pip-version-check", "-q", "-r", str(source)],
        check=True,
    )
    if scratch is not None:
        scratch.unlink()

    frozen = subprocess.run(
        [str(exe), "-m", "pip", "freeze", "--disable-pip-version-check"],
        check=True, capture_output=True, text=True,
    ).stdout

    if not lock.exists():
        lock.write_text(
            "# Lo que este paquete lleva, exactamente.\n"
            "# Lo escribe scripts/build_bundle.py la primera vez y se\n"
            "# commitea: a partir de ahi, armar el paquete otra vez da\n"
            "# el mismo resultado. Para subir una libreria, borra este\n"
            "# archivo, vuelve a armar, corre las pruebas y commitea el\n"
            "# lock nuevo.\n" + frozen,
            encoding="utf-8",
        )
        print(f"    wrote {lock.name} -- commit it, so a rebuild matches")


def local_browser_cache() -> Path | None:
    """
    Donde esta ya el Chromium de esta maquina, si esta.

    Vale la pena mirar antes de descargar: quien arma el paquete lleva
    tiempo usando QA2 contra Innovid, asi que casi siempre lo tiene. Y
    es lo que salva el build detras de un proxy corporativo que no deje
    salir a cdn.playwright.dev -- que es exactamente lo que pasa en
    muchas redes, y no se descubre hasta diez minutos despues de
    empezar.
    """
    candidates = []
    declared = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if declared:
        candidates.append(Path(declared))
    home = Path.home()
    candidates += [
        home / "AppData" / "Local" / "ms-playwright",   # Windows
        home / ".cache" / "ms-playwright",              # Linux
        home / "Library" / "Caches" / "ms-playwright",  # macOS
    ]
    for path in candidates:
        if path.is_dir() and any(path.glob("chromium*")):
            return path
    return None


def required_browsers(bundle: Path, target: str) -> list[str]:
    """
    Que revisiones exactas pide el Playwright de este paquete.

    `playwright install --dry-run` las imprime con su ruta. Hay que
    preguntarlo en vez de suponerlo: la cache de esta maquina tenia
    chromium-1194 y el Playwright del paquete queria 1243, asi que
    copiar "el chromium que haya" produjo un paquete que arrancaba y
    fallaba al abrir el navegador -- el peor momento para descubrirlo,
    ya en manos de otra persona.

    Y son tres, no una: Playwright usa chrome-headless-shell cuando se
    lanza en headless, que es como corre QA2 casi siempre.
    """
    exe = python_exe(bundle, target)
    environment = dict(
        os.environ, PLAYWRIGHT_BROWSERS_PATH=str(bundle / "browsers")
    )
    result = subprocess.run(
        [str(exe), "-m", "playwright", "install", "--dry-run", "chromium"],
        capture_output=True, text=True, env=environment,
    )
    if result.returncode != 0:
        return []

    names = []
    for line in result.stdout.splitlines():
        if "Install location:" not in line:
            continue
        name = Path(line.split("Install location:", 1)[1].strip()).name
        if name and name not in names:
            names.append(name)
    return names


def install_chromium(bundle: Path, target: str) -> bool:
    """
    El navegador de Playwright, dentro del paquete.

    PLAYWRIGHT_BROWSERS_PATH lo saca de la carpeta del usuario y lo
    mete en la de QA2, que es lo que hace que el paquete sirva en una
    maquina donde nadie ha instalado nada.

    Devuelve si quedo o no. Que falte no tira el build: son diez
    minutos de trabajo y el resto del paquete sirve igual -- se dice al
    final, en vez de perderlo todo.
    """
    browsers = bundle / "browsers"
    needed = required_browsers(bundle, target)

    cached = local_browser_cache()
    if cached is not None and needed:
        available = [n for n in needed if (cached / n).is_dir()]
        if len(available) == len(needed):
            print(f"  copying {', '.join(needed)} from {cached}")
            browsers.mkdir(parents=True, exist_ok=True)
            for name in needed:
                destination = browsers / name
                if destination.exists():
                    continue
                shutil.copytree(cached / name, destination, symlinks=True)
            size = sum(
                f.stat().st_size for f in browsers.rglob("*") if f.is_file()
            )
            print(f"    {size / 1_048_576:.0f} MB")
            return True
        missing = [n for n in needed if n not in available]
        print(f"  the local cache is a different revision ({missing}),")
        print("  so it cannot be reused -- downloading instead")

    exe = python_exe(bundle, target)
    print("  downloading Chromium for the Innovid connection")
    environment = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(browsers))
    result = subprocess.run(
        [str(exe), "-m", "playwright", "install", "chromium"],
        env=environment,
    )
    if result.returncode == 0:
        return True

    print()
    print("  ! Chromium could not be downloaded.")
    print("  ! Usually a proxy blocking cdn.playwright.dev.")
    print("  ! The package is still built and every check that does not")
    print("  ! need Innovid works. To add the browser, run this on a")
    print("  ! machine that can reach it, or run `playwright install")
    print("  ! chromium` there first -- a matching local copy is reused.")
    print()
    return False


def trim(bundle: Path, target: str) -> None:
    """Quita lo que solo servia para construir."""
    if target == "windows":
        site = bundle / "python" / "Lib" / "site-packages"
    else:
        site = bundle / "python" / "lib" / f"python3.11" / "site-packages"
    if not site.exists():
        return

    freed = 0
    for name in TRIM:
        for path in list(site.glob(f"{name}")) + list(site.glob(f"{name}-*")):
            freed += sum(
                f.stat().st_size for f in path.rglob("*") if f.is_file()
            ) if path.is_dir() else path.stat().st_size
            shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink()

    for name in TRIM_PTH:
        orphan = site / name
        if orphan.exists():
            orphan.unlink()

    for cache in list(bundle.rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)

    print(f"  trimmed {freed / 1_048_576:.0f} MB of build-only files")


def copy_app(bundle: Path) -> int:
    """
    El codigo, con las mismas reglas que el zip de solo codigo.

    Deliberadamente reutiliza app_files() de package_release: que es un
    secreto y que no se decide en un sitio, no en dos.
    """
    count = 0
    for source in app_files():
        destination = bundle / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        count += 1
    return count


def guard(bundle: Path) -> None:
    """Lo unico por lo que vale la pena abortar."""
    leaked = [
        str(p.relative_to(bundle))
        for p in bundle.rglob("*")
        if p.is_file() and p.name in SKIP_FILES
    ]
    if leaked:
        raise SystemExit(f"REFUSING: the sign-in is in the bundle: {leaked}")


def archive(bundle: Path, name: str) -> Path:
    out = bundle.parent / f"{name}.zip"
    if out.exists():
        out.unlink()
    print("  compressing (this takes a couple of minutes)")
    files = [p for p in sorted(bundle.rglob("*")) if p.is_file()]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in files:
            zf.write(path, Path(name) / path.relative_to(bundle))
    return out


def build(target: str, innovid: bool, keep: bool) -> Path:
    if target != host_platform():
        raise SystemExit(
            f"This builds a {target} package, but you are on "
            f"{host_platform()}.\n\n"
            "pandas and numpy ship compiled wheels and Chromium is an "
            "executable: both have to be put there by the target's own "
            "Python. Run this script on a "
            f"{target} machine -- once per release."
        )

    name = f"QA2-{version()}-{target}"
    bundle = ROOT / "dist" / name
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    print(f"Building {name}\n")
    fetch_python(bundle, target)
    install_requirements(bundle, target, innovid)
    has_browser = False
    if innovid:
        has_browser = install_chromium(bundle, target)
        if has_browser:
            missing = [
                name for name in required_browsers(bundle, target)
                if not (bundle / "browsers" / name).is_dir()
            ]
            if missing:
                print(f"  ! the browser is incomplete: {missing}")
                has_browser = False
    else:
        print("  skipping Chromium (--no-innovid)")
    count = copy_app(bundle)
    print(f"  copied {count} project files")
    trim(bundle, target)
    guard(bundle)

    out = archive(bundle, name)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()

    if not keep:
        shutil.rmtree(bundle, ignore_errors=True)

    print()
    print(f"  {out}")
    print(f"  {out.stat().st_size / 1_048_576:.0f} MB")
    print(f"  sha256 {digest}")
    print()
    print("  checked: no credentials, no session, no spreadsheets.")
    if innovid and not has_browser:
        print("  WITHOUT Chromium: the Innovid checks will not run.")
    print()
    print("  Upload it to the team's SharePoint library. Whoever gets it")
    print("  extracts the folder and double-clicks run_qa2.bat -- there")
    print("  is nothing to install.")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform", default=host_platform(), choices=sorted(TRIPLES),
        help="which platform the package is for (default: this one)",
    )
    parser.add_argument(
        "--no-innovid", action="store_true",
        help="leave Playwright and Chromium out (~300 MB smaller)",
    )
    parser.add_argument(
        "--keep-folder", action="store_true",
        help="keep dist/ after zipping, to look inside it",
    )
    args = parser.parse_args()
    build(args.platform, not args.no_innovid, args.keep_folder)


if __name__ == "__main__":
    main()

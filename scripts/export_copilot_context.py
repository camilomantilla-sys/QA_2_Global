"""
Arma los archivos de conocimiento para un agente de Copilot sin acceso al repo.

Copilot no ve el repositorio ni la carpeta: solo lo que se le sube. Este
script junta la documentacion y TODO el codigo fuente en unos pocos
archivos .md, agrupados por tema, cada archivo de codigo con su ruta como
titulo. Asi el agente puede citar la ruta exacta y devolver la funcion
completa para copiar y pegar.

Nunca incluye la sesion ni las credenciales de Innovid, ni hojas de
calculo, ni la carpeta de logs: se niega a terminar si alguna se cuela.

    python scripts/export_copilot_context.py
    python scripts/export_copilot_context.py --out "C:/ruta/que/quieras"

Por defecto deja los archivos FUERA del proyecto, en la carpeta
QA2_contexto_copilot junto a la del proyecto, para no mezclarlos con el
codigo ni con los paquetes de dist/. Se vuelve a correr despues de cada
cambio y se reemplazan los del agente.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "QA2_contexto_copilot"

sys.path.insert(0, str(ROOT))
from core.paths import LOCAL_ONLY_FILES  # noqa: E402

#: (archivo de salida, titulo, patrones de rutas que lleva). El orden de
#: los patrones es el orden dentro del archivo. Cada ruta va al primer
#: grupo que la reclama.
GROUPS: list[tuple[str, str, list[str]]] = [
    ("QA2_01_documentacion.md", "Documentacion principal", [
        ".github/copilot-instructions.md", "README.md", "docs/LEEME_PRIMERO.md",
        "docs/REFERENCIA_TECNICA.md", "docs/SEGURIDAD.md",
        "docs/GUIA_TECNICA.md",
    ]),
    ("QA2_02_mapa_del_codigo.md", "Mapa del codigo", [
        "docs/MAPA_DEL_CODIGO.md",
    ]),
    ("QA2_03_motor.md", "Motor: hallazgos, emparejamiento, veredicto, normalizacion", [
        "core/__init__.py", "core/engine.py", "core/findings.py",
        "core/verdict.py", "core/review.py", "core/matching.py",
        "core/intent.py", "core/colors.py", "core/extraction.py",
        "core/schema.py", "core/ts_schema.py", "core/normalize.py",
        "core/dates.py", "core/urls.py", "core/provenance.py",
        "core/paths.py",
    ]),
    ("QA2_04_conciliaciones.md", "Conciliaciones, tags, pixeles y DV", [
        "core/*reconciliation.py", "core/default_ads.py",
        "core/dv_subtype.py", "core/tag_*.py", "core/team_roster.py",
    ]),
    ("QA2_05_innovid_playwright.md", "Conexion a Innovid y Playwright", [
        "core/innovid_api.py", "core/innovid_login.py",
        "check_innovid_connection.py",
    ]),
    ("QA2_06_reportes.md", "Reportes Excel, PDF y hoja QA", [
        "core/qa_export.py", "core/excel_report.py", "core/pdf_report.py",
        "core/report_name.py", "core/ts_snapshot.py",
    ]),
    ("QA2_07_parsers.md", "Lectura de archivos", [
        "parsers/*.py",
    ]),
    ("QA2_08_reglas.md", "Reglas de QA", [
        "rules/*.py",
    ]),
    ("QA2_09_interfaz.md", "Interfaz Streamlit", [
        "ui/*.py",
    ]),
    ("QA2_10_arranque_config_scripts.md", "Arranque, configuracion, scripts y CLI", [
        "*.bat", "run_qa2.command", "VERSION", "requirements*.txt",
        ".streamlit/config.toml", ".gitignore", "config/*.json",
        "core/*.py", "scripts/*.py", "scripts/*.bat", "cli/*.py",
        "__init__.py",
    ]),
    ("QA2_11_pruebas.md", "Pruebas automaticas", [
        "tests/*.py", "tests/fixtures/ts/*.json", "tests/fixtures/ts/README.md",
    ]),
    ("QA2_12_historial_y_operacion.md", "Cambios, reglas originales e instalacion", [
        "docs/CHANGELOG.md", "docs/QA2_RULEBOOK.md", "docs/INSTALACION.md",
        "docs/COMANDOS.md", "docs/copilot/*.md",
    ]),
]

TEXT_SUFFIXES = {".py", ".md", ".json", ".toml", ".bat", ".txt", ".command", ""}
SKIP_DIRS = {".git", ".venv", "venv", "dist", "logs", "data", "browsers",
             "python", "__pycache__", ".pytest_cache", "backups"}
NEVER = set(LOCAL_ONLY_FILES) | {"secrets.toml"}
NEVER_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".csv", ".har", ".env"}

LANG = {".py": "python", ".json": "json", ".toml": "toml", ".bat": "bat",
        ".md": "markdown", ".txt": "text", ".command": "bash"}


def candidates() -> list[str]:
    out = []
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if not path.is_file() or set(rel.parts) & SKIP_DIRS:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.name in NEVER or path.suffix.lower() in NEVER_SUFFIXES:
            continue
        if path.name.startswith("~$"):
            continue
        out.append(rel.as_posix())
    return out


def assign(paths: list[str]) -> dict[str, list[str]]:
    taken: set[str] = set()
    groups: dict[str, list[str]] = {}
    for name, _, patterns in GROUPS:
        chosen = []
        for pattern in patterns:
            for rel in paths:
                if rel in taken:
                    continue
                if fnmatch.fnmatchcase(rel, pattern):
                    chosen.append(rel)
                    taken.add(rel)
        groups[name] = chosen
    return groups


def render(title: str, files: list[str]) -> str:
    parts = [
        f"# QA2 — {title}",
        "",
        "Archivo de conocimiento para el agente de QA2. Cada seccion es un "
        "archivo del proyecto; el titulo es su ruta exacta.",
        "",
        "Contenido: " + ", ".join(f"`{f}`" for f in files),
        "",
    ]
    for rel in files:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".md":
            parts += [f"## ARCHIVO: {rel}", "", "~~~~markdown", text.rstrip(), "~~~~", ""]
        else:
            lang = LANG.get(path.suffix, "text")
            parts += [f"## ARCHIVO: {rel}", "", f"~~~~{lang}", text.rstrip(), "~~~~", ""]
    return "\n".join(parts) + "\n"


def guard(groups: dict[str, list[str]]) -> None:
    leaked = [
        rel for files in groups.values() for rel in files
        if Path(rel).name in NEVER or Path(rel).suffix.lower() in NEVER_SUFFIXES
    ]
    if leaked:
        raise SystemExit(f"REFUSING: sensitive files in the export: {leaked}")


def build() -> dict[str, list[str]]:
    paths = candidates()
    groups = assign(paths)
    guard(groups)
    left = sorted(set(paths) - {f for files in groups.values() for f in files})
    if left:
        groups.setdefault("QA2_10_arranque_config_scripts.md", []).extend(left)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", type=Path, default=OUT,
                        help="carpeta de salida (por defecto, fuera del proyecto)")
    out = parser.parse_args().out.resolve()
    groups = build()
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("QA2_*.md"):
        old.unlink()
    titles = {name: title for name, title, _ in GROUPS}
    total = 0
    for name, files in groups.items():
        if not files:
            continue
        text = render(titles[name], files)
        (out / name).write_text(text, encoding="utf-8")
        size = len(text.encode("utf-8"))
        total += size
        print(f"  {name:40s} {len(files):3d} archivos  {size / 1024:7.0f} KB")
    print(f"\n  {out}  ({total / 1024 / 1024:.1f} MB en total)")
    print("  checked: no credentials, no session, no spreadsheets.")


if __name__ == "__main__":
    main()

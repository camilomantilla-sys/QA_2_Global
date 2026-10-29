"""
Genera docs/MAPA_DEL_CODIGO.md: el indice de todo el codigo de QA2.

Recorre cada modulo de Python y anota lo que dice el propio codigo:
la descripcion del modulo, sus clases y sus funciones con la firma y la
primera linea de su docstring. Tambien lista las pruebas por archivo.

Como sale del codigo y no de la memoria de nadie, nunca se queda atras:
despues de cambiar una funcion, se vuelve a correr y listo.

    python scripts/generate_code_map.py
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "MAPA_DEL_CODIGO.md"

SECTIONS = [
    ("core", "Motor: emparejamiento, conciliaciones, hallazgos, veredicto, reportes"),
    ("parsers", "Lectura de los archivos que sube el analista"),
    ("rules", "Reglas de QA, una familia por archivo"),
    ("ui", "Interfaz (Streamlit)"),
    ("cli", "Herramientas de linea de comandos"),
    ("scripts", "Arranque, empaquetado y diagnosticos"),
    (".", "Archivos en la raiz"),
]


def _first_paragraph(doc: str | None) -> str:
    if not doc:
        return ""
    lines = []
    for line in doc.strip().splitlines():
        if not line.strip():
            break
        lines.append(line.strip())
    return " ".join(lines)


def _first_line(doc: str | None) -> str:
    return _first_paragraph(doc).split(". ")[0].rstrip(".")


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    text = ast.unparse(node.args)
    if len(text) > 90:
        names = [a.arg for a in node.args.posonlyargs + node.args.args]
        if node.args.vararg:
            names.append("*" + node.args.vararg.arg)
        names += [a.arg for a in node.args.kwonlyargs]
        if node.args.kwarg:
            names.append("**" + node.args.kwarg.arg)
        text = ", ".join(names)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{node.name}({text}){returns}"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def describe_module(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    rel = path.relative_to(ROOT).as_posix()
    lines = [f"### `{rel}`", ""]
    summary = _first_paragraph(ast.get_docstring(tree))
    count = len(source.splitlines())
    lines.append(f"{summary} *({count} lineas)*" if summary else f"*({count} lineas)*")
    lines.append("")

    rows = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            rows.append(("clase", f"`{node.name}`", _first_line(ast.get_docstring(node))))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rows.append(("funcion", f"`{_signature(node)}`", _first_line(ast.get_docstring(node))))
    if rows:
        lines += ["| Tipo | Nombre | Que hace |", "| --- | --- | --- |"]
        lines += [f"| {k} | {_cell(n)} | {_cell(d)} |" for k, n, d in rows]
        lines.append("")
    return lines


def describe_tests() -> list[str]:
    lines = [
        "## Pruebas (`tests/`)",
        "",
        "Cada archivo prueba un comportamiento. Se corren todas con "
        "`python -m pytest tests/`, o una sola con "
        "`python -m pytest tests/<archivo>.py`.",
        "",
        "| Archivo | Pruebas | Que protege |",
        "| --- | --- | --- |",
    ]
    total = 0
    paths = sorted((ROOT / "tests").glob("test_*.py"))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        count = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test_")
        )
        total += count
        lines.append(
            f"| `{path.name}` | {count} | {_cell(_first_line(ast.get_docstring(tree)))} |"
        )
    lines += ["", f"Total: {total} funciones de prueba en {len(paths)} archivos "
              "(algunas se parametrizan y corren varias veces).", ""]
    return lines


def build() -> str:
    out = [
        "# QA2 — Mapa del código",
        "",
        "Índice generado automáticamente desde el código por "
        "`scripts/generate_code_map.py`. No se edita a mano: después de "
        "cambiar el código se vuelve a generar con "
        "`python scripts/generate_code_map.py`.",
        "",
        "Para entender **cómo** encaja todo, empieza por "
        "[`REFERENCIA_TECNICA.md`](REFERENCIA_TECNICA.md). Este mapa "
        "responde **dónde** está cada cosa.",
        "",
    ]
    for folder, title in SECTIONS:
        base = ROOT if folder == "." else ROOT / folder
        files = sorted(base.glob("*.py"))
        files = [f for f in files if f.name != "__init__.py" or folder != "."]
        if not files:
            continue
        name = "raíz" if folder == "." else f"`{folder}/`"
        out += [f"## {name} — {title}", ""]
        for path in files:
            if path.name == "__init__.py" and not path.read_text(encoding="utf-8").strip():
                continue
            out += describe_module(path)
    out += describe_tests()
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"escrito {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

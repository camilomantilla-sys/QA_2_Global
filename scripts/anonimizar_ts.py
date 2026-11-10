"""
Saca una copia ANONIMA de una Traffic Sheet (o de cualquier Excel de QA2)
para poder compartir un caso de feedback sin compartir datos de cliente.

    python scripts/anonimizar_ts.py "C:/ruta/a/la/TS.xlsx"

Deja al lado ``<nombre>_ANONIMA.xlsx`` y ``<nombre>_ANONIMA_revisar.txt``.

Qué conserva, porque es lo que QA2 usa para entender la hoja:
  - colores de relleno y de letra, celdas combinadas, filas y columnas
    ocultas, hojas ocultas, anchos y formatos;
  - encabezados y palabras de trabajo (Placement, Video, 1x1, Default,
    Even, N/A...): toda palabra que el propio código de QA2 busca;
  - fechas, dimensiones, duraciones, pesos y números cortos;
  - la relación entre hojas: el mismo nombre o ID original se cambia
    siempre por el mismo valor inventado, así un creativo sigue
    apuntando a su grupo y a su landing page.

Qué cambia o quita:
  - cualquier otra palabra (marcas, campañas, sitios, personas) por una
    inventada (W1, W2...);
  - los números largos (IDs de placement, creativo, campaña) por otros
    inventados del mismo largo;
  - comentarios de celda, vínculos y propiedades del archivo (autor,
    empresa, título).

Al terminar lee la original y la copia con el parser de QA2 y compara
las dos lecturas. Si QA2 entiende lo mismo de las dos, la copia sirve
para reproducir el caso. El archivo _revisar.txt lista cada palabra que
se conservó, para que la revises antes de compartir la copia.

Todo pasa en tu PC. El script no se conecta a nada.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tempfile
import warnings
from datetime import date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openpyxl import load_workbook  # noqa: E402

#: Carpetas cuyo código define lo que QA2 busca en una hoja.
VOCAB_SOURCES = ("core", "parsers", "rules")
#: Palabras de trabajo que conviene conservar aunque el código no las nombre.
EXTRA_VOCAB = {
    "na", "n", "a", "tbd", "yes", "no", "true", "false", "even", "default",
    "video", "display", "static", "html5", "rich", "media", "ctv", "ott",
    "mobile", "desktop", "tablet", "web", "app", "in", "stream", "instream",
    "outstream", "banner", "companion", "preroll", "pre", "roll", "midroll",
    "tracking", "pixel", "pixels", "tag", "tags", "clicktag", "click",
    "through", "impression", "survey", "monitoring", "omni", "dv",
    "doubleverify", "ias", "moat", "vpaid", "vast", "swap", "new", "remove",
    "removed", "add", "added", "paused", "active", "ongoing", "rotation",
    "creative", "creatives", "placement", "placements", "site", "sites",
    "landing", "page", "pages", "url", "lp", "id", "name", "start", "end",
    "date", "dates", "http", "https", "www", "com", "net", "org", "html",
    "utm", "source", "medium", "campaign", "content", "term", "and", "or",
    "the", "of", "for", "to", "on", "by", "with", "x", "s", "sec", "px",
    "kb", "mb", "gb", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
    "sep", "oct", "nov", "dec", "q1", "q2", "q3", "q4", "fy", "h1", "h2",
}

WORD = re.compile(r"[A-Za-z0-9]+")
#: Formas que no identifican a nadie: 300x250, 15s, 30sec, 100%, 2026.
SAFE_SHAPE = re.compile(
    r"^(\d{1,4}|\d+x\d+|\d+(s|sec|secs|px|kb|mb|pct|k)|[a-z]?\d{1,2})$",
    re.IGNORECASE,
)


def build_vocab() -> set[str]:
    """Cada palabra que aparece en un texto del código de QA2 (sin docstrings)."""
    vocab = set(EXTRA_VOCAB)
    for folder in VOCAB_SOURCES:
        for py in (ROOT / folder).rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.FunctionDef,
                                     ast.AsyncFunctionDef, ast.ClassDef)):
                    body = getattr(node, "body", [])
                    if body and isinstance(body[0], ast.Expr) and \
                            isinstance(getattr(body[0], "value", None), ast.Constant):
                        docstrings.add(id(body[0].value))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and id(node) not in docstrings:
                    for word in WORD.findall(node.value):
                        if not word.isdigit():
                            vocab.add(word.lower())
    return vocab


class Anonymizer:
    """Cambia cada palabra o número sensible, siempre por el mismo valor."""

    def __init__(self, vocab: set[str]):
        self.vocab = vocab
        self.words: dict[str, str] = {}
        self.numbers: dict[str, str] = {}
        self.kept: set[str] = set()

    def _number(self, digits: str) -> str:
        if digits not in self.numbers:
            n = len(self.numbers) + 1
            self.numbers[digits] = "9" + str(n).zfill(len(digits) - 1)
        return self.numbers[digits]

    def _word(self, word: str) -> str:
        if word.isdigit():
            return word if len(word) <= 4 else self._number(word)
        low = word.lower()
        if low in self.vocab or SAFE_SHAPE.match(word):
            if not SAFE_SHAPE.match(word) and len(word) > 2:
                self.kept.add(low)
            return word
        key = low
        if key not in self.words:
            self.words[key] = f"W{len(self.words) + 1}"
        fake = self.words[key]
        return fake.upper() if word.isupper() and len(word) > 1 else fake

    def text(self, value: str) -> str:
        return WORD.sub(lambda m: self._word(m.group(0)), value)

    def value(self, value):
        if value is None or isinstance(value, (bool, date, datetime, time)):
            return value
        if isinstance(value, int):
            return value if abs(value) < 10000 else int(self._number(str(abs(value))))
        if isinstance(value, float):
            if value.is_integer() and abs(value) >= 10000:
                return float(self._number(str(int(abs(value)))))
            return value
        if isinstance(value, str):
            return self.text(value)
        return value


def anonymize(source: Path, target: Path, vocab: set[str] | None = None) -> Anonymizer:
    anon = Anonymizer(vocab if vocab is not None else build_vocab())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        book = load_workbook(source, data_only=True,
                             keep_vba=source.suffix.lower() == ".xlsm")
    for ws in book.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.__class__.__name__ == "MergedCell":
                    continue
                cell.value = anon.value(cell.value)
                cell.comment = None
                if cell.hyperlink is not None:
                    cell.hyperlink = None
        ws.title = anon.text(ws.title)[:31]
        ws.oddHeader.center.text = None
        ws.oddFooter.center.text = None
    props = book.properties
    for attr in ("creator", "lastModifiedBy", "title", "subject", "description",
                 "keywords", "category", "identifier", "contentStatus"):
        setattr(props, attr, None)
    props.creator = "QA2"
    book.save(target)
    return anon


def compare(source: Path, target: Path) -> list[str]:
    """Qué entiende QA2 distinto entre la original y la copia. Vacío = igual."""
    from core.ts_snapshot import differences, summarise_ts
    from parsers.ts_parser import parse_ts

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = summarise_ts(parse_ts(source))
        b = summarise_ts(parse_ts(target))
    # Los nombres de hoja y de columnas no mapeadas pueden cambiar a
    # proposito (llevan nombres de cliente); lo que importa es todo lo demas.
    a = json.loads(json.dumps(a))
    b = json.loads(json.dumps(b))
    for snap in (a, b):
        snap.pop("profile_evidence", None)
        for key in ("placements", "rotations", "landing_pages"):
            if snap.get(key):
                snap[key].pop("unmapped_columns", None)
                snap[key].pop("sheet", None)
        snap["sheets"] = {k: len(v) for k, v in snap["sheets"].items()}
    return differences(a, b)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("archivo", type=Path, help="La Traffic Sheet (.xlsx o .xlsm)")
    parser.add_argument("--sin-comparar", action="store_true",
                        help="No leer las dos con el parser (para Excel que no son TS)")
    args = parser.parse_args(argv)

    source: Path = args.archivo
    if not source.is_file():
        print(f"No encuentro el archivo: {source}")
        return 1
    if source.suffix.lower() not in (".xlsx", ".xlsm"):
        print("Abre el archivo en Excel y guárdalo como .xlsx; luego corre esto otra vez.")
        return 1

    target = source.with_name(f"{source.stem}_ANONIMA{source.suffix}")
    review = source.with_name(f"{source.stem}_ANONIMA_revisar.txt")
    anon = anonymize(source, target)

    lines = [
        f"Copia anónima: {target.name}",
        f"Palabras cambiadas: {len(anon.words)} · números cambiados: {len(anon.numbers)}",
        "",
        "Palabras que se CONSERVARON (QA2 las busca). Revisa que ninguna sea",
        "un nombre de cliente, marca o persona antes de compartir la copia:",
        "",
    ]
    lines += sorted(anon.kept)
    review.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Listo: {target}")
    print(f"Revisa antes de compartir: {review}")

    if not args.sin_comparar:
        try:
            diffs = compare(source, target)
        except Exception as exc:  # noqa: BLE001 - se informa, no se oculta
            print(f"No pude comparar las dos lecturas ({type(exc).__name__}).")
            return 0
        if diffs:
            print("Ojo: QA2 no entiende exactamente lo mismo en la copia:")
            for line in diffs[:20]:
                print("  -", line)
            print("Comparte igual la copia y dime estas diferencias.")
        else:
            print("QA2 lee la copia igual que la original: sirve para reproducir el caso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

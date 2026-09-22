#!/usr/bin/env python3
"""Genera Seed.gs (contenido inicial para Apps Script) y dist/preview.html.

El contenido vive una sola vez en data/seed.json:
  · Seed.gs        -> lo usa instalarPortafolio() para llenar la hoja.
  · preview.html   -> un HTML suelto para ver el portafolio sin publicar nada.
"""
import json
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent
APPS = RAIZ / "apps-script"
DIST = RAIZ / "dist"


def main() -> None:
    seed = json.loads((RAIZ / "data" / "seed.json").read_text(encoding="utf-8"))
    DIST.mkdir(exist_ok=True)

    # --- Seed.gs -------------------------------------------------------------
    cabecera = (
        "/**\n"
        " * Contenido inicial del portafolio.\n"
        " * Generado por scripts/build.py a partir de data/seed.json — no editar a mano:\n"
        " * una vez instalado, el contenido real vive en la hoja de cálculo.\n"
        " */\n"
        "var SEED = "
    )
    (APPS / "Seed.gs").write_text(
        cabecera + json.dumps(seed, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    # --- preview.html --------------------------------------------------------
    index = (APPS / "Index.html").read_text(encoding="utf-8")

    def incluir(match: "re.Match[str]") -> str:
        return (APPS / f"{match.group(1)}.html").read_text(encoding="utf-8")

    html = re.sub(r"<\?!=\s*include\('([\w]+)'\)\s*\?>", incluir, index)
    html = html.replace(
        "<?!= datosIniciales ?>", json.dumps(seed, ensure_ascii=False)
    )
    html = html.replace("<base target=\"_top\">", "")
    (DIST / "preview.html").write_text(html, encoding="utf-8")

    print(f"Seed.gs         -> {len((APPS / 'Seed.gs').read_text(encoding='utf-8')):>7,} chars")
    print(f"dist/preview.html -> {len(html):>7,} chars")


if __name__ == "__main__":
    main()

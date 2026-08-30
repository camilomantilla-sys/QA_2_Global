"""
CLI: Calibrador de colores.

Inventaria TODOS los fills solidos de una Traffic Sheet, resuelve theme
colors y propone una clasificacion para que la confirmes.

Uso:
    python -m cli.colors --ts "data/ts/TS Adobe Variante 1.xlsx"
    python -m cli.colors --ts "..." --token "THEME:0:0.0"     # investigar un fill
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.colors import (
    GREEN, GREY, RED, UNKNOWN, WHITE, YELLOW, inventory, read_workbook_theme,
)
from core.extraction import list_sheets, read_sheet

app = typer.Typer(add_completion=False)
console = Console()

FAMILY_STYLE = {
    GREEN: "green", RED: "red", YELLOW: "yellow",
    GREY: "bright_black", WHITE: "white", UNKNOWN: "magenta",
}
FAMILY_MEANING = {
    GREEN: "NEW / nuevo del swap -> debe existir y estar activo",
    RED: "REMOVE / viejo del swap -> debe estar desasignado",
    YELLOW: "HOLD -> FUERA DE ALCANCE, cero findings",
    GREY: "no trabajado -> FUERA DE ALCANCE, cero findings",
    WHITE: "contexto existente",
    UNKNOWN: "sin clasificar -> REVIEW, nunca se adivina",
}

@app.command()
def main(
    ts: Path = typer.Option(..., "--ts", "-t", exists=True, help="Ruta a la Traffic Sheet"),
    sheets: str = typer.Option(None, "--sheets", "-s",
                               help="Hojas separadas por coma (default: todas)"),
    token: str = typer.Option(None, "--token",
                              help="Investigar un fill: lista celdas que lo usan"),
    limit: int = typer.Option(30, "--limit", help="Celdas a listar con --token"),
) -> None:
    console.print()
    console.rule("[bold cyan]CALIBRADOR DE COLORES[/]")

    all_sheets = list_sheets(ts)
    targets = [s.strip() for s in sheets.split(",")] if sheets else all_sheets

    theme_map = read_workbook_theme(ts)

    head = Table(show_header=False, box=None, padding=(0, 2))
    head.add_row("[dim]Archivo[/]", ts.name)
    head.add_row("[dim]Hojas del libro[/]", ", ".join(all_sheets))
    head.add_row("[dim]Hojas analizadas[/]", ", ".join(targets))
    head.add_row("[dim]Theme del workbook[/]",
                 f"{len(theme_map)} colores resueltos" if theme_map
                 else "[yellow]no se pudo leer[/]")
    console.print(Panel(head, title="Documento", border_style="cyan"))

    if theme_map:
        th = Table("idx", "RGB", "idx", "RGB", "idx", "RGB", box=None)
        items = sorted(theme_map.items())
        for i in range(0, len(items), 3):
            row = []
            for k, v in items[i:i + 3]:
                row += [str(k), v]
            while len(row) < 6:
                row.append("")
            th.add_row(*row)
        console.print(Panel(th, title="clrScheme del workbook", border_style="dim"))

    grids = []
    for name in targets:
        if name not in all_sheets:
            console.print(f"[yellow]  Hoja '{name}' no existe, se omite[/]")
            continue
        grid, anomalies = read_sheet(ts, name, capture_fill=True)
        for a in anomalies:
            if a.severity == "FATAL":
                console.print(f"[red]  {a.code}: {a.message}[/]")
        grids.append(grid)

    if not grids:
        console.print("[red]No se pudo leer ninguna hoja.[/]")
        raise typer.Exit(code=1)

    # ---- modo investigacion de un token concreto
    if token:
        it = Table("Celda", "Contenido", box=None)
        found = 0
        for grid in grids:
            for row_num, cells in sorted(grid.rows.items()):
                for col, cell in sorted(cells.items()):
                    if cell.fill_rgb != token:
                        continue
                    found += 1
                    if found <= limit:
                        it.add_row(f"{grid.sheet}!{cell.ref.col_letter}{row_num}",
                                   (cell.text[:70] or "(vacia)"))
        console.print(Panel(it, title=f"Celdas con fill '{token}': {found} "
                                      f"(mostrando {min(found, limit)})",
                            border_style="magenta"))
        raise typer.Exit(code=0)

    inv = inventory(grids, theme_map)

    if not inv:
        console.print(Panel("[yellow]No se encontro ningun relleno solido.[/]",
                            title="[yellow]Sin colores[/]", border_style="yellow"))
        raise typer.Exit(code=0)

    # ---- inventario ordenado por frecuencia
    t = Table("Token openpyxl", "RGB", "Familia", "Conf", "Celdas", "Hojas", box=None)
    for info in sorted(inv.values(), key=lambda x: -x.count):
        style = FAMILY_STYLE.get(info.family, "")
        t.add_row(
            info.token,
            info.rgb or "[red]sin resolver[/]",
            f"[{style}]{info.family}[/]",
            info.confidence,
            str(info.count),
            ", ".join(sorted(info.sheets))[:40],
        )
    console.print(Panel(t, title=f"Fills distintos encontrados: {len(inv)}",
                        border_style="magenta"))

    # ---- resumen por familia
    fam_counts: dict[str, int] = {}
    fam_cells: dict[str, int] = {}
    for info in inv.values():
        fam_counts[info.family] = fam_counts.get(info.family, 0) + 1
        fam_cells[info.family] = fam_cells.get(info.family, 0) + info.count

    ft = Table("Familia", "Fills", "Celdas", "Significado en QA2", box=None)
    for fam in (GREEN, RED, YELLOW, GREY, WHITE, UNKNOWN):
        if fam not in fam_counts:
            continue
        style = FAMILY_STYLE[fam]
        ft.add_row(f"[{style}]{fam}[/]", str(fam_counts[fam]),
                   str(fam_cells[fam]), FAMILY_MEANING[fam])
    console.print(Panel(ft, title="Resumen por familia", border_style="blue"))

    # ---- muestras
    st = Table("Token", "RGB", "Familia", "Ejemplos (hoja!celda: contenido)", box=None)
    for info in sorted(inv.values(), key=lambda x: -x.count)[:14]:
        style = FAMILY_STYLE.get(info.family, "")
        st.add_row(info.token, info.rgb or "-", f"[{style}]{info.family}[/]",
                   "\n".join(info.samples))
    console.print(Panel(st, title="Muestras para verificar contra Excel",
                        border_style="dim"))

    # ---- advertencias
    unresolved = [i for i in inv.values() if i.rgb is None]
    unknown = [i for i in inv.values() if i.family == UNKNOWN]
    low = [i for i in inv.values() if i.confidence == "LOW"]
    medium = [i for i in inv.values() if i.confidence == "MEDIUM"]

    msgs = []
    if unresolved:
        cells = sum(i.count for i in unresolved)
        msgs.append(f"[red]{len(unresolved)} fills sin RGB resoluble ({cells} celdas)[/]: "
                    f"{', '.join(i.token for i in unresolved[:5])}")
    if unknown:
        cells = sum(i.count for i in unknown)
        msgs.append(f"[magenta]{len(unknown)} fills sin clasificar ({cells} celdas)[/] "
                    f"-> REVIEW")
    if low:
        msgs.append(f"[yellow]{len(low)} fills confianza LOW[/] "
                    f"(naranja, ambiguo entre rojo y amarillo)")
    if medium:
        msgs.append(f"[cyan]{len(medium)} fills confianza MEDIUM[/] "
                    f"(tono palido, familia deducida por hue)")
    if msgs:
        console.print(Panel("\n".join(msgs), title="[yellow]Requiere tu confirmacion[/]",
                            border_style="yellow"))

    console.print("\n  [bold]Confirmame la tabla de familias.[/] "
                  "Usa --token 'XXX' para inspeccionar un fill concreto.\n")

if __name__ == "__main__":
    app()
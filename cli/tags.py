"""
CLI: Preview y QA estructural de archivos de Tags.

Uso:
    python -m cli.tags --tags "data/tags/archivo.xlsx"
"""
from __future__ import annotations

import warnings
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from parsers.innovid_tags import parse_innovid_tags


warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl",
)


app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def main(
    tags: Path = typer.Option(
        ...,
        "--tags",
        "-t",
        exists=True,
        help="Archivo de tags exportado desde Innovid",
    ),
    show: int = typer.Option(
        15,
        "--rows",
        "-r",
        help="Cantidad de placements a mostrar",
    ),
) -> None:
    console.print()
    console.rule("[bold cyan]QA2 TAGS · EXTRACTION PREVIEW[/]")

    result = parse_innovid_tags(tags)

    document = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )

    document.add_row("[dim]Archivo[/]", tags.name)
    document.add_row("[dim]Hoja[/]", result.sheet or "-")
    document.add_row(
        "[dim]Header[/]",
        str(result.header_row or "-"),
    )
    document.add_row(
        "[dim]Campaign[/]",
        result.metadata.get("campaign", "-"),
    )
    document.add_row(
        "[dim]Campaign ID[/]",
        result.campaign_id or "-",
    )
    document.add_row(
        "[dim]Placements[/]",
        str(result.distinct_placements),
    )
    document.add_row(
        "[dim]Tags materializados[/]",
        str(result.total_tags),
    )

    console.print(
        Panel(
            document,
            title="Documento",
            border_style="cyan",
        )
    )

    if result.anomalies:
        anomaly_table = Table(
            "Severidad",
            "Código",
            "Mensaje",
            box=None,
        )

        for anomaly in result.anomalies:
            style = (
                "red"
                if anomaly.severity == "FATAL"
                else "yellow"
            )

            anomaly_table.add_row(
                f"[{style}]{anomaly.severity}[/]",
                anomaly.code,
                anomaly.message,
            )

        console.print(
            Panel(
                anomaly_table,
                title="Anomalías",
                border_style="red",
            )
        )

    if result.fatal:
        raise typer.Exit(code=1)

    tag_type_counts = Counter(
        tag.tag_type
        for row in result.rows
        for tag in row.tags
    )

    type_table = Table(
        "Tipo de tag",
        "Cantidad",
        box=None,
    )

    for tag_type, total in sorted(
        tag_type_counts.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        type_table.add_row(tag_type, str(total))

    console.print(
        Panel(
            type_table,
            title="Tipos detectados",
            border_style="blue",
        )
    )

    rows_table = Table(
        "Placement ID",
        "Dim",
        "Third Party ID",
        "Placement Name",
        "Tags",
        "Tipos",
        box=None,
    )

    for row in result.rows[:show]:
        types = sorted(
            {tag.tag_type for tag in row.tags}
        )

        rows_table.add_row(
            row.placement_id,
            row.dimensions or "-",
            row.third_party_id or "-",
            row.placement_name[:55],
            str(row.tag_count),
            ", ".join(types) or "-",
        )

    console.print(
        Panel(
            rows_table,
            title=(
                f"Placements · muestra "
                f"{min(show, len(result.rows))} "
                f"de {len(result.rows)}"
            ),
            border_style="green",
        )
    )

    mismatch_table = Table(
        "Placement",
        "Tag",
        "Campaign embebida",
        "Placement embebido",
        "Dim embebida",
        "Nota",
        box=None,
    )

    mismatch_count = 0

    for row in result.rows:
        for tag in row.tags:
            notes = []

            if (
                tag.campaign_ids
                and result.campaign_id
                and result.campaign_id not in tag.campaign_ids
            ):
                notes.append("Campaign ID distinto")

            if (
                tag.placement_ids
                and row.placement_id not in tag.placement_ids
            ):
                notes.append("Placement ID distinto")

            if (
                tag.widths
                and row.width
                and row.width not in tag.widths
            ):
                notes.append("Width distinto")

            if (
                tag.heights
                and row.height
                and row.height not in tag.heights
            ):
                notes.append("Height distinto")

            if not notes:
                continue

            mismatch_count += 1

            if mismatch_count <= show:
                embedded_dims = "/".join(
                    f"{width}x{height}"
                    for width in tag.widths
                    for height in tag.heights
                )

                mismatch_table.add_row(
                    row.placement_id,
                    tag.column_name,
                    ", ".join(tag.campaign_ids) or "-",
                    ", ".join(tag.placement_ids) or "-",
                    embedded_dims or "-",
                    ", ".join(notes),
                )

    if mismatch_count:
        console.print(
            Panel(
                mismatch_table,
                title=(
                    f"[red]Inconsistencias internas "
                    f"en tags: {mismatch_count}[/]"
                ),
                border_style="red",
            )
        )
    else:
        console.print(
            Panel(
                "[green]No se detectaron inconsistencias "
                "internas entre las filas y el contenido "
                "de los tags.[/]",
                title="QA estructural",
                border_style="green",
            )
        )

    console.print()


if __name__ == "__main__":
    app()
    
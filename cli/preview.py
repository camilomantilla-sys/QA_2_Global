"""
CLI: Extraction Preview.

Este comando es el artefacto mas importante del proyecto.
No valida negocio. Demuestra que la lectura del archivo es correcta.

Uso:
    python -m cli.preview --export "data/exports/Export 3p con Dtree.xlsx"
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from parsers.innovid_export import parse_innovid_export

app = typer.Typer(add_completion=False)
console = Console()

@app.command()
def main(
    export: Path = typer.Option(..., "--export", "-e", exists=True,
                                help="Ruta al export de Innovid"),
    sheet: str = typer.Option(None, "--sheet", "-s",
                              help="Hoja a leer (default: Import)"),
    show_rows: int = typer.Option(5, "--rows", "-r",
                                  help="Filas de muestra a imprimir"),
) -> None:
    console.print()
    console.rule("[bold cyan]EXTRACTION PREVIEW[/]")

    res = parse_innovid_export(export, sheet_name=sheet)

    # -------------------------------------------------- documento
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("[dim]Archivo[/]", export.name)
    t.add_row("[dim]Hojas[/]", ", ".join(res.total_sheets) or "-")
    t.add_row("[dim]Hoja leida[/]", res.sheet or "-")
    t.add_row("[dim]Nivel[/]", f"[bold]{res.level or '?'}[/]")
    t.add_row("[dim]Header[/]",
              f"fila {res.header_row} ({res.header_evidence})"
              if res.header_row else "[red]NO ENCONTRADO[/]")
    if res.group_visible:
        vis = ", ".join(f"{k}={'si' if v else 'no'}"
                        for k, v in sorted(res.group_visible.items()))
    else:
        vis = "n/a"
    t.add_row("[dim]Arbol visible por tipo[/]", vis)
    t.add_row("[dim]Celdas heredadas[/]", str(res.merged_applied))
    console.print(Panel(t, title="Documento", border_style="cyan"))

    # -------------------------------------------------- anomalias fatales
    fatals = [a for a in res.anomalies if a.severity == "FATAL"]
    if fatals:
        ft = Table("Codigo", "Mensaje", box=None)
        for a in fatals:
            ft.add_row(f"[red]{a.code}[/]", a.message)
        console.print(Panel(ft, title="[red]ANOMALIAS FATALES - EXTRACCION ABORTADA[/]",
                            border_style="red"))
        console.print("\n[bold red]No se puede continuar al QA2 hasta resolver esto.[/]\n")
        raise typer.Exit(code=1)

    # -------------------------------------------------- metadata
    if res.metadata:
        mt = Table(show_header=False, box=None, padding=(0, 2))
        for k, v in res.metadata.items():
            mt.add_row(f"[dim]{k}[/]", str(v))
        console.print(Panel(mt, title="Metadata (filas 1-9)", border_style="blue"))

    # -------------------------------------------------- columnas
    cmap = res.cmap
    ct = Table(show_header=False, box=None, padding=(0, 2))
    ct.add_row("[dim]Mapeadas (simples)[/]", str(len(cmap.single)))
    ct.add_row("[dim]Mapeadas (familias)[/]",
               ", ".join(f"{k}[{len(v)}]" for k, v in cmap.multi.items()) or "-")
    ct.add_row("[dim]Sin mapear (ignoradas)[/]", str(len(cmap.unmapped)))
    if cmap.missing_optional:
        ct.add_row("[yellow]Opcionales ausentes[/]", ", ".join(cmap.missing_optional))
    console.print(Panel(ct, title="Mapeo de columnas", border_style="blue"))

    if cmap.unmapped:
        console.print("[dim]  Ignoradas: " +
                      ", ".join(h for _, h in cmap.unmapped[:18]) +
                      (" ..." if len(cmap.unmapped) > 18 else "") + "[/]")

    # -------------------------------------------------- segmentacion
    rt = Table("Clase", "Filas", box=None)
    for k in ("DATA", "BANNER", "TEMPLATE", "SEPARATOR", "CORRUPT"):
        n = res.row_class_counts.get(k, 0)
        if k == "CORRUPT" and n:
            style = "red"
        elif k in ("BANNER", "TEMPLATE") and n:
            style = "yellow"
        elif k == "SEPARATOR" and n:
            style = "cyan"
        elif n == 0:
            style = "dim"
        else:
            style = ""
        rt.add_row(f"[{style}]{k}[/]" if style else k,
                   f"[{style}]{n}[/]" if style else str(n))
    console.print(Panel(rt, title="Segmentacion de filas", border_style="blue"))

    # -------------------------------------------------- separadores
    if res.separator_reasons:
        sr = Table("Motivo", "Filas descartadas", box=None)
        for k, v in sorted(res.separator_reasons.items(), key=lambda x: -x[1]):
            sr.add_row(k, str(v))
        console.print(Panel(sr,
            title="[cyan]Filas SEPARADOR descartadas (transiciones del export)[/]",
            border_style="cyan"))

    # -------------------------------------------------- tipologia
    tt = Table("Tipo de fila", "Cantidad", box=None)
    for k, v in sorted(res.row_type_counts.items(), key=lambda x: -x[1]):
        tt.add_row(k, str(v))
    tt.add_row("[bold]Placements distintos[/]", f"[bold]{res.distinct_placements}[/]")
    console.print(Panel(tt, title="Tipologia (Actual Model)", border_style="blue"))

    # -------------------------------------------------- placements sin cabecera
    if res.placements_without_header:
        wt = Table("Placement_Type", "Placements sin fila de cabecera", box=None)
        for k, v in sorted(res.placements_without_header.items(), key=lambda x: -x[1]):
            wt.add_row(k, str(v))
        console.print(Panel(wt,
            title="[cyan]Placements sin PLACEMENT_HEADER (normal en Pixel/1x1)[/]",
            border_style="cyan"))

    # -------------------------------------------------- desglose UNASSIGNED
    if res.unassigned_reasons:
        ut = Table("Motivo", "Filas", box=None)
        for k, v in sorted(res.unassigned_reasons.items(), key=lambda x: -x[1]):
            ut.add_row(k, str(v))
        console.print(Panel(ut,
            title="Desglose UNASSIGNED_CREATIVE (senal de desasignacion)",
            border_style="yellow"))

    # -------------------------------------------------- desglose DIRECT
    if res.direct_reasons:
        dr = Table("Motivo", "Filas", box=None)
        for k, v in sorted(res.direct_reasons.items(), key=lambda x: -x[1]):
            dr.add_row(k, str(v))
        console.print(Panel(dr,
            title="Desglose DIRECT_CREATIVE (asignacion directa, sin dset)",
            border_style="green"))

    # -------------------------------------------------- fechas
    if res.date_diagnostics:
        dt = Table("Campo", "Orden", "Nativas", "Texto", "Sin parsear", "Evidencia", box=None)
        for k, d in res.date_diagnostics.items():
            style = "red" if d["order"] == "AMBIGUOUS" else "green"
            dt.add_row(k, f"[{style}]{d['order']}[/]", str(d["native"]),
                       str(d["text"]), str(d["unparsed"]), d["evidence"] or "-")
        console.print(Panel(dt, title="Resolucion de fechas", border_style="blue"))

    # -------------------------------------------------- capability profile
    cp = Table("Dominio", "Estado", "Reglas", "Detalle", box=None)
    for cap, rules in res.capabilities_on.items():
        cp.add_row(cap, "[green]ON[/]", rules, "")
    for cap, info in res.capabilities_off.items():
        cp.add_row(cap, "[red]OFF[/]", info["rules"],
                   f"{info.get('reason','')}. {info['hint']}".strip())
    console.print(Panel(cp, title="Capability Profile", border_style="magenta"))

    # -------------------------------------------------- fill rate global
    if res.fill_rates:
        key_fields = ["placement_id", "creative_id", "filename", "creative_name",
                      "dimensions", "group_name", "group_id", "third_party_id",
                      "status", "enabled", "rotation", "clicktag",
                      "third_party_impression", "third_party_survey"]
        fr = Table("Campo", "Poblado", box=None)
        for k in key_fields:
            if k not in res.fill_rates:
                continue
            pct = res.fill_rates[k] * 100
            style = "red" if pct == 0 else ("yellow" if pct < 50 else "green")
            fr.add_row(k, f"[{style}]{pct:5.1f}%[/]")
        console.print(Panel(fr, title="Fill rate de campos clave", border_style="blue"))

    # -------------------------------------------------- fill rate por tipo
    if len(res.fill_rates_by_type) > 1:
        seg_fields = ["creative_id", "filename", "group_name",
                      "third_party_id", "clicktag", "rotation"]
        sg = Table("Placement_Type", *seg_fields, box=None)
        for ptype, rates in sorted(res.fill_rates_by_type.items()):
            cells = []
            for f in seg_fields:
                if f not in rates:
                    cells.append("-")
                    continue
                pct = rates[f] * 100
                st = "red" if pct == 0 else ("yellow" if pct < 50 else "green")
                cells.append(f"[{st}]{pct:5.1f}%[/]")
            sg.add_row(ptype, *cells)
        console.print(Panel(sg, title="Fill rate por Placement_Type", border_style="blue"))

    # -------------------------------------------------- creativos sin attribution
    if res.level == "placement_creative" and res.cmap.has("third_party_id"):
        sin_atr = [r for r in res.rows
                   if r.row_type != "PLACEMENT_HEADER"
                   and not r.values.get("third_party_id")]
        if sin_atr:
            at = Table("placement_id", "creative_id", "tipo", "p_type",
                       "creative_type", "filename", "enabled", "clicktag", box=None)
            for r in sin_atr[:12]:
                at.add_row(
                    str(r.values.get("placement_id") or "-"),
                    str(r.values.get("creative_id") or "-"),
                    r.row_type,
                    str(r.values.get("placement_type") or "-"),
                    str(r.values.get("creative_type") or "-"),
                    str(r.values.get("filename") or "[red]-[/]")[:28],
                    str(r.values.get("enabled")),
                    "si" if r.multi.get("clicktag") else "[red]no[/]",
                )
            console.print(Panel(at,
                title=f"[yellow]Creativos sin Third_Party_ID: {len(sin_atr)} filas "
                      f"(muestra 12)[/]",
                border_style="yellow"))

    # -------------------------------------------------- muestra
    if show_rows > 0 and res.rows:
        cols = ["placement_id", "creative_id", "placement_type", "enabled",
                "group_name_norm", "group_id", "third_party_id", "dimensions",
                "start_date", "end_date", "status"]
        cols = [c for c in cols if any(c in r.values for r in res.rows[:50])]
        st = Table(*(["#", "tipo"] + cols), box=None, show_lines=False)
        for r in res.rows[:show_rows]:
            st.add_row(str(r.row), r.row_type,
                       *[str(r.values.get(c) if r.values.get(c) is not None else "-")[:26]
                         for c in cols])
        console.print(Panel(st, title=f"Muestra ({show_rows} filas)", border_style="dim"))

    # -------------------------------------------------- veredicto
    warns = [a for a in res.anomalies if a.severity != "FATAL"]
    verdict = "[green]OK[/]" if not warns else "[yellow]OK CON ADVERTENCIAS[/]"
    console.print(f"\n  RESULTADO DE INGESTION: {verdict}   "
                  f"({len(res.rows)} filas de datos materializadas)\n")

if __name__ == "__main__":
    app()
"""
CLI: Extraction Preview de Traffic Sheet.

Uso:
    python -m cli.ts --ts "data/ts/TS Adobe Variante B.xlsx"
    python -m cli.ts --ts "..." --profile adobe_variante_a
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.colors import GREEN, GREY, RED, UNKNOWN, WHITE, YELLOW
from parsers.ts_parser import REQ_NOT_WORKED, detect_profile, parse_ts

app = typer.Typer(add_completion=False)
console = Console()

INTENT_STYLE = {
    GREEN: "green", RED: "red", "SWAP": "magenta",
    "SCOPE_EXCLUDED": "bright_black", "REVIEW": "yellow", WHITE: "dim",
}
FAMILY_STYLE = {
    GREEN: "green", RED: "red", YELLOW: "yellow",
    GREY: "bright_black", WHITE: "white", UNKNOWN: "magenta",
}
INTENT_MEANING = {
    GREEN: "NEW / valor nuevo -> debe existir y estar activo",
    RED: "REMOVE / valor viejo -> debe estar desasignado",
    "SWAP": "verde y rojo en la misma fila",
    "SCOPE_EXCLUDED": "amarillo/gris -> fuera de alcance, cero findings",
    "REVIEW": "color no reconocido -> requiere revision",
    WHITE: "contexto existente, no se pidio tocar",
}
REQUEST_STYLE = {
    "NEW_PLACEMENT": "bold green", "CREATIVE_SWAP": "magenta",
    "CREATIVE_ADD": "green", "CREATIVE_REMOVE": "red",
    "URL_SWAP": "cyan", "FIELD_CHANGE": "cyan",
    "REVIEW": "yellow", "NOT_WORKED": "dim",
}
IMPL_MEANING = {
    "SITE_SERVED_1X1": "1x1 site-served: sin creativo en TS es lo ESPERADO",
    "THIRD_PARTY": "3P: se valida creativo, rotacion y grupo",
    "UNKNOWN": "sin dimensiones -> reglas degradadas",
}

def _sheet_panels(name: str, sr, show_rows: int) -> None:
    if sr is None:
        console.print(f"[dim]  ({name}: no aplica en este perfil)[/]")
        return

    h = Table(show_header=False, box=None, padding=(0, 2))
    h.add_row("[dim]Hoja[/]", sr.sheet or "-")
    h.add_row("[dim]Header[/]", f"fila {sr.header_row} ({sr.header_evidence})"
              if sr.header_row else "[red]NO ENCONTRADO[/]")
    h.add_row("[dim]Filas de datos[/]", str(len(sr.rows)))
    if sr.cmap:
        h.add_row("[dim]Columnas mapeadas[/]", str(len(sr.cmap.single)))
        if sr.cmap.missing_required:
            h.add_row("[red]Requeridas ausentes[/]",
                      ", ".join(sr.cmap.missing_required))
        if sr.cmap.unmapped:
            h.add_row("[dim]Sin mapear[/]",
                      ", ".join(x[1] for x in sr.cmap.unmapped[:6]))
    console.print(Panel(h, title=name, border_style="cyan"))

    if not sr.header_row:
        return

    if sr.impl_counts:
        pt = Table("Tipo de implementacion", "Filas", "Que se valida", box=None)
        for k, v in sorted(sr.impl_counts.items(), key=lambda x: -x[1]):
            pt.add_row(k, str(v), IMPL_MEANING.get(k, ""))
        console.print(Panel(pt, title=f"{name} · implementacion",
                            border_style="blue"))

    if sr.intent_counts:
        it = Table("Intencion", "Filas", "Significado", box=None)
        for k, v in sorted(sr.intent_counts.items(), key=lambda x: -x[1]):
            st = INTENT_STYLE.get(k, "")
            it.add_row(f"[{st}]{k}[/]" if st else k, str(v),
                       INTENT_MEANING.get(k, ""))
        console.print(Panel(it, title=f"{name} · INTENCION DE CAMBIO",
                            border_style="magenta"))

    if sr.date_diagnostics:
        dt = Table("Campo", "Orden", "Nativas", "Texto", "Sin parsear",
                   "Evidencia", box=None)
        for k, d in sr.date_diagnostics.items():
            st = "red" if d["order"] == "AMBIGUOUS" else "green"
            dt.add_row(k, f"[{st}]{d['order']}[/]", str(d["native"]),
                       str(d["text"]), str(d["unparsed"]), d["evidence"] or "-")
        console.print(Panel(dt, title=f"{name} · fechas", border_style="blue"))

    if sr.fill_rates:
        fr = Table("Campo", "Poblado", box=None)
        for k, v in sorted(sr.fill_rates.items(), key=lambda x: -x[1]):
            pct = v * 100
            st = "red" if pct == 0 else ("yellow" if pct < 50 else "green")
            fr.add_row(k, f"[{st}]{pct:5.1f}%[/]")
        console.print(Panel(fr, title=f"{name} · fill rate", border_style="blue"))

@app.command()
def main(
    ts: Path = typer.Option(..., "--ts", "-t", exists=True),
    profile: str = typer.Option(None, "--profile", "-p",
                                help="adobe_variante_a | adobe_variante_b | wpp_standard"),
    show_rows: int = typer.Option(15, "--rows", "-r"),
) -> None:
    console.print()
    console.rule("[bold cyan]TRAFFIC SHEET · EXTRACTION PREVIEW[/]")
    console.print("  [dim]leyendo archivo...[/]\n")

    with console.status("[cyan]parseando Traffic Sheet...", spinner="dots"):
        res = parse_ts(ts, profile_name=profile)

    d = Table(show_header=False, box=None, padding=(0, 2))
    d.add_row("[dim]Archivo[/]", ts.name)
    d.add_row("[dim]Perfil[/]", f"[bold]{res.profile}[/]  "
                                f"[dim]({res.profile_evidence})[/]")
    d.add_row("[dim]Hojas en scope[/]", ", ".join(res.in_scope_sheets) or "-")
    if res.out_of_scope_sheets:
        d.add_row("[bright_black]Fuera de scope[/]",
                  ", ".join(res.out_of_scope_sheets))
    if res.hidden_sheets:
        d.add_row("[bright_black]Ocultas (Digital)[/]", ", ".join(res.hidden_sheets))
    d.add_row("[dim]Theme[/]", f"{len(res.theme_colors)} colores resueltos"
              if res.theme_colors else "[yellow]no se pudo leer[/]")
    console.print(Panel(d, title="Documento", border_style="cyan"))

    fatals = [a for a in res.anomalies if a.severity == "FATAL"]
    if fatals:
        ft = Table("Codigo", "Mensaje", box=None)
        for a in fatals:
            ft.add_row(f"[red]{a.code}[/]", a.message)
        console.print(Panel(ft, title="[red]ANOMALIAS FATALES[/]", border_style="red"))
        raise typer.Exit(code=1)

    warns = [a for a in res.anomalies if a.severity == "WARNING"]
    for sr in (res.placements, res.rotations):
        if sr:
            warns += [a for a in sr.anomalies if a.severity == "WARNING"]
    if warns:
        wt = Table("Codigo", "Mensaje", box=None)
        for a in warns:
            wt.add_row(f"[yellow]{a.code}[/]", a.message)
        console.print(Panel(wt, title="[yellow]Advertencias de extraccion[/]",
                            border_style="yellow"))

    if res.campaign_info:
        ci = Table(show_header=False, box=None, padding=(0, 2))
        for k, v in res.campaign_info.items():
            ci.add_row(f"[dim]{k}[/]", str(v)[:70])
        console.print(Panel(ci, title="Campaign Information (lo relevante para QA2)",
                            border_style="blue"))

    if res.site_contacts:
        sct = Table("Site", "Contacto", box=None)
        for n, m in res.site_contacts[:10]:
            sct.add_row(n, m or "[yellow]sin email[/]")
        console.print(Panel(sct,
            title=f"Sites y contactos ({len(res.site_contacts)}) · para envio de tags",
            border_style="dim"))

    _sheet_panels("PLACEMENTS", res.placements, show_rows)
    _sheet_panels("CREATIVE ROTATIONS", res.rotations, show_rows)

    # ---------------- SCOPE DEL QA2
    if res.scope:
        worked = res.worked
        total = len(res.scope)
        sp = Table(show_header=False, box=None, padding=(0, 2))
        sp.add_row("[dim]Placements en la TS[/]", str(total))
        sp.add_row("[bold]Placements TRABAJADOS[/]", f"[bold green]{len(worked)}[/]")
        sp.add_row("[dim]Contexto (no se pidio tocar)[/]", str(total - len(worked)))
        console.print(Panel(sp, title="SCOPE DEL QA2", border_style="green"))

        if res.format_counts:
            fm = Table("Formato", "Placements trabajados", box=None)
            for k in ("display", "video", "1x1", "sin_dims"):
                if k in res.format_counts:
                    st = {"display": "cyan", "video": "magenta",
                          "1x1": "yellow", "sin_dims": "red"}.get(k, "")
                    fm.add_row(f"[{st}]{k}[/]", str(res.format_counts[k]))
            console.print(Panel(fm, title="DESGLOSE POR FORMATO",
                                border_style="cyan"))

        if res.request_counts:
            rq = Table("Tipo de solicitud", "Placements", "display", "video",
                       "1x1", box=None)
            for k, v in sorted(res.request_counts.items(), key=lambda x: -x[1]):
                if k == REQ_NOT_WORKED:
                    continue
                st = REQUEST_STYLE.get(k, "")
                rq.add_row(f"[{st}]{k}[/]" if st else k, str(v),
                           str(res.format_by_request.get((k, "display"), 0)),
                           str(res.format_by_request.get((k, "video"), 0)),
                           str(res.format_by_request.get((k, "1x1"), 0)))
            nw = res.request_counts.get(REQ_NOT_WORKED, 0)
            if nw:
                rq.add_row("[dim]NOT_WORKED[/]", f"[dim]{nw}[/]", "", "", "")
            console.print(Panel(rq, title="TIPOS DE SOLICITUD x FORMATO",
                                border_style="magenta"))

        if res.source_counts:
            sc2 = Table("Origen de la deteccion", "Placements", box=None)
            for k, v in sorted(res.source_counts.items(), key=lambda x: -x[1]):
                sc2.add_row(k, str(v))
            console.print(Panel(sc2, title="COMO SE DETECTO EL TRABAJO",
                                border_style="blue"))

        vr = [s for s in worked if s.visual_review]
        if vr:
            vt = Table("placement_id", "formato", "R", "nota", box=None)
            for s in vr[:show_rows]:
                vt.add_row(s.placement_id, s.fmt, str(s.red_rows), s.note[:56])
            console.print(Panel(vt,
                title=f"[yellow]REVISION VISUAL ({len(vr)}) · sin veredicto[/]",
                border_style="yellow"))

        real = [s for s in worked if not s.visual_review]
        if real:
            wt2 = Table("placement_id", "solicitud", "fmt", "G", "R", "W",
                        "origen", box=None)
            for s in real[:show_rows]:
                st = REQUEST_STYLE.get(s.request_type, "")
                wt2.add_row(s.placement_id,
                            f"[{st}]{s.request_type}[/]" if st else s.request_type,
                            s.fmt, str(s.green_rows), str(s.red_rows),
                            str(s.white_rows), s.source[:26])
            console.print(Panel(wt2,
                title=f"PLACEMENTS TRABAJADOS ({len(real)} total, "
                      f"muestra {min(len(real), show_rows)})",
                border_style="green"))

    if res.groups:
        gw = [g for g in res.groups.values() if g.worked]
        if gw:
            gt = Table("grupo / rotacion", "intencion", "G", "R", "W", box=None)
            for g in gw[:show_rows]:
                st = INTENT_STYLE.get(g.intent, "")
                gt.add_row(g.group_name[:58],
                           f"[{st}]{g.intent}[/]" if st else g.intent,
                           str(g.green_creatives), str(g.red_creatives),
                           str(g.white_creatives))
            console.print(Panel(gt,
                title=f"GRUPOS TRABAJADOS ({len(gw)} de {len(res.groups)})",
                border_style="magenta"))

    if res.lp_worked:
        console.print(f"[dim]  Landing pages con color: {len(res.lp_worked)}[/]")

    if res.region_palette:
        pt = Table("Token", "RGB", "Familia", "Conf", "Celdas", "Campos", box=None)
        for info in sorted(res.region_palette.values(), key=lambda x: -x.count):
            st = FAMILY_STYLE.get(info.family, "")
            pt.add_row(info.token, info.rgb or "[red]?[/]",
                       f"[{st}]{info.family}[/]", info.confidence,
                       str(info.count), ", ".join(sorted(info.fields))[:36])
        console.print(Panel(pt, title="PALETA EN LA DATA REGION",
                            border_style="magenta"))

    console.print()

if __name__ == "__main__":
    app()
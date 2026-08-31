"""
CLI: Matching Preview.

Establece los vinculos TS <-> export sobre el SCOPE TRABAJADO.
No emite veredictos de negocio: eso es el Rule Engine.

Uso:
    python -m cli.match \\
        --ts "data/ts/TS Adobe Variante B.xlsx" \\
        --export "data/exports/Export 1x1_3P directo placement creative.xlsm" \\
        --export-placement "data/exports/Export 1x1_3P directo placement.xlsm"
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.colors import GREEN, RED
from core.matching import CONF_HIGH, CONF_LOW, CONF_MEDIUM, CONF_NONE, match
from parsers.innovid_export import parse_innovid_export
from parsers.ts_parser import parse_ts
from core.matching import CONF_HIGH, CONF_LOW, CONF_MEDIUM, CONF_NONE, match
from core.urls import (
    TRI_EXPORT_MISMATCH, TRI_INCOMPLETE, TRI_OK, TRI_ALL_DIFFERENT,
    TRI_TS_MISMATCH, TRI_URL_MISMATCH, URL_BASE_DIFF, URL_BOTH_MISSING,
    URL_MALFORMED, URL_MATCH, URL_MISSING_ACTUAL, URL_MISSING_EXPECTED,
    URL_PARAMS_DIFF,
)

app = typer.Typer(add_completion=False)
console = Console()

CONF_STYLE = {CONF_HIGH: "green", CONF_MEDIUM: "yellow",
              CONF_LOW: "red", CONF_NONE: "bright_black"}
GROUP_STYLE = {"OK": "green", "NAME_ONLY": "yellow", "MISMATCH": "red",
               "MISSING": "red", "EXTRA": "yellow", "N/A": "dim",
               "NOT_DECLARED": "dim"}
URL_STYLE = {
    URL_MATCH: "green", URL_PARAMS_DIFF: "red", URL_BASE_DIFF: "bold red",
    URL_MISSING_ACTUAL: "bold red", URL_MISSING_EXPECTED: "yellow",
    URL_MALFORMED: "red", URL_BOTH_MISSING: "dim",
}
URL_MEAN = {
    URL_MATCH: "destination and params match",
    URL_PARAMS_DIFF: "same destination, different params -> check sdid/as_*",
    URL_BASE_DIFF: "different destination -> wrong URL",
    URL_MISSING_ACTUAL: "the creative has no ClickTag in Innovid",
    URL_MISSING_EXPECTED: "the TS doesn't declare a URL for this creative",
    URL_MALFORMED: "malformed URL on one side or the other",
    URL_BOTH_MISSING: "neither side declares a URL",
}
TRI_STYLE = {
    TRI_OK: "green", TRI_URL_MISMATCH: "bold red",
    TRI_EXPORT_MISMATCH: "bold red", TRI_TS_MISMATCH: "yellow",
    TRI_ALL_DIFFERENT: "bold red", TRI_INCOMPLETE: "dim",
}
TRI_MEAN = {
    TRI_OK: "TS = Innovid = URL sdid",
    TRI_URL_MISMATCH: "TS and Innovid match, the URL carries a different sdid",
    TRI_EXPORT_MISMATCH: "TS and URL match, Third_Party_ID in Innovid differs",
    TRI_TS_MISMATCH: "Innovid and URL match, the TS declares a different CGEN",
    TRI_ALL_DIFFERENT: "all three vertices differ",
    TRI_INCOMPLETE: "missing vertices -> NOT_VERIFIED",
}

@app.command()
def main(
    ts_path: Path = typer.Option(..., "--ts", "-t", exists=True),
    export: Path = typer.Option(..., "--export", "-e", exists=True,
                                help="Export Placement-Creative"),
    export_placement: Path = typer.Option(None, "--export-placement", "-P",
                                          help="Export nivel Placement (URL 1x1, pixel)"),
    profile: str = typer.Option(None, "--profile", "-p"),
    show: int = typer.Option(15, "--rows", "-r"),
) -> None:
    console.print()
    console.rule("[bold cyan]MATCHING · TS vs INNOVID[/]")

    with console.status("[cyan]parseando...", spinner="dots"):
        ts = parse_ts(ts_path, profile_name=profile)
        pc = parse_innovid_export(export)
        pl = parse_innovid_export(export_placement) if export_placement else None
        res = match(ts, pc, pl)

    # ---------------- inputs
    d = Table(show_header=False, box=None, padding=(0, 2))
    d.add_row("[dim]Traffic Sheet[/]", f"{ts_path.name}  [dim]({ts.profile})[/]")
    d.add_row("[dim]Export creativo[/]", f"{export.name}  [dim]({pc.level})[/]")
    d.add_row("[dim]Export placement[/]",
              f"{export_placement.name}" if export_placement
              else "[yellow]no provisto -> URL de 1x1 y pixel NO verificables[/]")
    console.print(Panel(d, title="Inputs", border_style="cyan"))

    # ---------------- L0
    st = {"OK": "green", "MISMATCH": "red", "UNKNOWN": "yellow"}[res.scope_guard]
    sg = Table(show_header=False, box=None, padding=(0, 2))
    sg.add_row("[dim]Scope Guard[/]", f"[{st}]{res.scope_guard}[/]")
    sg.add_row("[dim]Evidencia[/]", res.scope_evidence)
    console.print(Panel(sg, title="L0 · SCOPE GUARD", border_style=st))

    if res.blocked:
        console.print("\n[bold red]  BLOQUEADO: el export no corresponde "
                      "a la campana de la TS.[/]\n")
        raise typer.Exit(code=1)

    # ---------------- L1
    m = Table(show_header=False, box=None, padding=(0, 2))
    m.add_row("[dim]Placements trabajados en la TS[/]", str(res.expected_total))
    m.add_row("[dim]Placements en el export[/]", str(res.actual_total))
    m.add_row("[bold green]Matcheados[/]", f"[bold green]{len(res.matched)}[/]")
    m.add_row("[bold red]Esperados sin match[/]",
              f"[bold red]{len(res.only_expected)}[/]" if res.only_expected else "0")
    console.print(Panel(m, title="L1 · PLACEMENT MATCH", border_style="blue"))

    if res.only_expected:
        ot = Table("placement_id", "solicitud", "fmt", "nombre en la TS", box=None)
        for ep in res.only_expected[:show]:
            ot.add_row(ep.placement_id, ep.request_type, ep.fmt, ep.name[:52])
        console.print(Panel(ot,
            title=f"[red]NO ENCONTRADOS EN INNOVID ({len(res.only_expected)})[/]",
            border_style="red"))

    # ---------------- L3
    if res.group_counts:
        gt = Table("Resultado", "Placements", "Significado", box=None)
        MEAN = {
            "OK": "nombre + Decision_Tree_ID coinciden -> HIGH",
            "NAME_ONLY": "nombre coincide, ID no verificable -> MEDIUM",
            "MISMATCH": "nombre o ID distinto -> revisar",
            "MISSING": "la TS declara grupo, el export no lo tiene",
            "EXTRA": "el export tiene grupo que la TS no declara",
            "N/A": "sin grupo en ninguno (directo o 1x1)",
            "NOT_DECLARED": "el formato de TS no declara grupos -> informativo",
        }
        for k, v in sorted(res.group_counts.items(), key=lambda x: -x[1]):
            s = GROUP_STYLE.get(k, "")
            gt.add_row(f"[{s}]{k}[/]" if s else k, str(v), MEAN.get(k, ""))
        console.print(Panel(gt, title="L3 · GROUP / DECISION TREE",
                            border_style="magenta"))

        bad = [pm for pm in res.matched
               if pm.group_match in ("MISMATCH", "MISSING")]
        if bad:
            bt = Table("placement_id", "res", "TS declara", "Innovid tiene",
                       "nota", box=None)
            for pm in bad[:show]:
                bt.add_row(pm.placement_id, pm.group_match,
                           pm.expected.group_name[:26],
                           (pm.actual.group_name or "-")[:26],
                           pm.group_trace.note[:38])
            console.print(Panel(bt, title="[red]Grupos con problema[/]",
                                border_style="red"))

    # ---------------- L4
    if res.creative_conf_counts:
        ct = Table("Confianza", "Creativos", "Efecto en el veredicto", box=None)
        EFF = {
            CONF_HIGH: "se permite FAIL (creative_id o Ad-ID)",
            CONF_MEDIUM: "maximo REVIEW (filename o nombre unico)",
            CONF_LOW: "solo REVIEW (nombre ambiguo)",
            CONF_NONE: "sin match -> missing, nunca mismatch",
        }
        for k in (CONF_HIGH, CONF_MEDIUM, CONF_LOW, CONF_NONE):
            if k in res.creative_conf_counts:
                s = CONF_STYLE[k]
                ct.add_row(f"[{s}]{k}[/]", str(res.creative_conf_counts[k]),
                           EFF[k])
        console.print(Panel(ct, title="L4 · CREATIVE MATCH · confianza",
                            border_style="blue"))

    # ---------------- L6 URL
    if res.url_counts:
        ut = Table("Resultado", "Creativos verdes", "Significado", box=None)
        for k in (URL_MATCH, URL_PARAMS_DIFF, URL_BASE_DIFF, URL_MISSING_ACTUAL,
                  URL_MISSING_EXPECTED, URL_MALFORMED, URL_BOTH_MISSING):
            if k in res.url_counts:
                s = URL_STYLE[k]
                ut.add_row(f"[{s}]{k}[/]", str(res.url_counts[k]), URL_MEAN[k])
        console.print(Panel(ut, title="L6 · URL · TS vs Clicktag_1",
                            border_style="blue"))

        bad_url = [(pm, cl) for pm in res.matched for cl in pm.creative_links
                   if cl.url and not cl.url.is_ok
                   and cl.url.result != URL_BOTH_MISSING]
        if bad_url:
            # agrupar por (resultado, placement) para no repetir 40 veces lo mismo
            grouped: dict[tuple[str, str], list] = {}
            for pm, cl in bad_url:
                grouped.setdefault((cl.url.result, pm.placement_id), []).append(cl)

            bt = Table("res", "placement", "creativos", "detalle", box=None)
            for (result, pid), items in list(grouped.items())[:show]:
                s = URL_STYLE.get(result, "")
                bt.add_row(f"[{s}]{result}[/]", pid, str(len(items)),
                           items[0].url.note[:52])
            console.print(Panel(bt,
                title=f"[red]URLs con problema · {len(bad_url)} creativos "
                      f"en {len(grouped)} placements[/]",
                border_style="red"))

    # ---------------- L7 ATTRIBUTION
    if res.triangle_counts:
        tt2 = Table("Resultado", "Creativos verdes", "Significado", box=None)
        for k in (TRI_OK, TRI_URL_MISMATCH, TRI_EXPORT_MISMATCH,
                  TRI_TS_MISMATCH, TRI_ALL_DIFFERENT, TRI_INCOMPLETE):
            if k in res.triangle_counts:
                s = TRI_STYLE[k]
                tt2.add_row(f"[{s}]{k}[/]", str(res.triangle_counts[k]),
                            TRI_MEAN[k])
        console.print(Panel(tt2,
            title="L7 · ATTRIBUTION · TS.CGENS = Third_Party_ID = sdid",
            border_style="magenta"))

        bad_tri = [(pm, cl) for pm in res.matched for cl in pm.creative_links
                   if cl.triangle and cl.triangle.result not in (TRI_OK, TRI_INCOMPLETE)]
        if bad_tri:
            at2 = Table("placement", "creativo", "TS", "Innovid", "URL",
                        "desviado", box=None)
            for pm, cl in bad_tri[:show]:
                t = cl.triangle
                at2.add_row(pm.placement_id,
                            (cl.expected.name or "-")[:24],
                            t.ts or "[dim]-[/]", t.export or "[dim]-[/]",
                            t.url or "[dim]-[/]",
                            f"[bold red]{t.deviant or t.result}[/]")
            console.print(Panel(at2,
                title=f"[red]Attribution desviada ({len(bad_tri)})[/]",
                border_style="red"))

        ok_tri = [(pm, cl) for pm in res.matched for cl in pm.creative_links
                  if cl.triangle and cl.triangle.is_ok]
        if ok_tri:
            st2 = Table("placement", "creativo", "CGEN consenso", box=None)
            for pm, cl in ok_tri[:5]:
                st2.add_row(pm.placement_id,
                            (cl.expected.name or "-")[:44],
                            f"[green]{cl.triangle.consensus}[/]")
            console.print(Panel(st2,
                title=f"[green]Triangulo cerrado ({len(ok_tri)}) · muestra 5[/]",
                border_style="green"))

   # ---------------- vista previa por placement
    prev = [pm for pm in res.matched if pm.expected.creatives]
    if prev:
        pt = Table("placement", "solicitud", "verde esperado", "rojo esperado",
                   "extra corriendo", "extra apagado", "grupo", box=None)
        for pm in prev[:show]:
            g_ok = sum(1 for c in pm.creative_links
                       if c.expected.intent == GREEN and c.actual
                       and c.actual.running)
            g_tot = len(pm.expected.green)
            r_ok = sum(1 for c in pm.creative_links
                       if c.expected.intent == RED
                       and (c.actual is None or not c.actual.running))
            r_tot = len(pm.expected.red)

            gs = "green" if g_ok == g_tot else "red"
            rs = "green" if r_ok == r_tot else "red"
            gst = GROUP_STYLE.get(pm.group_match, "")
            n_run = len(pm.extra_running)
            es = "yellow" if n_run else "dim"

            pt.add_row(pm.placement_id, pm.expected.request_type,
                       f"[{gs}]{g_ok}/{g_tot} presentes[/]" if g_tot else "-",
                       f"[{rs}]{r_ok}/{r_tot} fuera[/]" if r_tot else "-",
                       f"[{es}]{n_run}[/]",
                       f"[dim]{len(pm.extra_stopped)}[/]",
                       f"[{gst}]{pm.group_match}[/]" if gst else pm.group_match)
        console.print(Panel(pt,
            title=f"VISTA PREVIA DE MEMBRESIA ({len(prev)} placements, "
                  f"muestra {min(len(prev), show)})",
            border_style="green"))

    # ---------------- extras
    if res.extra_running_total or res.extra_stopped_total:
        et = Table("Categoria", "Creativos", "Tratamiento", box=None)
        et.add_row("[dim]extra apagados[/]", str(res.extra_stopped_total),
                   "preexistentes con Status=Disabled -> INFO, es normal")
        et.add_row("[yellow]extra corriendo[/]", str(res.extra_running_total),
                   "activos sin estar declarados en la TS -> REVIEW")
        console.print(Panel(et,
            title="CREATIVOS EXTRA EN INNOVID (no declarados en esta solicitud)",
            border_style="blue"))

        runners = [(pm, c) for pm in res.matched for c in pm.extra_running]
        if runners:
            rt2 = Table("placement", "creative_id", "estado", "filename", box=None)
            for pm, c in runners[:show]:
                rt2.add_row(pm.placement_id, c.creative_id or "-",
                            c.state_label, (c.filename or c.name)[:46])
            console.print(Panel(rt2,
                title=f"[yellow]Extras CORRIENDO ({len(runners)}) · requieren "
                      f"revision[/]", border_style="yellow"))

    # ---------------- MatchTrace
    sample = None
    for pm in res.matched:
        if pm.creative_links:
            sample = pm
            break
    if sample:
        tt = Table("expected", "->", "actual", "conf", "llave", box=None)
        for cl in sample.creative_links[:8]:
            s = CONF_STYLE[cl.confidence]
            tt.add_row((cl.expected.name or cl.expected.creative_id)[:44],
                       "->", (cl.trace.right or "[red]sin match[/]")[:44],
                       f"[{s}]{cl.confidence}[/]", cl.trace.winner or "-")
        console.print(Panel(tt,
            title=f"MATCH TRACE · placement {sample.placement_id}",
            border_style="dim"))

    vr = [pm for pm in res.matched if pm.expected.visual_review]
    if vr:
        console.print(f"[yellow]  {len(vr)} placements marcados para "
                      f"revision visual (no generan veredicto).[/]")

    console.print()

if __name__ == "__main__":
    app()
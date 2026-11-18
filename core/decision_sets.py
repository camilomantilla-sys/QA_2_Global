"""
La solicitud vista por decision set (FB-08).

Una solicitud grande suele tener muchos placements y pocos decision
sets: 40 placements que comparten 3 rotaciones. Revisar placement por
placement repite 40 veces las mismas fechas, horas y URLs. Esta vista
las junta por decision set, que es como se implementan en Innovid:
una fila por creativo (o por tramo de fechas del mismo creativo), con
lo que pide la Traffic Sheet al lado de lo que hay en Innovid, y la
lista de placements que lo comparten.

Solo reorganiza lo que ya se reviso. No crea hallazgos ni cambia el
veredicto: el estado de cada fila es el peor hallazgo que ya existe
para ese creativo en esos placements.

El nombre del decision set es el de la columna Creative Rotation de la
TS. Los creativos que el placement declara sin rotacion (asignacion
directa) van juntos en su propio bloque.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any, Iterable

from core.colors import GREEN, RED, WHITE
from core.matching import norm_creative
from core.normalize import norm_compare

DIRECT = "Assigned directly (no decision set)"

STATUS_ORDER = {"FAIL": 0, "REVIEW": 1, "NOT_VERIFIED": 2, "INFO": 3, "PASS": 4}

INTENT_LABELS = {GREEN: "New", RED: "Removed", WHITE: "No change"}


def _date(value) -> str:
    return value.isoformat() if isinstance(value, date) else ""


def _worse(a: str, b: str) -> str:
    if not a:
        return b
    if not b:
        return a
    return a if STATUS_ORDER.get(a, 9) <= STATUS_ORDER.get(b, 9) else b


def _one_or_many(values: Iterable[str]) -> dict[str, Any]:
    """Un valor si todos los placements coinciden; si no, todos y la marca."""
    distinct = sorted({v for v in values if v})
    return {"value": distinct[0] if len(distinct) == 1 else "",
            "values": distinct, "varies": len(distinct) > 1}


def _flight_index(reconciliation) -> dict[tuple, Any]:
    """Los nodos que se leyeron en Innovid, por placement, creativo y fechas de la TS."""
    index: dict[tuple, Any] = {}
    for check in getattr(reconciliation, "flights", None) or []:
        key = (str(check.placement_id), norm_creative(check.creative_name),
               check.expected_start, check.expected_end)
        index.setdefault(key, check)
    return index


def decision_set_view(match_result, findings: list[dict[str, Any]],
                      innovid_reconciliation=None) -> list[dict[str, Any]]:
    """
    Los decision sets de la solicitud, el peor primero.

    ``findings`` son las filas de ``ui.web.results.finding_row`` (ya con
    las firmas de QA2 aplicadas), para que el estado de cada bloque sea
    el mismo que se ve en la lista de hallazgos.
    """
    worst_by_pl: dict[str, str] = {}
    worst_by_cr: dict[tuple[str, str], str] = {}
    for row in findings:
        pid, status = str(row.get("placement_id") or ""), row.get("status", "")
        if not pid:
            continue
        worst_by_pl[pid] = _worse(worst_by_pl.get(pid, ""), status)
        creative = norm_creative(str(row.get("creative") or ""))
        if creative:
            key = (pid, creative)
            worst_by_cr[key] = _worse(worst_by_cr.get(key, ""), status)

    flights = _flight_index(innovid_reconciliation)
    groups: dict[str, dict[str, Any]] = {}

    def _group(name: str) -> dict[str, Any]:
        key = norm_compare(name) if name else ""
        return groups.setdefault(key, {
            "name": name or DIRECT, "direct": not name,
            "placements": {}, "rows": {}, "innovid_names": set(),
        })

    # Los placements de la TS que no estan en el export tambien van: su
    # hallazgo ("no esta en Innovid") es justo lo que hay que ver.
    worked = [(pm.expected, list(pm.creative_links), False)
              for pm in getattr(match_result, "matched", None) or []]
    worked += [(ep, [SimpleNamespace(expected=c, url=None) for c in ep.creatives], True)
               for ep in getattr(match_result, "only_expected", None) or []]

    for ep, links, missing in worked:
        pid = str(ep.placement_id)
        placement = {
            "placement_id": pid, "placement_name": ep.name, "dims": ep.dims,
            "status": worst_by_pl.get(pid, ""), "missing": missing,
        }
        # Un placement sin creativos esperados (un 1x1 de tracking, un
        # placement que se apaga) igual tiene que aparecer en algun lado.
        if not links:
            _group(ep.group_name.strip())["placements"][pid] = placement
        for link in links:
            ec = link.expected
            g = _group(ec.group)
            g["placements"][pid] = placement
            row_key = (ec.key_norm, ec.start, ec.end)
            row = g["rows"].setdefault(row_key, {
                "creative": ec.name, "intent": INTENT_LABELS.get(ec.intent, ec.intent),
                "is_default": ec.is_default,
                "ts_start": _date(ec.start), "ts_end": _date(ec.end),
                "weight": ec.rotation_weight, "ts_url": ec.url,
                "placements": [], "status": "",
                "_innovid_start": [], "_innovid_end": [], "_innovid_url": [],
                "_innovid_weight": [],
            })
            row["placements"].append(pid)
            row["status"] = _worse(row["status"], worst_by_cr.get((pid, ec.key_norm), ""))
            url = getattr(getattr(link.url, "actual", None), "raw", "") if link.url else ""
            if url:
                row["_innovid_url"].append(url)
            node = flights.get((pid, ec.key_norm, ec.start, ec.end))
            if node is not None:
                start = " ".join(x for x in (_date(node.actual_start), node.actual_start_time) if x)
                end = " ".join(x for x in (_date(node.actual_end), node.actual_end_time) if x)
                row["_innovid_start"].append(start)
                row["_innovid_end"].append(end)
                row["_innovid_weight"].append(node.actual_weight_pct or node.actual_weight)
                if node.dset_name:
                    g["innovid_names"].add(node.dset_name)

    # El default de Innovid de cada placement, en el bloque donde esta
    # ese placement: AdOps lo quiere ver aunque repita un creativo.
    for check in getattr(innovid_reconciliation, "default_ads", None) or []:
        pid = str(check.placement_id)
        for g in groups.values():
            if pid not in g["placements"]:
                continue
            start = " ".join(x for x in (_date(check.actual_start), check.actual_start_time) if x)
            end = " ".join(x for x in (_date(check.actual_end), check.actual_end_time) if x)
            d = g.setdefault("defaults", {}).setdefault((check.actual_name, start, end), {
                "creative": check.actual_name, "ts_creative": check.creative_name,
                "innovid_start": start, "innovid_end": end or "ongoing",
                "dset_name": check.dset_name, "placements": [],
            })
            d["placements"].append(pid)

    out = []
    for g in groups.values():
        rows = []
        for row in g["rows"].values():
            row["innovid_start"] = _one_or_many(row.pop("_innovid_start"))
            row["innovid_end"] = _one_or_many(row.pop("_innovid_end"))
            row["innovid_url"] = _one_or_many(row.pop("_innovid_url"))
            row["innovid_weight"] = _one_or_many(row.pop("_innovid_weight"))
            row["placements"] = sorted(set(row["placements"]))
            rows.append(row)
        rows.sort(key=lambda r: (r["ts_start"] or "9999", r["creative"].lower()))
        placements = sorted(g["placements"].values(),
                            key=lambda p: (STATUS_ORDER.get(p["status"], 9), p["placement_id"]))
        worst = ""
        for p in placements:
            worst = _worse(worst, p["status"])
        counts: dict[str, int] = {}
        for p in placements:
            if p["status"]:
                counts[p["status"]] = counts.get(p["status"], 0) + 1
        out.append({
            "name": g["name"], "direct": g["direct"],
            "innovid_names": sorted(g["innovid_names"]),
            "status": worst, "counts": counts,
            "placements": placements, "rows": rows,
            "defaults": [dict(d, placements=sorted(set(d["placements"])))
                         for d in (g.get("defaults") or {}).values()],
        })
    out.sort(key=lambda g: (g["direct"], STATUS_ORDER.get(g["status"], 9), g["name"].lower()))
    return out

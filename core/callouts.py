"""
Los callouts del reporte (FB-09).

Lo que se firma a mano se firma en bloque y por el mismo motivo: 40
placements con la misma diferencia de fechas, 3 sites donde hay que
mirar Remove VPAID. En el Excel eso quedaba disperso en la hoja de
hallazgos, fila por fila. Un callout lo dice una vez, con un texto
predeterminado, y lista a quien aplica:

    The following placements have different flight dates in the
    Traffic Sheet and in Innovid. ...
      11310597  P3LCCFN_...   TS 2026-11-16 → 2026-12-31 · Innovid ...

Entra lo que pide una mirada humana: REVIEW, FAIL y NOT_VERIFIED
(firmado o no), y los INFO de las reglas que AdOps quiere ver aunque
no bloqueen (las fechas del placement). Cada callout dice cuantos se
aprobaron y con que observacion.
"""
from __future__ import annotations

from typing import Any

from core.rule_titles import RULE_TITLES

#: Lo que pide una persona aunque ya este firmado.
REVIEWABLE = ("REVIEW", "FAIL", "NOT_VERIFIED")

#: INFO que igual va a los callouts: no bloquea, pero alguien lo mira.
INFO_RULES = {"PLC-004"}

#: El texto predeterminado de cada grupo. Lo que no esta aqui usa el
#: titulo de la regla.
TEXTS = {
    "PLC-001": "These placements from the Traffic Sheet are not in the Innovid export.",
    "PLC-003": "The Traffic Sheet wants these placements running, but the export shows them off.",
    "PLC-004": ("The following placements have different flight dates in the Traffic Sheet "
                "and in Innovid. This doesn't block the QA; confirm the difference is intended."),
    "PLC-006": "The placement name in Innovid differs from the Traffic Sheet for these placements.",
    "INV-001": "These creatives run on other dates in their decision set than the Traffic Sheet asks.",
    "INV-001/no-end": "These creatives have no end date in Innovid, and the Traffic Sheet closes them.",
    "INV-002": "The rotation weight in the decision set differs from the Traffic Sheet for these creatives.",
    "INV-005": "The Traffic Sheet wants these placements running, but Innovid has them off today.",
    "TAG-015": "The tag file has empty cells after wrapping for these placements.",
    "VID-001": ("Remove VPAID has to be confirmed by hand on these sites "
                "(Video & Audio Settings > Media Filters)."),
}

#: Grupos en los que el detalle (TS contra Innovid) es lo que hay que ver.
SHOW_VALUES = {"PLC-004", "PLC-006", "INV-001", "INV-001/no-end", "INV-002", "TAG-015"}

MAX_ITEMS = 60


def _value(x) -> str:
    return str(getattr(x, "value", x) or "")


def _approval(reason: str) -> str:
    """La firma que dejo apply_review_overrides al final del reason, o ""."""
    last = str(reason or "").split(" | ")[-1].strip()
    return last if last.startswith("Approved") else ""


def _group_key(f) -> str:
    rule = f.rule_id
    if rule == "INV-001" and "no end date" in _value(f.message):
        return "INV-001/no-end"
    return rule


def _label(f) -> str:
    parts = [p for p in (_value(f.placement_id), _value(f.placement_name)) if p]
    creative = _value(f.creative_name) or _value(f.creative_id)
    if creative:
        parts.append(f"· {creative}")
    return " ".join(parts) or _value(f.message)


def build_callouts(findings, names: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """
    Los callouts, los que bloquean primero.

    ``findings`` son los del reporte, ya con las firmas aplicadas (lo
    firmado llega como PASS con "Approved by ..." al final del reason).
    ``names`` completa el nombre del placement cuando la regla no lo puso.
    """
    names = names or {}
    items = findings.findings if hasattr(findings, "findings") else findings
    groups: dict[str, dict[str, Any]] = {}
    order = {"FAIL": 0, "REVIEW": 1, "NOT_VERIFIED": 2, "INFO": 3, "PASS": 4}

    for f in items:
        status = _value(f.status)
        approval = _approval(_value(f.reason)) if status == "PASS" else ""
        if not (status in REVIEWABLE or approval or
                (status == "INFO" and f.rule_id in INFO_RULES)):
            continue
        key = _group_key(f)
        g = groups.setdefault(key, {
            "key": key, "rule": f.rule_id,
            "text": TEXTS.get(key, ""),
            "items": [], "approved": 0, "pending": 0, "worst": status,
        })
        detail = ""
        if key in SHOW_VALUES and (f.expected or f.actual):
            detail = f"Traffic Sheet {_value(f.expected) or '—'} · Innovid {_value(f.actual) or '—'}"
        label = _label(f)
        pid = _value(f.placement_id)
        if pid and not _value(f.placement_name) and names.get(pid):
            label = label.replace(pid, f"{pid} {names[pid]}", 1)
        g["items"].append({"label": label, "detail": detail,
                           "approval": approval, "status": status})
        if approval:
            g["approved"] += 1
        elif status != "INFO":
            g["pending"] += 1
        if order.get(status, 9) < order.get(g["worst"], 9):
            g["worst"] = status

    out = []
    for g in groups.values():
        if not g["text"]:
            title = RULE_TITLES.get(g["rule"], g["rule"])
            unchecked = all(i["status"] == "NOT_VERIFIED" or i["approval"] for i in g["items"])
            g["text"] = (f"{title}: QA2 couldn't check these, so they need a look by hand."
                         if unchecked else f"{title}: these need a look.")
        g["items"].sort(key=lambda i: i["label"])
        g["total"] = len(g["items"])
        g["more"] = max(0, g["total"] - MAX_ITEMS)
        g["items"] = g["items"][:MAX_ITEMS]
        g["state"] = state_line(g)
        out.append(g)
    out.sort(key=lambda g: (order.get(g["worst"], 9), g["key"]))
    return out


def state_line(g: dict[str, Any]) -> str:
    """"3 approved · 2 to review", o "Doesn't block the QA" para un INFO."""
    if not g["approved"] and not g["pending"]:
        return f"{g['total']} item{'s' if g['total'] != 1 else ''} · doesn't block the QA"
    parts = []
    if g["approved"]:
        parts.append(f"{g['approved']} approved")
    if g["pending"]:
        parts.append(f"{g['pending']} to review")
    return " · ".join(parts)

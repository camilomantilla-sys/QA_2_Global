"""
Lo que la TS pide de un placement frente a si esta encendido en Innovid.

Un placement apagado (en gris en Innovid: Stopped, Disabled...) no sirve
nada. Si la TS lo desasigna entero, apagado es lo pedido. Si la TS le
pide cualquier otra cosa -- placement nuevo, creativos, URL -- lo quiere
corriendo, y un QA con ese placement apagado no puede salir aprobado
aunque todo lo demas coincida (FB-25: la TS era de una solicitud vieja y
una posterior apago los placements).
"""
from __future__ import annotations

from parsers.ts_parser import (
    REQ_CREATIVE_ADD, REQ_CREATIVE_REMOVE, REQ_CREATIVE_SWAP,
    REQ_NEW_PLACEMENT, REQ_URL_SWAP,
)

#: Como llama Innovid a un placement que ya no sirve. "Draft" no esta:
#: es un placement que aun no sale, normal en uno nuevo.
INACTIVE_STATUSES = {
    "stopped", "disabled", "inactive", "deactivated", "paused",
    "archived", "hidden",
}

_ASKS = {
    REQ_NEW_PLACEMENT: "it is a new placement",
    REQ_CREATIVE_SWAP: "it asks for a creative swap",
    REQ_CREATIVE_ADD: "it asks for new creatives",
    REQ_URL_SWAP: "it asks for a landing page change",
}


def is_inactive(status) -> bool:
    return str(status or "").strip().lower() in INACTIVE_STATUSES


def wants_it_off(pm) -> bool:
    """La TS desasigna el placement entero: apagado es lo pedido (PLC-002)."""
    return getattr(pm.expected, "request_type", "") == REQ_CREATIVE_REMOVE


def what_the_ts_asks(pm) -> str:
    return _ASKS.get(getattr(pm.expected, "request_type", ""),
                     "it asks for changes on it")


OLDER_TS_NOTE = (
    "A placement that is off serves nothing, so the request can't pass "
    "as it is. If a later request turned it off, this Traffic Sheet is "
    "older than what is in Innovid now."
)
ACTION = (
    "Check the placement in Innovid. Activate it if this request needs it "
    "running; if a later request turned it off, approve this review."
)

"""
VID-001 -- Remove VPAID en el site de los placements de video (FB-03).

En Unilever y Wendy's todo lo de video se entrega sin VPAID. Se
configura por site, no por placement: Video & Audio Settings del site
> Verification Partner Media Filters > Media Filters = "Remove VPAID".
BlackRock solo pide 1x1 y display, asi que no aplica.

Ningun export trae ese ajuste. Con Innovid conectado se lee del panel
del site (videoConfig.optionGroups.ctvOttGroup.mediaFilter; None es
"Default"): PASS si dice Remove VPAID, FAIL si esta en Default. Sin
Innovid es una revision a mano: una por site, no una por placement,
porque se mira una sola vez por site. Se firma como cualquier REVIEW
y queda en los callouts del reporte.
"""
from __future__ import annotations

import re

from core.findings import Domain
from core.normalize import norm_compare
from core.team_roster import base_account
from core.ts_schema import FMT_VIDEO

#: Las cuentas que piden Remove VPAID en video.
ACCOUNTS = {"Unilever", "Wendy's"}

WHERE = "Video & Audio Settings > Verification Partner Media Filters > Media Filters"


def applies_to(account: str) -> bool:
    return base_account(account) in ACCOUNTS


def is_remove_vpaid(value) -> bool:
    """El valor de Media Filters dice Remove VPAID ("REMOVE_VPAID", "Remove VPAID"...)."""
    return "vpaid" in re.sub(r"[^a-z]", "", str(value or "").lower())


def _setting_for(site: str, ts_site: str, settings: dict) -> dict | None:
    """El ajuste del site: por el id que trae la TS ("Amazon (17627)") o por el nombre."""
    found = re.search(r"\((\d+)\)\s*$", ts_site or "")
    if found and found.group(1) in settings:
        return settings[found.group(1)]
    for entry in settings.values():
        if norm_compare(entry.get("name")) and norm_compare(entry.get("name")) == norm_compare(site):
            return entry
    return None


def evaluate(match_result, buffer, account: str = "", innovid_reconciliation=None) -> None:
    if not applies_to(account):
        return
    settings = getattr(innovid_reconciliation, "site_media_filters", None) or {}

    sites: dict[str, list] = {}
    for pm in getattr(match_result, "matched", None) or []:
        if getattr(pm.expected, "fmt", "") != FMT_VIDEO:
            continue
        site = str(getattr(pm.actual, "site", "") or pm.expected.site or "").strip()
        sites.setdefault(site or "(site not in the export)", []).append(pm)

    reason = (f"{base_account(account)} video goes out without VPAID, and it is set "
              "once per site, not per placement.")
    for site, placements in sorted(sites.items()):
        ids = ", ".join(str(pm.placement_id) for pm in placements)
        n = len(placements)
        common = dict(
            rule_id="VID-001",
            domain=Domain.SCOPE,
            placement_name=f"Site {site} · {n} video placement{'s' if n != 1 else ''}",
            expected=f"{WHERE} = Remove VPAID",
            reason=reason,
        )
        setting = _setting_for(site, placements[0].expected.site, settings)
        if setting is None:
            buffer.review(
                message=f"Check Remove VPAID on the site {site}",
                actual=(("Innovid wasn't connected, so QA2 couldn't read it. " if not settings
                         else "Innovid didn't return this site's settings. ")
                        + f"Video placements on this site: {ids}"),
                recommended_action=(f"Open the site's {WHERE} in Innovid, confirm it says "
                                    "Remove VPAID, and approve this."),
                **common,
            )
            continue
        value = setting.get("media_filter")
        if is_remove_vpaid(value):
            buffer.pass_(message=f"Remove VPAID is set on the site {site}",
                         actual=f"Media Filters = {value}. Video placements on this site: {ids}",
                         **common)
        elif value in (None, ""):
            buffer.fail(
                message=f"Remove VPAID is not set on the site {site}: Media Filters is Default",
                actual=f"Media Filters = Default. Video placements on this site: {ids}",
                recommended_action=f"Set {WHERE} to Remove VPAID on this site.",
                **common,
            )
        else:
            # Un valor que QA2 no conoce: mejor una persona que un FAIL
            # o un PASS adivinado.
            buffer.review(
                message=f"Check Remove VPAID on the site {site}: Media Filters says {value}",
                actual=f"Media Filters = {value}. Video placements on this site: {ids}",
                recommended_action=(f"Confirm {WHERE} is Remove VPAID on this site, "
                                    "and approve this."),
                **common,
            )

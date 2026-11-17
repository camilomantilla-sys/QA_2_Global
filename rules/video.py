"""
VID-001 -- Remove VPAID en el site de los placements de video (FB-03).

En Unilever y Wendy's todo lo de video se entrega sin VPAID. Se
configura por site, no por placement: Video & Audio Settings del site
> Verification Partner Media Filters > Media Filters = "Remove VPAID".
BlackRock solo pide 1x1 y display, asi que no aplica.

Ningun export trae ese ajuste, y Innovid no lo da en las llamadas que
QA2 ya hace. Hasta poder leerlo, es una revision a mano: una por site,
no una por placement, porque se mira una sola vez por site. Se firma
como cualquier REVIEW y queda en los callouts del reporte.
"""
from __future__ import annotations

from core.findings import Domain
from core.team_roster import base_account
from core.ts_schema import FMT_VIDEO

#: Las cuentas que piden Remove VPAID en video.
ACCOUNTS = {"Unilever", "Wendy's"}

WHERE = "Video & Audio Settings > Verification Partner Media Filters > Media Filters"


def applies_to(account: str) -> bool:
    return base_account(account) in ACCOUNTS


def evaluate(match_result, buffer, account: str = "") -> None:
    if not applies_to(account):
        return

    sites: dict[str, list] = {}
    for pm in getattr(match_result, "matched", None) or []:
        if getattr(pm.expected, "fmt", "") != FMT_VIDEO:
            continue
        site = str(getattr(pm.actual, "site", "") or pm.expected.site or "").strip()
        sites.setdefault(site or "(site not in the export)", []).append(pm)

    for site, placements in sorted(sites.items()):
        ids = ", ".join(str(pm.placement_id) for pm in placements)
        n = len(placements)
        buffer.review(
            rule_id="VID-001",
            domain=Domain.SCOPE,
            message=f"Check Remove VPAID on the site {site}",
            placement_name=f"Site {site} · {n} video placement{'s' if n != 1 else ''}",
            expected=f"{WHERE} = Remove VPAID",
            actual=f"QA2 can't read this setting yet. Video placements on this site: {ids}",
            reason=(f"{base_account(account)} video goes out without VPAID, and it is set "
                    "once per site, not per placement."),
            recommended_action=(f"Open the site's {WHERE} in Innovid, confirm it says "
                                "Remove VPAID, and approve this."),
        )

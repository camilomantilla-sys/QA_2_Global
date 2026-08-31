"""
Matching Engine.

Establece los vinculos entre el Expected (TS) y el Actual (export Innovid).
NO emite veredictos de negocio: eso es el Rule Engine.

Principios:
  - Solo se matchea el SCOPE TRABAJADO. El contexto no se toca.
  - Sin match fuerte no hay FAIL posible (gating por confianza).
  - Todo link guarda su MatchTrace: llaves intentadas, ganadora, descartados.
  - Sin match no es "mismatch": es only_expected / only_actual.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from core.colors import GREEN, RED
from core.normalize import norm_compare, norm_dims, split_platform_id
from core.urls import (
    AttributionTriangle, URLComparison, check_triangle, compare_urls,
)

CONF_HIGH = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW = "LOW"
CONF_NONE = "NONE"

_EXT = re.compile(r"\.(jpg|jpeg|png|gif|mp4|mov|webm|html|htm|zip|svg)$", re.I)

def norm_creative(value: object) -> str:
    """Forma canonica para comparar nombres de creativo y filenames."""
    s = norm_compare(str(value or ""))
    return _EXT.sub("", s).strip()

# ------------------------------------------------------------------ modelo

@dataclass
class ExpectedCreative:
    name: str = ""
    creative_id: str = ""
    universal_ad_id: str = ""
    intent: str = ""          # GREEN | RED
    ts_row: int = 0
    ts_sheet: str = ""
    url: str = ""             # URL completa declarada en la TS
    cgen: str = ""            # CGENS declarado en la TS
    dims: str = ""            # <-- NUEVA

    @property
    def key_norm(self) -> str:
        return norm_creative(self.name)

@dataclass
class ExpectedPlacement:
    placement_id: str
    name: str = ""
    site: str = ""
    dims: str = ""
    start: date | None = None
    end: date | None = None
    cgen: str = ""
    group_name: str = ""
    impl_type: str = ""
    fmt: str = ""
    request_type: str = ""
    visual_review: bool = False
    source: str = ""
    creatives: list[ExpectedCreative] = field(default_factory=list)
    ts_rows: list[int] = field(default_factory=list)

    @property
    def green(self) -> list[ExpectedCreative]:
        return [c for c in self.creatives if c.intent == GREEN]

    @property
    def red(self) -> list[ExpectedCreative]:
        return [c for c in self.creatives if c.intent == RED]

@dataclass
class ActualCreative:
    creative_id: str = ""
    filename: str = ""
    name: str = ""
    third_party_id: str = ""
    creative_type: str = ""
    enabled: bool | None = None
    status: str = ""
    group_name: str = ""
    group_id: str = ""
    row_type: str = ""
    clicktags: list[str] = field(default_factory=list)
    export_row: int = 0

    @property
    def running(self) -> bool:
        """
        Un creativo NO esta corriendo si se cumple cualquiera de las tres:
          Enabled = No
          Status  = Disabled / Inactive
          sin Decision_Tree_Name (no esta en ningun arbol)

        En Adobe, al hacer CREATIVE_ADD los creativos previos quedan
        asignados al dtree pero con Status=Disabled: siguen en el export
        y no corren. Sin esta regla se leerian como activos (bug B40).
        """
        if self.enabled is False:
            return False
        if norm_compare(self.status) in ("disabled", "inactive", "paused"):
            return False
        return True

    @property
    def state_label(self) -> str:
        if self.enabled is False:
            return "Enabled=No"
        s = norm_compare(self.status)
        if s in ("disabled", "inactive", "paused"):
            return f"Status={self.status}"
        if not self.group_name:
            return "sin arbol"
        return f"activo ({self.status or 'Active'})"

    @property
    def clicktag_1(self) -> str:
        return self.clicktags[0] if self.clicktags else ""


    @property
    def keys_norm(self) -> set[str]:
        out = set()
        if self.filename:
            out.add(norm_creative(self.filename))
        if self.name:
            out.add(norm_creative(self.name))
        return out

@dataclass
class ActualPlacement:
    placement_id: str
    name: str = ""
    name_norm: str = ""
    site: str = ""
    dims: str = ""
    start: date | None = None
    end: date | None = None
    status: str = ""
    placement_type: str = ""
    group_name: str = ""
    group_id: str = ""
    third_party_id: str = ""       # nivel placement
    clicktags: list[str] = field(default_factory=list)
    impressions: list[str] = field(default_factory=list)
    creatives: list[ActualCreative] = field(default_factory=list)
    export_rows: list[int] = field(default_factory=list)
    from_placement_level: bool = False

# ------------------------------------------------------------------ trace

@dataclass
class MatchTrace:
    entity: str = ""
    keys_tried: list[str] = field(default_factory=list)
    winner: str = ""
    left: str = ""
    right: str = ""
    discarded: list[str] = field(default_factory=list)
    note: str = ""

@dataclass
class CreativeLink:
    expected: ExpectedCreative
    actual: ActualCreative | None
    confidence: str = CONF_NONE
    trace: MatchTrace = field(default_factory=MatchTrace)
    url: URLComparison | None = None
    triangle: AttributionTriangle | None = None

@dataclass
class PlacementMatch:
    placement_id: str
    expected: ExpectedPlacement
    actual: ActualPlacement | None
    confidence: str = CONF_NONE
    group_match: str = ""
    group_trace: MatchTrace = field(default_factory=MatchTrace)
    creative_links: list[CreativeLink] = field(default_factory=list)
    actual_extra: list[ActualCreative] = field(default_factory=list)
    trace: MatchTrace = field(default_factory=MatchTrace)

    @property
    def extra_running(self) -> list[ActualCreative]:
        """Extras que SI estan corriendo: no declarados en la TS -> REVIEW."""
        return [c for c in self.actual_extra if c.running]

    @property
    def extra_stopped(self) -> list[ActualCreative]:
        """Extras desactivados: preexistentes normales -> INFO."""
        return [c for c in self.actual_extra if not c.running]

@dataclass
class MatchResult:
    scope_guard: str = ""            # OK | MISMATCH | UNKNOWN
    scope_evidence: str = ""
    ts_campaign_id: str = ""
    export_campaign_id: str = ""
    matched: list[PlacementMatch] = field(default_factory=list)
    only_expected: list[ExpectedPlacement] = field(default_factory=list)
    only_actual_in_scope: list[ActualPlacement] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    confidence_counts: dict[str, int] = field(default_factory=dict)
    group_counts: dict[str, int] = field(default_factory=dict)
    creative_conf_counts: dict[str, int] = field(default_factory=dict)
    expected_total: int = 0
    actual_total: int = 0
    url_counts: dict[str, int] = field(default_factory=dict)
    triangle_counts: dict[str, int] = field(default_factory=dict)
    extra_running_total: int = 0
    extra_stopped_total: int = 0

    @property
    def blocked(self) -> bool:
        return self.scope_guard == "MISMATCH"

# ------------------------------------------------------------------ Expected

def build_expected(ts) -> dict[str, ExpectedPlacement]:
    """
    Expected Model, solo con los placements TRABAJADOS.

    El export puede traer 1380 placements, pero si solo se trabajaron 48,
    unicamente esos 48 se validan. Lo no trabajado no se revisa.

    Creativos, URL y CGEN esperados:
      Variante B  -> Placements: creative_names + cgen (nivel placement)
      Variante A  -> Creative Rotations, via el grupo que declara el placement,
                     filtrando por dimension (bug B39)
    """
    from parsers.ts_parser import REQ_NOT_WORKED

    out: dict[str, ExpectedPlacement] = {}
    if ts.placements is None:
        return out

    worked = {pid for pid, sc in ts.scope.items()
              if sc.request_type != REQ_NOT_WORKED}

    # WPP / Unilever / Wendy's:
    # Creative Rotations contiene el Landing Page Name, no la URL final.
    # La URL autoritativa vive en la pestaña Landing Pages.
    landing_page_urls: dict[str, str] = {}

    if getattr(ts, "landing_pages", None) is not None:
        for lp_row in ts.landing_pages.rows:
            lp_name = norm_compare(
                str(lp_row.values.get("lp_name") or "")
            )
            lp_url = str(lp_row.values.get("lp_url") or "").strip()

            if lp_name and lp_url:
                landing_page_urls[lp_name] = lp_url

    # --- creativos con intencion, indexados por grupo (Creative Rotations)
    by_group: dict[str, list[ExpectedCreative]] = {}
    if ts.rotations is not None:
        for row in ts.rotations.rows:
            if row.intent not in (GREEN, RED, "SWAP"):
                continue
            g = norm_compare(str(row.values.get("group_name") or ""))
            if not g:
                continue
            intent = GREEN if row.intent in (GREEN, "SWAP") else RED
            by_group.setdefault(g, []).append(ExpectedCreative(
                name=str(row.values.get("creative_name") or ""),
                creative_id=str(row.values.get("creative_id") or ""),
                universal_ad_id=str(row.values.get("universal_ad_id") or ""),
                intent=intent, ts_row=row.row, ts_sheet=ts.rotations.sheet,
                # Adobe Decision Tree:
                # Landing Page Name contiene la URL completa.
                #
                # WPP / Unilever / Wendy's:
                # Landing Page Name contiene una referencia que debe
                # resolverse contra la pestaña Landing Pages.
                url=(
                    landing_page_urls.get(
                        norm_compare(
                            str(row.values.get("lp_url") or "")
                        ),
                        "",
                    )
                    if ts.profile == "wpp_standard"
                    else str(row.values.get("lp_url") or "")
                ),
                cgen=str(row.values.get("cgen") or ""),
                dims=norm_dims(row.values.get("dims_or_duration")),
            ))

    # --- placements trabajados
    for row in ts.placements.rows:
        pid = str(row.values.get("placement_id") or "")
        if not pid or pid not in worked:
            continue

        ep = out.get(pid)
        if ep is None:
            sc = ts.scope[pid]
            ep = ExpectedPlacement(
                placement_id=pid,
                name=str(row.values.get("placement_name") or ""),
                site=str(row.values.get("site") or ""),
                dims=norm_dims(row.values.get("dimensions")),
                start=row.values.get("start_date"),
                end=row.values.get("end_date"),
                cgen=str(row.values.get("cgen") or ""),
                group_name=str(row.values.get("group_name") or ""),
                impl_type=row.impl_type, fmt=row.fmt,
                request_type=sc.request_type,
                visual_review=sc.visual_review, source=sc.source,
            )
            out[pid] = ep
        ep.ts_rows.append(row.row)

        # el grupo o el cgen pueden venir en cualquiera de las filas
        if not ep.group_name and row.values.get("group_name"):
            ep.group_name = str(row.values.get("group_name"))
        if not ep.cgen and row.values.get("cgen"):
            ep.cgen = str(row.values.get("cgen"))

        # creativos declarados a nivel placement (Variante B)
        cname = str(row.values.get("creative_names") or "")
        if cname and row.intent in (GREEN, RED, "SWAP"):
            intent = GREEN if row.intent in (GREEN, "SWAP") else RED
            ep.creatives.append(ExpectedCreative(
                name=cname, intent=intent,
                ts_row=row.row, ts_sheet=ts.placements.sheet,
                # Adobe Direct / Site-Served:
                # CGEN y Landing Page viven a nivel placement.
                url=str(row.values.get("lp_ref") or ""),
                cgen=str(row.values.get("cgen") or ""),
                dims=norm_dims(row.values.get("dimensions")),
            ))

    # --- inyectar los creativos del grupo que el placement declara,
    #     FILTRANDO por dimension.
    #
    # Un grupo de Adobe contiene los creativos de todos los tamanos
    # (8 conceptos x 5 tamanos = 40). Un placement de 160x600 solo sirve
    # los 8 de 160x600. Sin este filtro se esperan 40 y solo matchean 8,
    # generando 32 falsos "creativo faltante" por placement (bug B39).
    for ep in out.values():
        g = norm_compare(ep.group_name)
        if not g:
            continue
        have = {c.key_norm for c in ep.creatives}
        for c in by_group.get(g, []):
            if not c.key_norm or c.key_norm in have:
                continue
            if ep.dims and c.dims and ep.dims != c.dims:
                continue
            ep.creatives.append(c)
            have.add(c.key_norm)

    return out
# ------------------------------------------------------------------ Actual

def build_actual(export_pc, export_pl=None) -> dict[str, ActualPlacement]:
    """
    Actual Model desde los exports de Innovid.
      export_pc: Placement-Creative  (creativos, dtree, status por creativo)
      export_pl: Placement           (URL de 1x1, integracion de pixel)
    """
    out: dict[str, ActualPlacement] = {}

    if export_pc is not None:
        for row in export_pc.rows:
            pid = str(row.values.get("placement_id") or "")
            if not pid:
                continue
            ap = out.get(pid)
            if ap is None:
                pname = str(row.values.get("placement_name") or "")
                nname, _ = split_platform_id(pname)
                ap = ActualPlacement(
                    placement_id=pid, name=pname, name_norm=nname,
                    site=str(row.values.get("site") or ""),
                    dims=norm_dims(row.values.get("dimensions")),
                    start=row.values.get("start_date"),
                    end=row.values.get("end_date"),
                    status=str(row.values.get("status") or ""),
                    placement_type=str(row.values.get("placement_type") or ""),
                )
                out[pid] = ap
            ap.export_rows.append(row.row)

            gname = str(row.values.get("group_name_norm")
                        or row.values.get("group_name") or "")
            gid = str(row.values.get("group_id") or "")
            if gname and not ap.group_name:
                ap.group_name = gname
                ap.group_id = gid

            if row.row_type == "PLACEMENT_HEADER":
                continue

            ap.creatives.append(ActualCreative(
                creative_id=str(row.values.get("creative_id") or ""),
                filename=str(row.values.get("filename") or ""),
                name=str(row.values.get("creative_name") or ""),
                third_party_id=str(row.values.get("third_party_id") or ""),
                creative_type=str(row.values.get("creative_type") or ""),
                enabled=row.values.get("enabled"),
                status=str(row.values.get("status") or ""),
                group_name=gname, group_id=gid,
                row_type=row.row_type,
                clicktags=list(row.multi.get("clicktag", [])),
                export_row=row.row,
            ))

    if export_pl is not None:
        for row in export_pl.rows:
            pid = str(row.values.get("placement_id") or "")
            if not pid:
                continue
            ap = out.get(pid)
            if ap is None:
                ap = ActualPlacement(
                    placement_id=pid,
                    name=str(row.values.get("placement_name") or ""),
                    site=str(row.values.get("site") or ""),
                    dims=norm_dims(row.values.get("dimensions")),
                    start=row.values.get("start_date"),
                    end=row.values.get("end_date"),
                    status=str(row.values.get("status") or ""),
                    placement_type=str(row.values.get("placement_type") or ""),
                    from_placement_level=True,
                )
                ap.name_norm, _ = split_platform_id(ap.name)
                out[pid] = ap
            ap.third_party_id = str(row.values.get("third_party_id") or "")
            ap.clicktags = list(row.multi.get("clicktag", []))
            ap.impressions = list(row.multi.get("third_party_impression", []))
            if not ap.status:
                ap.status = str(row.values.get("status") or "")

    return out

# ------------------------------------------------------------------ L3 grupo

def _match_group(ep: ExpectedPlacement, ap: ActualPlacement,
                 ts_declares_groups: bool = True) -> tuple[str, MatchTrace]:
    """
    ts_declares_groups: la TS de este perfil TIENE columna de grupo.
    Si no la tiene (Adobe Variante B), la ausencia no es un hallazgo:
    es que el formato no declara grupos. Corrige el bug B37.
    """
    t = MatchTrace(entity="group", left=ep.group_name, right=ap.group_name)

    if not ts_declares_groups:
        t.winner = "n/a"
        t.note = ("el formato de TS no declara grupos: los dtrees del export "
                  "no se validan contra la TS")
        return "NOT_DECLARED", t

    if not ep.group_name and not ap.group_name:
        t.winner = "n/a"
        t.note = "ninguno declara grupo (asignacion directa o 1x1)"
        return "N/A", t

    if ep.group_name and not ap.group_name:
        t.winner = "none"
        t.note = "la TS declara grupo y el export no lo tiene"
        return "MISSING", t

    if not ep.group_name and ap.group_name:
        t.winner = "none"
        t.note = "el export tiene grupo y la TS lo dejo vacio"
        return "EXTRA", t

    t.keys_tried.append("group_name_norm")
    exp_name, exp_id = split_platform_id(ep.group_name)
    if norm_compare(exp_name) == norm_compare(ap.group_name):
        t.winner = "group_name_norm"
        if exp_id and ap.group_id:
            t.keys_tried.append("decision_tree_id")
            if exp_id == ap.group_id:
                t.note = f"nombre + Dtree_ID {ap.group_id} coinciden"
                return "OK", t
            t.note = f"nombre coincide pero Dtree_ID difiere ({exp_id} vs {ap.group_id})"
            return "MISMATCH", t
        t.note = f"nombre coincide, Dtree_ID no verificable (export: {ap.group_id or '-'})"
        return "NAME_ONLY", t

    t.discarded.append(f"'{ap.group_name}' != '{exp_name}'")
    t.note = "nombre de grupo distinto (sin fuzzy por diseno)"
    return "MISMATCH", t

# ------------------------------------------------------------------ L4 creativo

def _match_creatives(ep: ExpectedPlacement,
                     ap: ActualPlacement) -> tuple[list[CreativeLink], list[ActualCreative]]:
    links: list[CreativeLink] = []
    pool = list(ap.creatives)
    used: set[int] = set()

    # indices
    by_id = {c.creative_id: i for i, c in enumerate(pool) if c.creative_id}
    by_norm: dict[str, list[int]] = {}
    for i, c in enumerate(pool):
        for k in c.keys_norm:
            by_norm.setdefault(k, []).append(i)

    for ec in ep.creatives:
        t = MatchTrace(entity="creative", left=ec.name or ec.creative_id)
        hit = None
        conf = CONF_NONE

        # 1. creative_id
        if ec.creative_id:
            t.keys_tried.append("creative_id")
            i = by_id.get(ec.creative_id)
            if i is not None and i not in used:
                hit, conf = i, CONF_HIGH
                t.winner = "creative_id"

        # 2. universal_ad_id
        if hit is None and ec.universal_ad_id:
            t.keys_tried.append("universal_ad_id")
            for i, c in enumerate(pool):
                if i in used:
                    continue
                if c.creative_id == ec.universal_ad_id:
                    hit, conf = i, CONF_HIGH
                    t.winner = "universal_ad_id"
                    break

        # 3. filename / creative_name normalizados
        if hit is None and ec.key_norm:
            t.keys_tried.append("filename_or_name_norm")
            cands = [i for i in by_norm.get(ec.key_norm, []) if i not in used]
            if len(cands) == 1:
                hit, conf = cands[0], CONF_MEDIUM
                t.winner = "filename_or_name_norm"
            elif len(cands) > 1:
                hit, conf = cands[0], CONF_LOW
                t.winner = "filename_or_name_norm (ambiguo)"
                t.discarded = [f"{len(cands)} candidatos con el mismo nombre"]

        if hit is not None:
            used.add(hit)
            ac = pool[hit]
            t.right = ac.filename or ac.name or ac.creative_id
            links.append(CreativeLink(expected=ec, actual=ac,
                                      confidence=conf, trace=t))
        else:
            t.note = "sin match: no esta en el placement"
            links.append(CreativeLink(expected=ec, actual=None,
                                      confidence=CONF_NONE, trace=t))

    extra = [c for i, c in enumerate(pool) if i not in used]
    return links, extra

# ------------------------------------------------------------------ orquestacion

def match(ts, export_pc, export_pl=None) -> MatchResult:
    res = MatchResult()

    # ---- L0 Scope Guard
    ts_cid = str(ts.campaign_info.get("campaignid") or "")
    ex_cid = ""
    for src in (export_pc, export_pl):
        if src is not None and src.metadata.get("campaignid"):
            ex_cid = str(src.metadata["campaignid"])
            break
    res.ts_campaign_id, res.export_campaign_id = ts_cid, ex_cid

    if not ts_cid or not ex_cid:
        res.scope_guard = "UNKNOWN"
        res.scope_evidence = (f"TS campaign_id='{ts_cid or 'ausente'}' · "
                              f"export='{ex_cid or 'ausente'}'")
    elif ts_cid == ex_cid:
        res.scope_guard = "OK"
        res.scope_evidence = f"campaign_id {ts_cid} coincide"
    else:
        res.scope_guard = "MISMATCH"
        res.scope_evidence = (f"TS declara {ts_cid} y el export {ex_cid}: "
                              f"son campanas distintas")
        return res

    expected = build_expected(ts)
    actual = build_actual(export_pc, export_pl)
    res.expected_total = len(expected)
    res.actual_total = len(actual)

    # ¿el formato de esta TS declara grupos?
    ts_declares_groups = bool(
        ts.placements and ts.placements.cmap
        and ts.placements.cmap.has("group_name")
    ) or ts.rotations is not None

    # ---- L1 Placement
    for pid, ep in sorted(expected.items()):
        ap = actual.get(pid)
        t = MatchTrace(entity="placement", keys_tried=["campaign+placement_id"],
                       left=pid, right=pid if ap else "")

        if ap is None:
            t.winner = "none"
            t.note = "el placement esperado no esta en el export"
            res.only_expected.append(ep)
            res.confidence_counts[CONF_NONE] = \
                res.confidence_counts.get(CONF_NONE, 0) + 1
            continue

        t.winner = "placement_id"
        t.note = f"{len(ap.export_rows)} filas en el export"
        pm = PlacementMatch(placement_id=pid, expected=ep, actual=ap,
                            confidence=CONF_HIGH, trace=t)

        gm, gt = _match_group(ep, ap, ts_declares_groups=ts_declares_groups)
        pm.group_match, pm.group_trace = gm, gt
        res.group_counts[gm] = res.group_counts.get(gm, 0) + 1

        pm.creative_links, pm.actual_extra = _match_creatives(ep, ap)

        # Contar extras una sola vez por placement.
        res.extra_running_total += len(pm.extra_running)
        res.extra_stopped_total += len(pm.extra_stopped)

        for cl in pm.creative_links:
            res.creative_conf_counts[cl.confidence] = \
                res.creative_conf_counts.get(cl.confidence, 0) + 1

            # solo los VERDES deben tener URL y CGEN correctos.
            # los rojos se van, no importa a donde apuntaban.
            if cl.expected.intent != GREEN:
                continue

            # ---- L6 URL: TS 'Landing Page Name' vs Clicktag_1 del creativo
            actual_tags = cl.actual.clicktags if cl.actual else []
            # en 1x1 el ClickTag vive a nivel placement
            if not actual_tags and ap.clicktags:
                actual_tags = ap.clicktags
            actual_url = actual_tags[0] if actual_tags else ""

            cl.url = compare_urls(cl.expected.url, actual_url)
            res.url_counts[cl.url.result] = \
                res.url_counts.get(cl.url.result, 0) + 1

            # ---- L7 triangulo: TS.CGENS == Export.Third_Party_ID == sdid
            exp_cgen = cl.expected.cgen or ep.cgen
            act_tpid = (cl.actual.third_party_id if cl.actual else "") \
                       or ap.third_party_id
            cl.triangle = check_triangle(exp_cgen, act_tpid, actual_url)
            res.triangle_counts[cl.triangle.result] = \
                res.triangle_counts.get(cl.triangle.result, 0) + 1

        res.matched.append(pm)
        res.confidence_counts[CONF_HIGH] = \
            res.confidence_counts.get(CONF_HIGH, 0) + 1

    return res
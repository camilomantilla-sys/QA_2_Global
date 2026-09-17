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
from dataclasses import dataclass, field, replace
from datetime import date

from core.colors import GREEN, RED, WHITE
from core.normalize import dims_match, norm_compare, norm_dims, split_platform_id
from core.urls import (
    AttributionTriangle, URLComparison, check_triangle, compare_urls,
)

CONF_HIGH = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW = "LOW"
CONF_NONE = "NONE"

_EXT = re.compile(r"\.(jpg|jpeg|png|gif|mp4|mov|webm|html|htm|zip|svg)$", re.I)

# El sello que Innovid pega al subir el archivo: el uuid del asset y
# su id numerico. Se exige la forma completa del uuid a proposito --
# recortar cualquier "__loquesea" final se llevaria por delante
# nombres reales, y estos creativos se distinguen justamente por el
# ultimo tramo del nombre (_Refresh, _Renew, _Uplift...). El id
# numerico es opcional: no todas las subidas lo traen.
_UPLOAD_STAMP = re.compile(
    r"__[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"(?:__\d+)?$",
    re.I,
)
_IS_DEFAULT = re.compile(r"\bdefault\b", re.I)

def _as_date(value: object) -> date | None:
    """
    Deja pasar solo fechas reales.

    La capa de extraccion ya convierte las columnas kind="date", pero
    una celda con texto libre ("TBD", "ver correo") llega tal cual. Si
    eso se colara como fecha, la comparacion con Innovid reventaria o,
    peor, compararia contra basura.
    """
    return value if isinstance(value, date) else None


def norm_creative(value: object) -> str:
    """
    Forma canonica para comparar nombres de creativo y filenames.

    Innovid elimina los espacios al generar el filename del creativo
    ('4X5 TO 9X16' en la TS -> '4X5TO9X16' en el export), aunque el
    resto del nombre sea identico. Sin colapsar los espacios aqui,
    match_creatives fallaba y reportaba el creativo como faltante
    (falso FAIL en CRE-001 / URL-001).

    Al subir el archivo, Innovid le pega ademas su propio sello:
    "__<uuid>__<id>.zip". La TS nunca lo lleva -- nadie lo escribe a
    mano, lo genera Innovid -- asi que el mismo creativo llegaba con
    dos nombres distintos a cada lado y se reportaba a la vez como
    "no esta en Innovid" y "no esta en la Traffic Sheet". En la
    solicitud de Dove lo traian 320 de las 1113 filas del export.
    """
    s = norm_compare(str(value or ""))
    s = _EXT.sub("", s).strip()
    s = _UPLOAD_STAMP.sub("", s).strip()
    return re.sub(r"\s+", "", s)

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

    # Vuelo declarado para ESTE creativo en Creative Rotations, que
    # puede diferir del vuelo del placement: una rotacion secuencial
    # declara un creativo del 14 al 26 y otro del 27 en adelante.
    # Ningun export los trae -- solo el decision set de Innovid.
    start: date | None = None
    end: date | None = None
    rotation_weight: str = ""
    sequence: str = ""
    dims: str = ""            # <-- NUEVA

    # El default ad, enganchado por dimension y no declarado por el
    # placement. Vive en su propio decision set -- el oficial de su
    # dimension -- asi que no reparte el 100% de rotacion con los
    # creativos que el placement si declara. Sin distinguirlo, un
    # grupo con un solo creativo asignado mas su default salia 50/50
    # cuando el asignado se lleva el 100%.
    is_default: bool = False

    # Que celdas venian pintadas en la TS. La hoja marca el CAMPO que
    # cambia, no la fila entera: un cambio de rotacion pinta solo la
    # celda de Rotation (%) sobre un creativo que ya existia. Sin
    # esto, las reglas leen esas filas como creativos nuevos y
    # validan el creativo entero en vez de lo que se pidio.
    intent_fields: frozenset[str] = frozenset()

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

    # "Vendors / Pixels" tal cual lo escribio la TS. De ahi sale si la
    # solicitud pide DV Blocking, que es lo unico que se implementa
    # con un Verification Partner en Innovid.
    vendors: str = ""
    impl_type: str = ""
    fmt: str = ""
    request_type: str = ""
    # URL declarada para el placement cuando lo unico que se trabajo fue
    # la landing page. En ese caso la TS no declara creativos, asi que
    # esta es la unica URL esperada que existe.
    url: str = ""
    # El unico cambio de landing page que alcanza a este placement es el
    # del default ad, que es un creativo aparte: no se puede validar
    # contra el clicktag del placement.
    url_is_default_only: bool = False
    # Adobe escribe la URL entera en la columna "Landing Page" de
    # Placements, en vez de un nombre que se resuelva contra la
    # pestaña Landing Pages -- que en sus TS viene vacia. Se guarda
    # aparte de `url` para que la cadena de la TS siga mandando cuando
    # existe, y esto solo entre cuando no hay nada mas.
    inline_url: str = ""
    # De que fila salio cada uno: de una de esta solicitud, o de una
    # vieja que quedo en gris mas arriba en la misma hoja.
    group_name_in_scope: bool = False
    cgen_in_scope: bool = False
    vendors_in_scope: bool = False
    inline_url_in_scope: bool = False
    visual_review: bool = False
    source: str = ""
    creatives: list[ExpectedCreative] = field(default_factory=list)
    ts_rows: list[int] = field(default_factory=list)
    # Los creativos PEDIDOS -- verdes o rojos -- de la rotacion que
    # este placement declara que se descartaron por no ser de su
    # dimension. Un grupo de Adobe trae los 5 tamanos y descartar los
    # otros 4 es correcto; descartarlos TODOS quiere decir que la
    # rotacion que el placement nombra no es de su tamano, y eso no se
    # puede quedar callado. Lo lee PLC-007.
    dims_dropped: list[tuple[str, str]] = field(default_factory=list)

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

    # La dimension de ESTE creativo, no la del placement.
    #
    # El export la trae por fila y no se estaba leyendo, asi que un
    # creativo servido a un tamano distinto del que pidio la Traffic
    # Sheet no tenia como salir a la luz: las unicas columnas de
    # dimensiones del Excel son las del placement, iguales en todas
    # sus filas. Camilo firmo un mismatch de 728x90 contra 720x50 y el
    # Excel le mostro los dos lados identicos.
    dims: str = ""

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

    @property
    def running(self) -> bool:
        """Un placement detenido no esta sirviendo, corran o no sus creativos."""
        return norm_compare(self.status) not in (
            "stopped", "disabled", "inactive", "paused"
        )

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
    # El pixel 1x1 generico de un placement site-served. Innovid lo
    # emite como una fila de creativo, pero no es un creativo: es el
    # placement. Va aparte de `actual_extra` porque contarlo como
    # extra reportaba "creativo no declarado en la TS" en todos los
    # 1x1 de Adobe, que es justo como se trafican.
    actual_trackers: list[ActualCreative] = field(default_factory=list)
    trace: MatchTrace = field(default_factory=MatchTrace)

    # Adobe Direct / Site-Served: la TS no declara creativos (Creative
    # Names = "N/A"), asi que no hay CreativeLink donde colgar la URL
    # ni la atribucion, y las dos quedaban sin revisar. Aqui van las
    # del placement: su clicktag y su CGEN.
    url: URLComparison | None = None
    triangle: AttributionTriangle | None = None

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
    from parsers.ts_parser import REQ_CREATIVE_REMOVE, REQ_NOT_WORKED

    out: dict[str, ExpectedPlacement] = {}
    if ts.placements is None:
        return out

    worked = {pid for pid, sc in ts.scope.items()
              if sc.request_type != REQ_NOT_WORKED}

    # WPP / Unilever / Wendy's:
    # Creative Rotations contiene el Landing Page Name, no la URL final.
    # La URL autoritativa vive en la pestaña Landing Pages.
    landing_page_urls: dict[str, str] = {}
    green_landing_page_urls: dict[str, str] = {}

    if getattr(ts, "landing_pages", None) is not None:
        for lp_row in ts.landing_pages.rows:
            lp_name = norm_compare(
                str(lp_row.values.get("lp_name") or "")
            )
            lp_url = str(lp_row.values.get("lp_url") or "").strip()

            if lp_name and lp_url:
                landing_page_urls[lp_name] = lp_url

                # La fila VERDE es la URL nueva del swap. Es la unica que
                # sirve como valor esperado: la roja es la que se va.
                if lp_row.intent in (GREEN, "SWAP"):
                    green_landing_page_urls[lp_name] = lp_url

    # --- creativos con intencion, indexados por grupo (Creative Rotations)
    by_group: dict[str, list[ExpectedCreative]] = {}
    if ts.rotations is not None:
        for row in ts.rotations.rows:
            # Los creativos en blanco de una rotacion trabajada no son
            # parte del cambio, pero si son el contenido del Decision
            # Set. Sin ellos el placement queda sin ningun creativo
            # esperado y todo lo que Innovid tiene aparece como "extra
            # creative", sin comparacion ni URL. Entran como contexto:
            # se muestran y se matchean, pero no generan hallazgos.
            if row.intent not in (GREEN, RED, "SWAP", WHITE):
                continue
            g = norm_compare(str(row.values.get("group_name") or ""))
            if not g:
                continue
            if row.intent == WHITE:
                intent = WHITE
            else:
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
                start=_as_date(row.values.get("start_date")),
                end=_as_date(row.values.get("end_date")),
                rotation_weight=str(row.values.get("rotation_weight") or ""),
                sequence=str(row.values.get("sequence") or ""),
                intent_fields=frozenset(row.intent_fields or ()),
            ))

    # --- lo que contiene un decision set cuya hoja esta oculta
    #
    # Un creativo blanco no es parte del cambio, pero SI es el
    # contenido del Decision Set, y sin el el placement se queda sin
    # ningun creativo esperado: todo lo que Innovid tiene sale como
    # "extra creative", sin comparacion, sin fechas y sin URL.
    #
    # En "TS_Q2-Q4 2026 Co Marketing" las 67 filas de Creative
    # Rotations estan ocultas, asi que no habia ninguno. Camilo, sobre
    # un swap de solo landing page: "los creativos blancos existentes
    # que andan activos me los lee como extra creatives... deberia
    # salir en creatives and assignment no?". Si.
    #
    # De una fila oculta se toma UNICAMENTE el creativo, y siempre
    # como contexto blanco. Ni un verde, ni un rojo: una fila oculta no
    # es parte de la solicitud, y esa regla no se toca. Es el mismo
    # criterio con el que se recupera el mapa grupo -> landing page.
    hidden_rotations = getattr(ts, "rotations_all", None)
    if hidden_rotations is not None:
        for row in hidden_rotations.rows:
            # Una fila gris NO se recupera. Recuperar es rellenar lo
            # que no se alcanzo a leer, no revivir lo que la TS
            # descarto a proposito: el gris es la forma en que
            # BlackRock retira el default viejo, y traerlo de vuelta
            # como blanco lo ponia otra vez a exigirse en Innovid,
            # donde ya no esta, y a ocupar el lugar del creativo que
            # si se pidio. Camilo: "sigue teniendo el problema de que
            # me trae grises a la app".
            if row.intent == "SCOPE_EXCLUDED":
                continue
            g = norm_compare(str(row.values.get("group_name") or ""))
            if not g:
                continue
            nombre = str(row.values.get("creative_name") or "")
            cid = str(row.values.get("creative_id") or "")
            if not nombre and not cid:
                continue
            ya = {c.key_norm for c in by_group.get(g, ())}
            candidato = ExpectedCreative(
                name=nombre,
                creative_id=cid,
                universal_ad_id=str(row.values.get("universal_ad_id") or ""),
                intent=WHITE,
                ts_row=row.row,
                ts_sheet=hidden_rotations.sheet,
                url=(
                    landing_page_urls.get(
                        norm_compare(str(row.values.get("lp_url") or "")), ""
                    )
                    if ts.profile == "wpp_standard"
                    else str(row.values.get("lp_url") or "")
                ),
                cgen=str(row.values.get("cgen") or ""),
                dims=norm_dims(row.values.get("dims_or_duration")),
                start=_as_date(row.values.get("start_date")),
                end=_as_date(row.values.get("end_date")),
                rotation_weight=str(row.values.get("rotation_weight") or ""),
                sequence=str(row.values.get("sequence") or ""),
            )
            if candidato.key_norm and candidato.key_norm not in ya:
                by_group.setdefault(g, []).append(candidato)

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

        # El grupo, el CGEN, los vendors y la landing page pueden
        # venir en cualquiera de las filas del placement -- pero no en
        # cualquiera vale lo mismo.
        #
        # Un placement ocupa varias filas de la Traffic Sheet, y las
        # de arriba suelen ser solicitudes anteriores que quedaron en
        # gris. En un swap de BlackRock el mismo placement sale dos
        # veces: la vieja en gris con su rotacion de entonces, y la
        # nueva en verde con la rotacion que se acaba de hacer.
        # Quedarse con la primera fila que trajera algo tomaba la
        # rotacion vieja -- y con ella, sus creativos -- asi que el
        # swap que se pedia revisar no se comparaba con nada.
        _in_scope = row.intent != "SCOPE_EXCLUDED"

        def _prefer(field: str, value: str) -> None:
            """Lo pone si no habia nada, o si esta fila si es de hoy."""
            value = str(value or "").strip()
            if not value:
                return
            flag = f"{field}_in_scope"
            if getattr(ep, field) and not (
                _in_scope and not getattr(ep, flag)
            ):
                return
            setattr(ep, field, value)
            setattr(ep, flag, _in_scope)

        _prefer("group_name", row.values.get("group_name"))
        _prefer("cgen", row.values.get("cgen"))
        _prefer("vendors", row.values.get("vendors"))

        lp_ref = str(row.values.get("lp_ref") or "").strip()
        if lp_ref.lower().startswith(("http://", "https://")):
            _prefer("inline_url", lp_ref)

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
            if not dims_match(ep.dims, c.dims):
                if c.intent in (GREEN, RED, "SWAP"):
                    ep.dims_dropped.append((c.name, c.dims))
                continue
            # Si el placement entero va en rojo, lo que tenga asignado
            # se va con el.
            #
            # BlackRock marca el placement en rojo -- desasignar -- y
            # deja los creativos de su rotacion en blanco, porque esa
            # rotacion la comparten otros placements que siguen
            # corriendo. Mostrandolos como contexto, la fila del
            # placement que hay que apagar se leia igual que una que
            # no hay que tocar. Camilo: "su placement 10657690 esta en
            # rojo asi que toca desasignarlo".
            if ep.request_type == REQ_CREATIVE_REMOVE and c.intent == WHITE:
                c = replace(c, intent=RED)
            ep.creatives.append(c)
            have.add(c.key_norm)

    # --- el default ad, enganchado por dimension.
    #
    # No se declara en la columna de rotacion del placement: vive en su
    # propia rotacion, una por dimension ("300x600 Co-Marketing Default
    # Ad"). Sin engancharlo, el default que corre en la plataforma
    # aparecia como un extra sin nada contra que compararlo.
    default_by_dims: dict[str, list[ExpectedCreative]] = {}
    for group_key, group_creatives in by_group.items():
        if not _IS_DEFAULT.search(group_key):
            continue
        for creative in group_creatives:
            if creative.dims:
                default_by_dims.setdefault(creative.dims, []).append(creative)

    for ep in out.values():
        if not ep.dims:
            continue
        have = {c.key_norm for c in ep.creatives}
        for creative in default_by_dims.get(ep.dims, []):
            if not creative.key_norm or creative.key_norm in have:
                continue
            # Siempre como contexto, sea cual sea su color en la TS: el
            # placement no lo declara, se engancha por dimension. Si se
            # dejara con su intencion original, un default en verde
            # pasaria a ser exigible en todos los placements de esa
            # dimension y los que no lo llevan darian FAIL.
            ep.creatives.append(
                replace(
                    creative,
                    # Salvo que el placement entero se este
                    # desasignando: entonces su default tampoco va a
                    # servir nada, y mostrarlo en blanco hacia que la
                    # fila del placement que hay que apagar se leyera
                    # igual que una que no hay que tocar.
                    intent=(
                        RED
                        if ep.request_type == REQ_CREATIVE_REMOVE
                        else WHITE
                    ),
                    is_default=True,
                )
            )
            have.add(creative.key_norm)

    # --- URL esperada del placement, siguiendo la cadena de la TS.
    #
    # En un swap de solo URL la TS no declara ningun creativo: los
    # placements siguen activos y en blanco, y lo unico marcado es la
    # fila verde de Landing Pages. La cadena que conecta una con otra es
    #   placement -> creative rotation -> landing page name -> URL
    # y el placement puede referenciar la landing page directamente en su
    # propia columna, o a traves de la rotacion que declara.
    # El default ad se excluye a proposito: es un creativo independiente,
    # el mismo para todos los placements de su dimension, con su propia
    # landing page. Su swap es un cambio distinto del de la landing page
    # del placement, y mezclarlos hacia comparar el clicktag del creativo
    # principal contra la URL del default.
    for pid, ep in out.items():
        sc = ts.scope.get(pid)
        if sc is None:
            continue

        own: list[str] = []
        default_only: list[str] = []

        for group in sorted(sc.groups):
            if group.startswith("__lp__"):
                names = [group[6:]]
            else:
                gs = ts.groups.get(group)
                names = sorted(gs.lp_names) if gs else []

            for name in names:
                url = green_landing_page_urls.get(name)
                if not url:
                    continue
                target = default_only if _IS_DEFAULT.search(name) else own
                if url not in target:
                    target.append(url)

        if own:
            ep.url = own[0]
        elif ep.inline_url:
            # Adobe Direct / Site-Served: la pestaña Landing Pages
            # viene vacia y la URL esta escrita en la fila del
            # placement. Sin esto no habia URL esperada con que
            # comparar, y el clicktag del placement no se revisaba.
            ep.url = ep.inline_url
        elif default_only:
            ep.url_is_default_only = True

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
                dims=norm_dims(row.values.get("dimensions")),
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

            # El Placement View manda sobre el status del placement. El
            # export placement-creative trae en esa columna el status del
            # CREATIVO, y al llenarse primero tapaba el del placement: un
            # placement Stopped se leia Active porque su creativo seguia
            # activo. Eso hacia fallar la desasignacion (PLC-002) y la
            # remocion de creativos (CRE-001) en placements ya apagados.
            status = str(row.values.get("status") or "")
            if status:
                ap.status = status

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
        # Un 1x1 va asignado DIRECTO al placement: no tiene decision
        # set y no le falta ninguno. La TS le pone un Creative
        # Rotation Name igual, como guia de quien traficara, pero eso
        # es una etiqueta, no algo que tenga que existir en Innovid.
        # Reportarlo como grupo faltante marcaba los treinta 1x1 de
        # una solicitud correcta.
        if is_site_served_1x1(ep):
            t.winner = "n/a"
            t.note = (
                "1x1: the creative is assigned straight to the "
                "placement, so there is no decision set -- the Traffic "
                "Sheet's Creative Rotation Name is a label for the "
                "trafficker"
            )
            return "N/A", t

        t.winner = "none"
        t.note = "the TS declares a group and the export doesn't have one"
        return "MISSING", t

    if not ep.group_name and ap.group_name:
        t.winner = "none"
        t.note = "the export has a group and the TS left it empty"
        return "EXTRA", t

    t.keys_tried.append("group_name_norm")
    exp_name, exp_id = split_platform_id(ep.group_name)
    if norm_compare(exp_name) == norm_compare(ap.group_name):
        t.winner = "group_name_norm"
        if exp_id and ap.group_id:
            t.keys_tried.append("decision_tree_id")
            if exp_id == ap.group_id:
                t.note = f"name + Dtree_ID {ap.group_id} match"
                return "OK", t
            t.note = f"name matches but Dtree_ID differs ({exp_id} vs {ap.group_id})"
            return "MISMATCH", t
        t.note = f"name matches, Dtree_ID not verifiable (export: {ap.group_id or '-'})"
        return "NAME_ONLY", t

    t.discarded.append(f"'{ap.group_name}' != '{exp_name}'")
    t.note = "different group name (no fuzzy matching by design)"
    return "MISMATCH", t

# ------------------------------------------------------------------ L4 creativo

def is_site_served_1x1(expected) -> bool:
    """
    Un 1x1 de tracking servido por el sitio.

    Se mira el formato que ya derivo la TS y, como respaldo, las
    dimensiones: un 1x1 puede llegar por cualquiera de los dos, y
    equivocarse aqui significa pedir revision de algo correcto.
    """
    if expected is None:
        return False
    if norm_compare(getattr(expected, "fmt", "")) == "1x1":
        return True
    return norm_compare(getattr(expected, "dims", "")) == "1x1"


def placement_clicktags(ap: ActualPlacement) -> list[str]:
    """
    Los clicktags que gobiernan el placement.

    En un 1x1 el creativo va asignado DIRECTO al placement, asi que su
    clicktag es el del placement -- y el Placement View a menudo no
    trae ninguno. Mirando solo ahi, la URL de esas solicitudes se
    quedaba sin comparar con el export delante.
    """
    if ap is None:
        return []
    if ap.clicktags:
        return list(ap.clicktags)

    out: list[str] = []
    for creative in ap.creatives:
        if not creative.running:
            continue
        for tag in creative.clicktags:
            if tag and tag not in out:
                out.append(tag)
    return out


def _tracker_cgen(ap: ActualPlacement) -> str:
    """
    El CGEN que Innovid tiene para un placement site-served.

    En un 1x1 la fila de creativo es el pixel generico de la cuenta
    (1x1.gif, el mismo id para todas), pero su Third_Party_ID SI es
    el CGEN de ese placement. El Third_Party_ID del Placement View es
    otro campo distinto y no sirve de sustituto.
    """
    trackers = [ac for ac in ap.creatives if ac.row_type == "TRACKER"]
    if len(trackers) == 1 and trackers[0].third_party_id:
        return trackers[0].third_party_id
    return ""


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

def compare_placement(pm: PlacementMatch, res: "MatchResult") -> None:
    """
    Empareja los creativos de un placement y compara URL y atribucion.

    Vive aparte de `match()` para poder probarla con un placement
    armado a mano: aqui es donde se decide que se compara con que, y
    esas decisiones son las que han hecho falta afinar caso a caso.
    """
    ep, ap = pm.expected, pm.actual

    pm.creative_links, pm.actual_extra = _match_creatives(ep, ap)

    # El pixel 1x1 de un site-served no es un creativo de mas: es
    # como se trafica ese placement. Se saca de los extras y se
    # guarda aparte, para que siga siendo visible sin reportar
    # como hallazgo lo que la TS pidio tal cual.
    pm.actual_trackers = [
        c for c in pm.actual_extra if c.row_type == "TRACKER"
    ]
    if pm.actual_trackers:
        pm.actual_extra = [
            c for c in pm.actual_extra if c.row_type != "TRACKER"
        ]

    # Contar extras una sola vez por placement.
    res.extra_running_total += len(pm.extra_running)
    res.extra_stopped_total += len(pm.extra_stopped)

    for cl in pm.creative_links:
        res.creative_conf_counts[cl.confidence] = \
            res.creative_conf_counts.get(cl.confidence, 0) + 1

        # solo los VERDES deben tener URL y CGEN correctos.
        # los rojos se van, no importa a donde apuntaban.
        # Un creativo removido no tiene URL ni atribucion que
        # revisar. Los de contexto (en blanco) si: se muestran para
        # poder comparar, aunque no generen hallazgos.
        if cl.expected.intent == RED:
            continue

        # Site-served 1x1 (Placement_Type=Pixel, row_type
        # TRACKER): el creativo nombrado en la TS no aparece
        # nunca, porque Innovid sirve el pixel generico de la
        # cuenta -- pero esa fila SI trae el CGEN correcto de
        # este placement en su Third_Party_ID.
        tracker_cgen = _tracker_cgen(ap) if cl.actual is None else ""

        # Un creativo que no esta en Innovid no tiene URL ni CGEN
        # que comparar. CRE-001 ya dice que falta; anadir aqui un
        # fallo de URL y otro de atribucion convertia UN problema
        # en TRES, y los dos de mas quedaban redactados como si la
        # URL y el CGEN estuvieran mal. Peor aun: el CGEN "de
        # Innovid" salia siendo el Third_Party_ID del Placement
        # View (P3JPFSN), que es otro campo y no un CGEN, asi que
        # el mensaje comparaba dos cosas que no se comparan.
        if cl.actual is None and not tracker_cgen:
            continue

        # ---- L6 URL: TS 'Landing Page Name' vs Clicktag_1 del creativo
        actual_tags = cl.actual.clicktags if cl.actual else []
        # en 1x1 el ClickTag vive a nivel placement
        if not actual_tags:
            actual_tags = placement_clicktags(ap)
        actual_url = actual_tags[0] if actual_tags else ""

        cl.url = compare_urls(cl.expected.url, actual_url)
        res.url_counts[cl.url.result] = \
            res.url_counts.get(cl.url.result, 0) + 1

        # ---- L7 triangulo: TS.CGENS == Export.Third_Party_ID == sdid
        exp_cgen = cl.expected.cgen or ep.cgen
        act_tpid = (
            cl.actual.third_party_id if cl.actual else ""
        ) or tracker_cgen

        cl.triangle = check_triangle(exp_cgen, act_tpid, actual_url)
        res.triangle_counts[cl.triangle.result] = \
            res.triangle_counts.get(cl.triangle.result, 0) + 1

    # --- URL y atribucion del PLACEMENT.
    #
    # Adobe Direct / Site-Served: la TS pone "N/A" en Creative
    # Names, el creativo es el pixel generico de la cuenta, y todo
    # lo que hay que revisar vive a nivel de placement -- la
    # landing page en su propia columna, el CGEN en la suya, y del
    # lado de Innovid el Clicktag_1 del Placement View y el
    # Third_Party_ID de la fila del pixel. Sin esto esas dos
    # comprobaciones no se hacian en ninguna solicitud de 1x1.
    # El placement se revisa cuando NINGUN creativo dio veredicto.
    #
    # No basta con "no hay creativos declarados": un swap de 1x1 deja
    # en la TS el creativo viejo en blanco, que en Innovid ya no esta,
    # asi que hay un link y ninguna comparacion. La URL del placement
    # estaba en el export, en el clicktag del creativo que si corre, y
    # nadie la miraba.
    if not any(cl.url is not None for cl in pm.creative_links):
        _tags = placement_clicktags(ap)
        placement_url = _tags[0] if _tags else ""

        if ep.url or placement_url:
            pm.url = compare_urls(ep.url, placement_url)
            res.url_counts[pm.url.result] = (
                res.url_counts.get(pm.url.result, 0) + 1
            )

        if ep.cgen:
            pm.triangle = check_triangle(
                ep.cgen,
                _tracker_cgen(ap) or ap.third_party_id,
                placement_url,
            )
            res.triangle_counts[pm.triangle.result] = (
                res.triangle_counts.get(pm.triangle.result, 0) + 1
            )


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
        res.scope_evidence = (f"TS campaign_id='{ts_cid or 'missing'}' · "
                              f"export='{ex_cid or 'missing'}'")
    elif ts_cid == ex_cid:
        res.scope_guard = "OK"
        res.scope_evidence = f"campaign_id {ts_cid} matches"
    else:
        # Adobe TS's declare Prisma/Advertising Cloud's own campaign ID
        # here, which is a different number space from Innovid's
        # ad-server-assigned Campaign ID in the export metadata -- the
        # two never match even for a perfectly correct pairing of
        # files. A hard abort on this alone used to zero out the whole
        # run (expected_total=0) for any such campaign. Report the
        # mismatch as evidence, but let placement-ID overlap (computed
        # below) be the real signal for whether these files belong
        # together -- a genuinely unrelated file naturally shows up as
        # 0 matched / all only_expected instead of a blank screen.
        res.scope_guard = "MISMATCH"
        res.scope_evidence = (f"TS declares {ts_cid} and the export {ex_cid}: "
                              f"different campaign IDs (informational only -- "
                              f"matching still runs by Placement ID)")

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
            t.note = "the expected placement isn't in the export"
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

        compare_placement(pm, res)

        res.matched.append(pm)
        res.confidence_counts[CONF_HIGH] = \
            res.confidence_counts.get(CONF_HIGH, 0) + 1

    return res
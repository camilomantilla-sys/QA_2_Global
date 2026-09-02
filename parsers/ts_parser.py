"""
Parser de Traffic Sheets.

Principios de negocio:
  - El color solo cuenta en la DATA REGION (hoja en scope, fila > header,
    columna de campo de intencion AdOps).
  - El scope de QA2 son los placements TRABAJADOS: color propio O
    referencia a un grupo con color (propagacion entre pestanas).
  - 1x1 site-served: creativo N/A o vacio es lo ESPERADO.
  - Placement con todos sus creativos en rojo -> REVISION VISUAL.
    AdOps no apaga placements ni los deja vacios; eso lo hace Digital.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.colors import (
    ACTIONABLE, GREEN, GREY, RED, UNKNOWN, WHITE, YELLOW,
    ColorResolver, inventory_region, read_workbook_theme,
)
from core.dates import resolve_date_column
from core.extraction import (
    ROW_DATA, ColumnMap, SheetSpec, classify_row, column_fill_rates,
    find_header_row, map_columns, read_sheet, resolve_sheet, sheet_states,
)
from core.normalize import clean_id, norm_compare, norm_dims, norm_key, norm_text
from core.provenance import Anomaly, Cell
from core.ts_schema import (
    FMT_DISPLAY, FMT_SITE_SERVED, FMT_UNKNOWN, FMT_VIDEO,
    IMPL_SITE_SERVED_1X1, IMPL_THIRD_PARTY, IMPL_UNKNOWN, NEVER_IN_SCOPE,
    PROFILES, SITE_TABLE_ANCHORS, TS_LANDING_PAGES, TS_PLACEMENTS,
    TS_ROTATIONS, TSProfile, format_from_dims,
)

# tipos de solicitud
REQ_NEW_PLACEMENT = "NEW_PLACEMENT"
REQ_CREATIVE_SWAP = "CREATIVE_SWAP"
REQ_CREATIVE_ADD = "CREATIVE_ADD"
REQ_CREATIVE_REMOVE = "CREATIVE_REMOVE"
REQ_URL_SWAP = "URL_SWAP"
REQ_FIELD_CHANGE = "FIELD_CHANGE"
REQ_NOT_WORKED = "NOT_WORKED"
REQ_REVIEW = "REVIEW"

# origen del trabajo
SRC_OWN = "color propio"
SRC_ROTATION = "propagado desde Creative Rotations"
SRC_LANDING = "propagado desde Landing Pages"
SRC_BOTH = "propio + propagado"

@dataclass
class TSRow:
    row: int
    values: dict[str, object] = field(default_factory=dict)
    colors: dict[str, str] = field(default_factory=dict)
    intent: str = WHITE
    intent_fields: list[str] = field(default_factory=list)
    inherited: set[str] = field(default_factory=set)
    impl_type: str = IMPL_UNKNOWN
    fmt: str = FMT_UNKNOWN

@dataclass
class GroupScope:
    """Un grupo/rotacion con intencion de cambio."""
    group_name: str
    green_creatives: int = 0
    red_creatives: int = 0
    white_creatives: int = 0
    rows: list[int] = field(default_factory=list)
    # Nombres de landing page que declara la rotacion. En el perfil WPP
    # la columna "Landing Page Name" de Creative Rotations trae un
    # NOMBRE que hay que resolver contra el tab Landing Pages; en Adobe
    # la misma columna trae la URL final. Se guarda tal cual y solo se
    # usa cuando coincide con un nombre real de landing page, asi que la
    # URL de Adobe nunca engancha por accidente.
    lp_names: set[str] = field(default_factory=set)

    @property
    def worked(self) -> bool:
        return bool(self.green_creatives or self.red_creatives)

    @property
    def intent(self) -> str:
        if self.green_creatives and self.red_creatives:
            return "SWAP"
        if self.green_creatives:
            return GREEN
        if self.red_creatives:
            return RED
        return WHITE

@dataclass
class PlacementScope:
    placement_id: str
    rows: list[int] = field(default_factory=list)
    request_type: str = REQ_NOT_WORKED
    impl_type: str = IMPL_UNKNOWN
    fmt: str = FMT_UNKNOWN
    green_rows: int = 0
    red_rows: int = 0
    white_rows: int = 0
    fields_touched: set[str] = field(default_factory=set)
    groups: set[str] = field(default_factory=set)
    source: str = ""
    visual_review: bool = False
    note: str = ""
    sample_name: str = ""

@dataclass
class TSSheetResult:
    sheet: str = ""
    header_row: int | None = None
    header_evidence: str = ""
    cmap: ColumnMap | None = None
    rows: list[TSRow] = field(default_factory=list)
    row_class_counts: dict[str, int] = field(default_factory=dict)
    fill_rates: dict[str, float] = field(default_factory=dict)
    date_diagnostics: dict[str, dict] = field(default_factory=dict)
    intent_counts: dict[str, int] = field(default_factory=dict)
    impl_counts: dict[str, int] = field(default_factory=dict)
    anomalies: list[Anomaly] = field(default_factory=list)
    merged_applied: int = 0

@dataclass
class TSResult:
    path: str = ""
    profile: str = ""
    profile_evidence: str = ""
    all_sheets: list[str] = field(default_factory=list)
    in_scope_sheets: list[str] = field(default_factory=list)
    out_of_scope_sheets: list[str] = field(default_factory=list)
    hidden_sheets: list[str] = field(default_factory=list)
    campaign_info: dict[str, str] = field(default_factory=dict)
    site_contacts: list[tuple[str, str]] = field(default_factory=list)
    placements: TSSheetResult | None = None
    rotations: TSSheetResult | None = None
    landing_pages: TSSheetResult | None = None
    groups: dict[str, GroupScope] = field(default_factory=dict)
    lp_worked: set[str] = field(default_factory=set)
    scope: dict[str, PlacementScope] = field(default_factory=dict)
    request_counts: dict[str, int] = field(default_factory=dict)
    format_counts: dict[str, int] = field(default_factory=dict)
    format_by_request: dict[tuple[str, str], int] = field(default_factory=dict)
    source_counts: dict[str, int] = field(default_factory=dict)
    theme_colors: dict[int, str] = field(default_factory=dict)
    region_palette: dict = field(default_factory=dict)
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def fatal(self) -> bool:
        return any(a.severity == "FATAL" for a in self.anomalies)

    @property
    def worked(self) -> list[PlacementScope]:
        return [s for s in self.scope.values() if s.request_type != REQ_NOT_WORKED]

# ------------------------------------------------------------------ hojas

def _split_sheets(path: Path) -> tuple[list[str], list[str], list[str]]:
    states = sheet_states(path)
    never = {norm_key(s) for s in NEVER_IN_SCOPE}
    in_scope, out_scope, hidden = [], [], []
    for name, st in states.items():
        if st != "visible":
            hidden.append(name)
        elif norm_key(name) in never:
            out_scope.append(name)
        else:
            in_scope.append(name)
    return in_scope, out_scope, hidden

# ------------------------------------------------------------------ deteccion

def detect_profile(path: Path) -> tuple[str, str]:
    """
    Senal 1: columna CGEN/CGENS en Placements O en Creative Rotations -> Adobe.
             Variante A lo tiene en Creative Rotations (header 'CGENS').
             Variante B lo tiene en Placements (header 'CGEN').
    Senal 2: Creative Rotations con datos -> A ; sin datos -> B.
    """
    in_scope, _o, _h = _split_sheets(path)
    pl_sheet = resolve_sheet(in_scope, ["Placements"])
    rot_sheet = resolve_sheet(in_scope, ["Creative Rotations", "Creative Rotation"])

    cgen_where = ""

    if pl_sheet:
        try:
            grid, _ = read_sheet(path, pl_sheet, capture_fill=False)
            hres, _ = find_header_row(grid, TS_PLACEMENTS)
            if hres.row:
                keys = {norm_key(t) for t in grid.row_text(hres.row)}
                if "cgen" in keys or "cgens" in keys:
                    cgen_where = "Placements"
        except Exception:
            pass

    rot_has_data = False
    if rot_sheet:
        try:
            grid, _ = read_sheet(path, rot_sheet, capture_fill=False)
            hres, _ = find_header_row(grid, TS_ROTATIONS)
            if hres.row:
                keys = {norm_key(t) for t in grid.row_text(hres.row)}
                if not cgen_where and ("cgen" in keys or "cgens" in keys):
                    cgen_where = "Creative Rotations"
                if grid.max_row > hres.row:
                    cmap, _ = map_columns(grid, hres.row, TS_ROTATIONS)
                    col = cmap.col("creative_name") or cmap.col("group_name")
                    if col:
                        for r in range(hres.row + 1,
                                       min(hres.row + 60, grid.max_row) + 1):
                            c = grid.cell(r, col)
                            if c is not None and c.has_value:
                                rot_has_data = True
                                break
        except Exception:
            pass

    if not cgen_where:
        return "wpp_standard", "no CGEN column in Placements or Creative Rotations"

    if rot_has_data:
        return "adobe_variante_a", f"CGEN in {cgen_where} + Creative Rotations has data"
    return "adobe_variante_b", f"CGEN in {cgen_where} + Creative Rotations is empty"

def _impl_type(vals: dict[str, object]) -> str:
    if norm_dims(vals.get("dimensions")) == "1x1":
        return IMPL_SITE_SERVED_1X1
    return IMPL_THIRD_PARTY if norm_dims(vals.get("dimensions")) else IMPL_UNKNOWN

# ------------------------------------------------------------------ hoja

def _repair_wpp_combined_rotation_header(
    grid,
    header_row: int,
    cmap: ColumnMap,
    spec: SheetSpec,
    anomalies: list[Anomaly],
) -> None:
    """
    Repara una variante defectuosa de WPP donde los encabezados
    'Creative Rotation' y 'Creative Name' fueron combinados.

    Contrato controlado:
      columna del encabezado combinado     -> group_name
      columna inmediatamente a la derecha  -> creative_name

    Solo aplica al contrato TS_ROTATIONS. Nunca se usa como fallback
    general para otras hojas o campos.
    """
    if spec is not TS_ROTATIONS:
        return

    missing_group = not cmap.has("group_name")
    missing_creative = not cmap.has("creative_name")

    if not missing_group and not missing_creative:
        return

    combined_col = None
    combined_header = ""

    for col, cell in sorted(grid.row_cells(header_row).items()):
        key = norm_key(cell.text)

        if "creativerotation" in key and "creativename" in key:
            combined_col = col
            combined_header = cell.text
            break

    repair_reason = ""

    if combined_col is not None:
        repair_reason = (
            "encabezado combinado detectado: "
            f"{combined_header!r}"
        )

    # Fallback controlado para TS WPP defectuosa:
    #
    # La columna A contiene Creative Rotation Name, pero la celda A1
    # no tiene encabezado. La columna B sí contiene Creative Name.
    #
    # Solo se aplica cuando:
    #   1. Estamos leyendo TS_ROTATIONS.
    #   2. group_name está ausente.
    #   3. creative_name fue reconocido.
    #   4. creative_name está en columna B o posterior.
    #   5. La columna inmediatamente anterior contiene datos reales.
    if combined_col is None and missing_group:
        creative_col = cmap.col("creative_name")

        if creative_col is not None and creative_col > 1:
            candidate_group_col = creative_col - 1

            populated_group_cells = 0
            samples = []

            first_data_row = header_row + 1
            last_sample_row = min(grid.max_row, header_row + 40)

            for row_number in range(first_data_row, last_sample_row + 1):
                candidate_cell = grid.cell(
                    row_number,
                    candidate_group_col,
                )

                creative_cell = grid.cell(
                    row_number,
                    creative_col,
                )

                if (
                    candidate_cell is not None
                    and candidate_cell.has_value
                    and creative_cell is not None
                    and creative_cell.has_value
                ):
                    populated_group_cells += 1

                    if len(samples) < 3:
                        samples.append(candidate_cell.text)

            if populated_group_cells >= 2:
                combined_col = candidate_group_col
                combined_header = "(columna sin encabezado)"
                repair_reason = (
                    "group_name inferido desde la columna inmediatamente "
                    "anterior a Creative Name; "
                    f"{populated_group_cells} filas con evidencia"
                )

    if combined_col is None:
        return

    if missing_group:
        cmap.single["group_name"] = combined_col

    if missing_creative:
        creative_col = combined_col + 1

        # La segunda columna puede tener el mismo texto por una celda
        # combinada o estar vacía debido al error de construcción.
        cmap.single["creative_name"] = creative_col

    cmap.missing_required = [
        field_name
        for field_name in cmap.missing_required
        if field_name not in {"group_name", "creative_name"}
    ]

    cmap.missing_optional = [
        field_name
        for field_name in cmap.missing_optional
        if field_name not in {"group_name", "creative_name"}
    ]

    # Elimina únicamente la anomalía anterior causada por estos campos.
    cleaned_anomalies = []

    for anomaly in anomalies:
        if anomaly.code != "EXT-COLUMN-MISSING":
            cleaned_anomalies.append(anomaly)
            continue

        missing = set(anomaly.detail.get("missing", []))
        remaining = missing - {"group_name", "creative_name"}

        if remaining:
            cleaned_anomalies.append(
                Anomaly(
                    "EXT-COLUMN-MISSING",
                    "FATAL",
                    "Missing required columns: "
                    + ", ".join(sorted(remaining)),
                    detail={"missing": sorted(remaining)},
                )
            )

    anomalies[:] = cleaned_anomalies

    anomalies.append(
        Anomaly(
            "TS-WPP-COMBINED-ROTATION-HEADER",
            "WARNING",
            (
                "The Creative Rotations sheet has an incomplete "
                "structure or a malformed header. "
                f"{repair_reason}. Applied the controlled mapping: "
                f"column {combined_col}=group_name and "
                f"column {cmap.col('creative_name')}=creative_name."
            ),
            detail={
                "header_row": header_row,
                "combined_column": combined_col,
                "group_name_column": combined_col,
                "creative_name_column": combined_col + 1,
            },
        )
    )


def _parse_sheet(path: Path, sheet_name: str, spec: SheetSpec,
                 intent_fields: list[str], resolver: ColorResolver,
                 primary_key: str) -> tuple[TSSheetResult, list[tuple[str, str, Cell]]]:
    res = TSSheetResult(sheet=sheet_name)
    region: list[tuple[str, str, Cell]] = []

    grid, anomalies = read_sheet(path, sheet_name, capture_fill=True)
    res.anomalies += anomalies
    res.merged_applied = grid.merged_applied
    if any(a.severity == "FATAL" for a in res.anomalies):
        return res, region

    hres, anomalies = find_header_row(grid, spec)
    res.anomalies += anomalies
    if hres.row is None:
        return res, region
    res.header_row = hres.row
    res.header_evidence = hres.evidence

    cmap, anomalies = map_columns(grid, hres.row, spec)

    # Excepción controlada para WPP con encabezado combinado:
    # "Creative Rotation | Creative Name".
    _repair_wpp_combined_rotation_header(
        grid,
        hres.row,
        cmap,
        spec,
        anomalies,
    )

    res.cmap = cmap
    res.anomalies += anomalies

    if any(a.severity == "FATAL" for a in res.anomalies):
        return res, region

    first, last = hres.row + 1, grid.max_row

    keep: list[int] = []
    for r in range(first, last + 1):
        cls, _ = classify_row(grid, r, cmap, spec, primary_key=primary_key)
        res.row_class_counts[cls] = res.row_class_counts.get(cls, 0) + 1
        if cls == ROW_DATA:
            keep.append(r)

    res.fill_rates = column_fill_rates(grid, cmap, spec, keep)

    resolved: dict[str, list] = {}
    for f in spec.fields:
        if f.kind != "date":
            continue
        col = cmap.col(f.name)
        if col is None:
            continue
        raws = [(grid.cell(r, col).raw if grid.cell(r, col) else None) for r in keep]
        dres = resolve_date_column(raws)
        resolved[f.name] = dres.values
        res.date_diagnostics[f.name] = {
            "order": dres.order, "evidence": dres.order_evidence,
            "native": dres.native_count, "text": dres.text_count,
            "unparsed": len(dres.unparsed),
        }

    last_seen: dict[str, object] = {}

    for idx, r in enumerate(keep):
        vals: dict[str, object] = {}
        colors: dict[str, str] = {}
        inherited: set[str] = set()

        for f in spec.fields:
            if f.multi:
                continue
            col = cmap.col(f.name)
            if col is None:
                continue
            cell = grid.cell(r, col)

            if cell is None or not cell.has_value:
                if f.name in spec.fill_down and f.name in last_seen:
                    vals[f.name] = last_seen[f.name]
                    inherited.add(f.name)
                else:
                    vals[f.name] = None
            else:
                if f.kind == "id":
                    vals[f.name] = clean_id(cell.raw)
                elif f.kind == "date":
                    vals[f.name] = resolved.get(f.name, [None] * len(keep))[idx]
                else:
                    vals[f.name] = norm_text(cell.text)
                if f.name in spec.fill_down:
                    last_seen[f.name] = vals[f.name]

            if f.name in intent_fields and cell is not None:
                fam, _c, _rgb = resolver.family(cell.fill_rgb)
                colors[f.name] = fam
                if cell.fill_rgb:
                    region.append((sheet_name, f.name, cell))

        fams = set(colors.values())
        actionable = [k for k, v in colors.items() if v in ACTIONABLE]

        if GREEN in fams and RED in fams:
            intent = "SWAP"
        elif GREEN in fams:
            intent = GREEN
        elif RED in fams:
            intent = RED
        elif fams and fams <= {YELLOW, GREY}:
            intent = "SCOPE_EXCLUDED"
        elif UNKNOWN in fams:
            intent = "REVIEW"
        else:
            intent = WHITE

        impl = _impl_type(vals)
        fmt = format_from_dims(vals.get("dimensions") or vals.get("dims_or_duration"))

        res.intent_counts[intent] = res.intent_counts.get(intent, 0) + 1
        res.impl_counts[impl] = res.impl_counts.get(impl, 0) + 1

        res.rows.append(TSRow(row=r, values=vals, colors=colors, intent=intent,
                              intent_fields=actionable, inherited=inherited,
                              impl_type=impl, fmt=fmt))

    return res, region

# ------------------------------------------------------------------ grupos

def _build_groups(sr: TSSheetResult | None) -> dict[str, GroupScope]:
    """Agrupa creativos por rotacion y detecta que rotaciones se trabajaron."""
    out: dict[str, GroupScope] = {}
    if sr is None:
        return out
    for row in sr.rows:
        gname = norm_compare(str(row.values.get("group_name") or ""))
        if not gname:
            continue
        g = out.get(gname)
        if g is None:
            g = GroupScope(group_name=str(row.values.get("group_name")))
            out[gname] = g
        g.rows.append(row.row)

        lp_ref = norm_compare(str(row.values.get("lp_url") or ""))
        if lp_ref:
            g.lp_names.add(lp_ref)

        if row.intent == GREEN:
            g.green_creatives += 1
        elif row.intent == RED:
            g.red_creatives += 1
        elif row.intent == "SWAP":
            g.green_creatives += 1
            g.red_creatives += 1
        elif row.intent == WHITE:
            g.white_creatives += 1
    return out

def _build_lp_worked(sr: TSSheetResult | None) -> set[str]:
    """Landing pages con color -> se trabajo su URL."""
    out: set[str] = set()
    if sr is None:
        return out
    for row in sr.rows:
        if row.intent in (GREEN, RED, "SWAP"):
            name = norm_compare(str(row.values.get("lp_name") or ""))
            if name:
                out.add(name)
    return out

# ------------------------------------------------------------------ scope

def _build_scope(sr: TSSheetResult, groups: dict[str, GroupScope],
                 lp_worked: set[str],
                 propagate: bool = True) -> dict[str, PlacementScope]:
    """
    El scope de QA2 = placements con color propio
                    U placements que apuntan a grupos con color
                    U placements que apuntan a landing pages con color

    Esta propagacion entre pestanas es lo que hace funcionar Unilever/Wendy's,
    donde los placements van en blanco y los swaps se declaran en las
    pestanas de rotaciones y landing pages.
    """
    out: dict[str, PlacementScope] = {}

    for row in sr.rows:
        pid = str(row.values.get("placement_id") or "")
        if not pid:
            continue
        sc = out.get(pid)
        if sc is None:
            sc = PlacementScope(
                placement_id=pid, impl_type=row.impl_type, fmt=row.fmt,
                sample_name=str(row.values.get("placement_name") or "")[:60])
            out[pid] = sc
        sc.rows.append(row.row)
        sc.fields_touched |= set(row.intent_fields)

        # Una fila gris/amarilla esta explicitamente fuera de scope: es
        # un cambio viejo que quedo documentado en la TS. El mismo
        # Placement ID puede aparecer dos veces, una gris con la rotacion
        # de la solicitud anterior y otra blanca con la rotacion vigente.
        # Si la gris aportara su rotacion, el placement heredaria la
        # landing page de aquella y se leeria como un swap de URL que
        # nadie pidio (los 4 falsos URL-002 de PBU).
        if row.intent != "SCOPE_EXCLUDED":
            gname = norm_compare(str(row.values.get("group_name") or ""))
            if gname:
                sc.groups.add(gname)
            lp = norm_compare(str(row.values.get("lp_ref") or ""))
            if lp:
                sc.groups.add("__lp__" + lp)

        if row.intent == GREEN:
            sc.green_rows += 1
        elif row.intent == RED:
            sc.red_rows += 1
        elif row.intent == "SWAP":
            sc.green_rows += 1
            sc.red_rows += 1
        elif row.intent == WHITE:
            sc.white_rows += 1
        elif row.intent == "REVIEW":
            sc.request_type = REQ_REVIEW

    # ---- clasificacion
    for sc in out.values():
        if sc.request_type == REQ_REVIEW:
            sc.source = SRC_OWN
            continue

        own = bool(sc.green_rows or sc.red_rows)

        # propagacion desde grupos (solo si el perfil lo permite)
        prop_green = prop_red = 0
        if propagate:
            for g in sc.groups:
                if g.startswith("__lp__"):
                    continue
                gs = groups.get(g)
                if gs and gs.worked:
                    prop_green += gs.green_creatives
                    prop_red += gs.red_creatives

        # Propagacion desde landing pages. La TS puede enganchar el
        # placement con su landing page por dos caminos:
        #
        #   1. el placement la referencia directamente en su propia
        #      columna Landing Page  (Unilever, Wendy's)
        #   2. el placement dice "See Creative Rotation Tab" y el nombre
        #      de la landing page vive en la fila de la rotacion. Esa es
        #      la cadena de BlackRock:
        #         placement -> creative rotation -> landing page -> URL
        #
        # Sin el segundo camino un swap de solo URL deja el scope vacio:
        # el tab de Placements va todo en blanco porque los placements
        # siguen activos, y el unico color esta en Landing Pages. La app
        # corria, no reportaba nada y daba NO_CHECKS.
        prop_lp = False
        if propagate:
            direct = any(g[6:] in lp_worked
                         for g in sc.groups if g.startswith("__lp__"))
            via_rotation = any(
                lp in lp_worked
                for g in sc.groups if not g.startswith("__lp__")
                for lp in (groups[g].lp_names if g in groups else ())
            )
            prop_lp = direct or via_rotation

        propagated = bool(prop_green or prop_red or prop_lp)

        if own and propagated:
            sc.source = SRC_BOTH
        elif own:
            sc.source = SRC_OWN
        elif prop_lp and not (prop_green or prop_red):
            sc.source = SRC_LANDING
        elif propagated:
            sc.source = SRC_ROTATION
        else:
            sc.source = ""

        g_tot = sc.green_rows + prop_green
        r_tot = sc.red_rows + prop_red

        touched_placement_level = bool(
            sc.fields_touched & {"placement_name", "start_date",
                                 "end_date", "dimensions"})

        if not g_tot and not r_tot:
            if prop_lp:
                sc.request_type = REQ_URL_SWAP
            elif sc.fields_touched:
                sc.request_type = REQ_FIELD_CHANGE
            else:
                sc.request_type = REQ_NOT_WORKED
            continue

        if g_tot and not r_tot and touched_placement_level and not sc.white_rows:
            sc.request_type = REQ_NEW_PLACEMENT
        elif g_tot and r_tot:
            sc.request_type = REQ_CREATIVE_SWAP
        elif g_tot:
            sc.request_type = REQ_CREATIVE_ADD
        else:
            sc.request_type = REQ_CREATIVE_REMOVE
            # AdOps no apaga placements ni los deja vacios: lo hace Digital.
            # Solo revision visual, sin veredicto PASS/FAIL.
            if sc.green_rows == 0 and prop_green == 0:
                sc.visual_review = True
                sc.note = ("todos los creativos en rojo · revision visual "
                           "(desasignar/apagar lo ejecuta Digital)")

    return out

# ------------------------------------------------------------------ parser

def parse_ts(path: Path, profile_name: str | None = None) -> TSResult:
    res = TSResult(path=str(path))

    in_scope, out_scope, hidden = _split_sheets(path)
    res.all_sheets = in_scope + out_scope + hidden
    res.in_scope_sheets = in_scope
    res.out_of_scope_sheets = out_scope
    res.hidden_sheets = hidden

    detected, evidence = detect_profile(path)
    res.profile = profile_name or detected
    res.profile_evidence = evidence if not profile_name else "forzado por --profile"
    profile: TSProfile = PROFILES[res.profile]

    res.theme_colors = read_workbook_theme(path)
    resolver = ColorResolver(res.theme_colors)

    # ---- Campaign Information: 4 datos + sites
    ci_sheet = resolve_sheet(in_scope, profile.campaign_info.sheet_aliases)
    if ci_sheet:
        grid, anomalies = read_sheet(path, ci_sheet, capture_fill=False)
        res.anomalies += anomalies
        wanted = set(profile.campaign_info.metadata_labels)
        anchors = set(SITE_TABLE_ANCHORS)
        site_start = None

        for r in range(1, min(profile.campaign_info.metadata_scan_rows,
                              grid.max_row) + 1):
            cells = grid.row_cells(r)
            for col in sorted(cells):
                label = norm_key(cells[col].text.rstrip(":"))
                if label in anchors and site_start is None:
                    site_start = r + 1
                if label in wanted and label not in res.campaign_info:
                    for nxt in sorted(c for c in cells if c > col):
                        if cells[nxt].has_value:
                            raw = cells[nxt].raw
                            if isinstance(raw, float) and raw.is_integer():
                                res.campaign_info[label] = str(int(raw))
                            else:
                                res.campaign_info[label] = cells[nxt].text
                            break

        if site_start:
            for r in range(site_start, min(site_start + 40, grid.max_row) + 1):
                cells = grid.row_cells(r)
                if not cells:
                    break
                fc = min(cells)
                name = cells[fc].text if cells[fc].has_value else ""
                if not name:
                    break
                mail = ""
                for nxt in sorted(c for c in cells if c > fc):
                    if cells[nxt].has_value:
                        mail = cells[nxt].text
                        break
                res.site_contacts.append((name[:44], mail[:70]))

    all_region: list[tuple[str, str, Cell]] = []

    # ---- Placements
    pl_sheet = resolve_sheet(in_scope, profile.placements.sheet_aliases)
    if pl_sheet is None:
        res.anomalies.append(Anomaly("TS-SHEET-MISSING", "FATAL",
            f"Placements sheet not found. In scope: {in_scope}"))
        return res

    res.placements, region = _parse_sheet(
        path, pl_sheet, profile.placements,
        profile.intent_fields.get("placements", []),
        resolver, primary_key="placement_id")
    all_region += region
    res.anomalies += [a for a in res.placements.anomalies if a.severity == "FATAL"]

    # ---- Creative Rotations
    if profile.rotations is not None:
        rot_sheet = resolve_sheet(in_scope, profile.rotations.sheet_aliases)
        if rot_sheet:
            res.rotations, region = _parse_sheet(
                path, rot_sheet, profile.rotations,
                profile.intent_fields.get("rotations", []),
                resolver, primary_key="creative_name")
            all_region += region
            res.anomalies += [a for a in res.rotations.anomalies
                              if a.severity == "FATAL"]

    # ---- Landing Pages (solo WPP)
    if profile.landing_pages_in_scope:
        lp_sheet = resolve_sheet(in_scope, TS_LANDING_PAGES.sheet_aliases)
        if lp_sheet:
            res.landing_pages, region = _parse_sheet(
                path, lp_sheet, TS_LANDING_PAGES,
                profile.intent_fields.get("landing_pages", []),
                resolver, primary_key="lp_name")
            all_region += region

    # ---- propagacion y scope
    res.groups = _build_groups(res.rotations)
    res.lp_worked = _build_lp_worked(res.landing_pages)

    if res.placements:
        res.scope = _build_scope(res.placements, res.groups, res.lp_worked,
                                 propagate=profile.propagate_from_rotations)
        for sc in res.scope.values():
            res.request_counts[sc.request_type] = \
                res.request_counts.get(sc.request_type, 0) + 1
            if sc.request_type != REQ_NOT_WORKED:
                res.format_counts[sc.fmt] = res.format_counts.get(sc.fmt, 0) + 1
                k = (sc.request_type, sc.fmt)
                res.format_by_request[k] = res.format_by_request.get(k, 0) + 1
                if sc.source:
                    res.source_counts[sc.source] = \
                        res.source_counts.get(sc.source, 0) + 1

    res.region_palette = inventory_region(all_region, resolver)
    return res
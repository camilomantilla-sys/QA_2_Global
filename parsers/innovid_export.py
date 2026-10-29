"""
Parser del export de Innovid Campaign Manager.

Un solo parser para los tres casos (Adobe 3P con Dtree, Adobe 1x1/3P directo,
vistas personalizadas): los headers son identicos y el discriminador real es
Placement_Type + presencia de Decision_Tree_Name  (hallazgo H11).

Hallazgos incorporados:
  H22 - los placements tipo Pixel NO tienen fila de cabecera
  H23 - el export a nivel Placement es la fuente autoritativa del inventario
  B25 - "columna de arbol ausente" != "creativo desasignado"
  B26 - reportar placements sin cabecera explicitamente
  B27 - fill rate segmentado por Placement_Type
  B28 - IDs de metadata sin sufijo .0
  B30 - group_visible se evalua por Placement_Type, no globalmente
  B33 - filas de transicion entre bloques se descartan (sin Filename/Creative_Name)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.dates import resolve_date_column
from core.extraction import (
    ROW_BANNER, ROW_CORRUPT, ROW_DATA, ROW_SEPARATOR, ROW_TEMPLATE,
    ColumnMap, SheetSpec, check_empty_required, classify_row,
    column_fill_rates, find_header_row, list_sheets, map_columns, read_sheet,
)
from core.normalize import clean_id, norm_key, norm_text, split_platform_id, to_bool
from core.provenance import Anomaly
from core.schema import (
    CAPABILITIES, CAPABILITY_HINTS, INNOVID_PLACEMENT, INNOVID_PLACEMENT_CREATIVE,
)

# ------------------------------------------------ tipologia de fila (spec 3.2)
T_PLACEMENT_HEADER = "PLACEMENT_HEADER"
T_ASSIGNED = "ASSIGNED_CREATIVE"
T_UNASSIGNED = "UNASSIGNED_CREATIVE"
T_DIRECT = "DIRECT_CREATIVE"
T_TRACKER = "TRACKER"
T_PLACEMENT = "PLACEMENT"

LEVEL_PLACEMENT_CREATIVE = "placement_creative"
LEVEL_PLACEMENT = "placement"

# umbral minimo para considerar que una columna "tiene datos"
MIN_FILL = 0.01

def norm_compare_sheet(name: str) -> str:
    return norm_key(name)

@dataclass
class ExportRow:
    row: int
    row_type: str
    row_reason: str = ""
    values: dict[str, object] = field(default_factory=dict)
    multi: dict[str, list[str]] = field(default_factory=dict)

@dataclass
class ExportResult:
    path: str = ""
    sheet: str = ""
    level: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    header_row: int | None = None
    header_evidence: str = ""
    cmap: ColumnMap | None = None
    rows: list[ExportRow] = field(default_factory=list)
    row_class_counts: dict[str, int] = field(default_factory=dict)
    row_type_counts: dict[str, int] = field(default_factory=dict)
    date_diagnostics: dict[str, dict] = field(default_factory=dict)
    capabilities_on: dict[str, str] = field(default_factory=dict)
    capabilities_off: dict[str, dict] = field(default_factory=dict)
    fill_rates: dict[str, float] = field(default_factory=dict)
    fill_rates_by_type: dict[str, dict[str, float]] = field(default_factory=dict)
    unassigned_reasons: dict[str, int] = field(default_factory=dict)
    direct_reasons: dict[str, int] = field(default_factory=dict)
    separator_reasons: dict[str, int] = field(default_factory=dict)
    placements_without_header: dict[str, int] = field(default_factory=dict)
    group_visible: dict[str, bool] = field(default_factory=dict)
    anomalies: list[Anomaly] = field(default_factory=list)
    merged_applied: int = 0
    total_sheets: list[str] = field(default_factory=list)

    @property
    def fatal(self) -> bool:
        return any(a.severity == "FATAL" for a in self.anomalies)

    @property
    def distinct_placements(self) -> int:
        return len({str(r.values.get("placement_id")) for r in self.rows
                    if r.values.get("placement_id")})

# ------------------------------------------------------------------ helpers

def _detect_level(grid, header_row: int) -> str:
    """Placement-Creative si existe la columna Creative_ID en el header."""
    keys = {norm_key(t) for t in grid.row_text(header_row)}
    return LEVEL_PLACEMENT_CREATIVE if "creativeid" in keys else LEVEL_PLACEMENT

def _read_metadata(grid, spec: SheetSpec) -> dict[str, str]:
    """
    Metadata de las filas 1-9, por ETIQUETA (nunca por posicion).
    El valor es la primera celda no vacia a la derecha de la etiqueta.
    Los numericos enteros se emiten sin '.0' (bug B28).
    """
    wanted = set(spec.metadata_labels)
    out: dict[str, str] = {}
    for r in range(1, min(spec.metadata_scan_rows, grid.max_row) + 1):
        cells = grid.row_cells(r)
        for col in sorted(cells):
            label = norm_key(cells[col].text.rstrip(":"))
            if label in wanted and label not in out:
                for nxt in sorted(c for c in cells if c > col):
                    if cells[nxt].has_value:
                        raw = cells[nxt].raw
                        if isinstance(raw, float) and raw.is_integer():
                            out[label] = str(int(raw))
                        else:
                            out[label] = cells[nxt].text
                        break
    return out

def _row_type(vals: dict[str, object], level: str,
              group_visible: dict[str, bool]) -> tuple[str, str]:
    """
    Devuelve (tipo, motivo).

    group_visible: por Placement_Type, la columna de arbol existe Y tiene datos.
    Se evalua por tipo porque Pixel nunca tiene arbol y HTML puede ir directo
    mientras VAST usa dtree en el mismo export (bug B30).
    """
    if level == LEVEL_PLACEMENT:
        return T_PLACEMENT, ""

    creative_id = str(vals.get("creative_id") or "")
    placement_name = str(vals.get("placement_name") or "")
    group_name = str(vals.get("group_name") or "")
    ptype_raw = str(vals.get("placement_type") or "?")
    ptype = ptype_raw.casefold()
    enabled = vals.get("enabled")

    # fila de cabecera de placement: sin Creative_ID pero con nombre
    if not creative_id and placement_name:
        return T_PLACEMENT_HEADER, "sin Creative_ID"

    # Enabled=No es evidencia directa e independiente del arbol
    if enabled is False:
        return T_UNASSIGNED, "Enabled=No" + ("" if group_name else " + sin arbol")

    # site-served: el pixel ES el placement (hallazgo H22)
    if ptype == "pixel":
        return T_TRACKER, "Placement_Type=Pixel"

    if group_name:
        return T_ASSIGNED, ""

    # sin arbol en esta fila: solo es desasignacion si el arbol ES visible
    if not group_visible.get(ptype_raw, False):
        return T_DIRECT, f"arbol no visible para Placement_Type={ptype_raw}"

    return T_UNASSIGNED, "sin arbol"

# ------------------------------------------------------------------ parser

def parse_innovid_export(path: Path, sheet_name: str | None = None) -> ExportResult:
    res = ExportResult(path=str(path))
    res.total_sheets = list_sheets(path)

    target = sheet_name or next(
        (s for s in res.total_sheets if norm_compare_sheet(s) == "import"),
        res.total_sheets[0] if res.total_sheets else "",
    )
    res.sheet = target

    grid, anomalies = read_sheet(path, target, capture_fill=False)
    res.anomalies += anomalies
    res.merged_applied = grid.merged_applied
    if res.fatal:
        return res

    # ---- header contractual en fila 10
    hres, anomalies = find_header_row(grid, INNOVID_PLACEMENT_CREATIVE)
    res.anomalies += anomalies
    if hres.row is None:
        return res
    res.header_row = hres.row
    res.header_evidence = hres.evidence

    # ---- nivel del export y spec correspondiente
    res.level = _detect_level(grid, hres.row)
    spec = (INNOVID_PLACEMENT_CREATIVE if res.level == LEVEL_PLACEMENT_CREATIVE
            else INNOVID_PLACEMENT)

    res.metadata = _read_metadata(grid, spec)

    # ---- mapeo de columnas POR NOMBRE (mata B1/B2)
    cmap, anomalies = map_columns(grid, hres.row, spec)
    res.cmap = cmap
    res.anomalies += anomalies
    if res.fatal:
        return res

    first, last = hres.row + 1, grid.max_row
    res.anomalies += check_empty_required(grid, cmap, spec, first, last)
    if res.fatal:
        return res

    # ---- clasificacion de filas (banner / template / corrupt / separador / data)
    keep: list[int] = []
    for r in range(first, last + 1):
        cls, reason = classify_row(grid, r, cmap, spec, primary_key="placement_id")
        res.row_class_counts[cls] = res.row_class_counts.get(cls, 0) + 1
        if cls == ROW_SEPARATOR and reason:
            res.separator_reasons[reason] = res.separator_reasons.get(reason, 0) + 1
        if cls == ROW_DATA:
            keep.append(r)

    # ---- fill rates globales y por tipo (necesarios antes de tipificar: B25/B30)
    res.fill_rates = column_fill_rates(grid, cmap, spec, keep)

    if res.level == LEVEL_PLACEMENT_CREATIVE and cmap.col("placement_type") is not None:
        pt_col = cmap.col("placement_type")
        rows_by_type: dict[str, list[int]] = {}
        for r in keep:
            c = grid.cell(r, pt_col)
            key = c.text if (c and c.has_value) else "?"
            rows_by_type.setdefault(key, []).append(r)
        for ptype, rows in rows_by_type.items():
            res.fill_rates_by_type[ptype] = column_fill_rates(grid, cmap, spec, rows)
            res.group_visible[ptype] = (
                cmap.has("group_name")
                and res.fill_rates_by_type[ptype].get("group_name", 0.0) > 0.0
            )

    # ---- fechas: por COLUMNA, para poder deducir el orden (B23)
    resolved_dates: dict[str, list] = {}
    for fname in ("start_date", "end_date"):
        col = cmap.col(fname)
        if col is None:
            continue
        raws = [(grid.cell(r, col).raw if grid.cell(r, col) else None) for r in keep]
        dres = resolve_date_column(raws)
        resolved_dates[fname] = dres.values
        res.date_diagnostics[fname] = {
            "order": dres.order,
            "evidence": dres.order_evidence,
            "native": dres.native_count,
            "text": dres.text_count,
            "unparsed": len(dres.unparsed),
            "samples": dres.unparsed[:3],
        }

    # ---- materializacion de filas
    for idx, r in enumerate(keep):
        vals: dict[str, object] = {}
        for f in spec.fields:
            if f.multi:
                continue
            col = cmap.col(f.name)
            if col is None:
                continue
            cell = grid.cell(r, col)
            if cell is None or not cell.has_value:
                vals[f.name] = None
                continue
            if f.kind == "id":
                vals[f.name] = clean_id(cell.raw)
            elif f.kind == "bool":
                vals[f.name] = to_bool(cell.raw)
            elif f.kind == "date":
                vals[f.name] = resolved_dates.get(f.name, [None] * len(keep))[idx]
            else:
                vals[f.name] = norm_text(cell.text)

        # separar el sufijo " (ID)" que inyecta Innovid  -> mata B11
        if vals.get("group_name"):
            gname, gid = split_platform_id(str(vals["group_name"]))
            vals["group_name_norm"] = gname
            vals["group_id_from_name"] = gid
        if vals.get("placement_name"):
            pname, pid = split_platform_id(str(vals["placement_name"]))
            vals["placement_name_norm"] = pname
            vals["placement_id_from_name"] = pid

        # familias de columnas (Clicktag_1..20, Third_Party_Impression_1..10, ...)
        multi: dict[str, list[str]] = {}
        for mname, cols in cmap.multi.items():
            found = []
            for col in cols:
                cell = grid.cell(r, col)
                if cell and cell.has_value:
                    found.append(cell.hyperlink or cell.text)
            if found:
                multi[mname] = found

        rtype, reason = _row_type(vals, res.level, res.group_visible)
        res.row_type_counts[rtype] = res.row_type_counts.get(rtype, 0) + 1
        if rtype == T_UNASSIGNED and reason:
            res.unassigned_reasons[reason] = res.unassigned_reasons.get(reason, 0) + 1
        if rtype == T_DIRECT and reason:
            res.direct_reasons[reason] = res.direct_reasons.get(reason, 0) + 1

        # WPP Media style Decision Set / Creative Rotation groups: this
        # account never populates Decision_Tree_Name. Instead Innovid
        # emits one header row per group (T_PLACEMENT_HEADER, no
        # Creative_ID) whose Filename holds the group name with an
        # injected "(id)" suffix, e.g. "Disp Fresh Seekers 2P UG
        # 160x600 (28809)". Recover it the same way Decision_Tree_Name
        # values are recovered so the group stays visible to matching
        # and the UI even when it's expressed this way instead of via
        # Adobe's Decision Tree feature. Only applies when
        # Decision_Tree_Name is absent, so it never overrides the
        # authoritative column when both are present.
        if (
            rtype == T_PLACEMENT_HEADER
            and not vals.get("group_name")
            and vals.get("filename")
        ):
            hname, hid = split_platform_id(str(vals["filename"]))
            if hname:
                vals["group_name"] = hname
                vals["group_name_norm"] = hname
                vals["group_id_from_name"] = hid

        res.rows.append(ExportRow(row=r, row_type=rtype, row_reason=reason,
                                  values=vals, multi=multi))

    # ---- placements sin fila de cabecera (hallazgo H22 / bug B26)
    if res.level == LEVEL_PLACEMENT_CREATIVE:
        with_header = {str(r.values.get("placement_id"))
                       for r in res.rows if r.row_type == T_PLACEMENT_HEADER}
        all_pids = {str(r.values.get("placement_id"))
                    for r in res.rows if r.values.get("placement_id")}
        for pid in all_pids - with_header:
            ptypes = {str(r.values.get("placement_type") or "?")
                      for r in res.rows if str(r.values.get("placement_id")) == pid}
            key = "/".join(sorted(ptypes))
            res.placements_without_header[key] = res.placements_without_header.get(key, 0) + 1

    # ---- capability profile: presencia Y poblacion
    for cap, meta in CAPABILITIES.items():
        absent = [n for n in meta["needs"] if not cmap.has(n)]
        empty = [n for n in meta["needs"]
                 if n not in absent and res.fill_rates.get(n, 0.0) < MIN_FILL]

        if absent or empty:
            reasons = []
            if absent:
                reasons.append(f"columna ausente: {', '.join(absent)}")
            if empty:
                reasons.append(f"columna vacia: {', '.join(empty)}")
            res.capabilities_off[cap] = {
                "missing": absent + empty,
                "reason": " | ".join(reasons),
                "rules": meta["rules"],
                "hint": CAPABILITY_HINTS.get(cap, ""),
            }
        else:
            res.capabilities_on[cap] = meta["rules"]

    return res
"""
Pixeles de vendor declarados en la TS vs. lo que Innovid tiene.

La columna "Vendors / Pixels" de la Traffic Sheet nombra los vendors
que ese placement debe llevar. Cada vendor entrega su pixel y ese pixel
tiene que quedar cargado en una columna concreta del export a nivel de
placement.

La tabla VENDORS de abajo es el unico sitio que hay que tocar para
agregar un vendor, cambiar el pixel de uno existente o mover en que
columna se espera. La logica no cambia.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.normalize import clean_id, norm_compare, norm_dims
from parsers.ts_parser import REQ_CREATIVE_REMOVE

# Columnas del export a nivel de placement donde viven los pixeles.
SURVEY = "third_party_survey"
IMPRESSION = "third_party_impression"

# Formatos, deducidos de la dimension del placement.
F_1X1 = "1x1"
F_VIDEO = "video"
F_DISPLAY = "display"

_VIDEO_DIMS = {"640x480", "1920x1080", "1280x720", "0x0"}

# Estados de Innovid en los que el placement no esta sirviendo.
_NOT_RUNNING = ("stopped", "disabled", "inactive", "paused")


@dataclass(frozen=True)
class Vendor:
    """
    name       nombre legible que se muestra en el hallazgo
    ts_terms   como aparece nombrado en "Vendors / Pixels"
    host_terms como se reconoce su pixel dentro del tag
    column     donde debe estar cargado
    formats    formatos a los que aplica
    note       por que no aplica a los formatos que quedan fuera
    """
    name: str
    ts_terms: tuple[str, ...]
    host_terms: tuple[str, ...]
    column: str
    formats: frozenset[str]
    note: str = ""


VENDORS: tuple[Vendor, ...] = (
    Vendor(
        name="DoubleVerify",
        ts_terms=("dv", "doubleverify"),
        host_terms=("doubleverify.com",),
        column=SURVEY,
        formats=frozenset({F_DISPLAY, F_VIDEO}),
        note=(
            "On 1x1 placements DV is delivered as a wrapped tag from "
            "DV Pinnacle, not as a placement-level pixel."
        ),
    ),
    Vendor(
        name="Dynata",
        ts_terms=("dynata",),
        host_terms=("researchnow.com", "dynata.com"),
        column=IMPRESSION,
        formats=frozenset({F_1X1, F_DISPLAY, F_VIDEO}),
    ),
    Vendor(
        name="Kantar / Flex Tag",
        ts_terms=("kantar", "flex tag", "flextag"),
        host_terms=("insightexpressai.com",),
        column=IMPRESSION,
        formats=frozenset({F_1X1, F_DISPLAY, F_VIDEO}),
    ),
)


@dataclass
class PixelCheck:
    placement_id: str
    placement_name: str = ""
    vendor: str = ""
    column: str = ""
    fmt: str = ""
    vendor_raw: str = ""
    result: str = "NOT_VERIFIED"
    message: str = ""
    found: str = ""


@dataclass
class PixelReconciliation:
    checks: list[PixelCheck] = field(default_factory=list)
    placement_view_loaded: bool = False


def placement_format(dims: object) -> str:
    normalized = norm_dims(dims)
    if normalized == F_1X1:
        return F_1X1
    if normalized in _VIDEO_DIMS:
        return F_VIDEO
    return F_DISPLAY


def _declared(vendor: Vendor, vendor_raw: str) -> bool:
    text = norm_compare(vendor_raw)
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)
        for term in vendor.ts_terms
    )


def _pixels_in(row, column: str) -> list[str]:
    return [tag for tag in (row.multi.get(column) or []) if tag]


def reconcile_pixels(ts_result, placement_view) -> PixelReconciliation:
    out = PixelReconciliation(placement_view_loaded=placement_view is not None)

    worked = {s.placement_id: s for s in ts_result.worked}
    if not worked or ts_result.placements is None:
        return out

    rows_by_placement = {}
    if placement_view is not None:
        for row in placement_view.rows:
            placement_id = clean_id(row.values.get("placement_id"))
            if placement_id:
                rows_by_placement.setdefault(placement_id, row)

    seen: set[tuple[str, str]] = set()

    for ts_row in ts_result.placements.rows:
        placement_id = clean_id(ts_row.values.get("placement_id"))
        if not placement_id or placement_id not in worked:
            continue

        # Un placement que la TS pide desasignar por completo, o que en
        # Innovid ya quedo detenido, no esta sirviendo: exigirle el pixel
        # del vendor no tiene sentido.
        if worked[placement_id].request_type == REQ_CREATIVE_REMOVE:
            continue

        row_for_status = rows_by_placement.get(placement_id)
        if row_for_status is not None:
            status = norm_compare(row_for_status.values.get("status"))
            if status in _NOT_RUNNING:
                continue

        vendor_raw = str(ts_row.values.get("vendors") or "").strip()
        if not vendor_raw:
            continue

        fmt = placement_format(ts_row.values.get("dimensions"))
        placement_name = str(ts_row.values.get("placement_name") or "").strip()

        for vendor in VENDORS:
            if not _declared(vendor, vendor_raw):
                continue
            if fmt not in vendor.formats:
                continue
            if (placement_id, vendor.name) in seen:
                continue
            seen.add((placement_id, vendor.name))

            check = PixelCheck(
                placement_id=placement_id,
                placement_name=placement_name,
                vendor=vendor.name,
                column=vendor.column,
                fmt=fmt,
                vendor_raw=vendor_raw,
            )

            row = rows_by_placement.get(placement_id)

            if placement_view is None:
                check.result = "NOT_VERIFIED"
                check.message = (
                    "The Innovid Placement View wasn't uploaded, so the "
                    f"{vendor.name} pixel can't be verified."
                )
            elif row is None:
                check.result = "NOT_VERIFIED"
                check.message = (
                    "This placement isn't in the Placement View, so the "
                    f"{vendor.name} pixel can't be verified."
                )
            else:
                pixels = _pixels_in(row, vendor.column)
                match = next(
                    (
                        pixel for pixel in pixels
                        if any(host in pixel.casefold()
                               for host in vendor.host_terms)
                    ),
                    None,
                )

                if match:
                    check.result = "PASS"
                    check.found = match
                    check.message = (
                        f"{vendor.name} pixel is loaded on the placement."
                    )
                elif pixels:
                    check.result = "FAIL"
                    check.found = pixels[0]
                    check.message = (
                        f"The Traffic Sheet asks for {vendor.name}, but "
                        "the pixel loaded on the placement is a "
                        "different one."
                    )
                else:
                    check.result = "FAIL"
                    check.message = (
                        f"The Traffic Sheet asks for {vendor.name}, but "
                        "the placement carries no pixel in this column."
                    )

            out.checks.append(check)

    return out

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

from core.dv_subtype import MONITORING, MONITORING_BLOCKING, OMNI, dv_subtype
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
    name            nombre legible que se muestra en el hallazgo
    ts_terms        como aparece nombrado en "Vendors / Pixels"
    host_terms      como se reconoce su pixel dentro del tag
    column          donde debe estar cargado
    formats         formatos a los que aplica
    note            por que no aplica a los formatos que quedan fuera
    site_exceptions sitios donde el vendor nunca aplica, aunque la TS
                    lo pida (el publisher lo integra distinto)
    """
    name: str
    ts_terms: tuple[str, ...]
    host_terms: tuple[str, ...]
    column: str
    formats: frozenset[str]
    note: str = ""
    site_exceptions: frozenset[str] = frozenset()


VENDORS: tuple[Vendor, ...] = (
    # DoubleVerify: solo cubre aqui el sub-tipo Monitoring (solo o con
    # Blocking) en Display, que es el unico que exige un pixel a nivel
    # de placement. Omni no lo usa (va por columna en el archivo de
    # tags, ver DV-003) y ningun sub-tipo lo exige en Video ni 1x1
    # (1x1 Monitoring va por el archivo de DV Pinnacle, ver DV-001).
    # El chequeo real se resuelve en _reconcile_double_verify, no por
    # la tabla generica de abajo.
    Vendor(
        name="DoubleVerify",
        ts_terms=("dv", "doubleverify"),
        host_terms=("doubleverify.com",),
        column=SURVEY,
        formats=frozenset({F_DISPLAY}),
        note=(
            "Monitoring on 1x1 is delivered as a wrapped tag from DV "
            "Pinnacle (DV-001), not as a placement-level pixel. Omni "
            "is verified through the Innovid tag file (DV-003)."
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
    # Wendy's only. Publishers apply Inmarket in the backend for 1x1,
    # so it never shows up as a placement-level pixel there even when
    # the TS lists it -- that's why 1x1 is excluded from formats.
    Vendor(
        name="Inmarket",
        ts_terms=("inmarket",),
        host_terms=("ninthdecimal.com",),
        column=IMPRESSION,
        formats=frozenset({F_DISPLAY, F_VIDEO}),
        site_exceptions=frozenset({"vevo"}),
    ),
    # Wendy's only. Same backend-applied logic as Inmarket for 1x1.
    # This is a separate entry from Adobe's DISQO (PIX-A01): different
    # accounts, different profile, same vendor name.
    Vendor(
        name="DISQO",
        ts_terms=("disqo",),
        host_terms=("activemetering.com",),
        column=IMPRESSION,
        formats=frozenset({F_DISPLAY, F_VIDEO}),
        site_exceptions=frozenset({"netflix"}),
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
        site_name = norm_compare(str(ts_row.values.get("site") or ""))

        for vendor in VENDORS:
            if not _declared(vendor, vendor_raw):
                continue
            if fmt not in vendor.formats:
                continue
            if site_name in vendor.site_exceptions:
                continue

            if vendor.name == "DoubleVerify":
                subtype = dv_subtype(vendor_raw)

                if subtype == OMNI:
                    # Omni no lleva pixel a nivel de placement: se
                    # verifica por columna en el archivo de tags
                    # (DV-003), no aqui.
                    continue

                if subtype not in (MONITORING, MONITORING_BLOCKING):
                    # La TS dice "DV"/"DoubleVerify" pero no aclara si
                    # es Omni, Monitoring o Blocking, y cada uno se
                    # verifica distinto -- no hay forma de saber cual
                    # regla aplica.
                    if (placement_id, vendor.name) in seen:
                        continue
                    seen.add((placement_id, vendor.name))
                    out.checks.append(
                        PixelCheck(
                            placement_id=placement_id,
                            placement_name=placement_name,
                            vendor=vendor.name,
                            column=vendor.column,
                            fmt=fmt,
                            vendor_raw=vendor_raw,
                            result="NOT_VERIFIED",
                            message=(
                                "Vendors / Pixels mentions DV but doesn't "
                                "say Omni, Monitoring or Blocking, so it "
                                "isn't clear which DV check applies."
                            ),
                        )
                    )
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

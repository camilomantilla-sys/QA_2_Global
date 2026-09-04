"""
Pixeles de vendor declarados en la TS vs. lo que Innovid tiene.

La columna "Vendors / Pixels" de la Traffic Sheet nombra los vendors
que ese placement debe llevar. Cada vendor entrega su pixel y ese pixel
tiene que quedar cargado en una columna concreta del export a nivel de
placement.

La tabla _DEFAULT_VENDORS de abajo son los valores de fabrica. La
fuente real una vez existe es config/vendor_pixels.json, editable
desde el panel "Pixels by account" de la app -- asi el equipo no
depende de que alguien toque este archivo para agregar un vendor,
cambiar su host o mover en que columna se espera.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

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

# Reconoce los macros que Innovid deja sin resolver en un pixel
# ("[%placementID%]", "%%SITE%%", "${CAMPAIGN}") para poder comparar
# la URL oficial contra la implementada ignorando esos valores, que
# cambian por diseno, sin ignorar el resto de la URL.
_PIXEL_MACRO = re.compile(
    r"\[%[^%\]]+%\]"
    r"|\$\{[^{}]+\}"
    r"|\[[A-Za-z_][A-Za-z0-9_]*\]"
    r"|%%[^%]+%%",
    re.IGNORECASE,
)


def _pixel_skeleton(url: str) -> str:
    """Pixel URL con cada macro reemplazado por un token comun, para comparar."""
    return _PIXEL_MACRO.sub("<MACRO>", str(url or "").strip()).casefold()


def pixel_matches_official(found: str, official: str) -> bool:
    """
    True si el pixel encontrado coincide con el oficial una vez se
    ignoran los macros de ambos lados. Cualquier otra diferencia (host,
    path, un parametro con valor fijo que cambio) cuenta como mismatch.
    """
    if not official:
        return True
    return _pixel_skeleton(found) == _pixel_skeleton(official)


def _host_from_pixel(url: str) -> str:
    """El dominio de una URL de pixel, para derivar host_terms automaticamente."""
    try:
        return urlsplit(str(url or "").strip()).netloc.casefold()
    except ValueError:
        return ""


@dataclass(frozen=True)
class Vendor:
    """
    name            nombre legible que se muestra en el hallazgo
    account         cuenta/campana a la que aplica esta fila ("" = todas)
    ts_terms        como aparece nombrado en "Vendors / Pixels"
    host_terms      como se reconoce su pixel dentro del tag. Si se
                    deja vacio y hay official_pixel, se deriva solo
                    del dominio de esa URL -- no hace falta llenar
                    los dos.
    column          donde debe estar cargado
    formats         formatos a los que aplica
    note            por que no aplica a los formatos que quedan fuera
    site_exceptions sitios donde el vendor nunca aplica, aunque la TS
                    lo pida (el publisher lo integra distinto)
    official_pixel  la URL de referencia vigente (con macros), tal
                    como Camilo la mantiene actualizada. Si esta
                    presente, un pixel encontrado se compara contra
                    ella -- ver pixel_matches_official() -- y de ahi
                    tambien se deriva host_terms si no se lleno.
    """
    name: str
    ts_terms: tuple[str, ...]
    host_terms: tuple[str, ...]
    column: str
    formats: frozenset[str]
    note: str = ""
    site_exceptions: frozenset[str] = frozenset()
    account: str = ""
    official_pixel: str = ""


_DEFAULT_VENDORS: tuple[Vendor, ...] = (
    # DV se parte en sus 4 sabores reales en vez de una sola fila
    # "DoubleVerify" -- cada uno se verifica distinto y Camilo quiere
    # ver los 4 en la tabla, con el pixel oficial de cada uno.
    #
    # DV Monitoring, Display: el unico que exige un pixel a nivel de
    # placement (Third_Party_Survey), asi que es el unico que participa
    # en el chequeo generico de abajo. Su host se deriva de
    # official_pixel una vez lo llenes -- no hace falta host_terms.
    Vendor(
        name="DV Monitoring",
        ts_terms=("dv", "doubleverify"),
        host_terms=("doubleverify.com",),
        column=SURVEY,
        formats=frozenset({F_DISPLAY}),
        # Camilo's reference URL has ctx=715607, but a real BlackRock
        # placement showed ctx=27799358 -- that value isn't a fixed
        # constant, it varies (by account or by DV setup). Left blank
        # on purpose: paste the real reference into the "Pixels by
        # account" panel only once you've confirmed with DV which
        # part of the URL is actually fixed for a given account.
        note=(
            "Placement-level pixel, Display only. On 1x1, Monitoring "
            "is delivered as a wrapped tag from DV Pinnacle (DV-001) "
            "instead -- no pixel to compare here."
        ),
    ),
    # DV Blocking (Monitoring/Blocking): su pixel vive en la columna
    # doubleverify_html del archivo de tags (Display) o
    # doubleverify_vast (Video, combinacion inusual) -- no es un pixel
    # de placement, asi que esta fila no participa en el chequeo
    # generico de abajo. DV-003 lee su official_pixel directamente.
    Vendor(
        name="DV Blocking",
        ts_terms=(),
        host_terms=(),
        column=IMPRESSION,
        formats=frozenset(),
        note=(
            "Column in the tag file (doubleverify_html for Display), "
            "not a placement pixel -- checked by DV-003, not here. "
            "Paste the reference tag/wrapper content, not just a URL."
        ),
    ),
    # DV Integration (1x1): no hay pixel que comparar -- solo hace
    # falta que los tags se descarguen normal (TAG-013). Fila de
    # referencia, sin chequeo activo.
    Vendor(
        name="DV Integration",
        ts_terms=(),
        host_terms=(),
        column=IMPRESSION,
        formats=frozenset(),
        note=(
            "No Pinnacle wrapping, no placement pixel, no tag-file "
            "column -- just needs the regular tags delivered "
            "(TAG-013 checks that). Nothing to validate here."
        ),
    ),
    # DV Omni (1x1, Video): su pixel vive en la columna
    # doubleverify_vast del archivo de tags -- tampoco es un pixel de
    # placement. DV-003 lee su official_pixel directamente.
    Vendor(
        name="DV Omni",
        ts_terms=(),
        host_terms=(),
        column=IMPRESSION,
        formats=frozenset(),
        note=(
            "Column in the tag file (doubleverify_vast), not a "
            "placement pixel -- checked by DV-003, not here."
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
        # Left blank for the same reason as DoubleVerify's ctx above:
        # bannerID=13015010 looks like it could be account-specific
        # too, unconfirmed against real data. Paste it into the UI
        # once you've checked it holds across accounts.
    ),
    # Wendy's only. Publishers apply Inmarket in the backend for 1x1,
    # so it never shows up as a placement-level pixel there even when
    # the TS lists it -- that's why 1x1 is excluded from formats.
    Vendor(
        name="Inmarket",
        account="Wendy's",
        ts_terms=("inmarket",),
        host_terms=("ninthdecimal.com",),
        column=IMPRESSION,
        formats=frozenset({F_DISPLAY, F_VIDEO}),
        site_exceptions=frozenset({"vevo"}),
        # Left blank -- same caution as above, not yet validated
        # against a real Wendy's export.
    ),
    # Wendy's only. Same backend-applied logic as Inmarket for 1x1.
    # This is a separate entry from Adobe's DISQO (PIX-A01): different
    # accounts, different profile, same vendor name.
    Vendor(
        name="DISQO",
        account="Wendy's",
        ts_terms=("disqo",),
        host_terms=("activemetering.com",),
        column=IMPRESSION,
        formats=frozenset({F_DISPLAY, F_VIDEO}),
        site_exceptions=frozenset({"netflix"}),
        # Left blank -- same caution as above, not yet validated
        # against a real Wendy's export.
    ),
)


# ------------------------------------------------------------------
# Editable config: config/vendor_pixels.json
#
# The account team shouldn't have to depend on someone editing this
# Python file to update a vendor's host, column or formats. The table
# above are the shipped defaults; a JSON file next to the repo is the
# actual source of truth once it exists, editable from the app's
# "Pixels by account" panel. Every call to reconcile_pixels() re-reads
# it, so an edit takes effect on the very next QA2 run, no restart.
#
# This only covers the flat per-vendor rows (Dynata, Kantar, Inmarket,
# DISQO, and the Display-only part of DoubleVerify Monitoring). DV's
# Omni/Monitoring/Blocking routing and Adobe's FTRACK/Protected column
# policy are structural, not a simple table, so they stay in code.
# ------------------------------------------------------------------

VENDOR_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "vendor_pixels.json"

_VENDOR_FIELDS = ("name", "ts_terms", "host_terms", "column", "formats", "note", "site_exceptions")


def _vendor_to_dict(vendor: Vendor) -> dict:
    return {
        "account": vendor.account,
        "name": vendor.name,
        "ts_terms": list(vendor.ts_terms),
        "host_terms": list(vendor.host_terms),
        "column": vendor.column,
        "formats": sorted(vendor.formats),
        "official_pixel": vendor.official_pixel,
        "note": vendor.note,
        "site_exceptions": sorted(vendor.site_exceptions),
    }


def _dict_to_vendor(data: dict) -> Vendor:
    official_pixel = str(data.get("official_pixel") or "").strip()
    host_terms = tuple(
        str(t).strip() for t in (data.get("host_terms") or []) if str(t).strip()
    )

    if not host_terms and official_pixel:
        # No hace falta llenar host_terms a mano si ya se dio el pixel
        # oficial completo -- se deriva su dominio.
        derived_host = _host_from_pixel(official_pixel)
        if derived_host:
            host_terms = (derived_host,)

    return Vendor(
        account=str(data.get("account") or "").strip(),
        name=str(data.get("name") or "").strip(),
        ts_terms=tuple(str(t).strip() for t in (data.get("ts_terms") or []) if str(t).strip()),
        host_terms=host_terms,
        column=str(data.get("column") or IMPRESSION).strip(),
        formats=frozenset(
            f for f in (data.get("formats") or []) if f in (F_1X1, F_DISPLAY, F_VIDEO)
        ),
        official_pixel=official_pixel,
        note=str(data.get("note") or ""),
        site_exceptions=frozenset(
            norm_compare(s) for s in (data.get("site_exceptions") or []) if str(s).strip()
        ),
    )


def default_vendor_rows() -> list[dict]:
    """The shipped defaults, as plain dicts -- used to seed the config file."""
    return [_vendor_to_dict(v) for v in _DEFAULT_VENDORS]


def load_vendor_rows() -> list[dict]:
    """
    Raw rows from config/vendor_pixels.json, or the shipped defaults if
    the file doesn't exist yet or fails to parse.
    """
    try:
        with open(VENDOR_CONFIG_PATH, encoding="utf-8") as f:
            rows = json.load(f)
        if isinstance(rows, list) and rows:
            return rows
    except (OSError, json.JSONDecodeError):
        pass
    return default_vendor_rows()


def save_vendor_rows(rows: list[dict]) -> None:
    """Writes the vendor table back to config/vendor_pixels.json."""
    VENDOR_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(VENDOR_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_vendors() -> tuple[Vendor, ...]:
    """
    Vendor table reconcile_pixels() actually uses: config file, else
    defaults. Rows without ts_terms/host_terms (DV Blocking, DV
    Integration, DV Omni) are kept -- they're reference-only rows read
    directly by name (see official_pixel_for()), not matched in the
    generic per-vendor loop below.
    """
    rows = load_vendor_rows()
    vendors = [_dict_to_vendor(row) for row in rows]
    vendors = [v for v in vendors if v.name]
    return tuple(vendors) if vendors else _DEFAULT_VENDORS


def official_pixel_for(name: str, account: str = "") -> str:
    """
    The official_pixel value configured for a vendor row by name, e.g.
    official_pixel_for("DV Omni"). Used by DV-003 to fetch the
    reference for a subtype that isn't in the generic PIX-002 loop.

    If `account` is given and more than one row shares that name
    (e.g. the same DV Omni reference split per account), the
    account-scoped row wins; otherwise the first unscoped row is used.
    """
    candidates = [v for v in load_vendors() if v.name == name]

    if account:
        scoped = next(
            (v for v in candidates if norm_compare(v.account) == norm_compare(account)),
            None,
        )
        if scoped:
            return scoped.official_pixel

    unscoped = next((v for v in candidates if not v.account), None)
    if unscoped:
        return unscoped.official_pixel

    return candidates[0].official_pixel if candidates else ""


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
    official: str = ""


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


def reconcile_pixels(ts_result, placement_view, account: str = "") -> PixelReconciliation:
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

        for vendor in load_vendors():
            if not _declared(vendor, vendor_raw):
                continue
            if fmt not in vendor.formats:
                continue
            if site_name in vendor.site_exceptions:
                continue
            if vendor.account and norm_compare(vendor.account) != norm_compare(account):
                continue

            if vendor.name == "DV Monitoring":
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

                if match and not pixel_matches_official(match, vendor.official_pixel):
                    check.result = "REVIEW"
                    check.found = match
                    check.official = vendor.official_pixel
                    check.message = (
                        f"{vendor.name} pixel is loaded, but doesn't match "
                        "the official pixel on record for this vendor."
                    )
                elif match:
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

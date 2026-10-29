"""
Resolucion y clasificacion de colores de relleno.

PRINCIPIO CLAVE (correccion del usuario):
  El color SOLO tiene significado dentro de la DATA REGION, es decir:
    - hoja visible y relevante
    - fila > header
    - columna mapeada a un campo canonico de AdOps
  Leyendas, titulos, headers, contactos y hojas ocultas quedan FUERA.

Semantica de negocio:
  VERDE    -> NEW / valor nuevo del swap     -> debe existir y estar activo
  ROJO     -> REMOVE / valor viejo del swap  -> debe estar desasignado
  AMARILLO -> HOLD / pending                 -> FUERA DE ALCANCE, cero findings
  GRIS     -> no trabajado                   -> FUERA DE ALCANCE, cero findings
  BLANCO   -> contexto existente             -> se valida solo si tiene hijos
  UNKNOWN  -> nunca se adivina               -> REVIEW
"""
from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from openpyxl import load_workbook

INDEXED_RGB: dict[int, str] = {
    0: "000000", 1: "FFFFFF", 2: "FF0000", 3: "00FF00", 4: "0000FF",
    5: "FFFF00", 6: "FF00FF", 7: "00FFFF", 8: "000000", 9: "FFFFFF",
    10: "FF0000", 11: "00FF00", 12: "0000FF", 13: "FFFF00", 14: "FF00FF",
    15: "00FFFF", 16: "800000", 17: "008000", 18: "000080", 19: "808000",
    22: "808080", 23: "9999FF", 26: "FFFFCC", 27: "CCFFFF", 29: "660066",
    31: "0066CC", 32: "CCCCFF", 34: "CCFFFF", 35: "CCFFCC", 36: "FFFF99",
    37: "99CCFF", 38: "FF99CC", 40: "FFCC99", 41: "3366FF", 42: "33CCCC",
    43: "99CC00", 44: "FFCC00", 45: "FF9900", 46: "FF6600", 47: "666699",
    48: "969696", 49: "003366", 50: "339966", 51: "003300", 52: "333300",
    53: "993300", 55: "333399", 56: "333333", 64: "000000", 65: "FFFFFF",
}

GREEN = "GREEN"
RED = "RED"
YELLOW = "YELLOW"
GREY = "GREY"
WHITE = "WHITE"
UNKNOWN = "UNKNOWN"

SCOPE_EXCLUDED = {YELLOW, GREY}
ACTIONABLE = {GREEN, RED}

_HEX = re.compile(r"^[0-9A-Fa-f]{6}$")
_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
_XML_ORDER_TO_THEME_IDX = [1, 0, 3, 2, 4, 5, 6, 7, 8, 9, 10, 11]

# ----------------------------------------------------------------- theme

def read_workbook_theme(path: Path) -> dict[int, str]:
    """Extrae el clrScheme del workbook: {indice_theme: 'RRGGBB'}."""
    try:
        wb = load_workbook(path, data_only=True, keep_vba=False)
        raw = getattr(wb, "loaded_theme", None)
        wb.close()
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        root = ET.fromstring(raw)
    except Exception:
        return {}
    scheme = root.find(".//a:clrScheme", _NS)
    if scheme is None:
        return {}

    out: dict[int, str] = {}
    for pos, child in enumerate(list(scheme)):
        if pos >= len(_XML_ORDER_TO_THEME_IDX):
            break
        srgb = child.find("a:srgbClr", _NS)
        val = srgb.get("val") if srgb is not None else None
        if val is None:
            sysclr = child.find("a:sysClr", _NS)
            val = sysclr.get("lastClr") if sysclr is not None else None
        if val and _HEX.match(val):
            out[_XML_ORDER_TO_THEME_IDX[pos]] = val.upper()
    return out

def apply_tint(rgb: str, tint: float) -> str:
    """Algoritmo de tint de Excel: modifica luminosidad en HLS."""
    if not tint:
        return rgb
    try:
        r = int(rgb[0:2], 16) / 255
        g = int(rgb[2:4], 16) / 255
        b = int(rgb[4:6], 16) / 255
    except ValueError:
        return rgb
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = l * (1 + tint) if tint < 0 else l * (1 - tint) + tint
    l = max(0.0, min(1.0, l))
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return "{:02X}{:02X}{:02X}".format(round(r2 * 255), round(g2 * 255), round(b2 * 255))

def resolve_rgb(token: str | None, theme_map: dict[int, str] | None = None) -> str | None:
    """Normaliza el token de openpyxl a RRGGBB."""
    if not token:
        return None
    if token.startswith("IDX:"):
        try:
            return INDEXED_RGB.get(int(token[4:]))
        except ValueError:
            return None
    if token.startswith("THEME:"):
        if not theme_map:
            return None
        parts = token.split(":")
        try:
            idx = int(parts[1])
            tint = float(parts[2]) if len(parts) > 2 else 0.0
        except (IndexError, ValueError):
            return None
        base = theme_map.get(idx)
        return apply_tint(base, tint) if base else None
    t = token.upper()
    if len(t) == 8 and _HEX.match(t[2:]):
        return t[2:]
    if len(t) == 6 and _HEX.match(t):
        return t
    return None

def classify(rgb: str | None) -> tuple[str, str]:
    """
    Clasifica por familia. Devuelve (familia, confianza).
    Umbral de gris bajo (s <= 0.04): los verdes/amarillos palidos de las TS
    tienen saturacion debil pero SI son intencion de cambio (bug B32).
    """
    if not rgb or len(rgb) != 6 or not _HEX.match(rgb):
        return UNKNOWN, "NONE"
    try:
        r = int(rgb[0:2], 16) / 255
        g = int(rgb[2:4], 16) / 255
        b = int(rgb[4:6], 16) / 255
    except ValueError:
        return UNKNOWN, "NONE"

    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue = h * 360

    if s <= 0.04:
        return (WHITE, "HIGH") if v >= 0.93 else (GREY, "HIGH")

    conf = "HIGH" if s >= 0.25 else "MEDIUM"

    if hue <= 14 or hue >= 346:
        return RED, conf
    if 15 <= hue <= 44:
        return YELLOW, "LOW"
    if 45 <= hue <= 72:
        return YELLOW, conf
    if 73 <= hue <= 175:
        return GREEN, conf
    return UNKNOWN, "NONE"

class ColorResolver:
    """Resuelve y cachea la familia de cada token de fill de un workbook."""

    def __init__(self, theme_map: dict[int, str] | None = None):
        self.theme_map = theme_map or {}
        self._cache: dict[str, tuple[str, str, str | None]] = {}

    def family(self, token: str | None) -> tuple[str, str, str | None]:
        """Devuelve (familia, confianza, rgb). Sin fill -> WHITE."""
        if not token:
            return WHITE, "HIGH", None
        hit = self._cache.get(token)
        if hit is None:
            rgb = resolve_rgb(token, self.theme_map)
            fam, conf = classify(rgb)
            hit = (fam, conf, rgb)
            self._cache[token] = hit
        return hit

# ----------------------------------------------------------------- inventario

@dataclass
class ColorInfo:
    """Un fill distinto encontrado DENTRO de la data region."""
    token: str
    rgb: str | None = None
    family: str = UNKNOWN
    confidence: str = "NONE"
    count: int = 0
    samples: list[str] = field(default_factory=list)
    sheets: set[str] = field(default_factory=set)
    fields: set[str] = field(default_factory=set)

def inventory_region(cells_by_field: list[tuple[str, str, object]],
                     resolver: ColorResolver) -> dict[str, ColorInfo]:
    """
    Inventaria fills solo dentro de la data region.
    cells_by_field: lista de (sheet, field_name, Cell)
    """
    out: dict[str, ColorInfo] = {}
    for sheet, fname, cell in cells_by_field:
        token = getattr(cell, "fill_rgb", None)
        if not token:
            continue
        info = out.get(token)
        if info is None:
            fam, conf, rgb = resolver.family(token)
            info = ColorInfo(token=token, rgb=rgb, family=fam, confidence=conf)
            out[token] = info
        info.count += 1
        info.sheets.add(sheet)
        info.fields.add(fname)
        if len(info.samples) < 4:
            txt = cell.text[:46] if cell.text else "(vacia)"
            info.samples.append(f"{sheet}!{cell.ref.col_letter}{cell.ref.row} [{fname}]: {txt}")
    return out
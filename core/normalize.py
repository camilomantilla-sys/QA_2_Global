"""
Normalizacion. Regla de oro: raw se conserva, normalizado es derivado.
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_PLATFORM_ID_SUFFIX = re.compile(r"\s*\((\d+)\)\s*$")
_DIMS = re.compile(r"(\d{1,5})\s*[xX\u00d7]\s*(\d{1,5})")

def norm_text(value: str | None) -> str:
    """Trim + colapso de espacios. Preserva mayusculas."""
    if value is None:
        return ""
    return _WS.sub(" ", str(value).replace("\u00a0", " ")).strip()

def norm_compare(value: str | None) -> str:
    """Forma canonica para comparar: sin case, sin espacios sobrantes."""
    return norm_text(value).casefold()

def norm_key(value: str | None) -> str:
    """
    Llave para matchear nombres de columna.
    'Third_Party_ID' / 'Third Party ID' -> 'thirdpartyid'
    'Base_File_Size (KB)' -> 'basefilesizekb'

    El '%' se preserva como 'pct' porque distingue headers reales:
      'Creative Rotation'    -> 'creativerotation'
      'Creative Rotation %'  -> 'creativerotationpct'
    Sin esto ambos colapsaban a la misma llave (bug B38).
    """
    if value is None:
        return ""
    s = str(value).casefold().replace("%", "pct")
    return re.sub(r"[^a-z0-9]", "", s)

def clean_id(value: object) -> str:
    """
    IDs siempre como string. Nunca float.
    Innovid/Excel pueden devolver 10139964.0 -> '10139964'
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    s = str(value)
    for ch in ("\n", "\r", "\t", '"', "'"):
        s = s.replace(ch, "")
    return s.strip()

def split_platform_id(value: str | None) -> tuple[str, str | None]:
    """
    'FY26_Stock_AU_Display_DV360_C1_V3 (288292)' -> ('FY26_..._V3', '288292')

    Resuelve el bug B11: Innovid inyecta el ID entre parentesis y la TS no lo tiene.
    """
    text = norm_text(value)
    if not text:
        return "", None
    m = _PLATFORM_ID_SUFFIX.search(text)
    if m:
        return text[: m.start()].strip(), m.group(1)
    return text, None

def norm_dims(value: object) -> str:
    """'160 x 600' / '160X600' / '160\u00d7600' -> '160x600'"""
    text = norm_text(str(value) if value is not None else "")
    if not text:
        return ""
    m = _DIMS.search(text)
    if m:
        return f"{int(m.group(1))}x{int(m.group(2))}"
    return text.replace(" ", "").casefold()

def dims_from_name(name: str | None) -> str | None:
    """
    Ultimo recurso: extraer dimensiones del nombre del placement.
    'DV360_..._BAN_160x600_NA_...' -> '160x600'
    Confianza MEDIUM (regla DIM-002).
    """
    text = norm_text(name)
    if not text:
        return None
    found = _DIMS.findall(text)
    if len(found) == 1:
        return f"{int(found[0][0])}x{int(found[0][1])}"
    return None

def to_bool(value: object) -> bool | None:
    """'Yes'/'No' de Innovid. None si no es interpretable."""
    text = norm_compare(str(value) if value is not None else "")
    if text in ("yes", "y", "true", "1", "si", "s\u00ed"):
        return True
    if text in ("no", "n", "false", "0"):
        return False
    return None
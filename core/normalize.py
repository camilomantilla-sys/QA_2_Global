"""
Normalizacion. Regla de oro: raw se conserva, normalizado es derivado.
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_EXCEL_CR = re.compile(r"_x000[dDaA]_")
_PLATFORM_ID_SUFFIX = re.compile(r"\s*\((\d+)\)\s*$")
_DIMS = re.compile(r"(\d{1,5})\s*[xX\u00d7]\s*(\d{1,5})")

def norm_text(value: str | None) -> str:
    """Trim + colapso de espacios. Preserva mayusculas."""
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ")
    # Excel serializa un salto de linea dentro de una celda como el
    # literal "_x000D_". Sobrevive al parseo y se pega al valor: una URL
    # partida con Alt+Enter llegaba como "&_x000D_ imm_pid=..." y se
    # reportaba como URL distinta cuando es la misma. Se trata como el
    # salto de linea que representa.
    text = _EXCEL_CR.sub(" ", text)
    return _WS.sub(" ", text).strip()

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

_ALNUM = re.compile(r"[^a-z0-9]+")
_MIN_SITE_TOKEN = 4


def site_names_match(left: object, right: object) -> bool:
    """
    ¿Son el mismo site escrito distinto?

    La TS y la plataforma nombran el mismo site de formas que no se
    contienen una a otra: "The Trade Desk" vs "FC TradeDesk-DBM". Basta
    con que compartan una palabra significativa -- se comparan los
    tokens de una contra la forma sin separadores de la otra, para que
    "trade" enganche dentro de "tradedesk".
    """
    a, b = norm_compare(left), norm_compare(right)
    if not a or not b:
        return False
    if a == b:
        return True

    flat_a, flat_b = _ALNUM.sub("", a), _ALNUM.sub("", b)
    if flat_a in flat_b or flat_b in flat_a:
        return True

    for text, other in ((a, flat_b), (b, flat_a)):
        for token in _ALNUM.split(text):
            if len(token) >= _MIN_SITE_TOKEN and token in other:
                return True
    return False


def dims_match(left: object, right: object) -> bool:
    """
    Compara dimensiones tolerando como se declara el video.

    Un placement de video se escribe 0x0 en un lado y con su tamano real
    (1920x1080, 640x480) en el otro; las dos formas significan lo mismo,
    asi que 0x0 hace match con cualquier dimension. Sin esto el filtro
    por dimension descartaba los creativos de video y terminaban
    reportados como "extra creative in Innovid".
    """
    a, b = norm_dims(left), norm_dims(right)
    if not a or not b:
        return True
    if a == b:
        return True
    return "0x0" in (a, b)

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
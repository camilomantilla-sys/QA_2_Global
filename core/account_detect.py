"""
De que cuenta es la solicitud, deducido de los archivos.

La cuenta decide reglas: el pixel oficial de cada cuenta (PIX-002),
Remove VPAID (solo Unilever y Wendy's), el CGEN (solo Adobe). Y se
olvida: los dos bundles de prueba del 18-nov (BlackRock y Wendy's) se
guardaron con "All / unknown".

La TS lo dice casi siempre. En Campaign Information:

    Advertiser:     WENDY'S INTERNTL PBU      Advertiser ID: 38314
    Advertiser:     BlackRock US                             29916
    Advertiser:     Adobe Wavemaker WW                       15091
    Advertiser:     Unilever_US / Dove Holiday               29418

y en los nombres: TS_4192_WEN_..., TS_US_BLK_..., UNE_KSI_231,
ULV_SMQ_209, TS_3818_UNI-C_...

Se usa en ese orden: el Advertiser, su ID, y las siglas de los nombres
de archivo y de la campana. Si las siglas apuntan a dos cuentas, no se
adivina.
"""
from __future__ import annotations

import re
from io import BytesIO

#: Palabras del Advertiser que nombran la cuenta.
ADVERTISER_WORDS = (
    ("wendy", "Wendy's"),
    ("blackrock", "BlackRock"),
    ("unilever", "Unilever"),
    ("adobe", "Adobe"),
)

#: Advertiser ID de Innovid de cada cuenta, visto en TS reales.
ADVERTISER_IDS = {
    "38314": "Wendy's",
    "29916": "BlackRock",
    "29418": "Unilever",
    "15091": "Adobe",
}

#: Siglas en los nombres de archivo y de campana.
TOKENS = {
    "WEN": "Wendy's", "WENDYS": "Wendy's",
    "BLK": "BlackRock", "BLACKROCK": "BlackRock",
    "UNE": "Unilever", "ULV": "Unilever", "UNI": "Unilever", "UNILEVER": "Unilever",
    "ADOBE": "Adobe",
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^A-Za-z0-9]+", str(text or "").upper()) if t]


def detect_account(advertiser: str = "", advertiser_id: str = "", campaign: str = "",
                   file_names=()) -> tuple[str, str]:
    """(cuenta, de donde salio) o ("", "") si no hay como saberlo."""
    adv = str(advertiser or "").casefold()
    for word, account in ADVERTISER_WORDS:
        if word in adv:
            return account, f"Advertiser \"{str(advertiser).strip()}\" in the Traffic Sheet"

    aid = str(advertiser_id or "").strip().split(".")[0]
    if aid in ADVERTISER_IDS:
        return ADVERTISER_IDS[aid], f"Advertiser ID {aid} in the Traffic Sheet"

    found: dict[str, str] = {}
    for source in (campaign, *file_names):
        for token in _tokens(source):
            if token in TOKENS:
                found.setdefault(TOKENS[token], f"\"{token}\" in {str(source).strip()[:60]}")
    if len(found) == 1:
        [(account, why)] = found.items()
        return account, why
    return "", ""


def peek_ts_identity(data: bytes) -> dict[str, str]:
    """
    Advertiser, Advertiser ID y Campaign Name de la hoja Campaign
    Information, sin leer la TS entera. Cualquier falla devuelve {}:
    esto nunca debe frenar una carga.
    """
    try:
        from openpyxl import load_workbook

        from core.normalize import norm_key

        wanted = {"advertiser": "advertiser", "advertiserid": "advertiser_id",
                  "campaignname": "campaign"}
        wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
        try:
            sheet = next((ws for ws in wb.worksheets
                          if norm_key(ws.title) in ("campaigninformation", "campaigninfo")), None)
            if sheet is None:
                return {}
            out: dict[str, str] = {}
            for row in sheet.iter_rows(min_row=1, max_row=45):
                for idx, cell in enumerate(row):
                    key = wanted.get(norm_key(str(cell.value or "").rstrip(":")))
                    if not key or key in out:
                        continue
                    value = next((c.value for c in row[idx + 1:] if c.value not in (None, "")), "")
                    out[key] = str(value).strip()
            return out
        finally:
            wb.close()
    except Exception:
        return {}


def detect_from_files(ts_name: str, ts_data: bytes, other_names=()) -> tuple[str, str]:
    """La cuenta de una solicitud a partir de la TS y los nombres de los exports."""
    info = peek_ts_identity(ts_data)
    return detect_account(info.get("advertiser", ""), info.get("advertiser_id", ""),
                          info.get("campaign", ""), (ts_name, *other_names))

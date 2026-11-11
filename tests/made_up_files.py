"""
Archivos inventados para probar la cadena completa sin datos de cliente.

Una Traffic Sheet de 10 placements 1x1 (5 verdes, 2 rojos, 1 amarillo
y 2 blancos) y el Placement-Creative View de Innovid que le
corresponde. Ningun nombre, ID ni URL es real.
"""
from __future__ import annotations

import datetime
import tempfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import PatternFill

TS_HEADERS = [
    "Site Name", "Placement ID", "Placement Name", "Start Date", "End Date",
    "Dimensions", "Creative Names", "Landing Page", "Vendors / Pixels",
    "Creative Rotation %", "CGEN", "Notes",
]
FILLS = {
    "green": PatternFill("solid", fgColor="FF00FF00"),
    "red": PatternFill("solid", fgColor="FFFF0000"),
    "yellow": PatternFill("solid", fgColor="FFFFFF00"),
}
START = datetime.date(2027, 1, 6)
END = datetime.date(2027, 3, 30)
LP = "https://landing.example"


def _bytes(wb: Workbook, name: str) -> bytes:
    target = Path(tempfile.mkdtemp()) / name
    wb.save(target)
    return target.read_bytes()


def traffic_sheet() -> bytes:
    """5 verdes, 2 rojas, 1 amarilla y 2 blancas."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Placements"
    for col, name in enumerate(TS_HEADERS, start=1):
        ws.cell(1, col, name)
    for i in range(10):
        values = [
            f"Site{'ABC'[i % 3]}", 900100 + i, f"DEMO_Placement_{i}",
            START, END, "1x1", f"DEMO_Creative_{i}", LP, "", 100, "ABCD", "",
        ]
        colour = "green" if i < 5 else "red" if i < 7 else "yellow" if i < 8 else None
        for col, value in enumerate(values, start=1):
            cell = ws.cell(i + 2, col, value)
            if colour:
                cell.fill = FILLS[colour]
    wb.create_sheet("Campaign Information")
    return _bytes(wb, "ts.xlsx")


PC_HEADERS = [
    "Enabled", "Site_ID", "Placement_ID", "Creative_ID", "Site", "Placement",
    "Dimensions", "Filename", "Placement_Type", "Start_Date", "End_Date",
    "Creative_Name", "Status", "Clicktag_1",
]


def placement_creative(ids=range(900100, 900105)) -> bytes:
    """El export de Innovid con un creativo por placement pedido."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Import"
    ws.cell(1, 1, "Campaign:")
    ws.cell(1, 2, "DEMO Campaign")
    ws.cell(2, 1, "Export Type:")
    ws.cell(2, 2, "Placement-Creative")
    for col, name in enumerate(PC_HEADERS, start=1):
        ws.cell(10, col, name)
    row = 11
    for pid in ids:
        i = pid - 900100
        site = f"Site{'ABC'[i % 3]}"
        ws.append([None, 77, pid, None, site, f"DEMO_Placement_{i} ({pid})",
                   "1x1", f"DEMO_Placement_{i}", "HTML", START, END, None, "Active", None])
        ws.append([True, 77, pid, 500100 + i, site, f"DEMO_Placement_{i} ({pid})",
                   "1x1", f"DEMO_Creative_{i}", "HTML", START, END,
                   f"DEMO_Creative_{i}", "Active", LP])
        row += 2
    return _bytes(wb, "pc.xlsx")


def session_bundle(account: str = "Unilever") -> bytes:
    """Un session bundle como el que guarda "Save session bundle"."""
    import io
    import json
    import zipfile

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("files/ts/DEMO_TS.xlsx", traffic_sheet())
        zf.writestr("files/pc/DEMO_PC.xlsx", placement_creative())
        zf.writestr("files/evidence/1_shot.png", b"\x89PNG demo")
        manifest = {
            "profile": "AUTO", "account": account, "campaign": "DEMO",
            "wrike_id": "000000", "implemented_by": "Demo Person",
            "implementation_date": "2027-01-05", "saved_at": "2027-01-05T10:00:00",
            "files": {"ts": "DEMO_TS.xlsx", "pc": "DEMO_PC.xlsx",
                      "evidence": [{"name": "shot.png", "stored_as": "1_shot.png"}]},
        }
        zf.writestr("manifest.json", json.dumps(manifest))
    return out.getvalue()

"""
Solicitudes inventadas (TS + Placement-Creative + Placement) con el
formato real de WPP / Innovid, para probar la interpretacion de QA2.
Ningun nombre, ID ni URL es real. Los casos estan en
tests/odd_requests.py y las pruebas en tests/test_odd_requests.py.

Un escenario es un dict:
  placements: [dict(pid, code, site, dims, start, end, group, lp, vendors, fill)]
      pid=None o "#N/A" -> celda con #N/A (y site/fechas/dims tambien)
      fill: color para toda la fila ("green"/"red"/"grey"/"yellow") o
            dict campo -> color
  rotations: [dict(group, creative, adid, cid, ctype, dims, weight, start, end, lp, fill)]
      group=None -> celda vacia (combinada visualmente con la de arriba)
  lps: [dict(name, url, fill)]      name=None -> celda vacia
  innovid: [dict(pid, code, site, dims, start, end, status, stopped,
                 creatives=[dict(cid, name, url, start, end, enabled, weight, status)])]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

COLORS = {"green": "FF92D050", "red": "FFFF0000", "yellow": "FFFFFF00",
          "grey": "FF808080", "lightgreen": "FFC6EFCE"}

PC_HEADERS = ['Enabled', 'Site_ID', 'Placement_ID', 'Creative_ID', 'Site', 'Placement', 'Dimensions', 'Legacy_Decision_Tree', 'Decision_Tree_Name', 'Decision_Tree_ID', 'Filename', 'Placement_Type', 'Placement_Creative_ID', 'Start_Date', 'End_Date', 'Third_Party_ID', 'Creative_Name', 'ClickTags', 'Rotation', 'Clicktag_1', 'Clicktag_2', 'Third_Party_Impression_1', 'Third_Party_Impression_2', 'Third_Party_Survey', 'Third_Party_Survey_2', 'Creative_Group_1', 'Creative_Group_2', 'Status', 'Stopped', 'Ad_Type', 'Creative_Type', 'Video', 'Rich']
PL_HEADERS = ['Site_ID', 'Placement_ID', 'Site', 'Placement', 'Dimensions', 'Start_Date', 'End_Date', 'Placement_Type', 'Status', 'Hidden', 'Stopped', 'Package_ID', 'Package_Name', 'Third_Party_ID', 'Clicktag_1', 'Third_Party_Impression_1', 'Third_Party_Survey']
TS_PL = ['Site Name', 'Placement ID', 'Placement Name', 'Start Date', 'End Date', 'Dimensions', 'Creative Rotation', 'Landing Page', 'Vendors / Pixels', 'Additional Requirements (Transcodes, Macros, Attribution Settings, etc.)']
TS_ROT = ['Creative Rotation Name', 'Creative Name', 'Universal Ad-ID (Video/Audio Only)', 'Creative ID', 'Creative Type', 'Dimensions / Durations', 'Rotation (%) or Even', 'Sequential', 'Start Date', 'End Date', 'Landing Page Name', 'Rich Media Click Out Event/s', 'Creative Links / Sharepoint Folder']


def D(s):
    return dt.datetime.strptime(s, "%Y-%m-%d") if isinstance(s, str) and len(s) == 10 and s[4] == "-" else s


def _fill(cell, color):
    if color:
        cell.fill = PatternFill("solid", fgColor=COLORS[color])


def _color_for(spec, field):
    f = spec.get("fill")
    if isinstance(f, dict):
        return f.get(field, f.get("*"))
    return f


def pname(code, site, dims, label):
    return f"{code}|TST|HOL|001|{site}|{dims.replace('x', ' x ')}|{label}"


def write_ts(sc, path):
    wb = Workbook()
    ci = wb.active
    ci.title = "Campaign Information"
    legend = [("New item/Change", "green"), ("Elements on Hold/Pending", "yellow"),
              ("Elements to be disabled", "red"), ("Elements previously disabled", "grey"),
              ("Element that has already been addressed", None)]
    ci["A3"] = "Legend:"
    for i, (txt, col) in enumerate(legend):
        ci.cell(4 + i, 1, txt)
        _fill(ci.cell(4 + i, 1), col)
    info = [("Traffic Sheet Version:", "Q4_2026"), ("Network ID:", "N/A"),
            ("Advertiser:", sc.get("advertiser", "WENDY'S INTERNTL PBU")),
            ("Advertiser ID:", sc.get("adv_id", "38314")),
            ("Campaign Name:", sc.get("campaign", "TST_HOL_001_Holiday Test")),
            ("Campaign ID:", sc.get("ts_campaign_id", "500100")),
            ("Campaign Start:", D("2026-11-01")), ("Campaign End:", D("2027-01-31"))]
    for i, (k, v) in enumerate(info):
        ci.cell(10 + i, 1, k)
        ci.cell(10 + i, 2, v)

    ws = wb.create_sheet("Placements")
    ws.append(TS_PL)
    keys = ["site", "pid", "name", "start", "end", "dims", "group", "lp", "vendors", "extra"]
    for p in sc["placements"]:
        na = p.get("pid") in (None, "#N/A")
        vals = {
            "site": "#N/A" if na else p.get("ts_site", p["site"]),
            "pid": "#N/A" if na else p["pid"],
            "name": pname(p["code"], p["site"], p.get("dims", "1x1"), p.get("label", "Display")),
            "start": "#N/A" if na else D(p.get("start", "2026-11-16")),
            "end": "#N/A" if na else D(p.get("end", "2026-12-31")),
            "dims": "#N/A" if na else p.get("ts_dims", p.get("dims", "1x1")).replace("x", " x "),
            "group": p.get("group"), "lp": p.get("lp"),
            "vendors": p.get("vendors", ""), "extra": p.get("extra", ""),
        }
        r = ws.max_row + 1
        for c, k in enumerate(keys, start=1):
            if vals[k] is not None:
                ws.cell(r, c, vals[k])
            _fill(ws.cell(r, c), _color_for(p, k))
        if p.get("hidden"):
            ws.row_dimensions[r].hidden = True

    rot = wb.create_sheet("Creative Rotations")
    rot.append(TS_ROT)
    group_start = 2
    rkeys = ["group", "creative", "adid", "cid", "ctype", "dims", "weight", "seq", "start", "end", "lp", "click", "links"]
    for x in sc.get("rotations", []):
        vals = {"group": x.get("group"), "creative": x.get("creative"), "adid": x.get("adid", "N/A"),
                "cid": x.get("cid"), "ctype": x.get("ctype", "Site Serve"), "dims": x.get("dims", "1x1"),
                "weight": x.get("weight", "Even"), "seq": "N/A", "start": D(x.get("start", "2026-11-16")),
                "end": D(x.get("end", "2026-12-31")), "lp": x.get("lp"), "click": "N/A", "links": "N/A"}
        r = rot.max_row + 1
        for c, k in enumerate(rkeys, start=1):
            if vals[k] is not None:
                rot.cell(r, c, vals[k])
            _fill(rot.cell(r, c), _color_for(x, k))
            if x.get("font"):
                rot.cell(r, c).font = Font(color=COLORS[x["font"]])
        if x.get("hidden"):
            rot.row_dimensions[r].hidden = True
        if x.get("group") is not None:
            group_start = r
        elif x.get("merge", True) and r > 2:
            # Como en las TS reales: la celda del grupo va combinada.
            rot.merge_cells(start_row=group_start, start_column=1, end_row=r, end_column=1)

    lp = wb.create_sheet("Landing Pages")
    lp.append(["Landing Page Name", "Landing Page URL"])
    for x in sc.get("lps", []):
        r = lp.max_row + 1
        if x.get("name") is not None:
            lp.cell(r, 1, x["name"])
        lp.cell(r, 2, x["url"])
        _fill(lp.cell(r, 1), _color_for(x, "name"))
        _fill(lp.cell(r, 2), _color_for(x, "url"))
    wb.save(path)


def _export_head(ws, sc, kind):
    ws["A1"] = "This template allows you to make bulk changes"
    ws["A3"], ws["B3"], ws["C3"], ws["D3"] = "Campaign Name:", sc.get("campaign", "TST_HOL_001_Holiday Test"), "Campaign ID:", sc.get("campaign_id", "500100")
    ws["A4"], ws["B4"], ws["C4"], ws["D4"] = "Media Buyer:", "Test (INV)", "Export Type:", kind
    ws["A5"], ws["B5"], ws["C5"], ws["D5"] = "Media Buyer Email:", "prisma@example.com", "Export Date:", "2026-11-18"
    ws["A6"], ws["B6"] = "Advertiser:", "Test (INV)"
    ws["A7"], ws["B7"] = "Start Date:", "2026-11-01"
    ws["A8"], ws["B8"] = "End Date:", "2027-01-31"


def write_exports(sc, pc_path, pl_path):
    pc = Workbook()
    ws = pc.active
    ws.title = "Import"
    _export_head(ws, sc, "Creative Level (entire campaign)")
    for c, h in enumerate(PC_HEADERS, start=1):
        ws.cell(10, c, h)
    pl = Workbook()
    wl = pl.active
    wl.title = "Import"
    _export_head(wl, sc, "Placement Level (entire campaign)")
    for c, h in enumerate(PL_HEADERS, start=1):
        wl.cell(10, c, h)
    pcid = 70000000
    for p in sc["innovid"]:
        name = pname(p["code"], p["site"], p.get("dims", "1x1"), p.get("label", "Display"))
        ptype = p.get("ptype", "Multi-tracker" if p.get("dims", "1x1") == "1x1" else "Standard Banner")
        stopped = p.get("stopped", False)
        wl.append({1: "18330", 2: p["pid"], 3: f"{p['site']} (18330)", 4: name, 5: p.get("dims", "1x1"),
                   6: p.get("start", "2026-11-16"), 7: p.get("end", "2026-12-31"), 8: ptype,
                   9: "Stopped" if stopped else p.get("status", "Available"), 10: "No",
                   11: "Yes" if stopped else "No", 12: "300000", 13: "PKG", 14: p["code"],
                   15: p.get("placement_click", ""), 16: "", 17: p.get("survey", "")})
        for cr in p.get("creatives", []):
            pcid += 1
            row = {h: "" for h in PC_HEADERS}
            row.update({"Enabled": "Yes" if cr.get("enabled", True) else "No", "Site_ID": "18330",
                        "Placement_ID": p["pid"], "Creative_ID": cr["cid"], "Site": p["site"],
                        "Placement": f"{name} ({p['pid']})", "Dimensions": cr.get("dims", p.get("dims", "1x1")),
                        "Legacy_Decision_Tree": "No", "Filename": f"{cr['name']}.png ({cr['cid']})",
                        "Placement_Type": ptype, "Placement_Creative_ID": str(pcid),
                        "Start_Date": cr.get("start", p.get("start", "2026-11-16")),
                        "End_Date": cr.get("end", p.get("end", "2026-12-31")),
                        "Creative_Name": cr["name"], "ClickTags": "1", "Rotation": cr.get("weight", "1.00"),
                        "Clicktag_1": cr.get("url", ""), "Third_Party_Survey": cr.get("survey", p.get("survey", "")),
                        "Status": cr.get("status", "Active"), "Stopped": "Yes" if stopped else "No",
                        "Ad_Type": "altimage", "Creative_Type": "image", "Video": "No", "Rich": "No"})
            ws.append([row[h] for h in PC_HEADERS])
    pc.save(pc_path)
    pl.save(pl_path)


def build(sc, out: Path):
    for k in ("ts", "pc", "pl"):
        (out / k).mkdir(parents=True, exist_ok=True)
    write_ts(sc, out / "ts" / f"TS_9999_WEN_US_{sc['id']}.xlsx")
    write_exports(sc, out / "pc" / "pc.xlsx", out / "pl" / "pl.xlsx")
    (out / "expect.json").write_text(json.dumps(sc.get("expect", {}), indent=1), encoding="utf-8")

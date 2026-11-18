"""
Casos raros, estilo Wendy's, con fechas vigentes (nov-2026 a ene-2027).
Los arma tests/synthetic_requests.py; los revisa tests/test_odd_requests.py.
"""

OLD, NEW = "https://brand.example/old-display", "https://brand.example/holiday-display"
OLDV, NEWV = "https://brand.example/old-video", "https://brand.example/holiday-video"


def plc(pid, code, **kw):
    d = dict(pid=pid, code=code, site="DV360", dims="300x250", group="HOL 300x250", lp="Holiday Display GM")
    d.update(kw)
    return d


def inv(pid, code, creatives, **kw):
    d = dict(pid=pid, code=code, site="DV360", dims="300x250", creatives=creatives)
    d.update(kw)
    return d


def cr(cid, name, url, **kw):
    d = dict(cid=cid, name=name, url=url)
    d.update(kw)
    return d


def rot(group, creative, cid, lp, **kw):
    d = dict(group=group, creative=creative, cid=cid, ctype="Display", dims="300x250", lp=lp)
    d.update(kw)
    return d


SCENARIOS = [
    # 1. Swap de URL bajo el mismo nombre (nombre blanco, URL roja + URL verde).
    dict(id="s01_lp_swap_same_name",
         placements=[plc("9100001", "P4AA001"), plc("9100002", "P4AA002"), plc("9100003", "P4AA003")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8100001", "Holiday Display GM"),
                    rot(None, "HOL_300x250_B", "8100002", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url=OLD, fill={"url": "red"}),
              dict(name=None, url=NEW, fill={"url": "green"})],
         innovid=[inv("9100001", "P4AA001", [cr("8100001", "HOL_300x250_A", NEW), cr("8100002", "HOL_300x250_B", NEW)]),
                  inv("9100002", "P4AA002", [cr("8100001", "HOL_300x250_A", NEW), cr("8100002", "HOL_300x250_B", OLD)]),
                  inv("9100003", "P4AA003", [cr("8100001", "HOL_300x250_A", NEW), cr("8100002", "HOL_300x250_B", NEW)])],
         expect={"9100001": "URL-002 PASS", "9100002": "URL-002 FAIL (B old)", "9100003": "URL-002 PASS"}),

    # 2. LP entera en rojo + otra LP entera en verde, sin rotacion que las una.
    dict(id="s02_lp_red_whole_green_other",
         placements=[plc("9200001", "P4BB001", lp="Core Display GM"), plc("9200002", "P4BB002", lp="Core Display GM")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8200001", "Core Display GM")],
         lps=[dict(name="Core Display GM", url=OLD, fill="red"),
              dict(name="Holiday Display LP GM", url=NEW, fill="green")],
         innovid=[inv("9200001", "P4BB001", [cr("8200001", "HOL_300x250_A", NEW)]),
                  inv("9200002", "P4BB002", [cr("8200001", "HOL_300x250_A", OLD)])],
         expect={"9200001": "swap -> new LP: PASS", "9200002": "still old: FAIL"}),

    # 3. Swap de creativos dentro del DS: el rojo sigue activo en un placement.
    dict(id="s03_creative_swap_left_behind",
         placements=[plc("9300001", "P4CC001"), plc("9300002", "P4CC002")],
         rotations=[rot("HOL 300x250", "HOL_300x250_OLD", "8300001", "Holiday Display GM", fill="red"),
                    rot(None, "HOL_300x250_NEW", "8300002", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9300001", "P4CC001", [cr("8300002", "HOL_300x250_NEW", NEW)]),
                  inv("9300002", "P4CC002", [cr("8300001", "HOL_300x250_OLD", NEW), cr("8300002", "HOL_300x250_NEW", NEW)])],
         expect={"9300001": "CREATIVE_SWAP PASS", "9300002": "old creative still active: FAIL"}),

    # 4. Cambio de fechas (principio 5): creativo blanco, fechas rojas, y otra fila con fechas verdes.
    dict(id="s04_date_change",
         placements=[plc("9400001", "P4DD001")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8400001", "Holiday Display GM", start="2026-11-16", end="2026-12-15", fill={"start": "red", "end": "red"}),
                    rot(None, "HOL_300x250_A", "8400001", "Holiday Display GM", start="2026-11-16", end="2027-01-15", fill={"start": "green", "end": "green"})],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9400001", "P4DD001", [cr("8400001", "HOL_300x250_A", NEW, start="2026-11-16", end="2026-12-15")])],
         expect={"9400001": "date change; export creative end 12-15 vs TS 01-15 -> flagged"}),

    # 5. Placements nuevos en verde; uno no existe en Innovid.
    dict(id="s05_new_placements_one_missing",
         placements=[plc("9500001", "P4EE001", fill="green", group="HOL NEW 300x250"),
                     plc("9500002", "P4EE002", fill="green", group="HOL NEW 300x250")],
         rotations=[rot("HOL NEW 300x250", "HOL_300x250_N1", "8500001", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9500001", "P4EE001", [cr("8500001", "HOL_300x250_N1", NEW)])],
         expect={"9500001": "NEW PASS", "9500002": "PLC-001 FAIL"}),

    # 6. Placements en rojo (apagar): uno sigue Available, otro Stopped.
    dict(id="s06_disable",
         placements=[plc("9600001", "P4FF001", fill="red"), plc("9600002", "P4FF002", fill="red")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8600001", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9600001", "P4FF001", [cr("8600001", "HOL_300x250_A", NEW)]),
                  inv("9600002", "P4FF002", [cr("8600001", "HOL_300x250_A", NEW)], stopped=True)],
         expect={"9600001": "still running: FAIL/REVIEW", "9600002": "stopped: PASS"}),

    # 7. Filas #N/A: una se recupera, otra no esta en el export.
    dict(id="s07_na_rows",
         placements=[plc("9700001", "P4GG001"), plc("#N/A", "P4GG002"), plc("#N/A", "P4GG099")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8700001", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url=OLD, fill={"url": "red"}), dict(name=None, url=NEW, fill={"url": "green"})],
         innovid=[inv("9700001", "P4GG001", [cr("8700001", "HOL_300x250_A", NEW)]),
                  inv("9700002", "P4GG002", [cr("8700001", "HOL_300x250_A", NEW)])],
         expect={"9700001": "URL PASS", "9700002": "recovered, URL PASS", "P4GG099": "REVIEW"}),

    # 8. Mismo placement dos veces: fila gris (DS viejo) y fila blanca (DS vigente) con creativo verde.
    dict(id="s08_grey_old_row",
         placements=[plc("9800001", "P4HH001", group="HOL OLD 300x250", fill="grey"),
                     plc("9800001", "P4HH001", group="HOL 300x250")],
         rotations=[rot("HOL OLD 300x250", "OLD_300x250", "8800009", "Holiday Display GM", fill="grey"),
                    rot("HOL 300x250", "HOL_300x250_A", "8800001", "Holiday Display GM"),
                    rot(None, "HOL_300x250_B", "8800002", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9800001", "P4HH001", [cr("8800001", "HOL_300x250_A", NEW), cr("8800002", "HOL_300x250_B", NEW)])],
         expect={"9800001": "CREATIVE_ADD PASS, grey ignored"}),

    # 9. La LP del placement no existe en Landing Pages (typo) durante un swap.
    dict(id="s09_lp_typo",
         placements=[plc("9900001", "P4II001", lp="Holiday Display GM "), plc("9900002", "P4II002", lp="Holiday Dsiplay GM")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8900001", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url=OLD, fill={"url": "red"}), dict(name=None, url=NEW, fill={"url": "green"})],
         innovid=[inv("9900001", "P4II001", [cr("8900001", "HOL_300x250_A", NEW)]),
                  inv("9900002", "P4II002", [cr("8900001", "HOL_300x250_A", NEW)])],
         expect={"9900001": "trailing space ok -> PASS", "9900002": "typo: reached via rotation -> PASS, maybe note"}),

    # 10. Cambios marcados con color de LETRA, no de relleno.
    dict(id="s10_font_colour_only",
         placements=[plc("9010001", "P4JJ001")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8010001", "Holiday Display GM", font="red"),
                    rot(None, "HOL_300x250_B", "8010002", "Holiday Display GM", font="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9010001", "P4JJ001", [cr("8010002", "HOL_300x250_B", NEW)])],
         expect={"9010001": "nothing read as worked; should WARN that the TS uses font colour"}),

    # 11. Verde claro (estilo Good de Excel) en vez del verde de la leyenda.
    dict(id="s11_light_green",
         placements=[plc("9110001", "P4KK001", fill="lightgreen", group="HOL NEW 300x250")],
         rotations=[rot("HOL NEW 300x250", "HOL_300x250_N1", "8110001", "Holiday Display GM", fill="lightgreen")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9110001", "P4KK001", [cr("8110001", "HOL_300x250_N1", NEW)])],
         expect={"9110001": "NEW_PLACEMENT PASS"}),

    # 12. Solo la celda Landing Page de un placement en verde, con LP nueva verde; otros comparten la vieja.
    dict(id="s12_one_placement_lp_change",
         placements=[plc("9120001", "P4LL001", lp="Holiday Display New", fill={"lp": "green"}),
                     plc("9120002", "P4LL002", lp="Holiday Display GM")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8120001", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url=OLD), dict(name="Holiday Display New", url=NEW, fill="green")],
         innovid=[inv("9120001", "P4LL001", [cr("8120001", "HOL_300x250_A", NEW)]),
                  inv("9120002", "P4LL002", [cr("8120001", "HOL_300x250_A", OLD)])],
         expect={"9120001": "URL change PASS (new LP)", "9120002": "not worked"}),

    # 13. Creativo verde con nombre algo distinto en Innovid (.png, v2, mayusculas).
    dict(id="s13_name_noise",
         placements=[plc("9130001", "P4MM001")],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8130001", "Holiday Display GM"),
                    rot(None, "HOL_Holiday_300x250_B.jpg", "8130002", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9130001", "P4MM001", [cr("8130001", "HOL_300x250_A", NEW), cr("8130002", "hol_holiday_300x250_b", NEW)])],
         expect={"9130001": "CREATIVE_ADD PASS (name noise)"}),

    # 14. Fila verde oculta en Placements.
    dict(id="s14_hidden_green",
         placements=[plc("9140001", "P4NN001"), plc("9140002", "P4NN002", fill="green", hidden=True)],
         rotations=[rot("HOL 300x250", "HOL_300x250_A", "8140001", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9140001", "P4NN001", [cr("8140001", "HOL_300x250_A", NEW)])],
         expect={"9140002": "hidden: ignored, but said"}),
]

SCENARIOS2 = [
    # 16. Un placement con dos DS (dos filas blancas), swap de creativo solo en uno.
    dict(id="s16_two_ds_one_swap",
         placements=[plc("9160001", "P4PP001", group="BRAND A 300x250"), plc("9160001", "P4PP001", group="BRAND B 300x250")],
         rotations=[rot("BRAND A 300x250", "A_300x250_OLD", "8160001", "Holiday Display GM", fill="red"),
                    rot(None, "A_300x250_NEW", "8160002", "Holiday Display GM", fill="green"),
                    rot("BRAND B 300x250", "B_300x250", "8160003", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9160001", "P4PP001", [cr("8160002", "A_300x250_NEW", NEW), cr("8160003", "B_300x250", NEW)])],
         expect={"9160001": "CREATIVE_SWAP PASS; B untouched"}),

    # 17. DS nuevo: celda de grupo verde, creativos en blanco.
    dict(id="s17_new_ds_group_cell_green",
         placements=[plc("9170001", "P4QQ001", group="HOL NEW DS", fill={"group": "green"})],
         rotations=[rot("HOL NEW DS", "N_300x250_1", "8170001", "Holiday Display GM", fill={"group": "green"}),
                    rot(None, "N_300x250_2", "8170002", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9170001", "P4QQ001", [cr("8170001", "N_300x250_1", NEW)])],
         expect={"9170001": "N_300x250_2 missing: FAIL"}),

    # 18. IDs escritos raro: con espacios y como decimal.
    dict(id="s18_ids_as_text",
         placements=[plc(" 9180001 ", "P4RR001", fill="green", group="HOL NEW"), plc(9180002.0, "P4RR002", fill="green", group="HOL NEW")],
         rotations=[rot("HOL NEW", "N_300x250_1", "8180001", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9180001", "P4RR001", [cr("8180001", "N_300x250_1", NEW)]),
                  inv("9180002", "P4RR002", [cr("8180001", "N_300x250_1", NEW)])],
         expect={"both": "NEW PASS"}),

    # 19. Placement en rojo pero su rotacion trae un creativo verde (contradiccion).
    dict(id="s19_red_placement_green_creative",
         placements=[plc("9190001", "P4SS001", fill="red")],
         rotations=[rot("HOL 300x250", "A_300x250", "8190001", "Holiday Display GM"),
                    rot(None, "B_300x250", "8190002", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9190001", "P4SS001", [cr("8190001", "A_300x250", NEW), cr("8190002", "B_300x250", NEW)], stopped=True)],
         expect={"9190001": "contradiction -> REVIEW?"}),

    # 20. URL con parametros en otro orden y http vs https.
    dict(id="s20_url_params",
         placements=[plc("9200101", "P4TT001")],
         rotations=[rot("HOL 300x250", "A_300x250", "8200101", "Holiday Display GM")],
         lps=[dict(name="Holiday Display GM", url="https://brand.example/old?utm_source=x", fill={"url": "red"}),
              dict(name=None, url="https://brand.example/holiday?utm_source=dv360&utm_medium=display", fill={"url": "green"})],
         innovid=[inv("9200101", "P4TT001", [cr("8200101", "A_300x250", "http://brand.example/holiday?utm_medium=display&utm_source=dv360")])],
         expect={"9200101": "same URL, params reordered: PASS or note"}),

    # 21. Misma LP dos veces en blanco con URLs distintas.
    dict(id="s21_duplicate_lp",
         placements=[plc("9210001", "P4UU001", fill="green", group="HOL NEW")],
         rotations=[rot("HOL NEW", "N_300x250_1", "8210001", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=OLD), dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9210001", "P4UU001", [cr("8210001", "N_300x250_1", OLD)])],
         expect={"9210001": "ambiguous LP: should REVIEW, not silently pick one"}),

    # 22. Swap de creativo: el nuevo no se subio a Innovid.
    dict(id="s22_new_creative_missing",
         placements=[plc("9220001", "P4VV001")],
         rotations=[rot("HOL 300x250", "OLD_300x250", "8220001", "Holiday Display GM", fill="red"),
                    rot(None, "NEW_300x250", "8220002", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9220001", "P4VV001", [cr("8220001", "OLD_300x250", NEW, status="Disabled")])],
         expect={"9220001": "NEW missing: FAIL; OLD disabled: PASS"}),

    # 23. Tamano distinto: TS 300x250, Innovid 300x600.
    dict(id="s23_dims_mismatch",
         placements=[plc("9230001", "P4WW001", fill="green", group="HOL NEW")],
         rotations=[rot("HOL NEW", "N_300x250_1", "8230001", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW)],
         innovid=[inv("9230001", "P4WW001", [cr("8230001", "N_300x250_1", NEW)], dims="300x600")],
         expect={"9230001": "dims mismatch flagged"}),
]

SCENARIOS2.append(
    # 24. La URL nueva (verde) va ARRIBA de la vieja (roja) bajo el mismo nombre.
    dict(id="s24_green_above_red",
         placements=[plc("9240001", "P4XX001", fill="green", group="HOL NEW")],
         rotations=[rot("HOL NEW", "N_300x250_1", "8240001", "Holiday Display GM", fill="green")],
         lps=[dict(name="Holiday Display GM", url=NEW, fill={"url": "green"}), dict(name=None, url=OLD, fill={"url": "red"})],
         innovid=[inv("9240001", "P4XX001", [cr("8240001", "N_300x250_1", NEW)])],
         expect={"9240001": "URL-001 PASS (green wins)"}))
ALL = SCENARIOS + SCENARIOS2

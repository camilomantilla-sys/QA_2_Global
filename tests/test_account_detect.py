"""
La cuenta deducida de la TS (18-nov): los bundles de BlackRock y
Wendy's se guardaron sin cuenta, y la cuenta decide el pixel oficial,
Remove VPAID y el CGEN.

Run with pytest, or directly:
    python tests/test_account_detect.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook  # noqa: E402

from core.account_detect import detect_account, detect_from_files  # noqa: E402


def test_the_advertiser_names_the_account():
    assert detect_account("WENDY'S INTERNTL PBU")[0] == "Wendy's"
    assert detect_account("BlackRock US")[0] == "BlackRock"
    assert detect_account("Adobe Wavemaker WW")[0] == "Adobe"
    assert detect_account("Unilever_US")[0] == "Unilever"


def test_a_brand_advertiser_falls_back_to_the_id_or_the_initials():
    assert detect_account("Dove Holiday", "29418")[0] == "Unilever"
    assert detect_account("Dove Holiday", "", "UNE_DHO_002_DOVE")[0] == "Unilever"
    assert detect_account("", "", "", ["TS_3818_UNI-C_US_MDS.xlsx"])[0] == "Unilever"
    assert detect_account("", "", "", ["TS_US_BLK_USWA_075.xlsx"])[0] == "BlackRock"


def test_no_guess_when_the_initials_disagree_or_are_missing():
    assert detect_account("", "", "", ["WEN_vs_BLK.xlsx"]) == ("", "")
    assert detect_account("", "", "Q4 Core Hamburger") == ("", "")


def test_it_reads_campaign_information():
    wb = Workbook()
    ws = wb.active
    ws.title = "Campaign Information"
    ws.append(["Advertiser:", "WENDY'S INTERNTL PBU"])
    ws.append(["Advertiser ID:", "38314"])
    ws.append(["Campaign Name:", "W3Z_HAM_006_Q4 Core Hamburger_PBU_FY26"])
    buf = io.BytesIO()
    wb.save(buf)
    account, why = detect_from_files("TS.xlsx", buf.getvalue())
    assert account == "Wendy's" and "Advertiser" in why


def test_a_broken_file_never_blocks():
    assert detect_from_files("x.xlsx", b"not an excel") == ("", "")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")

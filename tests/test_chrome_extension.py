"""
The Chrome extension prototype (innovid_extractor/chrome_extension).

Checked without a browser: the manifest asks for nothing beyond Innovid,
and walk.js -- the JavaScript port of the walk-through -- reads the same
real-campaign shapes the Python extractor does. Those run under Node
when it is installed, and are skipped otherwise.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

EXT = Path(__file__).resolve().parents[1] / "innovid_extractor" / "chrome_extension"


def test_the_manifest_asks_for_no_site_at_install():
    """
    Chrome words every site permission as "read and change your data".
    So none is asked at install: activeTab lets the extension into the
    Innovid tab only when the icon is clicked there, and Innovid's own
    site is asked for only to move through several campaigns.
    """
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert "host_permissions" not in manifest
    assert manifest["optional_host_permissions"] == ["https://campaign-manager.flashtalking.net/*"]
    assert "content_scripts" not in manifest
    # No "tabs" either: that one reads as "read your browsing history".
    assert set(manifest["permissions"]) == {"activeTab", "scripting", "downloads", "storage"}


def test_everything_the_extension_loads_is_inside_it():
    for page in ("popup.html",):
        html = (EXT / page).read_text(encoding="utf-8")
        assert "http://" not in html and "https://" not in html
    for ref in ("lib/xlsx.mini.min.js", "walk.js", "popup.js", "popup.css", "background.js",
                "icons/wpp-media-logo.png", "fonts/WPP-Regular.woff2"):
        assert (EXT / ref).exists(), ref


NODE_CHECK = r"""
const Walk = require(process.argv[1]);
const out = {};
(async () => {
  // A real campaign's shape: the decision set as a line under the
  // placement, and the default creative also rotating.
  const summary = {totalPages: 1, items: [
    {level: "PLACEMENT", placementId: "9001", placementName: "P1", status: "Live", siteId: 77,
     siteName: "Site A", isHidden: false, clickTag1: "https://lp.example/a", packageName: null,
     verificationPartner: "DV"},
    {level: "PLACEMENT-CREATIVE", placementId: "9001", fileName: "Display 160x600",
     placementModernDtreeId: "43580", modernDtreeName: "Display 160x600"},
    {level: "PLACEMENT-CREATIVE", placementId: "9001", creativeId: "1", fileName: "v1.jpg",
     clickTag1: "https://lp.example/v1", thirdPartyImpression2: "https://px.example/2"}]};
  const dset = {id: "43580", name: "Display 160x600", servingMethod: "Rotation",
    defaultServing: {id: "1", name: "v1.jpg"}, nodes: [
      {serving: {id: "1", name: "v1.jpg"}, startTimestamp: "2026-11-16 00:00:00",
       endTimestamp: "2026-12-05 23:59:00", weight: 1},
      {isDefault: true, startTimestamp: "2026-11-05 10:01:53", endTimestamp: null}]};
  const call = async (url) => url.includes("/summary") ? summary
    : url.includes("/dset/") ? dset : {items: []};
  const ex = await Walk.extract("337000", call, () => {});
  const sheets = Object.fromEntries(Walk.sheets(ex, []));
  out.placements = sheets.Placement;
  out.creatives = sheets["Placement-Creative"];
  out.fields = sheets["Innovid fields"];
  out.summary = sheets.Summary;
  out.plColumns = Walk.PL_COLUMNS;
  out.pcColumns = Walk.PC_COLUMNS;

  // Shaped like campaign 330328's real fields, against what its real
  // exports wrote for the same rows.
  const real = {totalPages: 1, items: [
    {level: "PLACEMENT", placementId: 11152306, placementName: "P3KK98M|X", siteName: "DV360", siteId: 18330,
     status: "Stopped", bookedCost: 0, costTypeMedia: "CPM", costRateMedia: 0, costTypeFt: "CPM", costRateFt: 0,
     impressionsDelivered: 5, percentDelivered: 0, isHidden: false},
    {level: "PLACEMENT-CREATIVE", placementId: 11152306, placementName: "P3KK98M|X", siteName: "DV360",
     creativeId: 6439175, fileName: "Tracking_Creative_Instream_15.png", numClickTags: 1, baseFileSize: 68,
     rotationWeight: "1.00", status: "Active"},
    {level: "PLACEMENT", placementId: 11320679, placementName: "P4|Y", siteName: "DV360", siteId: 18330,
     status: "Live", decisionSetId: 42422, decisionSetName: "Google SSP 6s", placementDecisionSetId: 80953},
    {level: "PLACEMENT-CREATIVE", placementId: 11320679, placementName: "P4|Y", siteName: "DV360",
     fileName: "Google SSP 6s", decisionSetId: 42422, decisionSetName: "Google SSP 6s", rotationWeight: "1.00"},
    {level: "PLACEMENT-CREATIVE", placementId: 11320679, placementName: "P4|Y", siteName: "DV360",
     creativeId: 6553310, fileName: "v.png", rotationWeight: "1.00", baseFileSize: 2043178}]};
  const exReal = await Walk.extract("330328", async (url) => url.includes("/summary") ? real
    : url.includes("/dset/") ? {id: "42422", name: "Google SSP 6s", nodes: []} : {items: []}, () => {});
  const sReal = Object.fromEntries(Walk.sheets(exReal, []));
  out.realPl = sReal.Placement;
  out.realPc = sReal["Placement-Creative"];
  out.realFields = sReal["Innovid fields"];
  out.realSummary = sReal.Summary;

  // Three identical failures and it stops asking.
  let asked = 0;
  const many = {totalPages: 1, items: [0, 1, 2, 3, 4, 5].map((i) => (
    {level: "PLACEMENT", placementId: String(9000 + i), placementModernDtreeId: String(500 + i)}))};
  const failing = async (url) => {
    if (url.includes("/summary")) return many;
    if (url.includes("/dset/")) { asked += 1; throw new Error("HTTP 400"); }
    return {items: []};
  };
  const ex2 = await Walk.extract("337001", failing, () => {});
  out.asked = asked;
  out.errors = ex2.errors;
  out.fromUrl = [Walk.campaignFromUrl("https://campaign-manager.flashtalking.net/337552/summary/"),
                 Walk.campaignFromUrl("https://example.org/337552/")];
  out.ids = Walk.campaignIds("337552, 330328 337552");

  // Filters, and never more than 4 decision sets in flight.
  const big = {totalPages: 1, items: []};
  for (let i = 0; i < 12; i++) {
    big.items.push({level: "PLACEMENT", placementId: String(8000 + i),
      placementName: `P3AB${String(i).padStart(3, "0")}_ULV_X`, placementModernDtreeId: String(700 + i),
      modernDtreeName: `DS ${i}`});
  }
  let inFlight = 0, maxInFlight = 0;
  const asked3 = [];
  const bigCall = async (url) => {
    if (url.includes("/summary")) return big;
    if (url.includes("/dset/")) {
      const id = url.split("/").pop();
      asked3.push(id);
      inFlight += 1; maxInFlight = Math.max(maxInFlight, inFlight);
      await new Promise((r) => setTimeout(r, 5));
      inFlight -= 1;
      return {id, name: `DS ${Number(id) - 700}`, nodes: []};
    }
    return {items: []};
  };
  await Walk.extract("1", bigCall, () => {});
  out.maxInFlight = maxInFlight;
  out.allAsked = asked3.length;

  asked3.length = 0;
  const f1 = await Walk.extract("1", bigCall, () => {}, {placements: "8001\nP3AB005\nNOPE"});
  out.byPlacement = asked3.slice().sort();
  out.byPlacementScope = f1.scope.sort();
  out.unmatched = f1.filters.unmatched;
  out.byPlacementSheet = Object.fromEntries(Walk.sheets(f1, [])).Placement.length - 1;

  asked3.length = 0;
  await Walk.extract("1", bigCall, () => {}, {dsets: "ds 7, 711"});
  out.byDset = asked3.slice().sort();

  // Who and when: the name typed in the popup, and the person's local time with its zone.
  const exBy = await Walk.extract("337000", call, () => {}, {by: "  Ana Ruiz "});
  out.byName = Object.fromEntries(Walk.sheets(exBy, []).find((s) => s[0] === "Summary")[1]);
  out.stamp = Walk.localStamp(new Date(2026, 10, 20, 10, 30));
  const api = "https://api.flashtalking.net";
  out.allowed = [
    Walk.isAllowedCall("POST", api + "/cm/v1/ui/campaigns/337552/summary?fields=status,placementId"),
    Walk.isAllowedCall("GET", api + "/dt/v1/ui/dset/43580"),
    Walk.isAllowedCall("GET", api + "/cm/v1/campaigns/337552/campaign-sites?rpp=543"),
    Walk.isAllowedCall("GET", api + "/tag/v1/ui/campaign-sites/1"),
  ];
  out.refused = [
    Walk.isAllowedCall("PUT", api + "/dt/v1/ui/dset/43580"),
    Walk.isAllowedCall("POST", api + "/dt/v1/ui/dset/43580"),
    Walk.isAllowedCall("DELETE", api + "/tag/v1/ui/campaign-sites/1"),
    Walk.isAllowedCall("POST", api + "/cm/v1/ui/campaigns/337552/placements"),
    Walk.isAllowedCall("GET", "https://example.org/dt/v1/ui/dset/1"),
  ];
  console.log(JSON.stringify(out));
})();
"""


@pytest.fixture(scope="module")
def walk():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node isn't installed here")
    done = subprocess.run([node, "-e", NODE_CHECK, str(EXT / "walk.js")],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_decision_set_line_fills_its_placement(walk):
    head, row = walk["placements"][0], walk["placements"][1]
    p = dict(zip(head, row))
    assert (p["Decision_Set_Name"], p["Decision_Set_ID"]) == ("Display 160x600", "43580")
    assert p["Verification_Partner"] == "DV"


def test_the_default_timestamp_is_not_a_flight(walk):
    # The decision set's own line, then the creative, as in the export.
    assert len(walk["creatives"]) == 3
    c = dict(zip(walk["creatives"][0], walk["creatives"][2]))
    assert (c["DS_Start_Date"], c["DS_End_Date"], c["DS_Weight"], c["DS_Default"]) == (
        "2026-11-16 00:00:00", "2026-12-05 23:59:00", "1", "Yes")


# Innovid's own export headers, in order (placement_v2 and
# placement-creative_v2): the extension's sheets start with exactly these.
EXPORT_PL_START = ["Site_ID", "Placement_ID", "Site", "Placement", "Dimensions", "Start_Date",
                   "End_Date", "Placement_Type", "Status", "Hidden", "Stopped", "Booked_Units"]
EXPORT_PC_START = ["Enabled", "Site_ID", "Placement_ID", "Creative_ID", "Site", "Placement",
                   "Dimensions", "Legacy_Decision_Tree", "Decision_Tree_Name", "Decision_Tree_ID",
                   "Filename", "Placement_Type", "Placement_Creative_ID", "Start_Date", "End_Date"]


def test_sheets_keep_the_export_column_names(walk):
    assert len(walk["plColumns"]) == 64 and len(walk["pcColumns"]) == 71
    assert walk["plColumns"][:12] == EXPORT_PL_START
    assert walk["pcColumns"][:15] == EXPORT_PC_START
    assert walk["placements"][0][:64] == walk["plColumns"]
    assert walk["creatives"][0][:71] == walk["pcColumns"]


def test_export_columns_come_from_innovid_fields(walk):
    p = dict(zip(walk["placements"][0], walk["placements"][1]))
    assert (p["Site_ID"], p["Site"], p["Hidden"], p["Clicktag_1"]) == (
        "77", "Site A (77)", "No", "https://lp.example/a")
    c = dict(zip(walk["creatives"][0], walk["creatives"][2]))
    assert (c["Creative_ID"], c["Filename"], c["Clicktag_1"], c["Third_Party_Impression_2"]) == (
        "1", "v1.jpg (1)", "https://lp.example/v1", "https://px.example/2")
    # The creative row doesn't repeat its placement's name: taken from it.
    assert (c["Placement"], c["Site"]) == ("P1 (9001)", "Site A")


def test_summary_says_which_export_columns_innovid_did_not_send(walk):
    s = dict((r[0], r[1]) for r in walk["summary"])
    assert s["Export columns · Placement"].endswith("of 64 found in Innovid's data")
    assert "Booked_Cost" in s["Not in Innovid's data · Placement"]
    assert "Site_ID" not in s["Not in Innovid's data · Placement"]
    # Sent but empty still counts as found: the export would be empty too.
    assert "Package_Name" not in s["Not in Innovid's data · Placement"]


def test_every_innovid_field_is_listed(walk):
    f = {r[0]: r for r in walk["fields"][1:]}
    assert f["siteId"][4] == "Placement · Site_ID"
    assert f["verificationPartner"][2] == 1
    assert f["packageName"][2] == 0


def test_stops_once_a_batch_fails_identically(walk):
    # Asked four at a time: the first batch fails the same way, the
    # remaining two are never asked.
    assert walk["asked"] == 4
    assert any("Stopped asking for 2 more" in e for e in walk["errors"])


def test_reads_the_campaign_from_the_innovid_tab_only(walk):
    assert walk["fromUrl"] == ["337552", ""]
    assert walk["ids"] == ["337552", "330328"]


def test_only_reads_leave_the_browser(walk):
    assert walk["allowed"] == [True, True, True, True]
    assert walk["refused"] == [False, False, False, False, False]


def test_decision_sets_go_four_at_a_time(walk):
    assert walk["allAsked"] == 12
    assert walk["maxInFlight"] == 4


def test_only_these_placements_by_id_or_p_code(walk):
    assert walk["byPlacement"] == ["701", "705"]
    assert walk["byPlacementScope"] == ["8001", "8005"]
    assert walk["unmatched"] == ["NOPE"]
    assert walk["byPlacementSheet"] == 2


def test_only_these_decision_sets_by_name_or_id(walk):
    assert walk["byDset"] == ["707", "711"]


def _rows(sheet):
    return [dict(zip(sheet[0], r)) for r in sheet[1:]]


def test_placement_values_are_written_as_the_export_writes_them(walk):
    # Expected values copied from the real 330328 placement export.
    p = _rows(walk["realPl"])[0]
    assert (p["Site"], p["Stopped"], p["Hidden"]) == ("DV360 (18330)", "Yes", "No")
    # Costs and rates keep their columns but are never written.
    assert (p["Booked_Cost"], p["Media_Cost_Type"], p["Media_Cost_Rate"]) == ("", "", "")
    assert (p["Flashtalking_Cost_Type"], p["Flashtalking_Cost"]) == ("", "")
    assert (p["Delivered_Impressions"], p["Percent_Delivered"]) == ("5", "0.00")
    assert _rows(walk["realPl"])[1]["Stopped"] == "No"


def test_creative_values_are_written_as_the_export_writes_them(walk):
    # Expected values copied from the real 330328 placement-creative export.
    direct, ds_line, in_ds = _rows(walk["realPc"])
    assert direct["Placement"] == "P3KK98M|X (11152306)"
    assert direct["Filename"] == "Tracking_Creative_Instream_15.png (6439175)"
    assert (direct["ClickTags"], direct["Base_File_Size (KB)"]) == ("1", "0.07")
    assert (direct["Rotation"], direct["Stopped"], direct["Site"]) == ("1.00", "Yes", "DV360")
    assert ds_line["Filename"] == "Google SSP 6s (42422)"
    assert (ds_line["Rotation"], in_ds["Rotation"], in_ds["Stopped"]) == (
        "Decision Tree", "Decision Tree", "No")
    # 1995.291 KB: the export rounds up.
    assert in_ds["Base_File_Size (KB)"] == "1995.30"


def test_costs_never_leave_innovid(walk):
    fields = {r[0]: r for r in walk["realFields"][1:]}
    for k in ("bookedCost", "costTypeMedia", "costRateMedia", "costTypeFt", "costRateFt"):
        assert fields[k][3] in ("", "(not extracted)"), k
    s = dict((r[0], r[1]) for r in walk["realSummary"])
    assert s["Left empty on purpose"].startswith("Booked_Cost, Media_Cost_Type")
    # Withheld, not missing: they still count as columns Innovid sends.
    assert "Booked_Cost" not in s.get("Not in Innovid's data · Placement", "")


def test_the_file_says_it_is_confidential(walk):
    assert walk["realSummary"][1][0] == "Classification"
    assert "Confidential" in walk["realSummary"][1][1]


def test_the_file_says_who_extracted_it_and_when(walk):
    assert walk["byName"]["Extracted by"] == "Ana Ruiz"
    assert dict((r[0], r[1]) for r in walk["summary"])["Extracted by"] == "(not given)"
    # Local time of whoever runs it, with the offset (and zone name when known).
    assert re.match(r"^2026-11-20 10:30 \(UTC[+-]\d{2}:\d{2}", walk["stamp"])
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} \(UTC", walk["byName"]["Extracted"])

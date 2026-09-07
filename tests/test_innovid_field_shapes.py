"""
Covers what campaign 323492 showed: Innovid sends ~130 fields, most of
them null, and carries two generations of decision set plus rows at
more than one level.
"""
import sys
sys.path.insert(0, "/home/user/QA_2_Global")
from core.innovid_api import (  # noqa: E402
    count_filled_fields, parse_summary_response, summary_field_names,
)

fails = []
def check(label, got, want):
    if got != want: fails.append(label); print(f"  FAIL {label}: {got!r} != {want!r}")
    else: print(f"  ok   {label} = {got!r}")

# Shaped like the real response: modern dtree null, legacy populated,
# rows at two levels.
PAYLOAD = {"items": [
    {"placementId": 10964183, "level": 1, "startDate": "2026-07-20",
     "endDate": "2026-08-23", "placementModernDtreeId": None,
     "modernDtreeId": None, "placementDecisionSetId": 44120,
     "decisionSetName": "Frosty GM 320x50", "verificationPartner": None,
     "rotationWeight": None},
    {"placementId": 10964183, "level": 2, "startDate": "2026-07-20",
     "endDate": "2026-08-23", "placementModernDtreeId": None,
     "decisionSetId": 44120, "rotationWeight": 50,
     "verificationPartner": None},
]}

print("the legacy decision set is read when the modern one is null")
rows = parse_summary_response(PAYLOAD)
check("both rows parsed", len(rows), 2)
check("modern stays empty", rows[0].dtree_id, "")
check("legacy is picked up", rows[0].legacy_dset_id, "44120")
check("legacy name too", rows[0].legacy_dset_name, "Frosty GM 320x50")
check("the other row's legacy field also works", rows[1].legacy_dset_id, "44120")

print("\nthe two are never conflated")
check("modern is not filled from legacy", rows[1].dtree_id, "")

print("\nrow level is kept so levels can be told apart")
check("placement row", rows[0].level, "1")
check("creative row", rows[1].level, "2")

print("\ncoverage counts rows with a value, not rows present")
cov = count_filled_fields(PAYLOAD, {})
check("null on every row counts zero", cov["placementModernDtreeId"], 0)
check("verificationPartner genuinely empty", cov["verificationPartner"], 0)
check("rotationWeight on one row only", cov["rotationWeight"], 1)
check("placementId on both", cov["placementId"], 2)
check("a field absent from one row still counted", cov["decisionSetId"], 1)

print("\nzero-valued numbers are data, not emptiness")
cov2 = count_filled_fields({"items": [{"rotationWeight": 0, "isHidden": False}]}, {})
check("weight 0 counts as present", cov2["rotationWeight"], 1)
check("false counts as present", cov2["isHidden"], 1)

print("\nfield names are the union across rows")
check("includes both dset spellings",
      {"placementDecisionSetId", "decisionSetId"} <= set(summary_field_names(PAYLOAD)),
      True)

print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("Field-shape handling verified.")

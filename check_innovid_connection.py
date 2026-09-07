"""
Checks that QA2 can talk to Innovid, before wiring any of it into the
app. Run it once after filling in config/innovid_credentials.env:

    python check_innovid_connection.py 323492

(that number is the Campaign ID -- the one next to the campaign name
in Innovid, e.g. "WEN_FRO_003_FROSTY_DIGTAL_FY26 (323492)")

Add --show to watch the browser do it instead of running invisibly,
which is the fastest way to see where a login is getting stuck.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.innovid_api import (  # noqa: E402
    CREDENTIALS_PATH,
    fetch_campaign,
    load_credentials,
)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_browser = "--show" in sys.argv

    if not args:
        print("Usage: python check_innovid_connection.py <CAMPAIGN_ID> [--show]")
        print("Example: python check_innovid_connection.py 323492")
        return 2

    campaign_id = args[0]

    credentials = load_credentials()
    if credentials is None:
        print("No credentials found.\n")
        print(f"Expected file: {CREDENTIALS_PATH}")
        print(
            "Copy config/innovid_credentials.env.example to "
            "config/innovid_credentials.env and fill in your Innovid "
            "username and password. That file is gitignored -- it "
            "never leaves your machine."
        )
        return 1

    print(f"Signing in as {credentials.username}")
    print(f"Campaign {campaign_id}")
    print(f"Browser: {'visible' if show_browser else 'hidden'}\n")

    result = fetch_campaign(
        campaign_id=campaign_id,
        credentials=credentials,
        headless=not show_browser,
    )

    if result.errors:
        print("Problems:")
        for error in result.errors:
            print(f"  - {error}")
        # Anything below would be guesswork: the run already knows why
        # it stopped, and adding "maybe the campaign ID is wrong" here
        # only sends people looking in the wrong place.
        return 1

    if not result.placements:
        print("No placements came back, and nothing went wrong.")
        print(
            "The login worked, so the campaign ID is the thing to "
            "check -- it's the number next to the campaign name in "
            "Innovid. Run again with --show to watch it happen."
        )
        return 1

    placement_ids = {r.placement_id for r in result.placements}
    print(f"{len(result.placements)} row(s), "
          f"{len(placement_ids)} distinct placement(s)")
    print(f"{len(result.creative_nodes)} creative node(s)\n")

    # Coverage across every row, not a sample. A field that is filled
    # in on the first five rows and empty on the other 404 is exactly
    # the kind of thing a sample hides.
    critical = {
        "Verification Partner": lambda r: r.verification_partner,
        "Decision set id": lambda r: r.dtree_id,
        "Start date": lambda r: r.start_date,
        "End date": lambda r: r.end_date,
        "Rotation weight": lambda r: r.rotation_weight,
    }
    total = len(result.placements)
    print("How much of each field actually came back:")
    missing_entirely = []
    for label, getter in critical.items():
        filled = sum(1 for r in result.placements if getter(r))
        flag = "" if filled else "   <-- nothing at all"
        print(f"  {label:22} {filled:>4} / {total}{flag}")
        if not filled:
            missing_entirely.append(label)

    if missing_entirely and result.returned_fields:
        print(
            "\nInnovid returned these field names (names only, no "
            "values):"
        )
        for name in result.returned_fields:
            print(f"  - {name}")
        print(
            "\nIf the fields above are missing from that list, "
            "Innovid didn't send them -- which usually means the "
            "saved column view is filtering them out, not that they "
            "are empty in the campaign. Send this list over."
        )

    print("\nFirst few placements:")
    for row in result.placements[:5]:
        print(
            f"  {row.placement_id}  {row.start_date} -> {row.end_date or '(ongoing)'}"
            f"  | {row.verification_partner or '-'}"
            f" {row.verification_status or ''}"
            f"  | dset {row.dtree_id or '-'}"
        )

    if result.creative_nodes:
        print("\nFirst few creatives (the part no export gives us):")
        for node in result.creative_nodes[:5]:
            print(
                f"  creative {node.creative_id}"
                f"  {node.start_timestamp or '-'} -> "
                f"{node.end_timestamp or '(ongoing)'}"
                f"  | weight {node.weight or '-'}"
                f"{'  | DEFAULT' if node.is_default else ''}"
            )

    # The whole point: catching a creative that starts after its
    # placement does. Checked across every row.
    mismatches = []
    for row in result.placements:
        for node in result.nodes_for_placement(row.placement_id):
            if node.is_default or not node.start_timestamp or not row.start_date:
                continue
            if node.start_timestamp[:10] != row.start_date[:10]:
                mismatches.append((row, node))

    print()
    if not result.creative_nodes:
        print(
            "No creative dates were checked: without a decision set "
            "id there is nothing to look them up with. That is the "
            "thing to fix before this is useful."
        )
    elif mismatches:
        print(f"{len(mismatches)} creative(s) starting on a different day "
              "than their placement:")
        for row, node in mismatches[:10]:
            print(
                f"  placement {row.placement_id} starts {row.start_date}"
                f"  ->  creative {node.creative_id} starts "
                f"{node.start_timestamp[:10]}"
            )
    else:
        print("Every creative starts the same day as its placement "
              "in this campaign.")

    print("\nConnection works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

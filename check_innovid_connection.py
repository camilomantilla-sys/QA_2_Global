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
    SESSION_PATH,
    InnovidAuthError,
    establish_session,
    fetch_campaign,
    load_credentials,
    session_is_saved,
)


def _sign_in_by_hand() -> int:
    """
    Opens a normal browser window so the sign-in happens the usual
    way -- SSO, verification code and all -- and keeps the session.
    """
    print("Opening a browser window.\n")
    print("Sign in to Innovid the way you normally would. Once the")
    print("campaign manager has loaded, this will save the session")
    print("and close the window by itself. Nothing is typed for you,")
    print("and your password is never read.\n")

    try:
        saved_to = establish_session()
    except InnovidAuthError as exc:
        print(f"Didn't work out:\n  {exc}")
        return 1

    print(f"Signed in. Session saved to {saved_to}")
    print(
        "\nThat file holds session cookies, which work like your "
        "password until they expire, so it stays on this machine -- "
        "it's gitignored and must not be shared or committed. When "
        "it expires, run --login again."
    )
    print("\nNow run the check without --login:")
    print(f"    {sys.executable} check_innovid_connection.py <CAMPAIGN_ID>")
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_browser = "--show" in sys.argv

    if not args:
        print("Usage: python check_innovid_connection.py "
              "<CAMPAIGN_ID> [--show] [--login]")
        print("Example: python check_innovid_connection.py 323492")
        return 2

    campaign_id = args[0]

    if "--login" in sys.argv:
        return _sign_in_by_hand()

    credentials = load_credentials()

    if not session_is_saved() and credentials is None:
        print("Nothing to sign in with.\n")
        print(
            "Either sign in by hand once (recommended -- it also "
            "handles verification codes):\n"
            f"    {sys.executable} check_innovid_connection.py "
            f"{campaign_id} --login\n"
        )
        print(
            "or copy config/innovid_credentials.env.example to "
            f"{CREDENTIALS_PATH.name} in the same folder and fill it "
            "in. Both files are gitignored -- they never leave your "
            "machine."
        )
        return 1

    if session_is_saved():
        print(f"Using the saved sign-in ({SESSION_PATH.name})")
    else:
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

    placement_level = result.placement_rows()
    creative_level = [r for r in result.placements if r.is_creative_level]
    print(f"{len(placement_level)} placement(s), "
          f"{len(creative_level)} creative row(s)")
    if result.creative_nodes:
        print(f"{len(result.creative_nodes)} decision-set node(s)")
    print()

    # Coverage across every row, not a sample. A field that is filled
    # in on the first five rows and empty on the other 404 is exactly
    # the kind of thing a sample hides.
    critical = {
        "Verification Partner": lambda r: r.verification_partner,
        "Decision set id (modern)": lambda r: r.dtree_id,
        "Decision set id (legacy)": lambda r: r.legacy_dset_id,
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

    # Rows arrive at more than one level, and a field that only
    # exists on one of them looks "half empty" until they're split.
    levels: dict[str, int] = {}
    for row in result.placements:
        levels[row.level or "(none)"] = levels.get(row.level or "(none)", 0) + 1
    if len(levels) > 1 or "(none)" not in levels:
        print("\nRow levels:")
        for level, count in sorted(levels.items()):
            print(f"  level {level:10} {count:>4} row(s)")

    if missing_entirely and result.field_coverage:
        filled = {k: v for k, v in result.field_coverage.items() if v}
        empty = sorted(k for k, v in result.field_coverage.items() if not v)

        seen = result.rows_seen or total
        print(
            f"\nOf the {len(result.field_coverage)} fields Innovid "
            f"sent, {len(filled)} carry data, counted over all {seen} "
            "rows it returned. Counts only, no values:"
        )
        for name, count in sorted(filled.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:>4} / {seen}  {name}")

        print(f"\nThe other {len(empty)} came back empty on every row:")
        print("  " + ", ".join(empty))
        print(
            "\nSend both lists over. A field that is empty on every "
            "single row is Innovid not filling it in for this "
            "campaign, which is a different problem from QA2 reading "
            "the wrong field name -- and they need opposite fixes."
        )

    print("\nFirst few placements:")
    for row in result.placements[:5]:
        print(
            f"  {row.placement_id}  {row.start_date} -> {row.end_date or '(ongoing)'}"
            f"  | {row.verification_partner or '-'}"
            f" {row.verification_status or ''}"
            f"  | dset {row.dtree_id or row.legacy_dset_id or '-'}"
            f"{' (legacy)' if not row.dtree_id and row.legacy_dset_id else ''}"
        )

    if creative_level:
        print("\nFirst few creative rows (the part no export gives us):")
        for row in creative_level[:5]:
            print(
                f"  under placement {row.placement_id}"
                f"  {row.start_date} -> {row.end_date or '(ongoing)'}"
                f"  | weight {row.rotation_weight or '-'}"
                f"  | {row.file_name or row.creative_description or ''}"
            )

    if result.creative_nodes:
        print("\nFirst few decision-set nodes:")
        for node in result.creative_nodes[:5]:
            print(
                f"  creative {node.creative_id}"
                f"  {node.start_timestamp or '-'} -> "
                f"{node.end_timestamp or '(ongoing)'}"
                f"  | weight {node.weight or '-'}"
                f"{'  | DEFAULT' if node.is_default else ''}"
            )

    # Creative flight dates are NOT in the summary. The creative rows
    # repeat their placement's dates, so comparing them here would
    # pass every time -- including on the very case this is for.
    print()
    if result.creative_nodes:
        mismatches = []
        for row in placement_level:
            for node in result.nodes_for_placement(row.placement_id):
                if node.is_default or not node.start_timestamp or not row.start_date:
                    continue
                if node.start_timestamp[:10] != row.start_date[:10]:
                    mismatches.append((row, node))
        if mismatches:
            print(f"{len(mismatches)} creative(s) starting on a different "
                  "day than their placement:")
            for row, node in mismatches[:15]:
                print(
                    f"  placement {row.placement_id} starts {row.start_date}"
                    f"  ->  creative {node.creative_id} starts "
                    f"{node.start_timestamp[:10]}"
                )
        else:
            print("Every creative in the decision sets read starts the "
                  "same day as its placement.")
    else:
        modern = sum(1 for r in result.placements if r.dtree_id)
        legacy = sum(1 for r in result.placements if r.legacy_dset_id)
        print("Creative flight dates were NOT checked.")
        print(
            "  They live inside the decision set, not in the summary "
            "-- the dates on the creative rows above are the "
            "placement's, repeated."
        )
        print(f"  Modern decision sets in this campaign: {modern} row(s)")
        print(f"  Legacy decision sets in this campaign: {legacy} row(s)")
        if legacy and not modern:
            print(
                "  Only legacy decision sets here, and QA2 does not "
                "know that endpoint yet, so nothing could be opened."
            )

    print("\nConnection works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

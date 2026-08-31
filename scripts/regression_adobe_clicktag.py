from __future__ import annotations

import subprocess
import sys


MODULE = "scripts.test_adobe_clicktag_requirements"

EXPECTED_TEXT = [
    "Click tag only placements : 2",
    "PASS                : 2",
    "FAIL                : 0",
    "REVIEW              : 0",
    "NOT_VERIFIED        : 0",
    "Placement ID        : 11038685",
    "Placement ID        : 11038689",
    "Columns found       : ['Update_Clicktag1']",
    "Update_Clicktag is present and Static_Clicktag is absent.",
    "ATTENTION REQUIRED",
    "None",
]


def main() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            MODULE,
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    output = (
        completed.stdout
        + completed.stderr
    )

    print(output)

    if completed.returncode != 0:
        raise SystemExit(
            f"FAIL: {MODULE} returned "
            f"exit code {completed.returncode}."
        )

    missing = [
        expected
        for expected in EXPECTED_TEXT
        if expected not in output
    ]

    if missing:
        print()
        print("=" * 100)
        print("REGRESSION FAILURE")
        print("=" * 100)

        for value in missing:
            print(f"MISSING: {value}")

        raise SystemExit(1)

    print()
    print("=" * 100)
    print("REGRESSION PASSED")
    print("=" * 100)
    print("Adobe Click tag only placements: 2/2 PASS")
    print("Static_Clicktag absent: validated")
    print("Update_Clicktag populated: validated")


if __name__ == "__main__":
    main()

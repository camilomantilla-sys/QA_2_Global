"""
El texto de ayuda dentro de la app (FB-05) y para que sirve cada archivo
que se descarga (FB-19).

Vive aparte de la interfaz, sin Streamlit, para que la interfaz nueva
(ui/web) muestre exactamente lo mismo. Las etiquetas de veredicto y de
estado salen de las mismas tablas que usan la pantalla y los reportes,
asi que si una cambia, la ayuda cambia con ella; una prueba lo vigila.
"""
from __future__ import annotations

from core.verdict import VERDICT_LABELS

#: Para que sirve cada cosa que se descarga. Una linea, en la app.
DOWNLOAD_PURPOSE = {
    "pdf": (
        "The record of this QA2: verdict, sign-off, who did what and "
        "the findings. Made to share, print and sign."
    ),
    "excel": (
        "The detailed working file: one tab per area (QA, Tags, "
        "Findings, Worked Placements, Rules Executed...). Made to "
        "filter and dig into a finding. With Innovid connected it also "
        "carries everything read from the decision sets."
    ),
    "bundle": (
        "The exact files of this request in one .zip, so the next "
        "person can reload them with \"Load a saved session\" instead "
        "of uploading each one again."
    ),
    "csv": "The findings as a plain table, for anyone who wants the raw list.",
}

#: Que significa cada estado de un hallazgo.
STATUS_HELP = {
    "Passed": "Checked and matches the Traffic Sheet.",
    "Failed": "Checked and does not match. Fix it in Innovid or with the requester.",
    "Review": "QA2 found something a person has to judge. Look at it and sign it off.",
    "Not Verified": (
        "QA2 could not check it: a file was missing, Innovid was not "
        "connected, or the data was not there. Check it by hand."
    ),
    "Info": "Context only. Nothing to do.",
}

#: Que significa cada veredicto.
VERDICT_HELP = {
    "PASSED": "Everything checked matches.",
    "FAILED": "At least one finding failed. Something has to be fixed.",
    "NEEDS_REVIEW": "Nothing failed, but some findings need a person to look at them or could not be checked.",
    "BLOCKED": "QA2 could not read a file well enough to run. The message says which and why.",
    "NO_CHECKS": "There was nothing to check in this area for this request.",
}


def help_markdown() -> str:
    """La ayuda completa, en Markdown, tal como se muestra en la app."""
    verdicts = "\n".join(
        f"- **{VERDICT_LABELS[key]}**: {text}" for key, text in VERDICT_HELP.items()
    )
    statuses = "\n".join(f"- **{label}**: {text}" for label, text in STATUS_HELP.items())
    downloads = "\n".join(
        f"- **{name}**: {DOWNLOAD_PURPOSE[key]}"
        for name, key in (
            ("PDF Report", "pdf"),
            ("Excel Report", "excel"),
            ("Session bundle (.zip)", "bundle"),
            ("Findings CSV", "csv"),
        )
    )
    return f"""
**1. Load the files (left panel)**

- **Traffic Sheet** and **Placement-Creative View** are required. With only these two, QA2 already runs.
- **Placement View** adds 1x1s, pixels and placement URLs. **Tag files** add IDs, dimensions, Campaign ID and delivered content. **DV Pinnacle tags** add DoubleVerify delivery. **Evidence screenshots** go into the reports.
- Anything optional you leave out shows up as **Not Verified**, never as a failure.
- If someone already ran QA on this request and saved a **session bundle**, load it under "Load a saved session" and skip the uploads.

**2. Check against Innovid (optional)**

Three things are in no export: the verification partner, the rotation weights and the creative dates inside each decision set. Sign in to Innovid from the app and QA2 reads them with your own account. It only reads.

**3. Fill in the Implementation Record and run**

Who implemented, who did QA2 and when. It goes into both reports. Then press **Run QA**. **Start over** clears everything for the next request and keeps your account and your name.

**4. Read the result**

There are two verdicts, **Implementation** and **Tags & pixels**, so you know which side to fix. The overall result is the worse of the two.

{verdicts}

Each finding has a status:

{statuses}

The colours of the Traffic Sheet decide what is checked: **green** rows must be in Innovid, **red** rows must be gone, **yellow or grey** rows are out of scope, and **white** rows are context.

**5. Sign off and download**

Findings that need a person are listed in **QA2 Review**. Sign them off there; the reports show who approved them.

{downloads}
""".strip()

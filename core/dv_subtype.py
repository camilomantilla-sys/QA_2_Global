"""
DV (DoubleVerify) sub-type detection, shared by every DV-related check.

WPP accounts don't just say "DV": the Traffic Sheet's "Vendors / Pixels"
names one of three flavors, and each is verified in a different place.

    DV Omni                1x1, Video
        No placement-level pixel. The delivered Innovid tag file must
        carry a column named doubleverify_vast with content.

    DV Monitoring (alone)  1x1, Display
        1x1: a DV Pinnacle wrapped-tag file must be delivered.
        Display: the placement's Third_Party_Survey must carry the
        DoubleVerify pixel. No column is expected in the tag file.

    DV Monitoring / Blocking   Display, (Video: unusual, callout)
        Display: BOTH the tag file needs a doubleverify_html column
        with content AND the placement needs the Third_Party_Survey
        pixel.
        Video: table says this combo "shouldn't normally show up" --
        treated as a callout, validated the same way as Omni Video.

    DV Integration          1x1
        Camilo: "solo hay que descargar tags, no es necesario hacer
        wrapping de DV Pinnacle." No Pinnacle file, no placement
        pixel, no tag-file column -- the only requirement is that the
        regular Innovid tags get delivered, which TAG-013 (tag
        coverage) already checks. DV-001 and DV-003 both skip this
        subtype outright.

Camilo confirmed the table isn't complete yet (still missing one
BlackRock and one Wendy's example), and none of the files reviewed so
far carry an actual doubleverify_vast/doubleverify_html column to
validate against. Any combination not explicitly listed above falls
through as UNDETERMINED so the caller can report NOT_VERIFIED instead
of guessing a PASS/FAIL.
"""
from __future__ import annotations

import re

from core.normalize import norm_compare

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

OMNI = "OMNI"
MONITORING = "MONITORING"
MONITORING_BLOCKING = "MONITORING_BLOCKING"
INTEGRATION = "INTEGRATION"
UNDETERMINED = "UNDETERMINED"


def _normalized(value: object) -> str:
    return _NON_ALNUM.sub(" ", norm_compare(str(value or ""))).strip()


def is_dv(vendor_raw: object) -> bool:
    text = _normalized(vendor_raw)
    return "dv" in text.split() or "doubleverify" in text


def dv_subtype(vendor_raw: object) -> str | None:
    """
    Return OMNI / MONITORING / MONITORING_BLOCKING / INTEGRATION /
    UNDETERMINED, or None if the text doesn't mention DV at all.
    """
    if not is_dv(vendor_raw):
        return None

    text = _normalized(vendor_raw)

    omni = "omni" in text
    monitoring = "monitoring" in text
    blocking = "blocking" in text
    integration = "integration" in text

    if omni:
        return OMNI
    if monitoring and blocking:
        return MONITORING_BLOCKING
    if blocking:
        return MONITORING_BLOCKING
    if monitoring:
        return MONITORING
    if integration:
        return INTEGRATION
    return UNDETERMINED

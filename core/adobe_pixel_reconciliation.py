"""
Adobe pixel reconciliation.

Sources:
    Traffic Sheet Vendors / Pixels
    Innovid Placement View
    Consolidated tag inventory

Business rules:

FTRACK:
    N/A. No finding is generated.

PROTECTED:
    N/A. No finding is generated.

DISQO required:
    Innovid YES + Tags NO  -> PASS
    Innovid NO  + Tags YES -> REVIEW
    Innovid NO  + Tags NO  -> FAIL
    Innovid YES + Tags YES -> REVIEW, unexpected duplicate evidence

DISQO not required:
    -> N/A

Innovid Placement View is the primary evidence for DISQO.
Tag files are secondary evidence.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from enum import Enum
from typing import Iterable

from core.normalize import norm_compare
from core.pixel_reconciliation import pixel_matches_official
from core.tag_inventory import TagInventory, TagSourceRow

# ------------------------------------------------------------------
# Editable config: config/vendor_pixels_adobe.json
#
# Independent from the WPP table in core/pixel_reconciliation.py --
# Adobe's DISQO/iSpot check doesn't gate presence off one host+column
# pair the way WPP's does (it searches broadly across Innovid and the
# tag files instead). This only supplies the official reference URL
# used, once evidence is found, to flag a vendor pixel that drifted.
# ------------------------------------------------------------------

ADOBE_VENDOR_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "vendor_pixels_adobe.json"
)


def _default_adobe_vendor_rows() -> list[dict]:
    return [
        {"name": "DISQO", "official_pixel": "", "note": ""},
        {"name": "iSpot", "official_pixel": "", "note": ""},
    ]


def load_adobe_vendor_rows() -> list[dict]:
    try:
        with open(ADOBE_VENDOR_CONFIG_PATH, encoding="utf-8") as f:
            rows = json.load(f)
        if isinstance(rows, list) and rows:
            return rows
    except (OSError, json.JSONDecodeError):
        pass
    return _default_adobe_vendor_rows()


def save_adobe_vendor_rows(rows: list[dict]) -> None:
    ADOBE_VENDOR_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ADOBE_VENDOR_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _official_pixels() -> dict[str, str]:
    """{vendor name -> official pixel}, skipping blanks."""
    return {
        str(row.get("name") or "").strip(): str(row.get("official_pixel") or "").strip()
        for row in load_adobe_vendor_rows()
        if str(row.get("official_pixel") or "").strip()
    }


def _evidence_value(evidence_line: str) -> str:
    """"row 12 | third_party_impression | <url>" -> "<url>"."""
    parts = str(evidence_line or "").split(" | ")
    return parts[-1].strip() if parts else ""


class PixelResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    NOT_APPLICABLE = "N/A"
    NOT_VERIFIED = "NOT_VERIFIED"


class PixelRequirement(str, Enum):
    DISQO = "DISQO"
    FTRACK = "FTRACK"
    NO_FTRACK = "NO_FTRACK"
    PROTECTED = "PROTECTED"
    CLICKTAG = "CLICKTAG"
    ISPOT = "ISPOT"
    OTHER = "OTHER"


@dataclass(frozen=True)
class AdobePixelCheck:
    placement_id: str
    placement_name: str = ""
    site: str = ""
    request_type: str = ""

    vendor_raw: str = ""
    requirements: tuple[str, ...] = ()

    disqo_required: bool = False
    innovid_disqo: bool = False
    tags_disqo: bool = False

    result: str = PixelResult.NOT_APPLICABLE.value
    message: str = ""
    expected: str = ""
    actual: str = ""
    recommended_action: str = ""

    innovid_evidence: tuple[str, ...] = ()
    tag_evidence: tuple[str, ...] = ()
    tag_files: tuple[str, ...] = ()


@dataclass
class AdobePixelReconciliation:
    checks: list[AdobePixelCheck] = field(default_factory=list)

    @property
    def by_result(self) -> dict[str, int]:
        counts = {
            PixelResult.PASS.value: 0,
            PixelResult.FAIL.value: 0,
            PixelResult.REVIEW.value: 0,
            PixelResult.NOT_APPLICABLE.value: 0,
            PixelResult.NOT_VERIFIED.value: 0,
        }

        for check in self.checks:
            counts[check.result] = counts.get(check.result, 0) + 1

        return counts

    @property
    def attention(self) -> list[AdobePixelCheck]:
        return [
            check
            for check in self.checks
            if check.result in {
                PixelResult.FAIL.value,
                PixelResult.REVIEW.value,
                PixelResult.NOT_VERIFIED.value,
            }
        ]


_VENDOR_SPLIT = re.compile(r"[,;/|\n]+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_DISQO_TERMS = (
    # Explicit vendor references.
    "disqo",

    # Adobe may implement DISQO through Active Metering in
    # Innovid Third_Party_Impression.
    "active metering",
    "activemetering",
    "track.activemetering.com",
    "activemetering.com",
)

_FTRACK_TERMS = (
    "ftrack",
    "ft track",
    "ft tracker",
)

_PROTECTED_TERMS = (
    "protected",
    "protection",
)

_CLICKTAG_TERMS = (
    "clicktag",
    "click tag",
)

_ISPOT_TERMS = (
    "ispot",
    "i spot",
)

# iSpot "funciona igual que DISQO tanto para third party como para
# site served": misma forma de verificar (Innovid o tags), pero su
# propio pixel no se identifica con los terminos de DISQO. Se busca
# evidencia de cualquiera de los dos vendors indistintamente.
_DISQO_EVIDENCE_TERMS = _DISQO_TERMS + _ISPOT_TERMS + ("ispot.tv",)


def _normalized_text(value: object) -> str:
    text = norm_compare(str(value or ""))
    return _NON_ALNUM.sub(" ", text).strip()


def _contains_any(
    value: object,
    terms: Iterable[str],
) -> bool:
    text = _normalized_text(value)

    return any(
        _normalized_text(term) in text
        for term in terms
    )


def classify_vendor_requirements(
    value: object,
) -> set[PixelRequirement]:
    """
    Classify Traffic Sheet Vendors / Pixels.

    Classification is conservative. Unknown populated values are OTHER.
    """
    raw = str(value or "").strip()

    if not raw:
        return set()

    normalized = _normalized_text(raw)
    requirements: set[PixelRequirement] = set()

    if "no ftrack" in normalized:
        requirements.add(PixelRequirement.NO_FTRACK)
    elif _contains_any(raw, _FTRACK_TERMS):
        requirements.add(PixelRequirement.FTRACK)

    if _contains_any(raw, _DISQO_TERMS):
        requirements.add(PixelRequirement.DISQO)

    if _contains_any(raw, _PROTECTED_TERMS):
        requirements.add(PixelRequirement.PROTECTED)

    if _contains_any(raw, _CLICKTAG_TERMS):
        requirements.add(PixelRequirement.CLICKTAG)

    if _contains_any(raw, _ISPOT_TERMS):
        requirements.add(PixelRequirement.ISPOT)

    if not requirements:
        requirements.add(PixelRequirement.OTHER)

    return requirements


def _tag_source_has_disqo(
    source: TagSourceRow,
) -> tuple[bool, list[str]]:
    evidence: list[str] = []

    for tag in source.row.tags:
        searchable_values = [
            tag.column_name,
            tag.tag_type,
            tag.raw,
            *tag.hosts,
            *tag.urls,
        ]

        if any(
            _contains_any(value, _DISQO_EVIDENCE_TERMS)
            for value in searchable_values
        ):
            evidence.append(
                f"{source.file_name} | "
                f"{source.sheet} | "
                f"row {source.row.row} | "
                f"{tag.column_name}"
            )

    return bool(evidence), evidence


def _inventory_has_disqo(
    inventory: TagInventory,
    placement_id: str,
) -> tuple[bool, list[str], list[str]]:
    evidence: list[str] = []
    files: set[str] = set()

    for source in inventory.by_placement.get(
        placement_id,
        [],
    ):
        found, source_evidence = _tag_source_has_disqo(
            source
        )

        if found:
            files.add(source.file_name)
            evidence.extend(source_evidence)

    return (
        bool(evidence),
        sorted(set(evidence)),
        sorted(files),
    )


def _row_disqo_evidence(row) -> list[str]:
    """
    Find DISQO evidence in one parsed Innovid Placement View row.

    Primary fields:
        third_party_impression
        third_party_survey
        clicktag

    Search also covers other populated values to support Current Views
    whose column aliases may vary.
    """
    evidence: list[str] = []

    for canonical_name, values in getattr(
        row,
        "multi",
        {},
    ).items():
        for value in values:
            if _contains_any(value, _DISQO_EVIDENCE_TERMS):
                evidence.append(
                    f"row {row.row} | "
                    f"{canonical_name} | "
                    f"{value}"
                )

    for canonical_name, value in getattr(
        row,
        "values",
        {},
    ).items():
        if _contains_any(value, _DISQO_EVIDENCE_TERMS):
            evidence.append(
                f"row {row.row} | "
                f"{canonical_name} | "
                f"{value}"
            )

    return evidence


def _placement_export_disqo_index(
    placement_export,
) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}

    if placement_export is None:
        return index

    for row in getattr(placement_export, "rows", []):
        placement_id = str(
            row.values.get("placement_id") or ""
        ).strip()

        if not placement_id:
            continue

        evidence = _row_disqo_evidence(row)

        if evidence:
            index.setdefault(
                placement_id,
                [],
            ).extend(evidence)

    return {
        placement_id: sorted(set(evidence))
        for placement_id, evidence in index.items()
    }


def _worked_vendor_data(ts_result) -> dict[str, dict]:
    """
    Build one vendor requirement record per worked Placement ID.
    """
    records: dict[str, dict] = {}

    # ts_result.scope holds EVERY placement row (including ones with
    # REQ_NOT_WORKED, i.e. out of scope for this request). Using it
    # directly pulled in placements from other work orders / prior
    # rounds on the same tab, producing DISQO FAILs for placements
    # that aren't even being worked right now. ts_result.worked is
    # already the correctly filtered subset everywhere else in the app.
    worked_ids = {s.placement_id for s in ts_result.worked}

    for row in ts_result.placements.rows:
        placement_id = str(
            row.values.get("placement_id") or ""
        ).strip()

        if (
            not placement_id
            or placement_id not in worked_ids
        ):
            continue

        record = records.setdefault(
            placement_id,
            {
                "placement_name": "",
                "site": "",
                "request_type": "",
                "raw_values": set(),
                "requirements": set(),
            },
        )

        if not record["placement_name"]:
            record["placement_name"] = str(
                row.values.get("placement_name") or ""
            ).strip()

        if not record["site"]:
            record["site"] = str(
                row.values.get("site") or ""
            ).strip()

        scope = ts_result.scope.get(placement_id)

        if scope is not None:
            record["request_type"] = str(
                scope.request_type or ""
            )

        vendor_raw = str(
            row.values.get("vendors") or ""
        ).strip()

        if vendor_raw:
            record["raw_values"].add(vendor_raw)
            record["requirements"].update(
                classify_vendor_requirements(
                    vendor_raw
                )
            )

    return records


def reconcile_adobe_pixels(
    ts_result,
    placement_export,
    tag_inventory: TagInventory,
) -> AdobePixelReconciliation:
    """
    Reconcile Adobe pixel requirements by worked Placement ID.

    The function returns every worked placement, including N/A records,
    so the interface can show complete coverage.
    """
    result = AdobePixelReconciliation()

    vendor_by_placement = _worked_vendor_data(
        ts_result
    )

    innovid_disqo = _placement_export_disqo_index(
        placement_export
    )

    for placement_id in sorted(vendor_by_placement):
        record = vendor_by_placement[placement_id]

        requirements = set(record["requirements"])
        raw_values = sorted(record["raw_values"])

        # iSpot funciona igual que DISQO tanto para Third Party como
        # para Site-Served: misma evidencia (Innovid o tags), mismo
        # veredicto. No es un requisito aparte, es el mismo cheque con
        # otro nombre de vendor.
        disqo_required = bool(
            requirements
            & {PixelRequirement.DISQO, PixelRequirement.ISPOT}
        )

        innovid_evidence = innovid_disqo.get(
            placement_id,
            [],
        )

        innovid_has_disqo = bool(
            innovid_evidence
        )

        (
            tags_have_disqo,
            tag_evidence,
            tag_files,
        ) = _inventory_has_disqo(
            tag_inventory,
            placement_id,
        )

        common = {
            "placement_id": placement_id,
            "placement_name": (
                record["placement_name"]
            ),
            "site": record["site"],
            "request_type": (
                record["request_type"]
            ),
            "vendor_raw": " | ".join(
                raw_values
            ),
            "requirements": tuple(
                sorted(
                    requirement.value
                    for requirement
                    in requirements
                )
            ),
            "disqo_required": disqo_required,
            "innovid_disqo": (
                innovid_has_disqo
            ),
            "tags_disqo": tags_have_disqo,
            "innovid_evidence": tuple(
                innovid_evidence
            ),
            "tag_evidence": tuple(
                tag_evidence
            ),
            "tag_files": tuple(tag_files),
        }

        if not disqo_required:
            result.checks.append(
                AdobePixelCheck(
                    result=(
                        PixelResult
                        .NOT_APPLICABLE
                        .value
                    ),
                    message=(
                        "DISQO is not required "
                        "for this placement."
                    ),
                    expected="N/A",
                    actual="N/A",
                    **common,
                )
            )
            continue

        if (
            innovid_has_disqo
            and not tags_have_disqo
        ):
            result.checks.append(
                AdobePixelCheck(
                    result=PixelResult.PASS.value,
                    message=(
                        "DISQO is integrated "
                        "in Innovid."
                    ),
                    expected=(
                        "DISQO integration "
                        "in Innovid"
                    ),
                    actual=(
                        "Found in Innovid "
                        "Placement View"
                    ),
                    **common,
                )
            )
            continue

        if (
            not innovid_has_disqo
            and tags_have_disqo
        ):
            result.checks.append(
                AdobePixelCheck(
                    result=PixelResult.PASS.value,
                    message=(
                        "DISQO is correctly included "
                        "in the 1x1 tag file."
                    ),
                    expected=(
                        "Populated DISQO column "
                        "in the 1x1 tag file"
                    ),
                    actual=(
                        "DISQO found in delivered "
                        "tag file"
                    ),
                    recommended_action=(
                        "No correction is required. "
                        "Additional DISQO evidence in "
                        "Innovid Third_Party_Impression "
                        "is not required for this "
                        "Site-Served 1x1 placement."
                    ),
                    **common,
                )
            )
            continue

        if (
            not innovid_has_disqo
            and not tags_have_disqo
        ):
            # No evidence yet is not the same as broken: Adobe workflows
            # often ship tags before DISQO delivers the vendor pixel for
            # a placement. This is inherently a pending/uncertain state
            # a human must confirm (still waiting vs. genuinely missing),
            # not a certain error, so it is REVIEW rather than FAIL.
            result.checks.append(
                AdobePixelCheck(
                    result=PixelResult.REVIEW.value,
                    message=(
                        "DISQO is required but no "
                        "implementation evidence was found yet "
                        "(may still be pending from the vendor)."
                    ),
                    expected=(
                        "DISQO integration "
                        "in Innovid"
                    ),
                    actual=(
                        "Not found in Innovid "
                        "or tag files"
                    ),
                    recommended_action=(
                        "Confirm with DISQO whether the pixel for "
                        "this placement has been delivered yet; "
                        "integrate in Innovid once available."
                    ),
                    **common,
                )
            )
            continue

        # Innovid YES + Tags YES.
        result.checks.append(
            AdobePixelCheck(
                result=PixelResult.REVIEW.value,
                message=(
                    "DISQO evidence was found in "
                    "both Innovid and tag files."
                ),
                expected=(
                    "DISQO integrated in Innovid "
                    "without duplicate tag evidence"
                ),
                actual=(
                    "Found in Innovid and tag files"
                ),
                recommended_action=(
                    "Review the placement to avoid "
                    "duplicate DISQO measurement."
                ),
                **common,
            )
        )

    return _flag_official_pixel_drift(result)


def _flag_official_pixel_drift(
    result: AdobePixelReconciliation,
) -> AdobePixelReconciliation:
    """
    Downgrades a PASS to REVIEW when the evidence that made it pass
    doesn't structurally match the official pixel on record for that
    requirement (config/vendor_pixels_adobe.json). Leaves every other
    result untouched -- this only adds a narrower check on top of the
    existing presence check, it never overrides a FAIL/REVIEW/N/A.
    """
    official_by_vendor = _official_pixels()

    if not official_by_vendor:
        return result

    updated: list[AdobePixelCheck] = []

    for check in result.checks:
        if check.result != PixelResult.PASS.value:
            updated.append(check)
            continue

        requirement = (
            "iSpot" if "ISPOT" in check.requirements else "DISQO"
        )
        official = official_by_vendor.get(requirement)

        if not official:
            updated.append(check)
            continue

        evidence_values = [
            _evidence_value(line)
            for line in (*check.innovid_evidence, *check.tag_evidence)
        ]

        if any(
            pixel_matches_official(value, official)
            for value in evidence_values
            if value
        ):
            updated.append(check)
            continue

        updated.append(
            replace(
                check,
                result=PixelResult.REVIEW.value,
                message=(
                    f"{requirement} evidence was found, but doesn't "
                    "match the official pixel on record for this "
                    "vendor."
                ),
                actual=" | ".join(v for v in evidence_values if v) or check.actual,
                recommended_action=(
                    "Confirm with the team whether the vendor rotated "
                    "its pixel -- if so, update the official pixel in "
                    "the Pixels by account (Adobe) panel."
                ),
            )
        )

    result.checks = updated
    return result

"""
Official Adobe pixel findings.

PIX-A01 validates DISQO using the applicable implementation source:

Site-Served 1x1:
    A populated DISQO column in the delivered tag file is sufficient.

Third Party:
    A recognized DISQO or Active Metering implementation in Innovid
    Third_Party_Impression is sufficient.

FTRACK and PROTECTED do not generate PIX-A01 findings because those
requirements have different applicability rules.

Checks marked N/A are intentionally excluded from PIX-A01.
"""
from __future__ import annotations

from typing import Any

from core.findings import Domain, EntityType, FindingsBuffer


RULE_ID = "PIX-A01"


def _text(value: Any) -> str:
    """Return a clean printable value without changing source content."""

    if value is None:
        return ""

    if hasattr(value, "value"):
        value = value.value

    return str(value).strip()


def _status(check: Any) -> str:
    """Read the reconciliation status safely."""

    return _text(
        getattr(
            check,
            "result",
            getattr(check, "status", ""),
        )
    ).upper()


def _value(
    check: Any,
    *attribute_names: str,
    default: Any = "",
) -> Any:
    """
    Return the first available non-empty attribute.

    This keeps the rule compatible with the current reconciliation
    dataclass without duplicating business logic inside the rule.
    """

    for attribute_name in attribute_names:
        if not hasattr(check, attribute_name):
            continue

        value = getattr(check, attribute_name)

        if value not in (None, "", [], (), {}, set()):
            return value

    return default


def _evidence_text(check: Any) -> str:
    """Build a short traceability description for the finding."""

    parts: list[str] = []

    site = _text(_value(check, "site"))
    request_type = _text(
        _value(
            check,
            "request_type",
            "request",
        )
    )
    vendor = _text(
        _value(
            check,
            "vendor_raw",
            "vendor",
            "vendor_ts",
        )
    )

    tags_disqo = _value(
        check,
        "tags_have_disqo",
        "tags_disqo",
        default=None,
    )

    innovid_disqo = _value(
        check,
        "innovid_has_disqo",
        "innovid_disqo",
        default=None,
    )

    if site:
        parts.append(f"Site: {site}")

    if request_type:
        parts.append(f"Request type: {request_type}")

    if vendor:
        parts.append(f"Traffic Sheet vendor: {vendor}")

    if tags_disqo is not None:
        parts.append(
            "DISQO in Tags: "
            + ("Yes" if bool(tags_disqo) else "No")
        )

    if innovid_disqo is not None:
        parts.append(
            "DISQO in Innovid: "
            + ("Yes" if bool(innovid_disqo) else "No")
        )

    tag_evidence = _value(
        check,
        "tag_evidence",
        "tag_sources",
        default=[],
    )

    innovid_evidence = _value(
        check,
        "innovid_evidence",
        "export_evidence",
        default=[],
    )

    if tag_evidence:
        parts.append(
            f"Tag evidence records: {len(tag_evidence)}"
        )

    if innovid_evidence:
        parts.append(
            f"Innovid evidence records: {len(innovid_evidence)}"
        )

    return " | ".join(parts)


def evaluate(
    reconciliation,
    buffer: FindingsBuffer,
) -> None:
    """
    Convert Adobe DISQO reconciliation checks into official findings.

    Parameters
    ----------
    reconciliation:
        Result returned by core.adobe_pixel_reconciliation.
        The object must expose a ``checks`` collection.

    buffer:
        Canonical QA2 FindingsBuffer.

    Status mapping
    --------------
    PASS         -> buffer.pass_
    FAIL         -> buffer.fail
    REVIEW       -> buffer.review
    NOT_VERIFIED -> buffer.not_verified
    N/A          -> no finding

    N/A is excluded because FTRACK and PROTECTED are not applicable
    to Adobe Third Party placements under the current business rule.
    """

    checks = getattr(reconciliation, "checks", None)

    if checks is None:
        raise TypeError(
            "Adobe pixel reconciliation result does not expose "
            "a 'checks' collection."
        )

    for check in checks:
        status = _status(check)

        # N/A checks are intentionally excluded from PIX-A01.
        if status in {
            "",
            "N/A",
            "NA",
            "NOT_APPLICABLE",
            "NOT APPLICABLE",
        }:
            continue

        placement_id = _text(
            _value(
                check,
                "placement_id",
            )
        )

        placement_name = _text(
            _value(
                check,
                "placement_name",
            )
        )

        message = _text(
            _value(
                check,
                "message",
                default="Adobe DISQO validation completed.",
            )
        )

        expected = _text(
            _value(
                check,
                "expected",
                default="DISQO implementation in the applicable source",
            )
        )

        actual = _text(
            _value(
                check,
                "actual",
                default="",
            )
        )

        recommended_action = _text(
            _value(
                check,
                "recommended_action",
                default="",
            )
        )

        reason = _evidence_text(check)

        finding_arguments = {
            "rule_id": RULE_ID,
            "domain": Domain.PIXEL,
            "message": message,
            "entity_type": EntityType.PLACEMENT,
            "placement_id": placement_id,
            "placement_name": placement_name,
            "expected": expected,
            "actual": actual,
            "reason": reason,
            "recommended_action": recommended_action,
        }

        if status == "PASS":
            buffer.pass_(**finding_arguments)

        elif status == "FAIL":
            buffer.fail(**finding_arguments)

        elif status == "REVIEW":
            buffer.review(**finding_arguments)

        elif status == "NOT_VERIFIED":
            buffer.not_verified(**finding_arguments)

        else:
            raise ValueError(
                "Unsupported Adobe pixel reconciliation status "
                f"{status!r} for placement {placement_id or '-'}."
            )

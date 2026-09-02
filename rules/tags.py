"""
QA2 rules for tag files.

Initial validations:
  TAG-001 File Campaign ID.
  TAG-002 Placement ID exists in Innovid.
  TAG-003 Placement ID belongs to the worked scope.
  TAG-004 Placement Name.
  TAG-005 Dimensions.
  TAG-006 Third Party ID.
  TAG-007 Placement ID embedded in the tag.
  TAG-008 Campaign ID embedded in the tag.
  TAG-009 Embedded dimensions.
  TAG-010 Empty tag.
  TAG-011 Duplicate placement within the file.
"""
from __future__ import annotations

from datetime import date, datetime

from core.findings import (
    Confidence,
    Domain,
    EntityType,
    FindingsBuffer,
    Severity,
)
from core.normalize import norm_compare, norm_dims
from core.tag_matching import TagMatchResult


AUXILIARY_PIXEL_TYPES = {
    "PIXEL",
    "PIXEL_HTML",
    "1X1_IMPRESSION",
}


def _date_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value or "").strip()


def evaluate(
    tag_match: TagMatchResult,
    buffer: FindingsBuffer,
) -> None:
    # ------------------------------------------------ TAG-001 Campaign ID

    expected_campaign = (
        tag_match.campaign_id_innovid
        or tag_match.campaign_id_ts
    )

    if not tag_match.campaign_id_tags:
        buffer.not_verified(
            rule_id="TAG-001",
            domain=Domain.TAG,
            message="The tag file does not declare a Campaign ID.",
            entity_type=EntityType.FILE,
            expected=expected_campaign,
            actual="",
            recommended_action=(
                "Re-export the tags including the Campaign ID."
            ),
        )

    elif (
        expected_campaign
        and tag_match.campaign_id_tags != expected_campaign
    ):
        buffer.blocker(
            rule_id="TAG-001",
            domain=Domain.TAG,
            message=(
                "The tag file belongs to a different campaign."
            ),
            entity_type=EntityType.FILE,
            expected=expected_campaign,
            actual=tag_match.campaign_id_tags,
            reason=(
                "Tag file Campaign ID differs from the Traffic "
                "Sheet or Innovid Campaign ID."
            ),
            recommended_action=(
                "Upload the tag file for the correct campaign."
            ),
        )

    else:
        buffer.pass_(
            rule_id="TAG-001",
            domain=Domain.TAG,
            message="Tag file Campaign ID is correct.",
            entity_type=EntityType.FILE,
            expected=expected_campaign,
            actual=tag_match.campaign_id_tags,
        )

    # ------------------------------------------------ TAG-011 duplicates

    for placement_id, count in (
        tag_match.duplicate_placement_ids.items()
    ):
        buffer.review(
            rule_id="TAG-011",
            domain=Domain.CARDINALITY,
            message=(
                "Placement ID repeated within the tag file."
            ),
            entity_type=EntityType.PLACEMENT,
            placement_id=placement_id,
            expected="1 row",
            actual=f"{count} rows",
            count=count,
            recommended_action=(
                "Confirm whether the rows represent different tags "
                "or an accidental duplication."
            ),
        )

    # ------------------------------------------------ placement rows

    for link in tag_match.links:
        row = link.tag_row

        # TAG-002: the placement must exist in the loaded export.

        if link.actual is None:
            buffer.review(
                rule_id="TAG-002",
                domain=Domain.TAG,
                message=(
                    "Tag file placement was not found in the "
                    "loaded Innovid export."
                ),
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                placement_name=row.placement_name,
                expected="Placement present in Innovid",
                actual="Not found",
                recommended_action=(
                    "Confirm the Innovid export includes this "
                    "placement, or upload the correct export."
                ),
            )
        else:
            buffer.pass_(
                rule_id="TAG-002",
                domain=Domain.TAG,
                message="Tag placement found in Innovid.",
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                placement_name=row.placement_name,
            )

        # TAG-003: flag when the tag doesn't belong to the worked scope.
        # Not a FAIL because a tag file may represent only part of the
        # campaign or include additional deliverables.

        if link.expected is None:
            buffer.info(
                rule_id="TAG-003",
                domain=Domain.SCOPE,
                message=(
                    "Tag file placement is outside the worked scope "
                    "detected in the Traffic Sheet."
                ),
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                placement_name=row.placement_name,
                recommended_action=(
                    "Confirm whether the tag file belongs to a "
                    "different request or additional context."
                ),
            )
        else:
            buffer.pass_(
                rule_id="TAG-003",
                domain=Domain.SCOPE,
                message=(
                    "Tag placement belongs to the worked scope."
                ),
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                placement_name=row.placement_name,
            )

        # TAG-004: Placement Name.
        # Compared against Innovid first, then against the TS.

        expected_name = ""

        if link.actual is not None:
            expected_name = (
                link.actual.name_norm
                or link.actual.name
            )
        elif link.expected is not None:
            expected_name = link.expected.name

        if not expected_name or not row.placement_name:
            buffer.not_verified(
                rule_id="TAG-004",
                domain=Domain.IDENTITY,
                message=(
                    "Placement Name is not verifiable in the tag file."
                ),
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                expected=expected_name,
                actual=row.placement_name,
            )

        elif (
            norm_compare(expected_name)
            == norm_compare(row.placement_name)
        ):
            buffer.pass_(
                rule_id="TAG-004",
                domain=Domain.IDENTITY,
                message="Tag Placement Name is correct.",
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                placement_name=row.placement_name,
                expected=expected_name,
                actual=row.placement_name,
            )

        else:
            buffer.fail(
                rule_id="TAG-004",
                domain=Domain.IDENTITY,
                message="Tag Placement Name doesn't match.",
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                placement_name=row.placement_name,
                expected=expected_name,
                actual=row.placement_name,
                recommended_action=(
                    "Regenerate the tags using the correct placement."
                ),
            )

        # TAG-005: dimensions.
        #
        # DISABLED:
        # Dimensions embedded in tracking tags don't represent the
        # placement's actual dimensions. A pixel can declare 0x0 or 1x1
        # even when the placement is 1920x1080, display, or video.
        #
        # Real dimensions are validated exclusively via:
        # Traffic Sheet vs Innovid Export.
        #
        # This rule emits no PASS, FAIL, REVIEW, or NOT_VERIFIED.

        # TAG-006: Third Party ID.
        expected_third_party_id = ""

        if link.actual is not None:
            expected_third_party_id = (
                link.actual.third_party_id
            )

            if (
                not expected_third_party_id
                and link.actual.creatives
            ):
                creative_values = {
                    creative.third_party_id
                    for creative in link.actual.creatives
                    if creative.third_party_id
                }

                if len(creative_values) == 1:
                    expected_third_party_id = next(
                        iter(creative_values)
                    )

        if not expected_third_party_id:
            buffer.not_verified(
                rule_id="TAG-006",
                domain=Domain.ATTRIBUTION,
                message=(
                    "Innovid Third Party ID is not available "
                    "to compare against the tag file."
                ),
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                expected="Innovid Third Party ID",
                actual=row.third_party_id,
            )

        elif not row.third_party_id:
            buffer.fail(
                rule_id="TAG-006",
                domain=Domain.ATTRIBUTION,
                message=(
                    "The tag file doesn't contain a Third Party ID."
                ),
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                expected=expected_third_party_id,
                actual="",
            )

        elif (
            expected_third_party_id
            == row.third_party_id
        ):
            buffer.pass_(
                rule_id="TAG-006",
                domain=Domain.ATTRIBUTION,
                message="Tag Third Party ID is correct.",
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                expected=expected_third_party_id,
                actual=row.third_party_id,
            )

        else:
            buffer.fail(
                rule_id="TAG-006",
                domain=Domain.ATTRIBUTION,
                message="Tag Third Party ID doesn't match.",
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                expected=expected_third_party_id,
                actual=row.third_party_id,
                recommended_action=(
                    "Regenerate the tags from the correct placement."
                ),
            )

        # TAG-010: the row must contain at least one tag.

        if row.tag_count == 0:
            buffer.fail(
                rule_id="TAG-010",
                domain=Domain.TAG,
                message=(
                    "Placement has no materialized tags."
                ),
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                placement_name=row.placement_name,
                expected="At least one tag",
                actual="0 tags",
            )
        else:
            buffer.pass_(
                rule_id="TAG-010",
                domain=Domain.TAG,
                message="Placement contains tags.",
                entity_type=EntityType.PLACEMENT,
                placement_id=row.placement_id,
                actual=f"{row.tag_count} tags",
            )

        # ------------------------------------------------ tag content

        for tag in row.tags:
            tag_source = (
                f"{row.placement_id} | {tag.column_name}"
            )

            # TAG-007: embedded Placement ID.

            if tag.placement_ids:
                if row.placement_id in tag.placement_ids:
                    buffer.pass_(
                        rule_id="TAG-007",
                        domain=Domain.TAG,
                        message=(
                            "Embedded Placement ID in the tag is correct."
                        ),
                        entity_type=EntityType.TAG,
                        placement_id=row.placement_id,
                        expected=row.placement_id,
                        actual=", ".join(tag.placement_ids),
                        reason=tag_source,
                    )
                else:
                    buffer.fail(
                        rule_id="TAG-007",
                        domain=Domain.TAG,
                        message=(
                            "Embedded Placement ID in the tag doesn't "
                            "match the row."
                        ),
                        entity_type=EntityType.TAG,
                        placement_id=row.placement_id,
                        expected=row.placement_id,
                        actual=", ".join(tag.placement_ids),
                        reason=tag_source,
                        recommended_action=(
                            "Regenerate the tag for this placement."
                        ),
                    )
            else:
                # No hay Placement ID embebido que contrastar. Eso es
                # una propiedad del tipo de tag, no un insumo que falte:
                # no hay nada que el trafficker pueda subir para que
                # este check corra. Como INFO queda registrado sin
                # arrastrar el veredicto a NEEDS_REVIEW, que dejaba la
                # campana sin poder aprobar por mas correcta que
                # estuviera la implementacion.
                buffer.info(
                    rule_id="TAG-007",
                    domain=Domain.TAG,
                    message=(
                        "The tag carries no embedded Placement ID, so "
                        "there's nothing to cross-check. This is how "
                        "this tag type is built, not a problem with "
                        "the implementation."
                    ),
                    entity_type=EntityType.TAG,
                    placement_id=row.placement_id,
                    reason=tag_source,
                    confidence=Confidence.NONE,
                )

            # TAG-008: embedded Campaign ID.

            if tag.campaign_ids:
                if (
                    tag_match.campaign_id_tags
                    in tag.campaign_ids
                ):
                    buffer.pass_(
                        rule_id="TAG-008",
                        domain=Domain.TAG,
                        message=(
                            "Embedded Campaign ID in the tag is correct."
                        ),
                        entity_type=EntityType.TAG,
                        placement_id=row.placement_id,
                        expected=tag_match.campaign_id_tags,
                        actual=", ".join(tag.campaign_ids),
                        reason=tag_source,
                    )
                else:
                    buffer.fail(
                        rule_id="TAG-008",
                        domain=Domain.TAG,
                        message=(
                            "Embedded Campaign ID in the tag doesn't "
                            "match the file."
                        ),
                        entity_type=EntityType.TAG,
                        placement_id=row.placement_id,
                        expected=tag_match.campaign_id_tags,
                        actual=", ".join(tag.campaign_ids),
                        reason=tag_source,
                    )

            # TAG-009: embedded dimensions.
            # Skipped for auxiliary pixels since they may use 0x0.

            if tag.tag_type not in AUXILIARY_PIXEL_TYPES:
                width_mismatch = (
                    bool(tag.widths)
                    and row.width not in tag.widths
                )

                height_mismatch = (
                    bool(tag.heights)
                    and row.height not in tag.heights
                )

                if width_mismatch or height_mismatch:
                    buffer.fail(
                        rule_id="TAG-009",
                        domain=Domain.DIMENSIONS,
                        message=(
                            "Embedded dimensions in the tag don't "
                            "match the row."
                        ),
                        entity_type=EntityType.TAG,
                        placement_id=row.placement_id,
                        expected=row.dimensions,
                        actual=(
                            f"width={tag.widths or '-'}; "
                            f"height={tag.heights or '-'}"
                        ),
                        reason=tag_source,
                    )
                elif tag.widths or tag.heights:
                    buffer.pass_(
                        rule_id="TAG-009",
                        domain=Domain.DIMENSIONS,
                        message=(
                            "Embedded dimensions in the tag are correct."
                        ),
                        entity_type=EntityType.TAG,
                        placement_id=row.placement_id,
                        expected=row.dimensions,
                        actual=(
                            f"width={tag.widths}; "
                            f"height={tag.heights}"
                        ),
                        reason=tag_source,
                    )
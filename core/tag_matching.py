"""
Matching de archivos de tags contra el resultado TS vs Innovid.

Este módulo no emite findings.
Solo vincula cada placement del archivo de tags con:
  - Expected Placement de la Traffic Sheet
  - Actual Placement del export de Innovid
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.matching import ActualPlacement, ExpectedPlacement, MatchResult
from parsers.innovid_tags import TagRow, TagsResult


@dataclass
class TagPlacementLink:
    tag_row: TagRow
    expected: ExpectedPlacement | None = None
    actual: ActualPlacement | None = None

    @property
    def placement_id(self) -> str:
        return self.tag_row.placement_id

    @property
    def in_ts_scope(self) -> bool:
        return self.expected is not None

    @property
    def in_innovid(self) -> bool:
        return self.actual is not None


@dataclass
class TagMatchResult:
    campaign_id_tags: str = ""
    campaign_id_ts: str = ""
    campaign_id_innovid: str = ""

    links: list[TagPlacementLink] = field(default_factory=list)

    duplicate_placement_ids: dict[str, int] = field(default_factory=dict)

    @property
    def matched_to_scope(self) -> list[TagPlacementLink]:
        return [
            link
            for link in self.links
            if link.expected is not None
        ]

    @property
    def matched_to_innovid(self) -> list[TagPlacementLink]:
        return [
            link
            for link in self.links
            if link.actual is not None
        ]

    @property
    def outside_scope(self) -> list[TagPlacementLink]:
        return [
            link
            for link in self.links
            if link.expected is None
        ]

    @property
    def missing_in_innovid(self) -> list[TagPlacementLink]:
        return [
            link
            for link in self.links
            if link.actual is None
        ]


def match_tags(
    match_result: MatchResult,
    tags_result: TagsResult,
) -> TagMatchResult:
    result = TagMatchResult(
        campaign_id_tags=tags_result.campaign_id,
        campaign_id_ts=match_result.ts_campaign_id,
        campaign_id_innovid=match_result.export_campaign_id,
    )

    expected_by_id: dict[str, ExpectedPlacement] = {}
    actual_by_id: dict[str, ActualPlacement] = {}

    for placement_match in match_result.matched:
        expected_by_id[placement_match.placement_id] = (
            placement_match.expected
        )

        if placement_match.actual is not None:
            actual_by_id[placement_match.placement_id] = (
                placement_match.actual
            )

    for expected in match_result.only_expected:
        expected_by_id[expected.placement_id] = expected

    counts: dict[str, int] = {}

    for tag_row in tags_result.rows:
        placement_id = tag_row.placement_id

        counts[placement_id] = counts.get(placement_id, 0) + 1

        result.links.append(
            TagPlacementLink(
                tag_row=tag_row,
                expected=expected_by_id.get(placement_id),
                actual=actual_by_id.get(placement_id),
            )
        )

    result.duplicate_placement_ids = {
        placement_id: count
        for placement_id, count in counts.items()
        if count > 1
    }

    return result
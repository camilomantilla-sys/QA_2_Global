"""
Inventario consolidado de múltiples archivos de Tags.

Agrupa todos los archivos por Placement ID y conserva:
- archivo
- hoja
- fila
- Campaign ID
- Third Party ID
- columnas y tipos de tag
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from parsers.innovid_tags import TagRow, TagsResult, parse_innovid_tags


@dataclass
class TagSourceRow:
    file_name: str
    sheet: str
    campaign_id: str
    row: TagRow


@dataclass
class TagInventory:
    files: list[str] = field(default_factory=list)
    results: list[TagsResult] = field(default_factory=list)
    by_placement: dict[str, list[TagSourceRow]] = field(
        default_factory=dict
    )
    campaigns: Counter[str] = field(default_factory=Counter)
    tag_types: Counter[str] = field(default_factory=Counter)
    parse_failures: list[dict] = field(default_factory=list)

    @property
    def placement_ids(self) -> set:
        return set(self.by_placement)

    @property
    def distinct_placements(self) -> int:
        return len(self.by_placement)

    @property
    def total_rows(self) -> int:
        return sum(len(rows) for rows in self.by_placement.values())

    @property
    def total_tags(self) -> int:
        return sum(
            source.row.tag_count
            for sources in self.by_placement.values()
            for source in sources
        )

    @property
    def duplicate_placements(self) -> dict[str, int]:
        return {
            placement_id: len(sources)
            for placement_id, sources in self.by_placement.items()
            if len(sources) > 1
        }


def build_tag_inventory(paths: list[Path]) -> TagInventory:
    inventory = TagInventory()
    grouped: dict[str, list[TagSourceRow]] = defaultdict(list)

    for path in sorted(paths, key=lambda item: item.name.casefold()):
        result = parse_innovid_tags(path)

        inventory.files.append(path.name)
        inventory.results.append(result)

        fatal = [
            anomaly
            for anomaly in result.anomalies
            if anomaly.severity == "FATAL"
        ]

        if fatal:
            inventory.parse_failures.append(
                {
                    "file": path.name,
                    "issues": [
                        f"{item.code}: {item.message}"
                        for item in fatal
                    ],
                }
            )
            continue

        if result.campaign_id:
            inventory.campaigns[result.campaign_id] += 1

        for row in result.rows:
            grouped[row.placement_id].append(
                TagSourceRow(
                    file_name=path.name,
                    sheet=result.sheet,
                    campaign_id=result.campaign_id,
                    row=row,
                )
            )

            for tag in row.tags:
                inventory.tag_types[tag.tag_type] += 1

    inventory.by_placement = dict(grouped)
    return inventory

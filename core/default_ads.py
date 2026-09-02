"""
Consistencia del default ad.

El default ad es un creativo aparte: el mismo para todos los placements
de su dimension, con su propia landing page. Eso lo vuelve verificable
sin salir del export -- si una dimension tiene dos defaults distintos, o
el mismo default apunta a dos landing pages distintas, alguno de los
placements se quedo sin actualizar.

Es el caso tipico del swap de solo defaults: se cambia el default de una
dimension y uno de los placements no recibe el cambio.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from core.normalize import clean_id, norm_dims

# Sin \b: en los nombres de archivo el default viene pegado con guion
# bajo ("..._728x90_Default.zip") y el guion bajo es caracter de palabra,
# asi que \bdefault\b no encuentra frontera y no matchea.
_IS_DEFAULT = re.compile(r"default", re.I)
_PLATFORM_ID = re.compile(r"\s*\(\d+\)\s*$")


@dataclass
class DefaultAdCheck:
    placement_id: str
    dims: str = ""
    creative: str = ""
    landing_page: str = ""
    expected_creative: str = ""
    expected_landing_page: str = ""
    result: str = "PASS"
    message: str = ""


@dataclass
class DefaultAdReconciliation:
    checks: list[DefaultAdCheck] = field(default_factory=list)
    # Por dimension: el default que usa la mayoria de los placements.
    baseline: dict[str, str] = field(default_factory=dict)


def _creative_name(row) -> str:
    raw = str(row.values.get("filename") or row.values.get("creative_name") or "")
    return _PLATFORM_ID.sub("", raw).strip()


def _landing_page(row) -> str:
    tags = row.multi.get("clicktag") or []
    return tags[0].split("?")[0].strip() if tags else ""


def reconcile_default_ads(ts_result, placement_creative) -> DefaultAdReconciliation:
    out = DefaultAdReconciliation()

    if placement_creative is None:
        return out

    worked = {s.placement_id for s in ts_result.worked}
    if not worked:
        return out

    # placement -> (creativo default, landing page)
    found: dict[str, tuple[str, str, str]] = {}

    for row in placement_creative.rows:
        if row.row_type == "PLACEMENT_HEADER":
            continue

        placement_id = clean_id(row.values.get("placement_id"))
        if not placement_id or placement_id not in worked:
            continue

        name = _creative_name(row)
        if not name or not _IS_DEFAULT.search(name):
            continue

        found[placement_id] = (
            norm_dims(row.values.get("dimensions")),
            name,
            _landing_page(row),
        )

    if not found:
        return out

    # El default de referencia de cada dimension es el que mas se repite.
    by_dims: dict[str, Counter] = defaultdict(Counter)
    for dims, name, landing_page in found.values():
        by_dims[dims][(name, landing_page)] += 1

    baseline: dict[str, tuple[str, str]] = {}
    ambiguous: set[str] = set()

    for dims, counter in by_dims.items():
        ranked = counter.most_common()
        winner, top = ranked[0]
        if len(ranked) > 1 and ranked[1][1] == top:
            ambiguous.add(dims)
        baseline[dims] = winner
        out.baseline[dims] = winner[0]

    for placement_id in sorted(found):
        dims, name, landing_page = found[placement_id]
        expected_name, expected_landing_page = baseline[dims]

        check = DefaultAdCheck(
            placement_id=placement_id,
            dims=dims,
            creative=name,
            landing_page=landing_page,
            expected_creative=expected_name,
            expected_landing_page=expected_landing_page,
        )

        if dims in ambiguous:
            check.result = "REVIEW"
            check.message = (
                f"{dims} placements carry more than one default ad and "
                "none is clearly the current one."
            )
        elif name != expected_name:
            check.result = "FAIL"
            check.message = (
                "This placement runs a different default ad than the "
                f"rest of the {dims} placements."
            )
        elif landing_page != expected_landing_page:
            check.result = "FAIL"
            check.message = (
                "The default ad points to a different landing page than "
                f"on the rest of the {dims} placements."
            )
        else:
            check.result = "PASS"
            check.message = (
                f"Default ad matches the one used across {dims} "
                "placements."
            )

        out.checks.append(check)

    return out

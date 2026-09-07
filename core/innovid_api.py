"""
Innovid Campaign Manager API client (the UI-only fields).

Some things QA2 has to check never make it into any export: the
Verification Partner configured on a placement, the rotation weight of
each creative, and the creative's own flight dates (which can differ
from the placement's -- a placement starting July 20 with creatives
starting July 24 is exactly the case this exists for).

Innovid's own interface reads those from an internal API, so this
fetches them the same way:

    POST {CM}/campaigns/{id}/summary?fields=...   -> placement level
    GET  {DT}/dset/{modernDtreeId}                -> creative level

Authentication is a session cookie plus an X-Csrf-Token, so there's no
API key to hand over: `fetch_campaign` drives a real browser through
the normal login, then reuses that session for the calls. Everything
below `parse_*` is pure and testable without a browser.

This is an internal API (note the `/ui/` in its paths) -- it exists to
serve Innovid's own front end, not as a documented product, so it can
change without notice. QA2 treats it as a complement to the exports,
never as the only source.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

CM_BASE = "https://api.flashtalking.net/cm/v1/ui"
DT_BASE = "https://api.flashtalking.net/dt/v1/ui"
APP_ORIGIN = "https://campaign-manager.flashtalking.net"

# What Innovid's own summary grid asks for, taken from the request
# its interface makes, plus the fields QA2 needs that its default
# view doesn't request. Asking for a field Innovid doesn't recognise
# is harmless -- it comes back absent rather than as an error -- and
# the response carries about 130 fields regardless of this list, so
# it is a floor rather than a filter.
SUMMARY_FIELDS = (
    # Innovid's own list, in its order.
    "status",
    "siteName",
    "placementId",
    "placementName",
    "placementType",
    "dimensions",
    "clickTag1",
    "startDate",
    "endDate",
    "creativeDescription",
    "creativeId",
    "fileName",
    "thirdPartySurvey1",
    "thirdPartyImpression1",
    "thirdPartyImpression2",
    "verificationPartner",
    "verificationStatus",
    "bookedUnits",
    "prismaPlacementId",

    # QA2's additions. The decision set ids are what link a placement
    # to its creatives' real flight dates; Innovid's grid gets them
    # from the decision set's own row instead of asking for them.
    "id",
    "name",
    "level",
    "rotationWeight",
    "placementModernDtreeId",
    "modernDtreeId",
    "modernDtreeName",
    "placementDecisionSetId",
    "decisionSetId",
    "decisionSetName",
)

# Innovid caps a page of results; 500 is what its own interface asks
# for. MAX_SUMMARY_PAGES is a stop so a bad response can't spin
# forever.
SUMMARY_PAGE_SIZE = 500
MAX_SUMMARY_PAGES = 40

# When decision set lookups keep failing the same way, the next one
# will too. Stopping keeps QA2 from firing dozens of doomed requests
# at an internal API that rate limits.
GIVE_UP_AFTER_FAILED_LOOKUPS = 3

# A saved sign-in, so QA2 doesn't have to log in again each run.
# Holds session cookies, which are as good as the password until they
# expire -- gitignored, same as the credentials.
SESSION_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "innovid_session.json"
)

CREDENTIALS_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "innovid_credentials.env"
)


class InnovidAuthError(RuntimeError):
    """Login failed, or the session wasn't usable for API calls."""


@dataclass
class InnovidCredentials:
    username: str
    password: str
    login_url: str = APP_ORIGIN


@dataclass
class InnovidPlacement:
    """One row of the campaign summary -- placement level."""

    placement_id: str = ""
    placement_name: str = ""
    site_name: str = ""
    dimensions: str = ""
    status: str = ""
    start_date: str = ""
    end_date: str = ""
    creative_id: str = ""
    file_name: str = ""
    creative_description: str = ""
    click_tag_1: str = ""
    third_party_survey_1: str = ""
    third_party_impression_1: str = ""
    third_party_impression_2: str = ""
    verification_partner: str = ""
    verification_status: str = ""
    rotation_weight: str = ""
    booked_units: str = ""

    # Innovid carries two generations of decision set. The modern one
    # is what /dt/v1/ui/dset reads; the legacy id is a different
    # system and is kept separate rather than folded in, because
    # looking one up as if it were the other returns the wrong
    # creative rather than nothing.
    dtree_id: str = ""
    dtree_name: str = ""

    # Two different numbers, which an earlier version collapsed into
    # one and got wrong. `decisionSetId` identifies the decision set.
    # `placementDecisionSetId` identifies the link between a placement
    # and that decision set -- consecutive ids in a narrow range, the
    # shape of a join table -- and asking /dset for one of those is
    # what produced HTTP 400 on every single lookup.
    dset_id: str = ""
    dset_name: str = ""
    dset_link_id: str = ""

    # Rows come at more than one level (placement, creative). Kept so
    # the two can be told apart instead of being counted together.
    level: str = ""

    @property
    def is_placement_level(self) -> bool:
        return self.level.strip().upper() == "PLACEMENT"

    @property
    def is_creative_level(self) -> bool:
        return self.level.strip().upper() == "PLACEMENT-CREATIVE"


@dataclass
class InnovidCreativeNode:
    """
    One creative inside a decision set, with the two things the
    exports never carry: its own flight dates and its rotation weight.
    """

    dtree_id: str = ""
    dtree_name: str = ""
    node_id: str = ""
    creative_id: str = ""
    start_timestamp: str = ""
    end_timestamp: str = ""
    weight: str = ""
    is_default: bool = False
    serving_method: str = ""


@dataclass
class InnovidFetchResult:
    campaign_id: str = ""
    placements: list[InnovidPlacement] = field(default_factory=list)
    creative_nodes: list[InnovidCreativeNode] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # The field names Innovid actually returned. Kept because "the
    # column came back blank" and "Innovid never sent that column"
    # look identical once parsed, and they need opposite fixes.
    returned_fields: list[str] = field(default_factory=list)

    # For each of those, how many rows actually carry a value. Counts
    # only -- never the values -- so this can be read out loud when
    # working out why a column is empty.
    field_coverage: dict[str, int] = field(default_factory=dict)

    # Every row Innovid sent, including the site-level rows that carry
    # no placement. field_coverage is counted against this, not
    # against the parsed placements -- otherwise a field present on
    # every row reads as "409 / 385", which looks like a bug.
    rows_seen: int = 0

    # The field names a decision-set node carries. Rotation nodes come
    # back identified only as "node 1", "node 2" -- the creative they
    # serve is in some field not being read, since Innovid's own panel
    # shows a filename and id per row. Names only, no values.
    node_fields: dict[str, int] = field(default_factory=dict)

    # What each level of the flattened tree actually contains: how
    # many rows, and which fields are filled in on at least one of
    # them. The rows QA2 discards for having no placement id are in
    # here too, which is the point -- a decision set arrives as its
    # own row, and discarding it silently is how its id went missing.
    levels: dict[str, dict[str, int]] = field(default_factory=dict)

    def nodes_for_placement(self, placement_id: str) -> list[InnovidCreativeNode]:
        """
        The creative nodes belonging to one placement.

        Matches on every id a decision set can be named by. Keying on
        the modern id alone linked nothing at all in a campaign that
        has none -- and a comparison over nothing reports that
        everything agrees, which is the failure this whole client
        exists to prevent.
        """
        wanted = str(placement_id).strip()
        dset_ids = set()
        for row in self.placements:
            if row.placement_id != wanted:
                continue
            for candidate in (row.dtree_id, row.dset_id):
                if candidate:
                    dset_ids.add(candidate)
        return [n for n in self.creative_nodes if n.dtree_id in dset_ids]

    def creative_flight_gaps(self) -> dict[str, list]:
        """
        Finds days when a placement is live with no creative scheduled.

        Creatives in a decision set are considered together, not one
        at a time. Sequential rotation is normal and correct -- one
        creative covering 14-26 Sep and another 27 Sep-31 Oct leaves
        no hole -- so comparing each against the placement separately
        reports the second one as two weeks late and buries any real
        finding under dozens of non-events.

        A gap is therefore a stretch inside the placement's flight
        that *no* creative covers. Each one records whether a default
        creative exists, because a default still serves something --
        usually a backup image rather than the intended creative, so
        it is a lesser problem, not a non-problem.

        `overflow` lists creatives scheduled outside their placement's
        flight. The placement gates delivery, so those cost nothing.
        """
        from datetime import date, timedelta

        def _as_date(value):
            try:
                return date.fromisoformat(str(value)[:10])
            except (ValueError, TypeError):
                return None

        gaps: list[dict] = []
        overflow: list[dict] = []
        default_only: list[InnovidPlacement] = []
        checked: list[InnovidPlacement] = []
        unchecked: list[tuple[InnovidPlacement, str]] = []

        for placement in self.placement_rows():
            p_start = _as_date(placement.start_date)
            p_end = _as_date(placement.end_date)
            if not p_start or not p_end or p_end < p_start:
                unchecked.append((placement, "no readable flight dates"))
                continue

            nodes = self.nodes_for_placement(placement.placement_id)
            if not nodes:
                # Skipping this quietly is how "no gaps found" comes
                # to mean "no gaps found in the ones I looked at",
                # which reads as a pass over unexamined placements.
                unchecked.append((placement, "no decision set could be read"))
                continue

            checked.append(placement)

            has_default = any(n.is_default for n in nodes)
            windows = []
            for node in nodes:
                if node.is_default:
                    continue
                # No start means it has always been scheduled; no end
                # means Ongoing. Neither is missing data.
                start = _as_date(node.start_timestamp) or p_start
                end = _as_date(node.end_timestamp) or p_end

                if start < p_start or end > p_end:
                    overflow.append({
                        "placement": placement, "node": node,
                        "start": start, "end": end,
                    })

                windows.append((max(start, p_start), min(end, p_end)))

            windows = [w for w in windows if w[0] <= w[1]]
            if not windows:
                default_only.append(placement)
                continue

            # Walk the merged windows and note what they leave out.
            windows.sort()
            cursor = p_start
            for start, end in windows:
                if start > cursor:
                    gaps.append({
                        "placement": placement,
                        "start": cursor,
                        "end": start - timedelta(days=1),
                        "days": (start - cursor).days,
                        "covered_by_default": has_default,
                    })
                cursor = max(cursor, end + timedelta(days=1))

            if cursor <= p_end:
                gaps.append({
                    "placement": placement,
                    "start": cursor,
                    "end": p_end,
                    "days": (p_end - cursor).days + 1,
                    "covered_by_default": has_default,
                })

        return {
            "gaps": gaps,
            "overflow": overflow,
            "default_only": default_only,
            "checked": checked,
            "unchecked": unchecked,
        }

    def linked_node_count(self) -> int:
        """
        How many creative nodes could actually be tied to a placement.

        Reported alongside any date comparison, because "no
        differences found" and "nothing was compared" look identical
        otherwise.
        """
        # Counted per distinct placement: the same placement appears
        # as several rows (its own, plus one per creative), and
        # counting rows would multiply every node by that.
        return sum(
            len(self.nodes_for_placement(placement_id))
            for placement_id in {
                r.placement_id for r in self.placements if r.placement_id
            }
        )

    def placement_rows(self) -> list[InnovidPlacement]:
        """The placement-level rows only."""
        return [r for r in self.placements if r.is_placement_level]

    def creative_rows_for(self, placement_id: str) -> list[InnovidPlacement]:
        """
        The creative-level rows under one placement.

        The summary comes back as a tree flattened into rows -- a
        PLACEMENT row followed by its PLACEMENT-CREATIVE rows -- and
        each level carries its own dates. That's where a creative
        that starts after its placement becomes visible, without
        needing to open the decision set at all.
        """
        wanted = str(placement_id).strip()
        return [
            r for r in self.placements
            if r.is_creative_level and r.placement_id == wanted
        ]

    # Deliberately no compare-the-dates helper here.
    #
    # The PLACEMENT-CREATIVE rows do carry startDate/endDate, but
    # those repeat the placement's dates rather than the creative's
    # own -- the summary grid shows the placement flight on every row
    # under it. Comparing them would match every time and report "all
    # creatives flight like their placement", which is a false pass on
    # exactly the error this is meant to catch. Creative flight dates
    # only exist inside the decision set, so they have to be read
    # from there.


# ----------------------------------------------------------------
# Credentials
# ----------------------------------------------------------------

def load_credentials(path: Path | None = None) -> InnovidCredentials | None:
    """
    Reads config/innovid_credentials.env (KEY=value lines). Returns
    None when the file is missing or incomplete -- the caller then
    just skips the Innovid fetch instead of failing the whole run.

    The file is gitignored: credentials only ever live on the machine
    running QA2.
    """
    target = path or CREDENTIALS_PATH
    if not target.exists():
        return None

    values: dict[str, str] = {}
    try:
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip().upper()] = value.strip().strip('"').strip("'")
    except Exception:
        return None

    username = values.get("INNOVID_USERNAME", "")
    password = values.get("INNOVID_PASSWORD", "")
    if not username or not password:
        return None

    return InnovidCredentials(
        username=username,
        password=password,
        login_url=values.get("INNOVID_LOGIN_URL") or APP_ORIGIN,
    )


# ----------------------------------------------------------------
# Parsing -- pure, no browser needed
# ----------------------------------------------------------------

def _text(value) -> str:
    """
    Flattens whatever the API puts in a cell into a plain string.

    Values come back as scalars, nulls, or single-item lists depending
    on the field, and `0`/`False` are meaningful -- so this can't just
    be `str(value or "")`.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ", ".join(_text(v) for v in value if _text(v))
    if isinstance(value, dict):
        for key in ("name", "value", "id"):
            if key in value:
                return _text(value[key])
    return str(value)


def summary_field_names(payload: dict) -> list[str]:
    """
    The field names present in a /summary response.

    Names only, never values: this is for working out why a column
    arrived empty, and it gets printed and pasted into chats.
    """
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []

    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in item:
            if key not in names:
                names.append(key)
    return sorted(names)


def count_levels(payload: dict, into: dict[str, dict[str, int]]) -> dict:
    """
    Groups the response's rows by `level`, counting how many rows each
    level has and which fields carry a value on them.

    Names and counts only, never values.
    """
    if not isinstance(payload, dict):
        return into
    items = payload.get("items")
    if not isinstance(items, list):
        return into

    for item in items:
        if not isinstance(item, dict):
            continue
        level = _text(item.get("level")) or "(no level)"
        bucket = into.setdefault(level, {"_rows": 0})
        bucket["_rows"] += 1
        for key, value in item.items():
            if key == "level":
                continue
            if _text(value):
                bucket[key] = bucket.get(key, 0) + 1
    return into


def count_filled_fields(payload: dict, into: dict[str, int]) -> dict[str, int]:
    """
    Adds to `into` the number of rows carrying a value for each field.

    Counts, not values: this is for answering "is this column empty
    for everyone, or only for these rows", which is the question that
    decides where to look next.
    """
    if not isinstance(payload, dict):
        return into
    items = payload.get("items")
    if not isinstance(items, list):
        return into

    for item in items:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            into.setdefault(key, 0)
            if _text(value):
                into[key] += 1
    return into


def parse_summary_response(payload: dict) -> list[InnovidPlacement]:
    """
    Turns a /summary response into placement rows.

    Field names are read straight off the JSON, so a field QA2 didn't
    ask for is simply absent rather than an error.
    """
    if not isinstance(payload, dict):
        return []

    items = payload.get("items")
    if not isinstance(items, list):
        return []

    rows: list[InnovidPlacement] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Innovid includes rows with no placement id (totals and
        # spacers). Counting those as placements would inflate every
        # figure QA2 reports.
        if not _text(item.get("placementId")):
            continue
        rows.append(
            InnovidPlacement(
                placement_id=_text(item.get("placementId")),
                placement_name=_text(item.get("placementName")),
                site_name=_text(item.get("siteName")),
                dimensions=_text(item.get("dimensions")),
                status=_text(item.get("status")),
                start_date=_text(item.get("startDate")),
                end_date=_text(item.get("endDate")),
                creative_id=_text(item.get("creativeId")),
                file_name=_text(item.get("fileName")),
                creative_description=_text(item.get("creativeDescription")),
                click_tag_1=_text(item.get("clickTag1")),
                third_party_survey_1=_text(item.get("thirdPartySurvey1")),
                third_party_impression_1=_text(item.get("thirdPartyImpression1")),
                third_party_impression_2=_text(item.get("thirdPartyImpression2")),
                verification_partner=_text(item.get("verificationPartner")),
                verification_status=_text(item.get("verificationStatus")),
                rotation_weight=_text(item.get("rotationWeight")),
                booked_units=_text(item.get("bookedUnits")),
                dtree_id=_text(
                    item.get("placementModernDtreeId")
                    or item.get("modernDtreeId")
                ),
                dtree_name=_text(item.get("modernDtreeName")),
                dset_id=_text(item.get("decisionSetId")),
                dset_name=_text(item.get("decisionSetName")),
                dset_link_id=_text(item.get("placementDecisionSetId")),
                level=_text(item.get("level")),
            )
        )
    return rows


def count_node_fields(payload: dict, into: dict[str, int]) -> dict[str, int]:
    """
    Counts how many decision-set nodes carry a value for each field.

    Exists to find where a node names the creative it serves, so a
    finding can say "creative V2_300x600.jpg starts 27 Sep" rather
    than "node 2".
    """
    if not isinstance(payload, dict):
        return into
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return into

    for node in nodes:
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            into.setdefault(key, 0)
            if _text(value):
                into[key] += 1
    return into


def parse_dset_response(payload: dict) -> list[InnovidCreativeNode]:
    """
    Turns a /dset/{id} response into one row per creative node.

    A node's `id` is the creative it serves; `endTimestamp: null`
    means "Ongoing", not missing data, so it stays an empty string
    rather than being invented.
    """
    if not isinstance(payload, dict):
        return []

    dtree_id = _text(payload.get("id"))
    dtree_name = _text(payload.get("name"))
    serving_method = _text(payload.get("servingMethod"))
    default_creative = ""
    default_serving = payload.get("defaultServing")
    if isinstance(default_serving, dict):
        default_creative = _text(default_serving.get("id"))

    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return []

    out: list[InnovidCreativeNode] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        out.append(
            InnovidCreativeNode(
                dtree_id=dtree_id,
                dtree_name=dtree_name,
                # A node's `id` is the node, not the creative it
                # serves -- node 1 with weight 1 is a rotation slot.
                # The creative is named separately where the response
                # says so, and the default node points at it.
                node_id=_text(node.get("id")),
                creative_id=_text(
                    node.get("creativeId")
                    or node.get("servingId")
                    or (default_creative if node.get("isDefault") else "")
                ),
                start_timestamp=_text(node.get("startTimestamp")),
                end_timestamp=_text(node.get("endTimestamp")),
                weight=_text(node.get("weight")),
                is_default=bool(node.get("isDefault")),
                serving_method=serving_method,
            )
        )
    return out


# ----------------------------------------------------------------
# Fetching -- drives a real browser for the session
# ----------------------------------------------------------------

_API_HOST = "api.flashtalking.net"


def _summary_url(campaign_id: str) -> str:
    return (
        f"{CM_BASE}/campaigns/{campaign_id}/summary"
        f"?fields={','.join(SUMMARY_FIELDS)}"
    )


def _summarise_dset_failures(
    failures: list[tuple[str, str]], attempted: int
) -> list[str]:
    """
    Collapses per-decision-set failures into one line per kind of
    failure, with a few example ids.

    Fifty lines saying the same thing hide the one line that differs,
    and the ids matter far less than the reason.
    """
    if not failures:
        return []

    by_reason: dict[str, list[str]] = {}
    for dset_id, reason in failures:
        # The id appears inside the message; strip it so the same
        # failure on different ids groups together.
        shape = reason.replace(str(dset_id), "{id}")
        by_reason.setdefault(shape, []).append(dset_id)

    messages = []
    for shape, ids in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        examples = ", ".join(ids[:3])
        more = f" (and {len(ids) - 3} more)" if len(ids) > 3 else ""
        messages.append(
            f"{len(ids)} of {attempted} decision set(s) could not be "
            f"read. Ids: {examples}{more}. Reason: {shape}"
        )
    return messages


def _dset_mismatch(dset: dict, asked_for: str, expected_name: str) -> str:
    """
    Describes how a decision set response fails to be the one asked
    for, or "" when it matches.

    Worth checking rather than assuming: Innovid holds two
    generations of decision set in overlapping id spaces, so a lookup
    can succeed and still return somebody else's creatives. Silently
    wrong flight dates are worse than no flight dates.
    """
    if not isinstance(dset, dict):
        return f"Decision set {asked_for} came back in an unexpected shape."

    got_id = _text(dset.get("id"))
    if got_id and got_id != str(asked_for).strip():
        return (
            f"Asked Innovid for decision set {asked_for} and it "
            f"returned {got_id}. Ignoring it -- the creative dates in "
            "it belong to a different decision set."
        )

    got_name = _text(dset.get("name"))
    if expected_name and got_name and got_name != expected_name:
        return (
            f"Decision set {asked_for} is called {got_name!r} in this "
            f"response but {expected_name!r} in the campaign summary. "
            "Ignoring it rather than risking the wrong creatives."
        )

    return ""


def _dset_url(dtree_id: str) -> str:
    return f"{DT_BASE}/dset/{dtree_id}"


def _venv_python_hint() -> str:
    """
    The full path of the interpreter running QA2, for pasting into a
    terminal. Saying plain "python" is what sends people to the system
    Python, which is never where QA2's packages are installed.
    """
    import sys

    return sys.executable or "python"


def _launch_browser(playwright, headless: bool):
    """
    Starts Chromium, turning the two failures people actually hit into
    instructions instead of tracebacks. Raises InnovidAuthError with
    the message to show.
    """
    try:
        return playwright.chromium.launch(headless=headless)
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            raise InnovidAuthError(
                "Playwright is installed but its browser isn't. "
                "Open a terminal in the QA2 folder and run:  "
                f"{_venv_python_hint()} -m playwright install chromium"
            ) from exc
        raise InnovidAuthError(f"Could not start the browser: {exc}") from exc


def session_is_saved(session_path: Path | None = None) -> bool:
    return (session_path or SESSION_PATH).exists()


# Query parameters whose values are safe to show: they describe what
# was asked for, not who is asking. Everything else is reduced to its
# name, because a sign-in redirect carries an authorization code in
# the query string and no denylist of scary-looking names would have
# caught it reliably.
SAFE_QUERY_PARAMS = frozenset({
    "fields", "rpp", "page", "sortBy", "sortOrder", "includeClosed",
    "quickFilter", "filterType", "level", "campaignId", "placementIds",
    "getFilterValues",
})

# Hosts that only ever handle signing in. Nothing there tells QA2
# anything about campaigns, and everything there is credential-shaped.
AUTH_HOSTS = ("uam-login.mediaocean.com", "auth0.com", "mediaocean.com")

AUTH_PATHS = (
    "/oauth2", "/oauth", "/authorize", "/uilogin", "/login?", "/signin",
    "/saml", "/sso",
)


def redact_url(url: str) -> str:
    """
    Prepares a recorded URL for someone to paste somewhere.

    Keeps the path -- which is the whole point -- and the handful of
    query parameters that describe the request. Every other value is
    replaced by its name.

    Sign-in URLs are dropped entirely rather than redacted: an OAuth
    redirect's `code` is a credential, and there is no version of that
    URL worth showing.

    Returns "" for anything that should not be recorded at all.
    """
    # Flat and in order, deliberately. An earlier version nested the
    # host check inside another condition and a sign-in URL still came
    # through on a real run; nothing about a credential filter should
    # depend on reading branching correctly.
    if not url:
        return ""
    if any(host in url.lower() for host in AUTH_HOSTS):
        return ""
    if any(marker in url.lower() for marker in AUTH_PATHS):
        return ""
    if _API_HOST not in url:
        return ""

    base, _, query = url.partition("?")
    if not query:
        return base

    kept = []
    for pair in query.split("&"):
        name, sep, value = pair.partition("=")
        if not sep:
            kept.append(name)
        elif name in SAFE_QUERY_PARAMS:
            # `fields` is never truncated: which columns Innovid asks
            # for is the entire reason for reading these URLs, and
            # cutting it at 80 characters hid the answer on the first
            # run that found it. Long id lists still get cut, since
            # the hundredth id says nothing the first three didn't.
            if name != "fields" and len(value) > 80:
                value = value[:80] + "...(truncated)"
            kept.append(f"{name}={value}")
        else:
            kept.append(f"{name}=<hidden>")

    return f"{base}?{'&'.join(kept)}"


# Body keys whose values describe what is being asked for. Anything
# else is reduced to its name, same rule as the query string.
SAFE_BODY_KEYS = frozenset({
    "page", "rpp", "sortBy", "sortOrder", "level", "levels", "parentId",
    "parentLevel", "placementId", "placementIds", "siteId", "expand",
    "expandAll", "groupBy", "type", "id", "ids", "campaignId",
    "decisionSetId", "dtreeId", "includeChildren", "fields",
})

# Only these endpoints have bodies worth reading. Keeping the list
# short matters: a body is the most likely place for something
# personal to turn up, and none of the others are being investigated.
BODY_ENDPOINTS = ("/summary", "/dset/")


def redact_body(url: str, body: str | None) -> str:
    """
    Summarises a request body as keys, with values shown only for the
    keys that describe the request.

    The summary endpoint is called several times with the same URL and
    different bodies -- expanding a placement in the grid is a body
    change, not a URL change -- so the URL alone can't explain how
    Innovid asks for a decision set. Reading the body is the only way
    to see that, and reading it this way keeps anything typed into a
    search box out of the output.
    """
    if not body or not url:
        return ""
    if not any(marker in url for marker in BODY_ENDPOINTS):
        return ""

    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return "(body is not JSON)"

    if not isinstance(parsed, dict):
        return f"(body is a {type(parsed).__name__})"

    parts = []
    for key in sorted(parsed):
        value = parsed[key]
        if key not in SAFE_BODY_KEYS:
            parts.append(f"{key}=<hidden>")
        elif isinstance(value, (dict, list)):
            # Structure is informative; contents may not be safe.
            shown = json.dumps(value)
            if len(shown) > 120:
                shown = shown[:120] + "...(truncated)"
            parts.append(f"{key}={shown}")
        else:
            parts.append(f"{key}={value}")

    return "{" + ", ".join(parts) + "}"


def record_api_calls(
    campaign_id: str,
    credentials: InnovidCredentials | None = None,
    session_path: Path | None = None,
    timeout_ms: int = 600_000,
) -> list[str]:
    """
    Opens Innovid in a normal window and writes down which API calls
    its own interface makes while a person clicks around.

    QA2 keeps hitting fields the interface clearly has and the
    documented-looking endpoints don't return -- decision set 38808 is
    visible in the UI but absent from every row of the campaign
    summary. Watching what the app itself asks for answers that in one
    sitting, and it beats asking somebody to dig through DevTools.

    Records request URLs only. Not headers, not cookies, not request
    or response bodies -- so the result can be pasted into a chat
    without carrying the session token, which is as good as a
    password.
    """
    saved_session = session_path or SESSION_PATH

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise InnovidAuthError(
            "Playwright isn't installed in the Python that's running "
            f"QA2. Install it there with:  {_venv_python_hint()} -m "
            "pip install -r requirements.txt"
        )

    seen: list[str] = []

    with sync_playwright() as p:
        browser = _launch_browser(p, headless=False)
        context = (
            browser.new_context(storage_state=str(saved_session))
            if saved_session.exists()
            else browser.new_context()
        )
        page = context.new_page()

        def _note(request):
            url = redact_url(request.url)
            if not url:
                return
            try:
                body = redact_body(url, request.post_data)
            except Exception:
                body = ""
            line = f"{url}\n      body: {body}" if body else url
            if line not in seen:
                seen.append(line)

        page.on("request", _note)

        try:
            if not saved_session.exists():
                if credentials is None:
                    raise InnovidAuthError(
                        "No saved session and no credentials. Run "
                        "with --login first."
                    )
                _login(page, credentials, 60_000)

            page.goto(
                f"{APP_ORIGIN}/campaign/{campaign_id}",
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            # The person drives from here.
            _wait_until_window_closed(page, timeout_ms)
        finally:
            try:
                context.close()
            except Exception:
                pass
            browser.close()

    return seen


def establish_session(
    session_path: Path | None = None,
    login_url: str = APP_ORIGIN,
    timeout_ms: int = 300_000,
) -> str:
    """
    Opens a normal browser window and waits for a human to sign in,
    then saves the session so later runs don't have to.

    Automating the sign-in itself turned out to be the wrong idea:
    Innovid authenticates through Mediaocean's Auth0 tenant, which
    treats repeated scripted logins as suspicious and starts refusing
    them, and it can ask for a verification code that no script can
    answer. Signing in by hand once sidesteps both, and is also how
    the person stays in control of their own credentials -- QA2 never
    has to see them.

    Returns the path the session was written to. Raises
    InnovidAuthError if the sign-in never completes.
    """
    target = session_path or SESSION_PATH

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise InnovidAuthError(
            "Playwright isn't installed in the Python that's running "
            f"QA2. Install it there with:  {_venv_python_hint()} -m "
            "pip install -r requirements.txt"
        )

    with sync_playwright() as p:
        browser = _launch_browser(p, headless=False)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(login_url, wait_until="domcontentloaded", timeout=60_000)

            if not _wait_until_signed_in(page, timeout_ms):
                raise InnovidAuthError(
                    "Timed out waiting for the sign-in. Nothing was "
                    "saved -- run it again and complete the sign-in "
                    "in the window that opens.\n"
                    f"  Left on: {page.url}"
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(target))
        finally:
            context.close()
            browser.close()

    return str(target)


def _wait_for_csrf(page, captured: dict, timeout_ms: int) -> bool:
    """
    Waits for the app to make an API call of its own, which is where
    the CSRF token comes from.

    Not fatal when it never arrives: the session cookie alone is
    sometimes enough, and a real HTTP status from the API says far
    more than a guess made here would.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if captured.get("value"):
            return True
        try:
            page.wait_for_timeout(250)
        except Exception:
            return False
    return False


def _looks_like_sign_in(page) -> bool:
    """
    True when the browser is showing a sign-in rather than the app --
    either a password box, or a URL that left the Innovid domain for
    an identity provider.
    """
    try:
        if not page.url.startswith(APP_ORIGIN):
            return True
        return _first_visible(page, PASS_SELECTORS) is not None
    except Exception:
        return False


def _wait_until_window_closed(page, timeout_ms: int) -> bool:
    """
    Blocks until the person closes the browser window, or the time
    runs out. True if they closed it.

    Closing the window is how someone says "done" without having to
    go back to a terminal they may not even have in front of them.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.is_closed():
                return True
            page.wait_for_timeout(500)
        except Exception:
            # The page or the whole browser went away mid-wait, which
            # is the same answer.
            return True
    return False


def _wait_until_signed_in(page, timeout_ms: int) -> bool:
    """
    True once the browser is sitting on Innovid itself with no
    password box in sight.

    Both halves matter: the sign-in bounces through Auth0 and back, so
    being on the Innovid domain isn't enough on its own, and an
    identity provider can show a password box on an Innovid-looking
    URL mid-flow.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            on_app = page.url.startswith(APP_ORIGIN)
            if on_app and _first_visible(page, PASS_SELECTORS) is None:
                return True
        except Exception:
            # The page is mid-navigation. Look again shortly.
            pass
        try:
            page.wait_for_timeout(1_000)
        except Exception:
            # The window was closed. Nothing more to wait for.
            return False
    return False


def fetch_campaign(
    campaign_id: str,
    credentials: InnovidCredentials | None = None,
    placement_ids: set[str] | None = None,
    headless: bool = True,
    timeout_ms: int = 60_000,
    session_path: Path | None = None,
) -> InnovidFetchResult:
    """
    Reads a campaign from Innovid's API using a browser session.

    Prefers the session saved by `establish_session` -- signing in by
    hand once and reusing it, which is both more reliable than
    scripting Auth0 and the only thing that works when the sign-in
    asks for a verification code. Falls back to filling in the login
    form with `credentials` when no session has been saved.

    `placement_ids` restricts the decision-set calls to the placements
    the Traffic Sheet actually worked, so a 200-placement campaign
    doesn't turn into 200 requests.

    Never raises for a partial failure: whatever could be fetched
    comes back, and what couldn't is described in `.errors`.
    """
    result = InnovidFetchResult(campaign_id=str(campaign_id))
    saved_session = session_path or SESSION_PATH

    if not saved_session.exists() and credentials is None:
        result.errors.append(
            "No saved Innovid session and no credentials to sign in "
            "with. Run the connection check with --login to sign in "
            "once by hand."
        )
        return result

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result.errors.append(
            "Playwright isn't installed in the Python that's running "
            f"QA2. Install it there with:  {_venv_python_hint()} -m pip "
            "install -r requirements.txt"
        )
        return result

    with sync_playwright() as p:
        try:
            browser = _launch_browser(p, headless)
        except InnovidAuthError as exc:
            result.errors.append(str(exc))
            return result

        using_saved_session = saved_session.exists()
        context = (
            browser.new_context(storage_state=str(saved_session))
            if using_saved_session
            else browser.new_context()
        )
        page = context.new_page()

        csrf_token = {"value": ""}

        def _capture_csrf(request):
            # The app sends X-Csrf-Token on its own API calls; borrow
            # it rather than trying to work out where it's stored.
            if _API_HOST in request.url:
                token = request.headers.get("x-csrf-token")
                if token:
                    csrf_token["value"] = token

        page.on("request", _capture_csrf)

        try:
            if not using_saved_session:
                _login(page, credentials, timeout_ms)

            # Visiting the campaign makes the app issue its own API
            # calls, which is what surfaces the CSRF token.
            #
            # Deliberately not waiting for the network to go quiet:
            # the campaign manager polls, and when Innovid is having
            # trouble it retries in a loop that never goes quiet at
            # all. That turned a bad day at Innovid into a 60-second
            # timeout with nothing useful said about it.
            page.goto(
                f"{APP_ORIGIN}/campaign/{campaign_id}",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )

            # A saved session expires eventually, and when it does the
            # campaign page quietly becomes a login page. Without this
            # check the run would report an empty campaign instead of
            # an expired sign-in.
            # The token rides on the app's own API calls, so it only
            # exists once the page has made one.
            _wait_for_csrf(page, csrf_token, timeout_ms=min(timeout_ms, 30_000))

            if using_saved_session and _looks_like_sign_in(page):
                raise InnovidAuthError(
                    "The saved Innovid session has expired. Run the "
                    "connection check with --login to sign in again.\n"
                    f"  Ended up on: {page.url}"
                )

            # One page at a time: a campaign with more placements
            # than fit in a page would otherwise come back silently
            # truncated, which is worse than failing outright.
            page_number = 1
            while True:
                summary = _api_get_json(
                    page,
                    _summary_url(campaign_id),
                    csrf_token["value"],
                    method="POST",
                    body={
                        "rpp": SUMMARY_PAGE_SIZE,
                        "page": page_number,
                        "searchTerm": None,
                        "sortBy": "name",
                        "sortOrder": "ASC",
                    },
                )
                if page_number == 1:
                    result.returned_fields = summary_field_names(summary)
                count_filled_fields(summary, result.field_coverage)
                count_levels(summary, result.levels)
                items = summary.get("items") if isinstance(summary, dict) else None
                result.rows_seen += len(items) if isinstance(items, list) else 0

                batch = parse_summary_response(summary)
                result.placements.extend(batch)

                total_pages = summary.get("totalPages") if isinstance(summary, dict) else None
                if not isinstance(total_pages, int) or page_number >= total_pages:
                    break
                if page_number >= MAX_SUMMARY_PAGES:
                    result.errors.append(
                        f"Stopped after {MAX_SUMMARY_PAGES} pages of "
                        f"placements ({len(result.placements)} rows). "
                        "This campaign is larger than expected -- the "
                        "results below are incomplete."
                    )
                    break
                page_number += 1

            wanted = {str(p).strip() for p in (placement_ids or set()) if str(p).strip()}
            # Innovid names this id differently depending on the
            # response: campaign 323492 returns it as decisionSetId
            # while the same decision set appears as
            # placementModernDtreeId elsewhere. Both are tried, and
            # the answer is checked against what was asked for rather
            # than trusted -- reading the wrong decision set would
            # hand QA2 another creative's flight dates, which is worse
            # than reading none.
            # Three places an id can come from, tried in the order
            # they are likely to actually be the decision set. Each is
            # its own group so that giving up on one doesn't skip the
            # next: collapsing them is what previously meant every
            # lookup used the link id and none used the real id.
            groups: list[tuple[str, dict[str, str]]] = [
                ("modern dtree id", {}),
                ("decisionSetId", {}),
                ("placementDecisionSetId", {}),
            ]
            for row in result.placements:
                if wanted and row.placement_id not in wanted:
                    continue
                if row.dtree_id:
                    groups[0][1].setdefault(row.dtree_id, row.dtree_name)
                if row.dset_id:
                    groups[1][1].setdefault(row.dset_id, row.dset_name)
                if row.dset_link_id:
                    groups[2][1].setdefault(row.dset_link_id, row.dset_name)

            # Never ask twice for the same number.
            already: set[str] = set()
            for _, ids in groups:
                for candidate in list(ids):
                    if candidate in already:
                        ids.pop(candidate)
                    else:
                        already.add(candidate)

            wanted_dsets = {k: v for _, ids in groups for k, v in ids.items()}

            # Failures are collected rather than appended one by one:
            # a campaign whose decision sets all fail the same way
            # produced fifty identical lines, which buries every other
            # problem in the run.
            failures: list[tuple[str, str]] = []
            skipped: list[str] = []

            for source, ids in groups:
                shapes_seen: set[str] = set()
                group_failures = 0

                for dset_id in sorted(ids):
                    # Give up on this source once it keeps failing the
                    # same way -- but only on this source. The next is
                    # a different number and deserves its own chance.
                    if (
                        group_failures >= GIVE_UP_AFTER_FAILED_LOOKUPS
                        and len(shapes_seen) == 1
                    ):
                        remaining = len(ids) - group_failures
                        if remaining > 0:
                            skipped.append(f"{remaining} more from {source}")
                        break

                    expected_name = ids[dset_id]
                    try:
                        dset = _api_get_json(
                            page, _dset_url(dset_id), csrf_token["value"]
                        )
                    except Exception as exc:
                        failures.append((dset_id, f"{source}: {exc}"))
                        shapes_seen.add(str(exc).replace(dset_id, "{id}"))
                        group_failures += 1
                        continue

                    problem = _dset_mismatch(dset, dset_id, expected_name)
                    if problem:
                        failures.append((dset_id, f"{source}: {problem}"))
                        shapes_seen.add(problem.replace(dset_id, "{id}"))
                        group_failures += 1
                        continue

                    count_node_fields(dset, result.node_fields)
                    result.creative_nodes.extend(parse_dset_response(dset))

            for message in _summarise_dset_failures(failures, len(wanted_dsets)):
                result.errors.append(message)

            if skipped:
                result.errors.append(
                    "Stopped early on sources that kept failing "
                    f"identically: {', '.join(skipped)}."
                )

        except InnovidAuthError as exc:
            result.errors.append(str(exc))
        except Exception as exc:
            result.errors.append(f"Innovid fetch failed: {exc}")
        finally:
            context.close()
            browser.close()

    return result


USER_SELECTORS = (
    "input[type='email']",
    "input[name='username']",
    "input[name='email']",
    "input[name='loginfmt']",   # Microsoft sign-in
    "input#username",
    "input#email",
    "input[autocomplete='username']",
)

PASS_SELECTORS = (
    "input[type='password']",
    "input[name='password']",
    "input[name='passwd']",     # Microsoft sign-in
    "input#password",
    "input[autocomplete='current-password']",
)

# "Next" on a two-step sign-in, where the password only appears after
# the address is submitted.
# Matched in order, and deliberately narrow: a login screen also
# carries "Cancel" and "Forgot password", and clicking one of those
# instead would look like a failed sign-in.
NEXT_SELECTORS = (
    "input[type='submit']",
    "button[type='submit']",
    "#idSIButton9",             # Microsoft's Next/Sign in button
    "button:has-text('Sign in')",
    "button:has-text('Log in')",
    "button:has-text('Login')",
    "button:has-text('Next')",
    "button:has-text('Continue')",
    "button:has-text('Iniciar')",
    "button:has-text('Continuar')",
)


def _login(page, credentials: InnovidCredentials, timeout_ms: int) -> None:
    """
    Drives the sign-in, handling both shapes we can hit: one page with
    both boxes, and the two-step flow (address, Next, then password)
    that corporate SSO uses.

    Fails loudly when neither shape appears -- a silent non-login would
    otherwise look like an empty campaign.
    """
    page.goto(credentials.login_url, wait_until="domcontentloaded", timeout=timeout_ms)

    # The sign-in form is rendered by JavaScript, so the elements
    # aren't there when the document finishes loading. Wait for a box
    # to actually exist before looking for it.
    step_timeout = min(timeout_ms, 30_000)
    try:
        _wait_for_any(page, USER_SELECTORS + PASS_SELECTORS, step_timeout)
    except Exception:
        # Nothing to type into. Fall through: the check below turns
        # this into a description of the page we actually landed on,
        # which is far more use than a timeout stack trace.
        pass

    user_box = _first_visible(page, USER_SELECTORS)
    pass_box = _first_visible(page, PASS_SELECTORS)

    if user_box is None and pass_box is None:
        raise InnovidAuthError(
            "Couldn't find anywhere to type the username or password.\n"
            f"  Ended up on: {page.url}\n"
            f"  Page title:  {_safe_title(page)}\n"
            f"  Fields found: {_describe_inputs(page)}\n"
            "Send those three lines over -- they say which sign-in "
            "page this is, which is all that's needed to teach QA2 "
            "how to fill it in."
        )

    if user_box is not None:
        user_box.fill(credentials.username)

    # Two-step sign-in: submit the address, then wait for the password
    # box that appears on the next screen.
    if pass_box is None:
        _submit_step(page, user_box)
        try:
            _wait_for_any(page, PASS_SELECTORS, step_timeout)
        except Exception:
            raise InnovidAuthError(
                "The username was accepted but no password box "
                "appeared.\n"
                f"  Ended up on: {page.url}\n"
                f"  Page title:  {_safe_title(page)}\n"
                f"  Fields found: {_describe_inputs(page)}\n"
                "If that page is asking for a verification code, this "
                "sign-in needs multi-factor auth and QA2 has to keep "
                "a saved session instead of logging in each time."
            )
        pass_box = _first_visible(page, PASS_SELECTORS)
        if pass_box is None:
            raise InnovidAuthError(
                f"A password box exists on {page.url} but isn't "
                "visible. Run with --show to see what's covering it."
            )

    pass_box.fill(credentials.password)
    _submit_step(page, pass_box)

    try:
        page.wait_for_url(re.compile(r"campaign", re.I), timeout=timeout_ms)
    except Exception:
        # Landing somewhere other than a campaign page isn't proof of
        # failure (Innovid may open a dashboard, or SSO may ask to
        # stay signed in), so only a still-visible password box is
        # treated as a real failure.
        if _first_visible(page, PASS_SELECTORS) is not None:
            raise InnovidAuthError(
                "Login didn't go through -- the password field is "
                "still on screen. Check the credentials in "
                "config/innovid_credentials.env (the password rotates "
                "every few months).\n"
                f"  Ended up on: {page.url}"
            )


def _submit_step(page, box, timeout_ms: int = 20_000) -> None:
    """
    Moves one step forward in the sign-in.

    Enter submits most forms, but not all, so a button is the
    fallback. Both the order and the patience matter here:

    - Clicking unconditionally after Enter lands the click on the
      *next* screen's button, which on a two-step sign-in submits the
      password screen before the password is typed.
    - Giving up on Enter too early is just as bad. Corporate SSO takes
      seconds to answer, so a short wait concludes Enter did nothing
      and clicks the button -- a second submit, which the identity
      provider rejects and bounces back to the login page. That looks
      exactly like a wrong password.

    So: wait for the navigation Enter starts, generously, and only
    reach for the button once nothing has happened at all.
    """
    before_url = page.url

    try:
        with page.expect_navigation(
            timeout=timeout_ms, wait_until="domcontentloaded"
        ):
            box.press("Enter")
        return
    except Exception:
        # Either Enter did nothing, or the form advances without a
        # navigation (a single-page sign-in swapping the screen).
        pass

    if _moved_on(page, box, before_url):
        return

    button = _first_visible(page, NEXT_SELECTORS)
    if button is not None:
        try:
            button.click(timeout=5_000)
        except Exception:
            # The page moved between the check and the click. Not a
            # problem -- that was the goal.
            pass


def _moved_on(page, box, before_url: str, timeout_ms: int = 4_000) -> bool:
    """
    True once the sign-in has advanced without a navigation: the box
    that was just filled left the page, as happens on single-page
    forms that swap the screen in place.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.url != before_url:
                return True
            if box.count() == 0 or not box.is_visible(timeout=500):
                return True
        except Exception:
            # The element went away mid-check, which is itself the
            # page having moved on.
            return True
        page.wait_for_timeout(200)
    return False


def _wait_for_any(page, selectors, timeout_ms: int):
    """Waits until any one of `selectors` is attached to the page."""
    page.wait_for_selector(", ".join(selectors), timeout=timeout_ms, state="attached")


def _safe_title(page) -> str:
    try:
        return page.title() or "(no title)"
    except Exception:
        return "(unavailable)"


def _describe_inputs(page) -> str:
    """
    Lists the input boxes on the page by their identifying attributes.

    Deliberately never reads `value`: this text is meant to be pasted
    into a chat or an email to work out which sign-in page we landed
    on, so it must not be able to carry anything typed into the form.
    """
    script = """
        () => Array.from(document.querySelectorAll('input, button'))
            .filter(el => el.type !== 'hidden')
            .slice(0, 25)
            .map(el => {
                const bits = [el.tagName.toLowerCase()];
                for (const attr of ['type', 'name', 'id', 'placeholder',
                                    'aria-label', 'autocomplete']) {
                    const v = el.getAttribute(attr);
                    if (v) bits.push(attr + '=' + v);
                }
                return bits.join(' ');
            })
    """
    try:
        found = page.evaluate(script)
    except Exception as exc:
        return f"(couldn't read the page: {exc})"

    if not found:
        return "(none -- the page may still be loading or is a redirect)"
    return "\n    - " + "\n    - ".join(found)


def _first_visible(page, selectors):
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.is_visible(timeout=2_000):
                return locator
        except Exception:
            continue
    return None


def _api_get_json(page, url: str, csrf_token: str, method: str = "GET", body=None):
    """
    Runs the API call inside the logged-in page, so the session cookie
    rides along automatically and we only have to add the CSRF header.
    """
    script = """
        async ([url, method, body, csrf]) => {
            const headers = {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            };
            if (csrf) headers['X-Csrf-Token'] = csrf;
            const options = { method, headers, credentials: 'include' };
            if (body !== null) {
                headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(body);
            }
            const response = await fetch(url, options);
            const text = await response.text();
            return { status: response.status, text };
        }
    """
    outcome = page.evaluate(script, [url, method, body, csrf_token])

    status = outcome.get("status")
    text = outcome.get("text") or ""

    if isinstance(status, int) and 500 <= status < 600:
        # Worth separating out: nothing about QA2 or the sign-in can
        # fix this one, and Innovid does have bad days.
        raise RuntimeError(
            f"Innovid returned a server error (HTTP {status}). That is "
            "a problem on their side, not with the sign-in or with "
            "QA2 -- if their own campaign manager is also showing "
            "errors, the thing to do is wait and try later."
        )

    if status != 200:
        raise RuntimeError(f"{url} returned HTTP {status}")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} did not return JSON ({exc})") from exc

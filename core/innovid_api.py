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

# Everything QA2 can use today, plus the two IDs that stitch the
# placement level to the creative level. Asked for explicitly so the
# result never depends on which column view the user has configured
# in Innovid.
SUMMARY_FIELDS = (
    "placementId",
    "placementName",
    "siteName",
    "dimensions",
    "status",
    "startDate",
    "endDate",
    "creativeId",
    "fileName",
    "creativeDescription",
    "clickTag1",
    "thirdPartySurvey1",
    "thirdPartyImpression1",
    "thirdPartyImpression2",
    "verificationPartner",
    "verificationStatus",
    "rotationWeight",
    "bookedUnits",
    "placementModernDtreeId",
    "modernDtreeName",
)

# Innovid caps a page of results; 500 is what its own interface asks
# for. MAX_SUMMARY_PAGES is a stop so a bad response can't spin
# forever.
SUMMARY_PAGE_SIZE = 500
MAX_SUMMARY_PAGES = 40

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
    dtree_id: str = ""
    dtree_name: str = ""


@dataclass
class InnovidCreativeNode:
    """
    One creative inside a decision set, with the two things the
    exports never carry: its own flight dates and its rotation weight.
    """

    dtree_id: str = ""
    dtree_name: str = ""
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

    def nodes_for_placement(self, placement_id: str) -> list[InnovidCreativeNode]:
        dtree_ids = {
            p.dtree_id
            for p in self.placements
            if p.placement_id == str(placement_id).strip() and p.dtree_id
        }
        return [n for n in self.creative_nodes if n.dtree_id in dtree_ids]


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
            )
        )
    return rows


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
                creative_id=_text(node.get("id")),
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


def fetch_campaign(
    campaign_id: str,
    credentials: InnovidCredentials,
    placement_ids: set[str] | None = None,
    headless: bool = True,
    timeout_ms: int = 60_000,
) -> InnovidFetchResult:
    """
    Logs into Innovid in a real browser, then calls the API with that
    session. `placement_ids` restricts the decision-set calls to the
    placements the Traffic Sheet actually worked, so a 200-placement
    campaign doesn't turn into 200 requests.

    Never raises for a partial failure: whatever could be fetched
    comes back, and what couldn't is described in `.errors`.
    """
    result = InnovidFetchResult(campaign_id=str(campaign_id))

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
            browser = p.chromium.launch(headless=headless)
        except Exception as exc:
            if "Executable doesn't exist" in str(exc):
                result.errors.append(
                    "Playwright is installed but its browser isn't. "
                    "Open a terminal in the QA2 folder and run:  "
                    f"{_venv_python_hint()} -m playwright install chromium"
                )
            else:
                result.errors.append(f"Could not start the browser: {exc}")
            return result

        context = browser.new_context()
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
            _login(page, credentials, timeout_ms)

            # Visiting the campaign makes the app issue its own API
            # calls, which is what surfaces the CSRF token.
            page.goto(
                f"{APP_ORIGIN}/campaign/{campaign_id}",
                wait_until="networkidle",
                timeout=timeout_ms,
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
            dtree_ids = sorted(
                {
                    row.dtree_id
                    for row in result.placements
                    if row.dtree_id
                    and (not wanted or row.placement_id in wanted)
                }
            )

            for dtree_id in dtree_ids:
                try:
                    dset = _api_get_json(
                        page, _dset_url(dtree_id), csrf_token["value"]
                    )
                    result.creative_nodes.extend(parse_dset_response(dset))
                except Exception as exc:
                    result.errors.append(
                        f"Decision set {dtree_id} could not be read: {exc}"
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

    if status != 200:
        raise RuntimeError(f"{url} returned HTTP {status}")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{url} did not return JSON ({exc})") from exc

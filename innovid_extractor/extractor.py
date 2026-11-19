"""
Innovid Extractor -- the Innovid walk-through on its own.

Signs in to Innovid once (by hand, in a real browser window), then for
each Campaign ID reads:

  * the campaign summary: one row per placement and per creative, with
    status, flight, Verification Partner, pixels and click URL;
  * every decision set the placements use: each creative's own flight,
    rotation weight and whether it is the default;
  * each site's Media Filters (Remove VPAID).

and writes one Excel per campaign, with a Summary sheet that says how
long each step took and what could not be read.

It reads no Traffic Sheet, no export and runs no QA rule. It imports
nothing from QA2: this folder can be copied anywhere and still works.

Run it with the launcher next to it ("Innovid Extractor.bat") or:

    python extractor.py 330328 305807
    python extractor.py --login        # sign in again
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent

# The saved sign-in. Holds session cookies, which are as good as the
# password until they expire: never share this file, never commit it.
SESSION_PATH = HERE / "session" / "innovid_session.json"
OUTPUT_DIR = HERE / "output"

APP_ORIGIN = "https://campaign-manager.flashtalking.net"
API_HOST = "api.flashtalking.net"
CM_BASE = f"https://{API_HOST}/cm/v1/ui"
DT_BASE = f"https://{API_HOST}/dt/v1/ui"
TAG_BASE = f"https://{API_HOST}/tag/v1/ui"
CM_V1 = f"https://{API_HOST}/cm/v1"

SUMMARY_FIELDS = (
    "status", "siteName", "placementId", "placementName", "placementType",
    "dimensions", "clickTag1", "startDate", "endDate", "creativeDescription",
    "creativeId", "fileName", "thirdPartySurvey1", "thirdPartyImpression1",
    "thirdPartyImpression2", "verificationPartner", "verificationStatus",
    "bookedUnits", "id", "name", "level", "rotationWeight",
    "placementModernDtreeId", "modernDtreeId", "modernDtreeName",
    "placementDecisionSetId", "decisionSetId", "decisionSetName",
)
SUMMARY_PAGE_SIZE = 500
MAX_SUMMARY_PAGES = 40
GIVE_UP_AFTER_FAILED_LOOKUPS = 3
MAX_SITES = 40

PASSWORD_BOXES = ("input[type=password]", "input[name=password]")


class SessionProblem(RuntimeError):
    """The sign-in is missing, expired or refused: signing in again fixes it."""


# ------------------------------------------------------------------ data

@dataclass
class Row:
    """One row of the campaign summary (placement or creative level)."""
    level: str = ""
    placement_id: str = ""
    placement_name: str = ""
    site: str = ""
    dimensions: str = ""
    status: str = ""
    start: str = ""
    end: str = ""
    creative_id: str = ""
    file_name: str = ""
    click_url: str = ""
    survey_pixel: str = ""
    impression_pixel_1: str = ""
    impression_pixel_2: str = ""
    verification_partner: str = ""
    verification_status: str = ""
    rotation_weight: str = ""
    dtree_id: str = ""
    dtree_name: str = ""
    dset_id: str = ""
    dset_name: str = ""
    dset_link_id: str = ""

    @property
    def is_creative(self) -> bool:
        return self.level.strip().upper() == "PLACEMENT-CREATIVE"

    @property
    def is_decision_set(self) -> bool:
        """
        Innovid lists a placement's decision set as one more line under
        it, at creative level but with no creative id. Seen on a real
        campaign: the line named "Display 160x600" is the decision set.
        """
        return not self.creative_id and bool(self.dtree_id or self.dset_id or self.dset_link_id)


@dataclass
class Node:
    """One creative inside a decision set."""
    dset_id: str = ""
    dset_name: str = ""
    serving_method: str = ""
    creative_id: str = ""
    creative_name: str = ""
    start: str = ""
    end: str = ""
    weight: str = ""
    is_default: bool = False


@dataclass
class Extraction:
    campaign_id: str
    rows: list[Row] = field(default_factory=list)
    nodes: list[Node] = field(default_factory=list)
    media_filters: list[tuple[str, str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timings: list[tuple[str, float]] = field(default_factory=list)
    dsets_asked: int = 0
    dsets_read: int = 0
    summary_pages: int = 0

    @property
    def placements(self) -> list[Row]:
        return [r for r in self.rows if not r.is_creative]

    @property
    def creatives(self) -> list[Row]:
        return [r for r in self.rows if r.is_creative and not r.is_decision_set]

    @property
    def decision_set_rows(self) -> list[Row]:
        return [r for r in self.rows if r.is_creative and r.is_decision_set]


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("name") or value.get("value") or ""
    return str(value).strip()


def parse_summary(payload) -> list[Row]:
    items = payload.get("items") if isinstance(payload, dict) else None
    rows = []
    for item in items if isinstance(items, list) else []:
        # Totals and site rows carry no placement id.
        if not isinstance(item, dict) or not _text(item.get("placementId")):
            continue
        g = lambda key: _text(item.get(key))  # noqa: E731
        rows.append(Row(
            level=g("level"), placement_id=g("placementId"),
            placement_name=g("placementName"), site=g("siteName"),
            dimensions=g("dimensions"), status=g("status"),
            start=g("startDate"), end=g("endDate"),
            creative_id=g("creativeId"), file_name=g("fileName"),
            click_url=g("clickTag1"), survey_pixel=g("thirdPartySurvey1"),
            impression_pixel_1=g("thirdPartyImpression1"),
            impression_pixel_2=g("thirdPartyImpression2"),
            verification_partner=g("verificationPartner"),
            verification_status=g("verificationStatus"),
            rotation_weight=g("rotationWeight"),
            dtree_id=g("placementModernDtreeId") or g("modernDtreeId"),
            dtree_name=g("modernDtreeName"),
            dset_id=g("decisionSetId"), dset_name=g("decisionSetName"),
            dset_link_id=g("placementDecisionSetId"),
        ))
    return rows


def parse_dset(payload, asked_for: str) -> list[Node]:
    if not isinstance(payload, dict) or not isinstance(payload.get("nodes"), list):
        return []
    default = payload.get("defaultServing") if isinstance(payload.get("defaultServing"), dict) else {}
    out = []
    for node in payload["nodes"]:
        if not isinstance(node, dict):
            continue
        serving = node.get("serving")
        is_default = bool(node.get("isDefault"))
        if isinstance(serving, dict):
            cid, cname = _text(serving.get("id")), _text(serving.get("name") or serving.get("fileName"))
        else:
            cid, cname = _text(serving), ""
        if is_default and not cid:
            cid, cname = _text(default.get("id")), _text(default.get("name"))
        out.append(Node(
            dset_id=asked_for, dset_name=_text(payload.get("name")),
            serving_method=_text(payload.get("servingMethod")),
            creative_id=cid, creative_name=cname,
            start=_text(node.get("startTimestamp")), end=_text(node.get("endTimestamp")),
            weight=_text(node.get("weight")), is_default=is_default,
        ))
    return out


def dset_mismatch(payload, asked_for: str, expected_name: str) -> str:
    """Innovid's two generations of decision set share id ranges: check the answer."""
    if not isinstance(payload, dict):
        return "came back in an unexpected shape"
    got = _text(payload.get("id"))
    if got and got != asked_for:
        return f"asked for {asked_for}, Innovid returned {got}; ignored"
    name = _text(payload.get("name"))
    if expected_name and name and name != expected_name:
        return f"named {name!r} here but {expected_name!r} in the summary; ignored"
    return ""


def media_filter_of(detail) -> str:
    group = ((((detail or {}).get("videoConfig") or {}).get("optionGroups") or {})
             .get("ctvOttGroup") or {})
    value = group.get("mediaFilter")
    return "Default" if value in (None, "") else str(value)


# ------------------------------------------------------------------ the walk

Call = Callable[[str, str, object], object]   # (url, method, body) -> parsed JSON


def extract(campaign_id: str, call: Call, say: Callable[[str], None] = print) -> Extraction:
    """
    Reads one campaign through `call`, which performs an API request
    inside the signed-in browser. Never raises for a partial failure:
    what could be read comes back, what couldn't goes to `.errors`.
    A SessionProblem is raised, because only signing in again fixes it.
    """
    ex = Extraction(campaign_id=str(campaign_id))

    # 1. Placement level: the summary, page by page.
    t0 = time.monotonic()
    page = 1
    while True:
        payload = call(f"{CM_BASE}/campaigns/{campaign_id}/summary?fields={','.join(SUMMARY_FIELDS)}",
                       "POST", {"rpp": SUMMARY_PAGE_SIZE, "page": page, "searchTerm": None,
                                "sortBy": "name", "sortOrder": "ASC"})
        ex.rows.extend(parse_summary(payload))
        ex.summary_pages = page
        total = payload.get("totalPages") if isinstance(payload, dict) else None
        if not isinstance(total, int) or page >= total:
            break
        if page >= MAX_SUMMARY_PAGES:
            ex.errors.append(f"Stopped after {MAX_SUMMARY_PAGES} summary pages: the placement list is incomplete.")
            break
        page += 1
    say(f"   placements read: {len({r.placement_id for r in ex.rows})} "
        f"({len(ex.creatives)} creative rows, {ex.summary_pages} page(s))")
    ex.timings.append(("Campaign summary (placements)", time.monotonic() - t0))

    # 2. Creative level: every decision set, each id asked once.
    t0 = time.monotonic()
    groups: list[tuple[str, dict[str, str]]] = [("modern decision tree", {}), ("decisionSetId", {}),
                                                 ("placementDecisionSetId", {})]
    for r in ex.rows:
        if r.dtree_id:
            groups[0][1].setdefault(r.dtree_id, r.dtree_name)
        if r.dset_id:
            groups[1][1].setdefault(r.dset_id, r.dset_name)
        elif r.dset_link_id and not r.dtree_id:
            # The id of the placement-to-decision-set link, not of a
            # decision set: only worth a try when nothing else exists.
            groups[2][1].setdefault(r.dset_link_id, r.dset_name)
    seen: set[str] = set()
    for _, ids in groups:
        for k in list(ids):
            if k in seen:
                ids.pop(k)
            seen.add(k)
    ex.dsets_asked = sum(len(ids) for _, ids in groups)

    done = 0
    for source, ids in groups:
        failures, shapes = 0, set()
        for dset_id in sorted(ids):
            if failures >= GIVE_UP_AFTER_FAILED_LOOKUPS and len(shapes) == 1:
                ex.errors.append(f"Stopped asking for {len(ids) - failures} more {source} id(s): "
                                 f"the first {failures} failed the same way.")
                break
            done += 1
            if done % 5 == 0 or done == ex.dsets_asked:
                say(f"   decision sets {done}/{ex.dsets_asked}")
            try:
                payload = call(f"{DT_BASE}/dset/{dset_id}", "GET", None)
                problem = dset_mismatch(payload, dset_id, ids[dset_id])
            except SessionProblem:
                raise
            except Exception as exc:  # noqa: BLE001 - reported, not hidden
                problem = str(exc)
            if problem:
                failures += 1
                shapes.add(problem.replace(dset_id, "{id}"))
                ex.errors.append(f"Decision set {dset_id} ({source}): {problem}")
                continue
            ex.nodes.extend(parse_dset(payload, dset_id))
            ex.dsets_read += 1
    say(f"   decision sets read: {ex.dsets_read} of {ex.dsets_asked} ({len(ex.nodes)} creatives inside)")
    ex.timings.append(("Decision sets (creatives)", time.monotonic() - t0))

    # 3. Media Filters of each site (Remove VPAID).
    t0 = time.monotonic()
    try:
        sites = call(f"{CM_V1}/campaigns/{campaign_id}/campaign-sites?rpp=543", "GET", None)
        items = sites.get("items", sites) if isinstance(sites, dict) else sites
        for item in (items if isinstance(items, list) else [])[:MAX_SITES]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            site = item.get("site") if isinstance(item.get("site"), dict) else {}
            detail = call(f"{TAG_BASE}/campaign-sites/{item['id']}", "GET", None)
            ex.media_filters.append((_text(site.get("id") or item.get("siteId")),
                                     _text(site.get("name")), media_filter_of(detail)))
    except SessionProblem:
        raise
    except Exception as exc:  # noqa: BLE001
        ex.errors.append(f"Couldn't read the sites' Media Filters: {exc}")
    say(f"   sites read for Media Filters: {len(ex.media_filters)}")
    ex.timings.append(("Media Filters (sites)", time.monotonic() - t0))
    return ex


# ------------------------------------------------------------------ Excel

NAVY, LIME, INK = "000050", "B0F467", "1F2340"


def _nodes_for(row: Row, by_dset: dict[str, list[Node]]) -> list[Node]:
    """The decision-set nodes that serve this creative row."""
    found = []
    for key in (row.dtree_id, row.dset_id, row.dset_link_id):
        for node in by_dset.get(key, []):
            same_id = row.creative_id and node.creative_id == row.creative_id
            same_name = row.file_name and node.creative_name.casefold() == row.file_name.casefold()
            if (same_id or same_name) and node not in found:
                found.append(node)
    return found


def write_workbook(ex: Extraction, path: Path, extra_timings=()) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    head_font, head_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor=NAVY)

    def sheet(title, headers, rows, first=False):
        ws = wb.active if first else wb.create_sheet()
        ws.title = title
        ws.append(headers)
        for cell in ws[1]:
            cell.font, cell.fill = head_font, head_fill
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for r in rows:
            ws.append(list(r))
        ws.freeze_panes = "A2"
        if rows:
            ws.auto_filter.ref = ws.dimensions
        for i, h in enumerate(headers, 1):
            width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows[:300]])
            ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
        return ws

    # Summary
    total = sum(s for _, s in list(extra_timings) + ex.timings)
    summary = [("Campaign ID", ex.campaign_id),
               ("Extracted", datetime.now().strftime("%Y-%m-%d %H:%M")),
               ("Placements", len({r.placement_id for r in ex.rows})),
               ("Creative rows", len(ex.creatives)),
               ("Placements with a decision set", len({r.placement_id for r in ex.decision_set_rows}
                                                       | {r.placement_id for r in ex.placements
                                                          if r.dtree_id or r.dset_id or r.dset_link_id})),
               ("Decision sets read", f"{ex.dsets_read} of {ex.dsets_asked}"),
               ("Creatives inside decision sets", len(ex.nodes)),
               ("Sites (Media Filters)", len(ex.media_filters)),
               ("", "")]
    summary += [(f"Time · {name}", f"{secs:.1f} s") for name, secs in list(extra_timings) + ex.timings]
    summary += [("Time · total", f"{total:.1f} s"), ("", "")]
    summary += [("Could not read", e) for e in ex.errors] or [("Could not read", "Nothing: everything was read.")]
    ws = sheet("Summary", ["Item", "Value"], summary, first=True)
    ws.column_dimensions["B"].width = 90
    for row in ws.iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")

    # The decision set of a placement: on its own row, or on the line
    # Innovid adds under it for the decision set.
    ds_of: dict[str, Row] = {}
    for r in ex.placements + ex.decision_set_rows:
        if (r.dtree_id or r.dset_id or r.dset_link_id) and r.placement_id not in ds_of:
            ds_of[r.placement_id] = r

    def ds_name(pid):
        d = ds_of.get(pid)
        return (d.dtree_name or d.dset_name or d.file_name) if d else ""

    def ds_id(pid):
        d = ds_of.get(pid)
        return (d.dtree_id or d.dset_id or d.dset_link_id) if d else ""

    sheet("Placements",
          ["Placement ID", "Placement", "Site", "Size", "Status", "Start", "End",
           "Verification Partner", "Verification Status", "Decision set", "Decision set ID"],
          [(r.placement_id, r.placement_name, r.site, r.dimensions, r.status, r.start, r.end,
            r.verification_partner, r.verification_status, ds_name(r.placement_id), ds_id(r.placement_id))
           for r in ex.placements])

    by_dset: dict[str, list[Node]] = {}
    for n in ex.nodes:
        by_dset.setdefault(n.dset_id, []).append(n)
    dset_of = {r.placement_id: r for r in ex.placements}
    creative_rows = []
    for r in ex.creatives:
        parent = dset_of.get(r.placement_id)
        probe = Row(**{**r.__dict__})
        holder = ds_of.get(r.placement_id)
        if holder and not (probe.dtree_id or probe.dset_id):
            probe.dtree_id, probe.dset_id, probe.dset_link_id = holder.dtree_id, holder.dset_id, holder.dset_link_id
        nodes = _nodes_for(probe, by_dset)
        # The default node's timestamp is when it was set as default,
        # not a flight: it would read as a third date range.
        flights = [n for n in nodes if not n.is_default]
        join = lambda attr: " | ".join(getattr(n, attr) or ("Ongoing" if attr == "end" else "") for n in flights)  # noqa: E731
        creative_rows.append((
            r.placement_id, r.placement_name or (parent.placement_name if parent else ""),
            r.creative_id, r.file_name, r.status, r.click_url,
            r.impression_pixel_1, r.impression_pixel_2, r.survey_pixel,
            join("start"), join("end"), join("weight"),
            "Yes" if any(n.is_default for n in nodes) else ("" if nodes else "Not found in its decision set")))
    sheet("Creatives",
          ["Placement ID", "Placement", "Creative ID", "File name", "Status", "Click URL",
           "Impression pixel 1", "Impression pixel 2", "Survey pixel",
           "DS start", "DS end", "DS weight", "Default"], creative_rows)

    sheet("Decision sets",
          ["Decision set ID", "Decision set", "Serving method", "Creative ID", "Creative",
           "Start", "End", "Weight", "Default"],
          [(n.dset_id, n.dset_name, n.serving_method, n.creative_id, n.creative_name,
            n.start, n.end or "Ongoing", n.weight, "Yes" if n.is_default else "")
           for n in ex.nodes])

    sheet("Media Filters", ["Site ID", "Site", "Media Filters (Remove VPAID)"], ex.media_filters)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


# ------------------------------------------------------------------ browser

def session_state() -> str:
    """'missing', 'expired' or 'ok' -- read from the file, no network."""
    try:
        data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "missing"
    stamps = [float(c["expires"]) for c in data.get("cookies", [])
              if "flashtalking" in str(c.get("domain", ""))
              and isinstance(c.get("expires"), (int, float)) and c["expires"] > 0]
    if stamps and datetime.fromtimestamp(min(stamps), tz=timezone.utc) <= datetime.now(timezone.utc):
        return "expired"
    return "ok"


def _launch(p, headless: bool):
    try:
        return p.chromium.launch(headless=headless)
    except Exception as exc:  # noqa: BLE001
        if "Executable doesn't exist" in str(exc):
            raise SystemExit("Playwright's browser is missing. Run:  "
                             f"{sys.executable} -m playwright install chromium") from exc
        raise


def _password_visible(page) -> bool:
    for sel in PASSWORD_BOXES:
        try:
            if page.locator(sel).first.is_visible():
                return True
        except Exception:  # noqa: BLE001
            pass
    return False


def sign_in(timeout_s: int = 300) -> None:
    """Opens a real window; the person signs in; the session is saved."""
    from playwright.sync_api import sync_playwright

    print("\nA browser window is opening. Sign in to Innovid and open any campaign.")
    print("The extractor never sees your password. The window closes by itself.\n")
    with sync_playwright() as p:
        browser = _launch(p, headless=False)
        context = browser.new_context()
        page = context.new_page()
        api_ok = {"seen": False}
        page.on("response", lambda r: api_ok.update(seen=True)
                if API_HOST in r.url and "/v1/" in r.url and r.status < 400 else None)
        try:
            page.goto(APP_ORIGIN, wait_until="domcontentloaded", timeout=60_000)
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                try:
                    if page.url.startswith(APP_ORIGIN) and not _password_visible(page) and api_ok["seen"]:
                        break
                    page.wait_for_timeout(1_000)
                except Exception:  # noqa: BLE001 - window closed
                    break
            if not api_ok["seen"]:
                raise SessionProblem("The sign-in didn't finish (or Innovid's API never answered). "
                                     "Nothing was saved: try again and let a campaign load.")
            SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(SESSION_PATH))
        finally:
            context.close()
            browser.close()
    print("Signed in. The session is saved on this computer only.\n")


_FETCH_JS = """
async ([url, method, body, csrf]) => {
    const headers = {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'};
    if (csrf) headers['X-Csrf-Token'] = csrf;
    const options = {method, headers, credentials: 'include'};
    if (body !== null) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(body); }
    const r = await fetch(url, options);
    return {status: r.status, text: await r.text()};
}
"""
_CSRF_JS = """
() => { for (const k of ['csrf', 'csrfToken', 'XSRF-TOKEN', 'X-Csrf-Token']) {
          const v = sessionStorage.getItem(k); if (v) return v; } return ''; }
"""


class Browser:
    """One headless browser for the whole run, reusing the saved session."""

    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = _launch(self._pw, headless=True)
        self._context = self._browser.new_context(storage_state=str(SESSION_PATH))
        self.page = self._context.new_page()
        self.csrf = {"value": ""}
        self.page.on("request", self._capture)

    def _capture(self, request):
        if API_HOST in request.url and request.headers.get("x-csrf-token"):
            self.csrf["value"] = request.headers["x-csrf-token"]

    def _page_csrf(self) -> str:
        try:
            return str(self.page.evaluate(_CSRF_JS) or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    def open_campaign(self, campaign_id: str) -> None:
        self.csrf["value"] = ""
        self.page.goto(f"{APP_ORIGIN}/{campaign_id}/summary/", wait_until="domcontentloaded", timeout=60_000)
        if not self.page.url.startswith(APP_ORIGIN) or _password_visible(self.page):
            raise SessionProblem("The saved Innovid session has expired.")
        deadline = time.monotonic() + 30
        while not self.csrf["value"] and time.monotonic() < deadline:
            self.page.wait_for_timeout(250)
        self.csrf["value"] = self.csrf["value"] or self._page_csrf()

    def call(self, url: str, method: str = "GET", body=None, _retried: bool = False):
        token = self._page_csrf() or self.csrf["value"]
        out = self.page.evaluate(_FETCH_JS, [url, method, body, token])
        status = out.get("status")
        if status == 401:
            raise SessionProblem("Innovid didn't recognise the session (HTTP 401).")
        if status == 403 and not _retried:
            self.page.reload(wait_until="domcontentloaded", timeout=30_000)
            self.page.wait_for_timeout(2_000)
            return self.call(url, method, body, _retried=True)
        if status == 403:
            raise RuntimeError("HTTP 403: the account may not have access to this campaign")
        if isinstance(status, int) and status >= 500:
            raise RuntimeError(f"Innovid server error (HTTP {status}); try again later")
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        return json.loads(out.get("text") or "null")

    def close(self):
        for closer in (self._context.close, self._browser.close, self._pw.stop):
            try:
                closer()
            except Exception:  # noqa: BLE001
                pass


# ------------------------------------------------------------------ console

def output_path(campaign_id: str, when: datetime | None = None) -> Path:
    """Innovid_<campaign>_Summary_DecisionSets_Extraction_<YYYY-MM-DD>.xlsx, never overwriting."""
    day = (when or datetime.now()).strftime("%Y-%m-%d")
    base = f"Innovid_{campaign_id}_Summary_DecisionSets_Extraction_{day}"
    path, n = OUTPUT_DIR / f"{base}.xlsx", 1
    while path.exists():
        path, n = OUTPUT_DIR / f"{base} ({n}).xlsx", n + 1
    return path


def campaign_ids(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\d{3,}", text or "")))


def _open_folder(path: Path) -> None:
    if os.name == "nt":
        try:
            os.startfile(str(path))  # noqa: S606 - the person's own output folder
        except OSError:
            pass


def run(ids: list[str]) -> list[Path]:
    written = []
    extra = []
    if session_state() != "ok":
        print("No valid Innovid session on this computer yet." if session_state() == "missing"
              else "The saved Innovid session has expired.")
        t0 = time.monotonic()
        sign_in()
        extra.append(("Sign-in (only when the session is missing or expired)", time.monotonic() - t0))

    t0 = time.monotonic()
    browser = Browser()
    extra.append(("Open Innovid in the background", time.monotonic() - t0))
    try:
        for cid in ids:
            print(f"\nCampaign {cid}")
            t0 = time.monotonic()
            for attempt in (1, 2):
                try:
                    browser.open_campaign(cid)
                    opened = [("Open the campaign", time.monotonic() - t0)]
                    ex = extract(cid, browser.call)
                    break
                except SessionProblem as exc:
                    if attempt == 2:
                        raise
                    print(f"   {exc} Signing in again...")
                    browser.close()
                    sign_in()
                    browser = Browser()
                    t0 = time.monotonic()
            path = write_workbook(ex, output_path(cid), extra + opened)
            extra = []  # the one-off steps count once, on the first campaign
            total = sum(s for _, s in opened + ex.timings)
            print(f"   done in {total:.0f} s -> {path.name}"
                  + (f"  ({len(ex.errors)} thing(s) could not be read; see Summary)" if ex.errors else ""))
            written.append(path)
    finally:
        browser.close()
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Reads Innovid campaigns into Excel.")
    parser.add_argument("ids", nargs="*", help="Campaign ID(s)")
    parser.add_argument("--login", action="store_true", help="sign in to Innovid again")
    args = parser.parse_args(argv)

    print("=" * 60 + "\n  Innovid Extractor\n" + "=" * 60)
    try:
        import openpyxl  # noqa: F401
        import playwright  # noqa: F401
    except ImportError as exc:
        print(f"Missing library: {exc.name}. Run the launcher again, or:\n"
              f"  {sys.executable} -m pip install -r {HERE / 'requirements.txt'}")
        return 1

    if args.login:
        sign_in()
    ids = campaign_ids(" ".join(args.ids))
    while True:
        if not ids:
            ids = campaign_ids(input("\nCampaign ID(s), separated by spaces (Enter to exit): "))
            if not ids:
                return 0
        try:
            written = run(ids)
        except SessionProblem as exc:
            print(f"\n{exc}\nRun the launcher again to sign in.")
            return 1
        if written:
            print(f"\nSaved in: {OUTPUT_DIR}")
            _open_folder(OUTPUT_DIR)
        ids = []


if __name__ == "__main__":
    sys.exit(main())

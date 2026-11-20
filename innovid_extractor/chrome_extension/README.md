# Innovid Extractor (Chrome extension) — developer guide

The extension reads an Innovid campaign and saves it as an Excel file. QA2
web uses that Excel as its "Innovid Excel". It replaces downloading Innovid's
exports by hand.

It only **reads**. It uses the Innovid session that is already open in the
browser tab. It never sees a password, stores nothing, and sends nothing
anywhere except Innovid's own API.

> **Python or JavaScript?** Chrome extensions run JavaScript, so the
> extension is written in JavaScript. It is the same walk as `../extractor.py`
> (the Python version), and its tests are in Python
> (`tests/test_chrome_extension.py`). If you can read Python you can read this
> code: every file starts with a short explanation, every function has a
> comment that says what it does, and `walk.js` opens with a Python ↔
> JavaScript cheat sheet.

Version: see `"version"` in `manifest.json` (0.5.4 at the time of writing).
The map of files and functions is `../docs/extension_code_map.drawio`
(open it in draw.io; a picture of it is `../docs/extension_code_map.png`).

---

## 1. The files

| File | What it is | Open it when you want to… |
|---|---|---|
| `manifest.json` | The extension's ID card for Chrome: name, version, permissions, which files to load. | Bump the version, or change permissions. |
| `popup.html` | The small window that opens from the icon: the texts and the boxes. | Change a text the person reads. |
| `popup.css` | The look of the window (WPP colours, fonts). | Change colours or spacing. |
| `popup.js` | The window's logic: checks it's the Innovid tab, reads the inputs, starts the run, shows the progress. | Change how the window behaves. |
| `background.js` | The worker: opens the campaign in the tab, makes the API calls inside it, builds and saves the Excel. Keeps running if the popup closes. | Change how calls are made, how the file is named or saved. |
| `walk.js` | The brain: which API calls, in which order, and how the answers become Excel sheets. No Chrome code, so the tests can run it. | Change what is read or what goes in the Excel. **Most changes happen here.** |
| `lib/xlsx.mini.min.js` | SheetJS, the library that writes `.xlsx` files. Third-party, don't edit. | Never. |
| `icons/`, `fonts/` | The icon and the WPP fonts. | Change the icon. |

There is **no build step**: what is in this folder is exactly what Chrome
loads. Edit a file, then reload the extension (section 5).

---

## 2. How it works, start to finish

```
Person clicks the icon on the Innovid tab
        │
popup.js ── findInnovidTab(): is this tab Innovid?  ── no ─▶ "Open this from the Innovid tab"
        │ yes
        │  person types Campaign ID(s), picks All / Placements / Decision sets, clicks Extract
        ▼
popup.js ── chrome.runtime.sendMessage({type: "start", ids, tabId, opts})
        ▼
background.js ── run(ids, tabId, opts)            (one campaign after another)
        │   openCampaign()  → the tab goes to /<campaign>/summary/ and gets its security token
        │   innovidUser()   → the name Innovid shows at the top right ("Welcome, …")
        │   makeCall()      → call(): only allowed reads, made inside the tab (pageFetch)
        ▼
walk.js ── extract(campaignId, call, say, opts)
        │   1. summary API, 500 rows a page (up to 40 pages)  → parseSummary()
        │   2. applyFilters()  → only the placements / decision sets asked for
        │   3. /dset API for each decision set, 4 at a time   → parseDset()
        │   4. sites API → Media Filters (Remove VPAID)       → mediaFilterOf()
        ▼
walk.js ── sheets(ex)  → Summary, Placement, Placement-Creative, Decision sets,
        │                Media Filters, Innovid fields
        ▼
background.js ── workbookBase64() (SheetJS) → chrome.downloads → Downloads folder
        │   progress written to chrome.storage.session at every step
        ▼
popup.js ── render(): one line per campaign, clock, "Show in folder"
```

---

## 3. The most important functions

| Function | File | In plain words |
|---|---|---|
| `run(ids, tabId, opts)` | background.js | The main loop. For each campaign: open it, read it, build the Excel, save it, update the progress. |
| `openCampaign(tabId, id)` | background.js | Moves the Innovid tab to the campaign and waits for the page and its token. Stops with a clear message if Innovid asks to sign in. |
| `makeCall(tabId)` | background.js | Builds the `call()` used for every API request. Refuses anything not on the allowed list, and turns HTTP errors into readable messages. |
| `pageFetch(url, method, body)` | background.js | Runs inside the Innovid tab, so the request carries the tab's session, like the Innovid site's own requests. |
| `workbookBase64(ex, extra)` | background.js | Turns the sheets into an `.xlsx` with SheetJS. |
| `extract(id, call, say, opts)` | walk.js | Reads one campaign: summary pages, decision sets, sites. Partial failures go to the Summary sheet; it only stops for a session problem. `opts.by` is the Innovid user, for "Extracted by". |
| `innovidUser(tabId)` | background.js | Reads the user Innovid shows at the top right of the tab ("Welcome, Camilo Mantilla" → "Camilo Mantilla") for "Extracted by". Read from the page only, no API call. |
| `localStamp(date)` | walk.js | The "Extracted" time in the Summary: the person's own local time with its zone, e.g. `2026-11-20 10:30 (UTC-05:00 · America/Bogota)`. |
| `applyFilters(ex, opts)` | walk.js | The "What to read" filter. Placements by ID; decision sets by the name the Traffic Sheet gives them (or by Innovid ID). |
| `parseSummary(payload)` | walk.js | One summary page → simple rows (placement, creative line, decision set line). |
| `parseDset(payload, id)` | walk.js | One decision set → its creatives with dates (with the hour), weight and default. |
| `sheets(ex)` | walk.js | Everything read → the Excel sheets, with the same column names as Innovid's exports. |
| `exportColumns(rows, columns)` | walk.js | Fills each export column from the Innovid field of the same (or aliased) name. |
| `isAllowedCall(method, url)` | walk.js | The safety list: only 4 read calls may leave the browser. |
| `render(run)` | popup.js | Draws the progress card from what background.js wrote. |

---

## 4. Where to change things (recipes)

**A text in the window** → `popup.html` (titles, labels, footer) or
`PLACEHOLDER` / `HINT` in `popup.js` (the examples and help under the list box).

**A new column in the Placement or Placement-Creative sheet** → add the export
column name to `PL_COLUMNS` or `PC_COLUMNS` in `walk.js`. If Innovid's field has
a different name, add it to `FIELD_ALIASES`. If Innovid doesn't send it at all, it
stays empty and the Summary sheet lists it under "Not in Innovid's data".

**A new field from the summary API** → add it to `SUMMARY_FIELDS` in `walk.js`.

**Rows per page, page limit, parallel calls** → the settings at the top of
`walk.js`: `SUMMARY_PAGE_SIZE`, `MAX_SUMMARY_PAGES`, `PARALLEL`.

**A new API call** → write it in `extract()` **and** add its address to
`ALLOWED` in `walk.js`. Without that, `makeCall()` refuses it. Only add reads.

**The Excel's file name** → `fileName()` in `background.js`.

**Who and when in the Summary sheet** → the "Extracted" and "Extracted by" rows in
`sheets()` (`walk.js`). The time comes from `localStamp()`; the name comes from
`innovidUser()` (`background.js`), which uses `pageUserText()` and `userFromHeader()`
in `walk.js`. If Innovid changes its header, the CSS selector to fix is in `pageUserText()`.

**A new sheet** → add `["Sheet name", rows]` to the list `sheets()` returns at its end.

After any change: bump `"version"` in `manifest.json`, run the tests, reload
the extension.

---

## 5. Run it and try a change

1. Chrome → `chrome://extensions` → turn on **Developer mode** (top right).
2. **Load unpacked** → choose this folder (`chrome_extension`, the one with `manifest.json`).
3. Open a campaign in Innovid, click the extension's icon, click **Extract**.
4. After editing a file, click the circular arrow on the extension's card to reload it.
   A change to `popup.*` shows the next time the popup opens.
5. To see errors: on the card, **Inspect views: service worker** opens the
   console of `background.js`. Right-click inside the popup → **Inspect** opens
   the popup's console.

The step-by-step guide with screenshots for the team is the "Instalar Innovid
Extractor en Chrome" doc; the zip given to the team is this folder zipped.

---

## 6. Tests

From the repository root:

```
python -m pytest -q tests/test_chrome_extension.py
```

They check the permissions in `manifest.json`, that the popup loads nothing
from the internet, that only the allowed calls can go out, and they run
`walk.js` under Node against sample Innovid answers (Node must be
installed; without it those tests are skipped).

---

## 7. Rules to keep

- **Read only.** Every call goes through `isAllowedCall()`. Never add a call that changes anything in Innovid.
- **No passwords, no stored data.** The session is the tab's own; only the progress is kept, in session storage, which Chrome clears when it closes. The name for "Extracted by" is read from Innovid's page on each run, never stored.
- **No costs.** `WITHHELD` keeps cost and rate columns empty: the QA doesn't need them.
- **Minimal permissions.** `activeTab` gives access to the Innovid tab only after the icon is clicked there. Innovid's site permission is asked for only when moving through several campaigns. Adding permissions makes Chrome show scarier warnings to the team.
- **Partial failures don't stop the run.** They are written in the Summary sheet as "Could not read".

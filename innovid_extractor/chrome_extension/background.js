/*
 * background.js -- the "worker" of the extension.
 *
 * WHAT IT DOES
 *   Runs the extraction when the popup asks for it, and keeps running even if
 *   the popup closes. For each campaign id it:
 *     1. opens the campaign in the Innovid tab        (openCampaign)
 *     2. reads it with Walk.extract()                 (walk.js)
 *     3. builds the Excel with Walk.sheets() + SheetJS (workbookBase64)
 *     4. saves it to Downloads                        (chrome.downloads)
 *   and writes its progress to chrome.storage.session, which the popup shows.
 *
 * HOW IT TALKS TO INNOVID
 *   Every API call is made from inside the Innovid tab (world MAIN), so it
 *   carries that tab's own session and security token -- exactly what the
 *   campaign manager does itself. The extension never sees or stores a
 *   password. Nothing is stored but the progress shown in the popup (and the
 *   name for "Extracted by", which popup.js keeps); the Excel goes to Downloads.
 *
 * START READING AT run(), near the end of the file.
 */

// Loads SheetJS (writes .xlsx files) and walk.js (exposes `Walk`) into this worker.
importScripts("lib/xlsx.mini.min.js", "walk.js");

// The key under which the current run's progress is kept in chrome.storage.session.
// popup.js reads the same key. Session storage is wiped when Chrome closes.
const RUN = "run";

// Progress updates run one after another: they read and rewrite the
// same record, and two at once would lose one of them.
let queue = Promise.resolve();
// update(fn): fn gets the current progress record and returns the new one.
function update(fn) {
  queue = queue.then(async () => {
    const cur = (await chrome.storage.session.get(RUN))[RUN] || {};
    await chrome.storage.session.set({[RUN]: fn(cur)});
  }).catch(() => {});
  return queue;
}

// setRun({...}): change some fields of the progress record (running, finished, problem, downloads...).
const setRun = (patch) => update((cur) => Object.assign({}, cur, patch));

// setLine(campaignId, icon, text): change the progress line of one campaign in the popup.
// icon is one of "wait", "run", "ok", "warn", "err" (see ICON in popup.js).
function setLine(id, icon, text, extra) {
  return update((cur) => Object.assign({}, cur, {
    lines: (cur.lines || []).map((l) => (l.id === id ? Object.assign({}, l, {icon, text}, extra || {}) : l))
  }));
}

/*
 * pageFetch(url, method, body) -> {status, text}
 * Runs INSIDE the Innovid tab (injected by inTab below), so the request goes
 * out with the tab's own cookies and the page's security token (CSRF), the way
 * the Innovid site makes its own requests. It must be self-contained: it can't
 * use anything else from this file, because only its code is copied into the tab.
 */
function pageFetch(url, method, body) {
  const keys = ["csrf", "csrfToken", "XSRF-TOKEN", "X-Csrf-Token"];
  let csrf = "";
  for (const k of keys) { const v = sessionStorage.getItem(k); if (v) { csrf = v; break; } }
  const headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"};
  if (csrf) headers["X-Csrf-Token"] = csrf;
  const options = {method, headers, credentials: "include"};
  if (body !== null && body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  return fetch(url, options)
    .then((r) => r.text().then((text) => ({status: r.status, text})))
    .catch((e) => ({status: 0, text: String(e)}));
}

// Runs inside the Innovid tab: true once the page has stored its security token.
function pageHasToken() {
  return ["csrf", "csrfToken", "XSRF-TOKEN", "X-Csrf-Token"].some((k) => !!sessionStorage.getItem(k));
}

// inTab(tabId, func, args): runs `func(...args)` inside the Innovid tab and returns its result.
async function inTab(tabId, func, args) {
  const [res] = await chrome.scripting.executeScript({target: {tabId}, world: "MAIN", func, args: args || []});
  return res ? res.result : undefined;
}

// Polls rather than listening: a fast page can finish loading before a
// listener is attached, and then the wait would run out its full time.
async function waitForLoad(tabId, timeoutMs) {
  const end = Date.now() + timeoutMs;
  await sleep(250);
  while (Date.now() < end) {
    const tab = await chrome.tabs.get(tabId);
    if (tab.status === "complete" && !tab.pendingUrl) return;
    await sleep(250);
  }
}

// Waits ms milliseconds: await sleep(500).
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/*
 * openCampaign(tabId, campaignId)
 * Makes the Innovid tab show /<campaignId>/summary/ (if it isn't there
 * already), waits for it to load and for its security token. If Innovid sent
 * the tab to the sign-in page instead, raises SessionProblem.
 */
async function openCampaign(tabId, campaignId) {
  const tab = await chrome.tabs.get(tabId);
  if (Walk.campaignFromUrl(tab.url) !== campaignId) {
    await chrome.tabs.update(tabId, {url: `${Walk.APP_ORIGIN}/${campaignId}/summary/`});
    await waitForLoad(tabId, 60000);
  }
  const now = await chrome.tabs.get(tabId);
  if (now.url && now.url.indexOf(Walk.APP_ORIGIN) !== 0) {
    throw new Walk.SessionProblem("Innovid asked to sign in. Sign in in that tab, then press Extract again.");
  }
  // The page writes its security token as it loads.
  for (let i = 0; i < 60 && !(await inTab(tabId, pageHasToken)); i++) await sleep(500);
}

/*
 * makeCall(tabId) -> call(url, method, body)
 * Builds the `call` function walk.js uses for every API request:
 *   - refuses any request not in the ALLOWED list of walk.js (read-only by design);
 *   - runs it inside the Innovid tab with pageFetch;
 *   - turns HTTP errors into clear messages. 401 = sign in again (SessionProblem);
 *     403 = reload the tab once and try again.
 */
function makeCall(tabId) {
  return async function call(url, method, body, retried) {
    // Read-only by construction: nothing outside the list leaves the browser.
    if (!Walk.isAllowedCall(method, url)) throw new Error(`Refused: ${method} ${url} is not a read this extension makes`);
    const out = await inTab(tabId, pageFetch, [url, method, body === undefined ? null : body]);
    const status = out && out.status;
    if (status === 401) throw new Walk.SessionProblem("Innovid didn't recognise the session. Sign in in that tab and try again.");
    if (status === 403 && !retried) {
      await chrome.tabs.reload(tabId);
      await waitForLoad(tabId, 30000);
      await sleep(1500);
      return call(url, method, body, true);
    }
    if (status === 403) throw new Error("HTTP 403: the account may not have access to this campaign");
    if (status >= 500) throw new Error(`Innovid server error (HTTP ${status}); try again later`);
    if (status === 0) throw new Error(`Network error: ${out.text}`);
    if (status !== 200) throw new Error(`HTTP ${status}`);
    return JSON.parse(out.text || "null");
  };
}

/*
 * workbookBase64(ex, extra) -> the .xlsx file as base64 text
 * Turns Walk.sheets() into an Excel workbook with SheetJS: column widths from
 * the content (max 60 characters) and a filter on every sheet but Summary.
 */
function workbookBase64(ex, extra) {
  const wb = XLSX.utils.book_new();
  for (const [name, rows] of Walk.sheets(ex, extra)) {
    const ws = XLSX.utils.aoa_to_sheet(rows);
    const widths = rows[0].map((_, i) =>
      Math.min(60, Math.max(10, ...rows.slice(0, 300).map((r) => String(r[i] == null ? "" : r[i]).length + 2))));
    ws["!cols"] = widths.map((wch) => ({wch: name === "Summary" && wch > 30 ? 90 : wch}));
    if (rows.length > 1 && name !== "Summary") ws["!autofilter"] = {ref: ws["!ref"]};
    XLSX.utils.book_append_sheet(wb, ws, name);
  }
  return XLSX.write(wb, {type: "base64", bookType: "xlsx"});
}

// Innovid_<campaign>_Summary_DecisionSets_Extraction_<YYYY-MM-DD>.xlsx
function fileName(campaignId) {
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  const day = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  return `Innovid_${campaignId}_Summary_DecisionSets_Extraction_${day}.xlsx`;
}

/*
 * run(ids, tabId, opts) -- THE MAIN FUNCTION
 * Extracts each campaign in `ids`, one after another, in the Innovid tab
 * `tabId`, with the popup's filter `opts`. One Excel per campaign goes to
 * Downloads. If a campaign fails with a session problem, the run stops and
 * the popup shows the reason; any other partial failure is written in that
 * campaign's Summary sheet instead.
 */
async function run(ids, tabId, opts) {
  await setRun({running: true, finished: false, problem: "", downloads: [], startedAt: Date.now(), endedAt: 0,
    lines: ids.map((id) => ({id, icon: "wait", text: "Waiting"}))});
  const call = makeCall(tabId);
  const downloads = [];
  try {
    for (const id of ids) {
      const started = Date.now();
      await setLine(id, "run", "Opening the campaign…", {startedAt: started});
      const t0 = performance.now();
      await openCampaign(tabId, id);
      const opened = [["Open the campaign", (performance.now() - t0) / 1000]];
      const ex = await Walk.extract(id, call, (msg) => setLine(id, "run", msg), opts || {});
      const b64 = workbookBase64(ex, opened);
      const downloadId = await chrome.downloads.download({
        url: "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + b64,
        filename: fileName(id), conflictAction: "uniquify", saveAs: false
      });
      downloads.push(downloadId);
      const placements = ex.scope ? ex.scope.length : new Set(ex.rows.map((r) => r.placementId)).size;
      const summary = `${placements} placements · ${ex.dsetsRead} decision sets`;
      await setLine(id, ex.errors.length ? "warn" : "ok",
        ex.errors.length ? `${summary} · ${ex.errors.length} not read (see Summary)` : summary,
        {secs: (Date.now() - started) / 1000});
      await setRun({downloads});
    }
  } catch (e) {
    await setRun({problem: (e && e.message) || String(e)});
    const cur = (await chrome.storage.session.get(RUN))[RUN] || {};
    for (const l of cur.lines || []) if (l.icon === "run") await setLine(l.id, "err", "Stopped");
  } finally {
    await setRun({running: false, finished: true, endedAt: Date.now()});
  }
}

// The popup sends {type: "start", ids, tabId, opts} when the person clicks Extract.
chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg && msg.type === "start") {
    run(msg.ids, msg.tabId, msg.opts);
    reply({ok: true});
  }
  return false;
});

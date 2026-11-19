/*
 * Runs the extraction so it survives the popup closing.
 *
 * Every API call is made from inside the Innovid tab (world MAIN), so it
 * carries that tab's own session and security token -- exactly what the
 * campaign manager does itself. Nothing is stored but the progress shown
 * in the popup; the Excel goes to Downloads.
 */
importScripts("lib/xlsx.mini.min.js", "walk.js");

const RUN = "run";

async function setRun(patch) {
  const cur = (await chrome.storage.session.get(RUN))[RUN] || {};
  await chrome.storage.session.set({[RUN]: Object.assign({}, cur, patch)});
}

async function setLine(id, icon, text) {
  const cur = (await chrome.storage.session.get(RUN))[RUN] || {};
  const lines = (cur.lines || []).map((l) => (l.id === id ? {id, icon, text} : l));
  await chrome.storage.session.set({[RUN]: Object.assign({}, cur, {lines})});
}

// Injected into the Innovid tab. Must be self-contained.
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

function pageHasToken() {
  return ["csrf", "csrfToken", "XSRF-TOKEN", "X-Csrf-Token"].some((k) => !!sessionStorage.getItem(k));
}

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

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

async function run(ids, tabId) {
  await setRun({running: true, finished: false, problem: "", downloads: [],
    lines: ids.map((id) => ({id, icon: "wait", text: "Waiting"}))});
  const call = makeCall(tabId);
  const downloads = [];
  try {
    for (const id of ids) {
      await setLine(id, "run", "Opening the campaign…");
      const t0 = performance.now();
      await openCampaign(tabId, id);
      const opened = [["Open the campaign", (performance.now() - t0) / 1000]];
      const ex = await Walk.extract(id, call, (msg) => setLine(id, "run", msg));
      const b64 = workbookBase64(ex, opened);
      const downloadId = await chrome.downloads.download({
        url: "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + b64,
        filename: fileName(id), conflictAction: "uniquify", saveAs: false
      });
      downloads.push(downloadId);
      const secs = opened.concat(ex.timings).reduce((a, t) => a + t[1], 0);
      const placements = new Set(ex.rows.map((r) => r.placementId)).size;
      const summary = `${placements} placements · ${ex.dsetsRead} decision sets · ${secs.toFixed(0)} s`;
      await setLine(id, ex.errors.length ? "warn" : "ok",
        ex.errors.length ? `${summary} · ${ex.errors.length} not read (see Summary)` : summary);
      await setRun({downloads});
    }
  } catch (e) {
    await setRun({problem: (e && e.message) || String(e)});
    const cur = (await chrome.storage.session.get(RUN))[RUN] || {};
    for (const l of cur.lines || []) if (l.icon === "run") await setLine(l.id, "err", "Stopped");
  } finally {
    await setRun({running: false, finished: true});
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg && msg.type === "start") {
    run(msg.ids, msg.tabId);
    reply({ok: true});
  }
  return false;
});

/*
 * popup.js -- the small window that opens when the extension's icon is clicked.
 *
 * WHAT IT DOES
 *   - Checks that it was opened from an Innovid tab (findInnovidTab, showTab).
 *   - Reads the campaign id(s) and the "What to read" choice.
 *   - On Extract, sends {type: "start", ...} to background.js, which does the work.
 *   - Shows the progress that background.js writes to chrome.storage.session (render).
 *
 * The popup only shows state; the work runs in background.js, so closing the
 * popup doesn't stop an extraction. Texts the person reads are in popup.html
 * and in PLACEHOLDER / HINT below.
 */
// $("go") is the element with id="go" in popup.html.
const $ = (id) => document.getElementById(id);
// The symbol shown next to each campaign in the progress list.
const ICON = {ok: "✓", warn: "!", run: "⟳", wait: "○", err: "✕"};
let innovidTab = null;   // the Innovid tab the popup was opened from (null if it isn't Innovid)
let lastRun = null;      // the last progress record shown

// 75 -> "1:15"
function clock(secs) {
  secs = Math.max(0, Math.round(secs));
  return `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
}

// Only the tab the popup was opened from: with activeTab, Chrome lets the
// extension into that tab alone, and only after this click.
async function findInnovidTab() {
  const [active] = await chrome.tabs.query({active: true, currentWindow: true});
  return active && active.url && active.url.indexOf(Walk.APP_ORIGIN) === 0 ? active : null;
}

// Fills the first card: "Innovid open · campaign 311907", or the warning to open this from Innovid.
function showTab() {
  const card = $("tabCard");
  const campaign = innovidTab ? Walk.campaignFromUrl(innovidTab.url) : "";
  if (!innovidTab) {
    card.classList.add("warn");
    $("tabTitle").textContent = "Open this from the Innovid tab";
    $("tabHint").textContent = "Go to the campaign in Innovid (signed in as usual) and click this icon there.";
  } else {
    card.classList.remove("warn");
    $("tabTitle").textContent = campaign ? `Innovid open · campaign ${campaign}` : "Innovid open";
    $("tabHint").textContent = "Uses the session of that tab. Nothing to sign in here.";
    if (!$("ids").value && campaign) $("ids").value = campaign;
  }
}

/*
 * render(run): draws the progress card from the progress record that
 * background.js keeps: one line per campaign, the clock, any problem,
 * and the "Show in folder" button when finished.
 */
function render(run) {
  run = run || {};
  lastRun = run;
  const running = !!run.running;
  $("go").disabled = running || !innovidTab;
  $("goText").textContent = running ? "Extracting…" : "Extract";
  $("goChip").textContent = running ? "⟳" : "→";
  const lines = run.lines || [];
  $("progressCard").hidden = !lines.length;
  $("lines").innerHTML = "";
  for (const l of lines) {
    const li = document.createElement("li");
    li.className = l.icon;
    li.innerHTML = `<span class="i-${l.icon}"></span><span class="id"></span><span></span>`;
    li.children[0].textContent = ICON[l.icon] || "";
    li.children[1].textContent = l.id;
    li.children[2].textContent = l.text;
    const secs = l.secs !== undefined ? l.secs : (l.icon === "run" && l.startedAt ? (Date.now() - l.startedAt) / 1000 : null);
    if (secs !== null) {
      const t = document.createElement("span");
      t.className = "t";
      t.textContent = "· " + clock(secs);
      li.children[2].appendChild(t);
    }
    $("lines").appendChild(li);
  }
  const end = run.running ? Date.now() : run.endedAt;
  $("clock").textContent = run.startedAt && end ? (run.running ? "⏱ " : "Total ") + clock((end - run.startedAt) / 1000) : "";
  $("problem").hidden = !run.problem;
  $("problem").textContent = run.problem || "";
  $("doneActions").hidden = !(run.finished && (run.downloads || []).length);
}

// Extract button: read the inputs and ask background.js to start.
$("go").addEventListener("click", () => {
  const ids = Walk.campaignIds($("ids").value);
  if (!ids.length || !innovidTab) return;
  const here = Walk.campaignFromUrl(innovidTab.url);
  const kind = scopeKind();
  const opts = {placements: kind === "placements" ? $("scopeList").value : "",
                dsets: kind === "dsets" ? $("scopeList").value : ""};
  const start = () => chrome.runtime.sendMessage({type: "start", ids, tabId: innovidTab.id, opts});
  if (ids.length === 1 && ids[0] === here) { start(); return; }
  // Moving the tab to other campaigns needs Innovid's site permission,
  // asked for here and only now (it must be asked in the click itself).
  chrome.permissions.request({origins: [Walk.APP_ORIGIN + "/*"]}).then((ok) => {
    if (ok) start();
    else showProblem("Without that permission, extract one campaign at a time from its own tab.");
  });
});

// Shows a message in red in the progress card.
function showProblem(text) {
  $("progressCard").hidden = false;
  $("problem").hidden = false;
  $("problem").textContent = text;
}

// "Show in folder": opens Downloads on the last Excel saved.
$("openFolder").addEventListener("click", async () => {
  const run = (await chrome.storage.session.get("run")).run || {};
  const last = (run.downloads || []).slice(-1)[0];
  if (last !== undefined) chrome.downloads.show(last);
  else chrome.downloads.showDefaultFolder();
});

// Redraw every time background.js updates the progress.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes.run) render(changes.run.newValue);
});

// One choice: the whole campaign, only these placements, or only these
// decision sets -- never a mix, which read as confusing.
// Literal on purpose (feedback from the development team): what goes in the box and how.
const PLACEHOLDER = {
  placements: "11299523\n11299525\n11299527",
  dsets: "S&P D&B 728x90\nS&P Bombora 728x90\nS&P Captify 728x90"
};
const HINT = {
  placements: "Placement IDs only, one per line. Copy the Placement ID column from the Traffic Sheet and paste it here as is.",
  dsets: "Decision set names, one per line. Copy the Decision Set column from the Traffic Sheet and paste it here as is."
};
// "all", "placements" or "dsets": the "What to read" choice.
function scopeKind() {
  return document.querySelector('input[name="scope"]:checked').value;
}
// Show or hide the list box when the "What to read" choice changes.
document.querySelectorAll('input[name="scope"]').forEach((r) => r.addEventListener("change", () => {
  const kind = scopeKind();
  $("scopeList").hidden = kind === "all";
  $("scopeList").placeholder = PLACEHOLDER[kind] || "";
  $("scopeHint").hidden = kind === "all";
  $("scopeHint").textContent = HINT[kind] || "";
  if (kind !== "all") $("scopeList").focus();
}));

// The clock ticks while a run is going.
setInterval(() => { if (lastRun && lastRun.running) render(lastRun); }, 1000);

// "Camilo Mantilla": the user Innovid shows at the top right of the tab, read
// from the page (Walk.pageUserText). It goes in the Excel as "Extracted by".
async function readInnovidUser() {
  try {
    const [res] = await chrome.scripting.executeScript({target: {tabId: innovidTab.id}, world: "MAIN", func: Walk.pageUserText});
    return Walk.userFromHeader(res && res.result);
  } catch (e) { return ""; }
}

// When the popup opens: find the Innovid tab and its user, then show any run in progress.
(async () => {
  innovidTab = await findInnovidTab();
  showTab();
  if (innovidTab) {
    const who = await readInnovidUser();
    if (who) $("tabHint").textContent = `Signed in as ${who}. That name goes in the Excel as \u201cExtracted by\u201d.`;
  }
  render((await chrome.storage.session.get("run")).run);
})();

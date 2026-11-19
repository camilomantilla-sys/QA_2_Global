/* The popup only shows state; the work runs in background.js. */
const $ = (id) => document.getElementById(id);
const ICON = {ok: "✓", warn: "!", run: "⟳", wait: "○", err: "✕"};
let innovidTab = null;
let lastRun = null;

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

function showProblem(text) {
  $("progressCard").hidden = false;
  $("problem").hidden = false;
  $("problem").textContent = text;
}

$("openFolder").addEventListener("click", async () => {
  const run = (await chrome.storage.session.get("run")).run || {};
  const last = (run.downloads || []).slice(-1)[0];
  if (last !== undefined) chrome.downloads.show(last);
  else chrome.downloads.showDefaultFolder();
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes.run) render(changes.run.newValue);
});

// One choice: the whole campaign, only these placements, or only these
// decision sets -- never a mix, which read as confusing.
const PLACEHOLDER = {
  placements: "Placement IDs or P codes, one per line (paste the TS column as is)",
  dsets: "Decision set IDs or names, one per line"
};
function scopeKind() {
  return document.querySelector('input[name="scope"]:checked').value;
}
document.querySelectorAll('input[name="scope"]').forEach((r) => r.addEventListener("change", () => {
  const kind = scopeKind();
  $("scopeList").hidden = kind === "all";
  $("scopeList").placeholder = PLACEHOLDER[kind] || "";
  if (kind !== "all") $("scopeList").focus();
}));

// The clock ticks while a run is going.
setInterval(() => { if (lastRun && lastRun.running) render(lastRun); }, 1000);

(async () => {
  innovidTab = await findInnovidTab();
  showTab();
  render((await chrome.storage.session.get("run")).run);
})();

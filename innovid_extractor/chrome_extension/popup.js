/* The popup only shows state; the work runs in background.js. */
const $ = (id) => document.getElementById(id);
const ICON = {ok: "✓", warn: "!", run: "⟳", wait: "○", err: "✕"};
let innovidTab = null;

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
    $("lines").appendChild(li);
  }
  $("problem").hidden = !run.problem;
  $("problem").textContent = run.problem || "";
  $("doneActions").hidden = !(run.finished && (run.downloads || []).length);
}

$("go").addEventListener("click", () => {
  const ids = Walk.campaignIds($("ids").value);
  if (!ids.length || !innovidTab) return;
  const here = Walk.campaignFromUrl(innovidTab.url);
  const start = () => chrome.runtime.sendMessage({type: "start", ids, tabId: innovidTab.id});
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

(async () => {
  innovidTab = await findInnovidTab();
  showTab();
  render((await chrome.storage.session.get("run")).run);
})();

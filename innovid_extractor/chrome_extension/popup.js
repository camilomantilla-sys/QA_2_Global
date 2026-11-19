/* The popup only shows state; the work runs in background.js. */
const $ = (id) => document.getElementById(id);
const ICON = {ok: "✓", warn: "!", run: "⟳", wait: "○", err: "✕"};
let innovidTab = null;

async function findInnovidTab() {
  const [active] = await chrome.tabs.query({active: true, currentWindow: true});
  if (active && active.url && active.url.indexOf(Walk.APP_ORIGIN) === 0) return active;
  const tabs = await chrome.tabs.query({url: Walk.APP_ORIGIN + "/*"});
  return tabs.find((t) => Walk.campaignFromUrl(t.url)) || tabs[0] || null;
}

function showTab() {
  const card = $("tabCard");
  const campaign = innovidTab ? Walk.campaignFromUrl(innovidTab.url) : "";
  if (!innovidTab) {
    card.classList.add("warn");
    $("tabTitle").textContent = "Open Innovid in a tab";
    $("tabHint").textContent = "Sign in to the campaign manager as usual and open a campaign. Then come back here.";
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

$("go").addEventListener("click", async () => {
  const ids = Walk.campaignIds($("ids").value);
  if (!ids.length || !innovidTab) return;
  await chrome.runtime.sendMessage({type: "start", ids, tabId: innovidTab.id});
});

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

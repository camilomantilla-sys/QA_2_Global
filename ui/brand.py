"""
The WPP Media look for the Streamlit app.

AdOps asked (18-nov) for QA2 to look like the team's other tools -- the
SBA Hub and the RQ Rotation app, both Apps Script: a white top bar with
the logo, a dark navy hero with the title in lime, white cards with the
lime / teal / cornflower stripe, small uppercase labels, navy buttons.

Everything here is HTML and CSS that Streamlit draws as-is. What
Streamlit draws itself (uploaders, selects, the data grids) only takes
colours and corners: those are set in .streamlit/config.toml and in the
overrides at the end of BRAND_CSS. Those overrides hook onto Streamlit's
data-testid attributes, which are stable across versions; class names
are not, so none are used.
"""
from __future__ import annotations

import html

NAVY = "#000050"
CORNFLOWER = "#5465FF"
PERIWINKLE = "#788BFF"
TEAL = "#00DBEE"
PANTONE_629 = "#93DFE3"
LIME = "#B0F467"

STRIPE = (f"linear-gradient(90deg, {LIME} 0 28%, {TEAL} 28% 56%, "
          f"{CORNFLOWER} 56% 100%)")


BRAND_CSS = f"""
<style>
:root {{
    --navy: {NAVY}; --accent: {CORNFLOWER}; --peri: {PERIWINKLE};
    --teal: {TEAL}; --mint: {PANTONE_629}; --lime: {LIME};
    --paper: #F7F9F2; --line: #ECEEF6; --muted: #7B7E9E; --muted-2: #8A8DAD;
    --shadow-card: 0 10px 24px -10px rgba(20,20,60,.14);
    --stripe: {STRIPE};
}}

/* ---------- page ---------- */
.stApp {{ background: var(--paper); }}
.stApp::after {{
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background: radial-gradient(circle at 8% 15%, rgba(0,219,238,.10), transparent 38%),
                radial-gradient(circle at 95% 30%, rgba(120,139,255,.14), transparent 42%),
                radial-gradient(circle at 40% 95%, rgba(84,101,255,.09), transparent 40%);
}}
[data-testid="stHeader"] {{ background: transparent; height: 2.6rem; }}
[data-testid="stMainBlockContainer"], .block-container {{
    padding-top: 1.1rem !important; position: relative; z-index: 1;
}}

/* ---------- top bar ---------- */
.wm-topbar {{
    display: flex; align-items: center; justify-content: space-between; gap: 20px;
    background: rgba(255,255,255,.92); border: 1px solid rgba(0,0,80,.08);
    border-radius: 14px; padding: 12px 22px; margin-bottom: 14px;
    box-shadow: 0 4px 20px rgba(20,20,60,.06);
}}
.wm-brand {{ display: flex; align-items: center; gap: 16px; min-width: 0; }}
.wm-brand img {{ display: block; height: 30px; width: auto; }}
.wm-divider {{ width: 1px; height: 22px; background: rgba(0,0,80,.16); }}
.wm-name {{ font-weight: 700; font-size: 18px; letter-spacing: -.4px; color: var(--navy); line-height: 1.1; }}
.wm-sub {{ font-size: 9.5px; color: var(--accent); letter-spacing: 1px; text-transform: uppercase; font-weight: 600; }}
.wm-chips {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.wm-chip {{
    display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 12px;
    border: 1px solid rgba(0,0,80,.12); border-radius: 999px; background: #fff;
    font-size: 12px; color: #475569; white-space: nowrap;
}}
.wm-chip b {{ color: var(--navy); }}
.wm-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--lime); }}

/* ---------- hero ---------- */
.wm-hero {{
    position: relative; overflow: hidden; color: #fff; border-radius: 18px;
    padding: 38px 40px 40px; margin-bottom: 22px;
    background: radial-gradient(circle at 18% 25%, rgba(84,101,255,.42), transparent 45%),
                radial-gradient(circle at 84% 15%, rgba(116,91,255,.32), transparent 42%),
                radial-gradient(circle at 68% 100%, rgba(0,219,238,.12), transparent 42%),
                linear-gradient(120deg, #0A1048 0%, #151D67 42%, #29289A 76%, #3931B7 100%);
    box-shadow: 0 20px 40px -18px rgba(0,0,80,.45);
}}
.wm-hero::before {{
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
    background-size: 34px 34px;
}}
.wm-hero::after {{
    content: "QA2 QA2 QA2 QA2"; position: absolute; top: 50%; left: -20px;
    transform: translateY(-55%); font-size: 210px; font-weight: 700; letter-spacing: -6px;
    line-height: 1; white-space: nowrap; color: rgba(255,255,255,.045); pointer-events: none;
}}
.wm-hero-inner {{ position: relative; z-index: 2; }}
.wm-eyebrow {{
    display: inline-flex; align-items: center; gap: 8px; margin: 0 0 16px; padding: 6px 14px;
    border-radius: 7px; background: rgba(7,10,55,.62); border: 1px solid rgba(176,244,103,.36);
    color: var(--lime); font-size: 10.5px; font-weight: 700; letter-spacing: 1.5px;
    text-transform: uppercase;
}}
.wm-hero h1 {{
    margin: 0 0 12px !important; padding: 0 !important; color: #fff !important;
    font-size: clamp(30px, 3vw, 44px) !important; line-height: 1.08 !important; font-weight: 700 !important;
    letter-spacing: -1.2px;
}}
.wm-hl {{
    background: linear-gradient(90deg, #B0F467 0%, #C9FF7A 55%, #77E7B2 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent; color: var(--lime);
}}
.wm-hero p {{ margin: 0; color: rgba(255,255,255,.82) !important; font-size: 15.5px; line-height: 1.7; }}
.wm-hero p b {{ color: #fff; }}
.wm-rule {{ width: 58px; height: 4px; margin-top: 20px; border-radius: 4px;
            background: linear-gradient(90deg, #B0F467, #77E7B2); }}
.wm-steps {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 18px; }}
.wm-steps span {{
    padding: 5px 10px; border-radius: 6px; border: 1px dashed rgba(176,244,103,.4);
    font-size: 12px; color: rgba(255,255,255,.78);
}}
.wm-steps b {{ color: #fff; }}
.wm-hero.compact {{ padding: 22px 32px 24px; }}
.wm-hero.compact::after {{ font-size: 120px; }}
.wm-hero.compact h1 {{ font-size: 30px !important; margin-bottom: 6px !important; }}
.wm-hero.compact .wm-eyebrow {{ margin-bottom: 10px; }}
.wm-hero.compact p {{ font-size: 14px; }}

/* ---------- section titles ---------- */
.wm-section {{ margin: 18px 0 10px; }}
.wm-kicker {{
    font-size: 10.5px; font-weight: 700; letter-spacing: 1.4px; text-transform: uppercase;
    color: #00838F;
}}
.wm-title {{ font-size: 22px; font-weight: 700; letter-spacing: -.4px; color: var(--navy); }}
[data-testid="stMain"] h2, [data-testid="stMain"] h3 {{
    color: var(--navy); letter-spacing: -.4px; font-weight: 700;
}}

/* ---------- cards ---------- */
.wm-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 6px 0 20px; }}
.wm-card {{
    position: relative; overflow: hidden; background: #fff; border: 1px solid var(--line);
    border-radius: 12px; padding: 22px 20px 18px; box-shadow: var(--shadow-card);
    color: var(--navy);
}}
.wm-card::before {{ content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px; background: var(--stripe); }}
.wm-card .n {{
    display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 8px;
    background: var(--navy); color: var(--lime); font-weight: 700; font-size: 13px; margin-bottom: 12px;
}}
.wm-card h4 {{ margin: 0 0 6px !important; padding: 0 !important; font-size: 16px !important; color: var(--navy) !important; }}
.wm-card p {{ margin: 0; font-size: 13px; line-height: 1.55; color: #475569; }}

/* Streamlit's metric, drawn as a Rotation KPI card. */
div[data-testid="stMetric"] {{
    position: relative; overflow: hidden; background: #fff; border: 1px solid var(--line);
    border-radius: 12px; padding: 16px 20px 18px; box-shadow: var(--shadow-card);
}}
div[data-testid="stMetric"]::after {{
    content: ""; position: absolute; left: 20px; bottom: 0; width: 36px; height: 3px;
    border-radius: 3px 3px 0 0; background: var(--accent);
}}
[data-testid="stColumn"]:nth-of-type(4n+2) div[data-testid="stMetric"]::after {{ background: #00838F; }}
[data-testid="stColumn"]:nth-of-type(4n+3) div[data-testid="stMetric"]::after {{ background: var(--navy); }}
[data-testid="stColumn"]:nth-of-type(4n+4) div[data-testid="stMetric"]::after {{ background: var(--lime); }}
[data-testid="stMetricLabel"] p {{
    font-size: 10.5px !important; font-weight: 700 !important; color: var(--muted-2) !important;
    text-transform: uppercase; letter-spacing: .8px;
}}
[data-testid="stMetricValue"] {{
    font-size: 30px !important; font-weight: 700 !important; letter-spacing: -.8px; color: var(--navy) !important;
}}

/* The verdict and the scope cards carry the stripe. */
.verdict-card, .scope-card, .profile-card {{
    position: relative; overflow: hidden; border: 1px solid var(--line);
    box-shadow: var(--shadow-card) !important;
}}
.verdict-card::before {{ content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px; background: var(--stripe); }}
.verdict-caption {{ color: var(--muted-2) !important; font-size: 10.5px !important; font-weight: 700 !important; letter-spacing: 1.4px !important; }}
.verdict-value {{ font-weight: 700 !important; letter-spacing: -.6px; }}

/* Expanders as white cards. */
div[data-testid="stExpander"] {{
    border: 1px solid var(--line) !important; border-radius: 12px !important;
    box-shadow: 0 6px 16px -10px rgba(20,20,60,.18);
}}
div[data-testid="stExpander"] summary p {{ font-weight: 600; color: var(--navy); }}

/* ---------- buttons ---------- */
.stButton > button, [data-testid="stDownloadButton"] > button {{
    border-radius: 10px !important; font-weight: 700 !important; letter-spacing: .1px;
}}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button {{
    background: var(--navy) !important; border: 1px solid var(--navy) !important;
    color: #fff !important; box-shadow: 0 10px 20px -10px rgba(0,0,80,.6) !important;
}}
.stButton > button[kind="primary"]::before {{
    content: "\\2192"; display: inline-grid; place-items: center; width: 22px; height: 22px;
    margin-right: 10px; border-radius: 6px; background: var(--lime); color: var(--navy);
    font-size: 13px; font-weight: 900;
}}
.stButton > button[kind="primary"]:hover {{ background: #14167A !important; transform: translateY(-1px); }}
.stButton > button[kind="secondary"] {{
    background: #fff; border: 1px solid rgba(0,0,80,.14); color: var(--navy);
}}
.stButton > button[kind="secondary"]:hover {{ border-color: var(--accent); color: var(--accent); }}

/* Downloads: white and outlined, like "Export all" in RQ Rotation. */
[data-testid="stDownloadButton"] > button {{
    background: #fff !important; border: 1px solid rgba(0,0,80,.18) !important;
    color: var(--navy) !important; min-height: 44px;
}}
[data-testid="stDownloadButton"] > button::before {{
    /* An arrow drawn as SVG: the WPP font has no down-arrow glyph. */
    content: ""; width: 22px; height: 22px; margin-right: 10px; border-radius: 6px; flex-shrink: 0;
    background: var(--navy) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 5v12M6 12l6 6 6-6' fill='none' stroke='%23B0F467' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center / 15px no-repeat;
}}
[data-testid="stDownloadButton"] > button:hover {{ border-color: var(--accent) !important; color: var(--accent) !important; }}

/* Long KPI labels wrap instead of ending in "...". */
[data-testid="stMetricLabel"] div, [data-testid="stMetricLabel"] p {{
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
}}

@media (max-width: 900px) {{
    .wm-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .wm-topbar {{ flex-wrap: wrap; }}
    .wm-hero {{ padding: 26px 22px 28px; }}
}}

/* ---------- section switch: the Rotation "All: 4" pill ---------- */
[data-testid="stButtonGroup"] button {{
    border-radius: 9px !important; font-weight: 600 !important; color: var(--navy) !important;
    border-color: rgba(0,0,80,.12) !important; background: #fff !important;
}}
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stButtonGroup"] button[aria-checked="true"] {{
    background: var(--navy) !important; border-color: var(--navy) !important; color: #fff !important;
}}
[data-testid="stButtonGroup"] button[kind*="Active"] p, [data-testid="stButtonGroup"] button[aria-checked="true"] p {{
    color: #fff !important;
}}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {{
    background: #fff !important; border-right: 1px solid rgba(0,0,80,.08) !important;
}}
section[data-testid="stSidebar"] h2 {{
    font-size: 10.5px !important; font-weight: 700 !important; letter-spacing: 1.4px;
    text-transform: uppercase; color: #00838F !important; padding-bottom: 0 !important;
}}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-weight: 600; color: var(--navy); }}
section[data-testid="stSidebar"] hr {{ border-color: var(--line); }}

/* ---------- alerts ---------- */
div[data-testid="stAlert"] > div {{ border-radius: 12px; }}
</style>
"""


def topbar_html(logo_b64: str, logo_mime: str, version: str) -> str:
    logo = (f'<img src="data:{logo_mime};base64,{logo_b64}" alt="WPP Media">'
            if logo_b64 else "<b>WPP Media</b>")
    return f"""
<div class="wm-topbar">
  <div class="wm-brand">
    {logo}
    <div class="wm-divider"></div>
    <div>
      <div class="wm-name">Innovid QA</div>
      <div class="wm-sub">WPP Media · QA2</div>
    </div>
  </div>
  <div class="wm-chips">
    <span class="wm-chip"><span class="wm-dot"></span>Internal use · AdOps</span>
    <span class="wm-chip">Version <b>{html.escape(version)}</b></span>
  </div>
</div>
"""


def hero_html(compact: bool) -> str:
    if compact:
        return """
<div class="wm-hero compact"><div class="wm-hero-inner">
  <div class="wm-eyebrow">&#9889; Innovid QA &middot; Results</div>
  <h1>Implementation <span class="wm-hl">against the Traffic Sheet</span></h1>
  <p>Review what failed, sign off what is acceptable, and download the report.</p>
</div></div>
"""
    return """
<div class="wm-hero"><div class="wm-hero-inner">
  <div class="wm-eyebrow">&#9889; Innovid QA &middot; QA2</div>
  <h1>Check every placement <span class="wm-hl">against the Traffic Sheet</span></h1>
  <p>Upload the <b>Traffic Sheet</b> and the <b>Innovid exports</b> on the left. QA2 compares
     placements, creatives, dates, landing pages and tags, and tells you what to fix.</p>
  <div class="wm-steps">
    <span><b>1</b> Traffic Sheet</span><span><b>2</b> Placement-Creative</span>
    <span><b>3</b> Placement View</span><span><b>4</b> Tags</span>
  </div>
  <div class="wm-rule"></div>
</div></div>
"""


def section_html(kicker: str, title: str) -> str:
    return (f'<div class="wm-section"><div class="wm-kicker">{html.escape(kicker)}</div>'
            f'<div class="wm-title">{html.escape(title)}</div></div>')


def cards_html(cards: list[tuple[str, str]]) -> str:
    items = "".join(
        f'<div class="wm-card"><div class="n">{i}</div><h4>{html.escape(title)}</h4>'
        f'<p>{html.escape(text)}</p></div>'
        for i, (title, text) in enumerate(cards, start=1))
    return f'<div class="wm-grid">{items}</div>'

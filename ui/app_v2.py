from __future__ import annotations

import base64
import sys
import tempfile
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd  # type: ignore
import streamlit as st  # type: ignore


# ============================================================
# Project and imports
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.engine import run_rules
from core.adobe_pixel_reconciliation import (
    reconcile_adobe_pixels,
)
from core.tag_inventory import (
    build_tag_inventory_from_results,
)
from core.matching import match
from core.normalize import norm_compare, norm_dims
from core.tag_matching import match_tags
from parsers.innovid_export import parse_innovid_export
from parsers.innovid_tags import parse_innovid_tags
from parsers.ts_parser import detect_profile, parse_ts
from rules import tags as tag_rules
from rules import adobe_pixels


warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl",
)


# ============================================================
# Visual constants
# ============================================================

PROFILE_LABELS = {
    "AUTO": "Auto-detect",
    "adobe_variante_a": (
        "Adobe · Decision Tree Implementation"
    ),
    "adobe_variante_b": (
        "Adobe · Direct & Site-Served Implementation"
    ),
    "wpp_standard": (
        "WPP Media · Standard Trafficking"
    ),
}
def professional_profile_name(profile_name: str) -> str:
    """Corporate-facing name that avoids exposing internal technical keys."""

    return PROFILE_LABELS.get(
        profile_name,
        profile_name.replace("_", " ").title(),
    )


STATUS_PRIORITY = {
    "FAIL": 5,
    "REVIEW": 4,
    "NOT_VERIFIED": 3,
    "INFO": 2,
    "PASS": 1,
}


STATUS_ICON = {
    "PASS": "✅",
    "FAIL": "❌",
    "REVIEW": "⚠️",
    "NOT_VERIFIED": "◻️",
    "INFO": "ℹ️",
}


STATUS_LABEL = {
    "PASS": "Passed",
    "FAIL": "Failed",
    "REVIEW": "Review",
    "NOT_VERIFIED": "Not Verified",
    "INFO": "Info",
}


STATUS_COLOR = {
    "PASS": "#0FA97C",
    "FAIL": "#DC2626",
    "REVIEW": "#D97706",
    "NOT_VERIFIED": "#64748B",
    "INFO": "#0EA5C4",
}


VERDICT_LABELS = {
    "PASSED": "PASSED",
    "FAILED": "REQUIRES CORRECTION",
    "BLOCKED": "BLOCKED",
    "NEEDS_REVIEW": "REVIEW REQUIRED",
    "NO_CHECKS": "NO CHECKS RUN",
}


VERDICT_COLORS = {
    "PASSED": "#0FA97C",
    "FAILED": "#DC2626",
    "BLOCKED": "#991B1B",
    "NEEDS_REVIEW": "#D97706",
    "NO_CHECKS": "#64748B",
}


# ============================================================
# File helpers
# ============================================================

def save_upload(
    uploaded_file,
    directory: Path,
    prefix: str,
) -> Path:
    """
    Saves an UploadedFile to the temporary folder.

    The prefix avoids collisions when two files share the same name.
    """
    safe_name = Path(uploaded_file.name).name
    destination = directory / f"{prefix}{safe_name}"
    destination.write_bytes(uploaded_file.getbuffer())
    return destination


def anomaly_rows(
    source_name: str,
    result,
) -> list[dict]:
    rows = []

    for anomaly in getattr(result, "anomalies", []):
        rows.append(
            {
                "Source": source_name,
                "Severity": anomaly.severity,
                "Code": anomaly.code,
                "Message": anomaly.message,
                "Reference": (
                    str(anomaly.ref)
                    if getattr(anomaly, "ref", None)
                    else ""
                ),
            }
        )

    return rows


def result_is_fatal(result) -> bool:
    return any(
        anomaly.severity == "FATAL"
        for anomaly in getattr(result, "anomalies", [])
    )


# ============================================================
# Findings helpers
# ============================================================

def placement_findings(
    placement_id: str,
    findings_buffer,
):
    return [
        finding
        for finding in findings_buffer.findings
        if finding.placement_id == placement_id
    ]


def placement_status(
    placement_id: str,
    findings_buffer,
) -> str:
    statuses = [
        finding.status.value
        for finding in placement_findings(
            placement_id,
            findings_buffer,
        )
    ]

    if not statuses:
        return "NOT_VERIFIED"

    return max(
        statuses,
        key=lambda status: STATUS_PRIORITY.get(status, 0),
    )


def findings_dataframe(findings) -> pd.DataFrame:
    rows = []

    for finding in findings:
        rows.append(
            {
                "Status": finding.status.value,
                "Severity": finding.severity.value,
                "Rule": finding.rule_id,
                "Domain": finding.domain.value,
                "Placement ID": finding.placement_id,
                "Placement Name": finding.placement_name,
                "Creative ID": finding.creative_id,
                "Creative Name": finding.creative_name,
                "Message": finding.message,
                "Expected": finding.expected,
                "Found": finding.actual,
                "Reason": finding.reason,
                "Recommended Action": finding.recommended_action,
                "Confidence": finding.confidence.value,
                "Count": finding.count,
            }
        )

    return pd.DataFrame(rows)


def rule_summary_dataframe(findings_buffer) -> pd.DataFrame:
    grouped: dict[str, Counter] = defaultdict(Counter)

    for finding in findings_buffer.findings:
        grouped[finding.rule_id][finding.status.value] += max(
            finding.count,
            1,
        )

    rows = []

    for rule_id in sorted(grouped):
        counts = grouped[rule_id]

        rows.append(
            {
                "Rule": rule_id,
                "PASS": counts.get("PASS", 0),
                "FAIL": counts.get("FAIL", 0),
                "REVIEW": counts.get("REVIEW", 0),
                "NOT_VERIFIED": counts.get(
                    "NOT_VERIFIED",
                    0,
                ),
                "INFO": counts.get("INFO", 0),
                "Total": sum(counts.values()),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# Visual comparison helpers
# ============================================================

def clean_value(value) -> str:
    if value is None:
        return ""

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    return str(value).strip()


def compare_value(
    expected,
    actual,
    *,
    normalizer=None,
    optional: bool = False,
) -> str:
    expected_text = clean_value(expected)
    actual_text = clean_value(actual)

    if not expected_text and not actual_text:
        return "INFO" if optional else "NOT_VERIFIED"

    if not expected_text or not actual_text:
        return "INFO" if optional else "NOT_VERIFIED"

    if normalizer is not None:
        expected_comparable = normalizer(expected_text)
        actual_comparable = normalizer(actual_text)
    else:
        expected_comparable = norm_compare(expected_text)
        actual_comparable = norm_compare(actual_text)

    if expected_comparable == actual_comparable:
        return "PASS"

    return "FAIL"


def comparison_row(
    field_name: str,
    expected,
    actual,
    *,
    normalizer=None,
    optional: bool = False,
) -> dict:
    return {
        "Validated Field": field_name,
        "Expected in Traffic Sheet": clean_value(expected),
        "Found in Innovid": clean_value(actual),
        "Visual Result": compare_value(
            expected,
            actual,
            normalizer=normalizer,
            optional=optional,
        ),
    }


def render_status_badge(status: str) -> None:
    icon = STATUS_ICON.get(status, "")
    label = STATUS_LABEL.get(status, status)
    color = STATUS_COLOR.get(status, "#64748b")

    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:5px 12px;
            margin-bottom:10px;
            border-radius:999px;
            background:{color}18;
            border:1px solid {color}40;
            color:{color};
            font-weight:800;
            font-size:0.82rem;
        ">
            {icon} {label}
        </span>
        """,
        unsafe_allow_html=True,
    )


def show_verdict(verdict: str) -> None:
    label = VERDICT_LABELS.get(verdict, verdict)
    color = VERDICT_COLORS.get(verdict, "#64748b")

    st.markdown(
        f"""
        <div class="verdict-card"
             style="border-left:10px solid {color};">
            <div class="verdict-caption">
                OVERALL QA2 RESULT
            </div>
            <div class="verdict-value"
                 style="color:{color};">
                {label}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Streamlit configuration
# ============================================================

st.set_page_config(
    page_title="Innovid QA2 Automation",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
        :root {
            --wpp-indigo: #4B5EEA;
            --wpp-indigo-dark: #2C36A8;
            --wpp-cyan: #17B4DE;
            --wpp-mint: #0FA97C;
            --wpp-ink: #171B2E;
            --wpp-bg: #F5F7FD;
        }

        .stApp {
            background-color: var(--wpp-bg);
        }

        .block-container {
            max-width: 1850px;
            padding-top: 1.2rem;
            padding-bottom: 3rem;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(
                180deg,
                #EEF1FE 0%,
                #F5F7FD 55%
            );
            border-right: 1px solid #E2E6FB;
        }

        .wpp-logo-wrap {
            border-radius: 14px;
            overflow: hidden;
            margin-bottom: 18px;
            box-shadow: 0 6px 16px rgba(43, 54, 168, 0.18);
        }

        .qa-header {
            color: white;
            background: linear-gradient(
                120deg,
                var(--wpp-indigo-dark) 0%,
                var(--wpp-indigo) 45%,
                var(--wpp-cyan) 80%,
                var(--wpp-mint) 115%
            );
            padding: 28px 32px;
            border-radius: 18px;
            box-shadow: 0 14px 34px rgba(43, 54, 168, 0.25);
            margin-bottom: 20px;
            position: relative;
            overflow: hidden;
        }

        .qa-header::after {
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(
                circle at 85% -20%,
                rgba(255, 255, 255, 0.35),
                transparent 55%
            );
            pointer-events: none;
        }

        .qa-header h1 {
            margin: 0;
            padding: 0;
            font-size: 2.1rem;
            font-weight: 900;
            letter-spacing: -0.01em;
        }

        .qa-header p {
            margin: 8px 0 0 0;
            opacity: 0.94;
            font-size: 0.97rem;
        }

        .verdict-card {
            background: white;
            border-radius: 16px;
            padding: 20px 24px;
            margin: 10px 0 18px 0;
            box-shadow: 0 6px 20px rgba(23, 27, 46, 0.07);
        }

        .verdict-caption {
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.09em;
        }

        .verdict-value {
            margin-top: 4px;
            font-size: 1.95rem;
            font-weight: 900;
        }

        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #E5E9FA;
            border-radius: 14px;
            padding: 14px;
            box-shadow: 0 3px 12px rgba(23, 27, 46, 0.05);
        }

        div[data-testid="stExpander"] {
            background: white;
            border: 1px solid #E2E6FB;
            border-radius: 13px;
            margin-bottom: 8px;
            overflow: hidden;
            transition: box-shadow 0.15s ease, border-color 0.15s ease;
        }

        div[data-testid="stExpander"]:hover {
            border-color: var(--wpp-indigo);
            box-shadow: 0 4px 14px rgba(75, 94, 234, 0.12);
        }

        div[data-testid="stFileUploader"] {
            background: white;
            border-radius: 13px;
            padding: 6px;
        }

        .upload-help {
            color: #94a3b8;
            font-size: 0.75rem;
            margin-top: -8px;
            margin-bottom: 13px;
            line-height: 1.35;
        }

        .profile-card {
            background: white;
            border: 1px solid #E2E6FB;
            border-radius: 13px;
            padding: 13px 16px;
            margin-bottom: 15px;
            line-height: 1.55;
        }

        .profile-card strong {
            color: var(--wpp-indigo-dark);
        }

        .section-note {
            background: #EEF1FE;
            border-left: 5px solid var(--wpp-indigo);
            border-radius: 10px;
            padding: 11px 14px;
            margin-bottom: 12px;
            color: var(--wpp-indigo-dark);
        }

        .stButton > button {
            width: 100%;
            min-height: 48px;
            border-radius: 11px;
            font-weight: 850;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(
                100deg,
                var(--wpp-indigo) 0%,
                var(--wpp-cyan) 130%
            );
            border: none;
            box-shadow: 0 6px 16px rgba(75, 94, 234, 0.3);
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }

        .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(75, 94, 234, 0.4);
        }

        button[role="tab"][aria-selected="true"] {
            color: var(--wpp-indigo-dark) !important;
        }

        div[data-baseweb="tab-highlight"] {
            background-color: var(--wpp-indigo) !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="qa-header">
        <h1>INNOVID QA2 AUTOMATION</h1>
        <p>
            Validation of Traffic Sheet, Placement-Creative View,
            Placement View, and Tag files
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:
    _logo_path = PROJECT_ROOT / "ui" / "assets" / "wpp-media-logo.png.png"

    if _logo_path.exists():
        _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()
        st.markdown(
            f"""
            <div class="wpp-logo-wrap">
                <img src="data:image/png;base64,{_logo_b64}"
                     style="width:100%; display:block;">
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.header("QA2 Files")

    uploaded_ts = st.file_uploader(
        "1. Upload Traffic Sheet",
        type=["xlsx", "xlsm"],
        accept_multiple_files=False,
        key="qa2_ts",
    )

    st.markdown(
        """
        <div class="upload-help">
            Source document for scope, placements, and requested changes.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_pc = st.file_uploader(
        "2. Upload Innovid Placement-Creative View",
        type=["xlsx", "xlsm"],
        accept_multiple_files=False,
        key="qa2_pc",
    )

    st.markdown(
        """
        <div class="upload-help">
            Export with Creative_ID, association, status,
            Decision Tree, Clicktag, and Third Party ID.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_pl = st.file_uploader(
        "3. Upload Innovid Placement View",
        type=["xlsx", "xlsm"],
        accept_multiple_files=False,
        key="qa2_pl",
    )

    st.markdown(
        """
        <div class="upload-help">
            Optional. Recommended for 1x1s, pixels,
            and placement-level URL validations.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_tags = st.file_uploader(
        "4. Upload Tag files",
        type=["xlsx", "xlsm"],
        accept_multiple_files=True,
        key="qa2_tags",
    )

    st.markdown(
        """
        <div class="upload-help">
            Allows selecting multiple files at once.
            On Windows use Ctrl+click or Shift+click.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    selected_profile = st.selectbox(
        "Traffic Sheet Profile",
        options=list(PROFILE_LABELS),
        format_func=lambda value: PROFILE_LABELS[value],
        index=0,
    )

    analyze_button = st.button(
        "Run QA2",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# Landing screen
# ============================================================

if not analyze_button:
    st.info(
        "Upload at least the Traffic Sheet and the "
        "Innovid Placement-Creative View."
    )

    st.subheader("Analysis Flow")

    flow_columns = st.columns(4)

    flow_columns[0].markdown(
        """
        **1. Traffic Sheet**

        Detects account, profile, colors, scope, and worked placements.
        """
    )

    flow_columns[1].markdown(
        """
        **2. Placement-Creative**

        Validates creatives, association, status, Decision Tree, URL, and attribution.
        """
    )

    flow_columns[2].markdown(
        """
        **3. Placement View**

        Adds supporting info for 1x1 placements, URLs, and pixels.
        """
    )

    flow_columns[3].markdown(
        """
        **4. Tags**

        Validates IDs, dimensions, Campaign ID, and delivered content.
        """
    )

    st.stop()


if uploaded_ts is None or uploaded_pc is None:
    st.error(
        "You must upload the Traffic Sheet and the "
        "Innovid Placement-Creative View."
    )
    st.stop()


# ============================================================
# Processing
# ============================================================

with tempfile.TemporaryDirectory(
    prefix="qa2_v2_"
) as temporary_directory:
    temporary_path = Path(temporary_directory)

    ts_path = save_upload(
        uploaded_ts,
        temporary_path,
        "ts_",
    )

    pc_path = save_upload(
        uploaded_pc,
        temporary_path,
        "pc_",
    )

    pl_path = (
        save_upload(
            uploaded_pl,
            temporary_path,
            "pl_",
        )
        if uploaded_pl is not None
        else None
    )

    tag_paths = []

    for index, uploaded_tag in enumerate(
        uploaded_tags or [],
        start=1,
    ):
        tag_paths.append(
            (
                uploaded_tag.name,
                save_upload(
                    uploaded_tag,
                    temporary_path,
                    f"tag_{index}_",
                ),
            )
        )

    try:
        # ----------------------------------------------------
        # Traffic Sheet
        # ----------------------------------------------------

        with st.spinner(
            "Reading and parsing the Traffic Sheet..."
        ):
            detected_profile, detection_evidence = (
                detect_profile(ts_path)
            )

            forced_profile = (
                None
                if selected_profile == "AUTO"
                else selected_profile
            )

            ts_result = parse_ts(
                ts_path,
                profile_name=forced_profile,
            )

        # ----------------------------------------------------
        # Placement-Creative
        # ----------------------------------------------------

        with st.spinner(
            "Reading Innovid Placement-Creative View..."
        ):
            pc_result = parse_innovid_export(pc_path)

        # ----------------------------------------------------
        # Placement View
        # ----------------------------------------------------

        pl_result = None

        if pl_path is not None:
            with st.spinner(
                "Reading Innovid Placement View..."
            ):
                pl_result = parse_innovid_export(pl_path)

        # ----------------------------------------------------
        # Tags
        # ----------------------------------------------------

        tags_results = []

        if tag_paths:
            with st.spinner(
                f"Reading {len(tag_paths)} tag file(s)..."
            ):
                for original_name, tag_path in tag_paths:
                    tags_results.append(
                        (
                            original_name,
                            parse_innovid_tags(tag_path),
                        )
                    )

        # ----------------------------------------------------
        # File understanding
        # ----------------------------------------------------

        file_rows = [
            {
                "File": uploaded_ts.name,
                "Expected Type": "Traffic Sheet",
                "Detected Type": ts_result.profile,
                "Status": (
                    "FATAL"
                    if result_is_fatal(ts_result)
                    else "OK"
                ),
                "Records": (
                    len(ts_result.placements.rows)
                    if ts_result.placements
                    else 0
                ),
            },
            {
                "File": uploaded_pc.name,
                "Expected Type": "Placement-Creative View",
                "Detected Type": (
                    pc_result.level
                    or "Not Recognized"
                ),
                "Status": (
                    "FATAL"
                    if result_is_fatal(pc_result)
                    else "OK"
                ),
                "Records": len(pc_result.rows),
            },
        ]

        if pl_result is not None:
            file_rows.append(
                {
                    "File": uploaded_pl.name,
                    "Expected Type": "Placement View",
                    "Detected Type": (
                        pl_result.level
                        or "Not Recognized"
                    ),
                    "Status": (
                        "FATAL"
                        if result_is_fatal(pl_result)
                        else "OK"
                    ),
                    "Records": len(pl_result.rows),
                }
            )

        for file_name, tags_result in tags_results:
            file_rows.append(
                {
                    "File": file_name,
                    "Expected Type": "Tags",
                    "Detected Type": (
                        f"Tags | sheet {tags_result.sheet}"
                        if tags_result.sheet
                        else "Not Recognized"
                    ),
                    "Status": (
                        "FATAL"
                        if result_is_fatal(tags_result)
                        else "OK"
                    ),
                    "Records": len(tags_result.rows),
                }
            )

        files_dataframe = pd.DataFrame(file_rows)

        # ----------------------------------------------------
        # Anomalies
        # ----------------------------------------------------

        all_anomaly_rows = []

        all_anomaly_rows.extend(
            anomaly_rows(
                "Traffic Sheet",
                ts_result,
            )
        )

        all_anomaly_rows.extend(
            anomaly_rows(
                "Placement-Creative View",
                pc_result,
            )
        )

        if pl_result is not None:
            all_anomaly_rows.extend(
                anomaly_rows(
                    "Placement View",
                    pl_result,
                )
            )

        for file_name, tags_result in tags_results:
            all_anomaly_rows.extend(
                anomaly_rows(
                    f"Tags | {file_name}",
                    tags_result,
                )
            )

        # Explicit file-type validations.

        if (
            not result_is_fatal(pc_result)
            and pc_result.level != "placement_creative"
        ):
            all_anomaly_rows.append(
                {
                    "Source": "Placement-Creative View",
                    "Severity": "FATAL",
                    "Code": "UI-WRONG-PC-FILE",
                    "Message": (
                        "The uploaded file was not recognized as a "
                        "Placement-Creative View. It must contain Creative_ID."
                    ),
                    "Reference": uploaded_pc.name,
                }
            )

        if (
            pl_result is not None
            and not result_is_fatal(pl_result)
            and pl_result.level != "placement"
        ):
            all_anomaly_rows.append(
                {
                    "Source": "Placement View",
                    "Severity": "FATAL",
                    "Code": "UI-WRONG-PL-FILE",
                    "Message": (
                        "The uploaded file was not recognized as a "
                        "Placement View. Do not upload a TAGS file here."
                    ),
                    "Reference": uploaded_pl.name,
                }
            )

        fatal_rows = [
            row
            for row in all_anomaly_rows
            if row["Severity"] == "FATAL"
        ]

        if fatal_rows:
            st.error(
                "The analysis was blocked because one or more "
                "documents don't match the expected format."
            )

            st.subheader("File Understanding")

            st.dataframe(
                files_dataframe,
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Issues Found")

            st.dataframe(
                pd.DataFrame(fatal_rows),
                use_container_width=True,
                hide_index=True,
            )

            st.stop()

        # ----------------------------------------------------
        # Matching and rules
        # ----------------------------------------------------

        with st.spinner(
            "Running QA2 matching and validations..."
        ):
            match_result = match(
                ts_result,
                pc_result,
                pl_result,
            )

            # Run TS vs Innovid rules first.
            findings_buffer = run_rules(match_result)

            tag_matches = []
            tag_inventory = None
            adobe_pixel_result = None

            # Every tag file keeps its independent structural checks.
            for file_name, tags_result in tags_results:
                tag_match_result = match_tags(
                    match_result,
                    tags_result,
                )

                tag_rules.evaluate(
                    tag_match_result,
                    findings_buffer,
                )

                tag_matches.append(
                    (
                        file_name,
                        tags_result,
                        tag_match_result,
                    )
                )

            # Consolidated multi-file Tag Inventory.
            #
            # Structural TAG rules run once per delivered file.
            # Adobe business requirements run once against the
            # consolidated inventory to avoid duplicate findings.
            if tags_results:
                tag_inventory = (
                    build_tag_inventory_from_results(
                        tags_results
                    )
                )

            # PIX-A01 applies only to Adobe Direct & Site-Served.
            #
            # Traffic Sheet defines whether DISQO is required.
            # Tags and Innovid Placement View provide evidence.
            if (
                ts_result.profile == "adobe_variante_b"
                and tag_inventory is not None
                and pl_result is not None
            ):
                adobe_pixel_result = (
                    reconcile_adobe_pixels(
                        ts_result,
                        pl_result,
                        tag_inventory,
                    )
                )

                adobe_pixels.evaluate(
                    adobe_pixel_result,
                    findings_buffer,
                )

            scorecard = findings_buffer.scorecard()

        # ----------------------------------------------------
        # Results header
        # ----------------------------------------------------

        show_verdict(scorecard.verdict)

        st.markdown(
            f"""
            <div class="profile-card">
                <strong>Profile used:</strong>
                {ts_result.profile}<br>
                <strong>Detected profile:</strong>
                {detected_profile}<br>
                <strong>Evidence:</strong>
                {detection_evidence}<br>
                <strong>Scope Guard:</strong>
                {match_result.scope_guard or "UNKNOWN"}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # Adobe Pixel & Tag Requirements
        # ----------------------------------------------------

        if (
            ts_result.profile == "adobe_variante_b"
            and adobe_pixel_result is not None
        ):
            st.subheader("Pixel & Tag Requirements")

            disqo_checks = [
                check
                for check in adobe_pixel_result.checks
                if check.disqo_required
            ]

            disqo_pass = sum(
                check.result == "PASS"
                for check in disqo_checks
            )

            disqo_fail = sum(
                check.result == "FAIL"
                for check in disqo_checks
            )

            disqo_review = sum(
                check.result == "REVIEW"
                for check in disqo_checks
            )

            tag_supported = sum(
                check.result == "PASS"
                and check.tags_disqo
                for check in disqo_checks
            )

            innovid_supported = sum(
                check.result == "PASS"
                and not check.tags_disqo
                and check.innovid_disqo
                for check in disqo_checks
            )

            metric_columns = st.columns(5)

            metric_columns[0].metric(
                "DISQO required",
                len(disqo_checks),
            )

            metric_columns[1].metric(
                "Pass",
                disqo_pass,
            )

            metric_columns[2].metric(
                "Fail",
                disqo_fail,
            )

            metric_columns[3].metric(
                "Tag evidence",
                tag_supported,
            )

            metric_columns[4].metric(
                "Innovid evidence",
                innovid_supported,
            )

            if disqo_fail:
                st.error(
                    f"{disqo_fail} placements require DISQO "
                    "but no valid evidence was found."
                )
            elif disqo_review:
                st.warning(
                    f"{disqo_review} DISQO placements require review."
                )
            else:
                st.success(
                    "All DISQO requirements have valid implementation "
                    "evidence in the delivered tag files or Innovid."
                )

            disqo_rows = []

            for check in disqo_checks:
                if check.tags_disqo:
                    evidence_source = (
                        "Delivered Tag File"
                    )
                elif check.innovid_disqo:
                    evidence_source = (
                        "Innovid Active Metering / "
                        "Third Party Impression"
                    )
                else:
                    evidence_source = (
                        "No evidence found"
                    )

                disqo_rows.append(
                    {
                        "Placement ID": (
                            check.placement_id
                        ),
                        "Placement Name": (
                            check.placement_name
                        ),
                        "Site": check.site,
                        "Requirement": "DISQO",
                        "Result": check.result,
                        "Evidence Source": (
                            evidence_source
                        ),
                        "Message": check.message,
                        "Recommended Action": (
                            check.recommended_action
                            or "No correction required."
                        ),
                    }
                )

            with st.expander(
                "View DISQO placement details",
                expanded=bool(
                    disqo_fail or disqo_review
                ),
            ):
                st.dataframe(
                    pd.DataFrame(disqo_rows),
                    use_container_width=True,
                    hide_index=True,
                )

        metric_columns = st.columns(7)

        metric_columns[0].metric(
            "Worked Placements",
            match_result.expected_total,
        )

        metric_columns[1].metric(
            "Found",
            len(match_result.matched),
        )

        metric_columns[2].metric(
            "Missing",
            len(match_result.only_expected),
        )

        metric_columns[3].metric(
            "Tag Files",
            len(tags_results),
        )

        metric_columns[4].metric(
            "Errors",
            scorecard.errors,
        )

        metric_columns[5].metric(
            "Reviews",
            scorecard.reviews,
        )

        metric_columns[6].metric(
            "Not Verified",
            scorecard.not_verified,
        )

        # ----------------------------------------------------
        # Prepare per-placement data
        # ----------------------------------------------------

        matched_by_id = {
            placement_match.placement_id: placement_match
            for placement_match in match_result.matched
        }

        expected_missing_by_id = {
            expected.placement_id: expected
            for expected in match_result.only_expected
        }

        tags_by_placement = defaultdict(list)

        outside_scope_tag_rows = []

        for (
            file_name,
            tags_result,
            tag_match_result,
        ) in tag_matches:
            for tag_link in tag_match_result.links:
                tags_by_placement[
                    tag_link.placement_id
                ].append(
                    {
                        "file_name": file_name,
                        "tags_result": tags_result,
                        "link": tag_link,
                    }
                )

                if not tag_link.in_ts_scope:
                    outside_scope_tag_rows.append(
                        {
                            "File": file_name,
                            "Placement ID": tag_link.placement_id,
                            "Placement Name": (
                                tag_link.tag_row.placement_name
                            ),
                            "Dimensions": (
                                tag_link.tag_row.dimensions
                            ),
                            "Third Party ID": (
                                tag_link.tag_row.third_party_id
                            ),
                            "Status": (
                                "Outside worked scope"
                            ),
                        }
                    )

        (
            tab_workspace,
            tab_attention,
            tab_rules,
            tab_files,
            tab_tags,
        ) = st.tabs(
            [
                "Worked Placements",
                "Findings",
                "Rules Executed",
                "Files & Extraction",
                "Tag Coverage",
            ]
        )

        # ====================================================
        # TAB: Worked Placements
        # ====================================================

        with tab_workspace:
            st.subheader(
                "Worked Placements in the Request"
            )

            st.markdown(
                """
                <div class="section-note">
                    Each row represents a placement in scope.
                    Use the arrow to expand creatives,
                    URLs, attribution, tags, and validations.
                </div>
                """,
                unsafe_allow_html=True,
            )

            filter_columns = st.columns([2, 1, 1])

            with filter_columns[0]:
                search_text = st.text_input(
                    "Search Placement ID or name",
                    placeholder=(
                        "Type an ID or part of the name"
                    ),
                )

            with filter_columns[1]:
                status_filter = st.multiselect(
                    "Result",
                    options=[
                        "FAIL",
                        "REVIEW",
                        "NOT_VERIFIED",
                        "INFO",
                        "PASS",
                    ],
                    default=[
                        "FAIL",
                        "REVIEW",
                        "NOT_VERIFIED",
                        "INFO",
                        "PASS",
                    ],
                )

            with filter_columns[2]:
                request_options = sorted(
                    {
                        (
                            item.expected.request_type
                            if item.expected
                            else ""
                        )
                        for item in match_result.matched
                    }
                    | {
                        item.request_type
                        for item in match_result.only_expected
                    }
                )

                request_options = [
                    item
                    for item in request_options
                    if item
                ]

                request_filter = st.multiselect(
                    "Request Type",
                    options=request_options,
                )

            placement_ids = sorted(
                set(matched_by_id)
                | set(expected_missing_by_id)
            )

            visible_count = 0

            for placement_id in placement_ids:
                placement_match = matched_by_id.get(
                    placement_id
                )

                if placement_match is not None:
                    expected = placement_match.expected
                    actual = placement_match.actual
                else:
                    expected = expected_missing_by_id[
                        placement_id
                    ]
                    actual = None

                status = placement_status(
                    placement_id,
                    findings_buffer,
                )

                if status not in status_filter:
                    continue

                if (
                    request_filter
                    and expected.request_type
                    not in request_filter
                ):
                    continue

                searchable_text = (
                    f"{placement_id} "
                    f"{expected.name} "
                    f"{actual.name if actual else ''}"
                ).casefold()

                if (
                    search_text
                    and search_text.casefold()
                    not in searchable_text
                ):
                    continue

                visible_count += 1

                creative_links = (
                    placement_match.creative_links
                    if placement_match
                    else []
                )

                tag_records = tags_by_placement.get(
                    placement_id,
                    [],
                )

                placement_label = (
                    f"{STATUS_ICON.get(status, '')} "
                    f"{placement_id}  |  "
                    f"{expected.request_type}  |  "
                    f"{expected.dims or '-'}  |  "
                    f"{len(creative_links)} creative(s)  |  "
                    f"{len(tag_records)} tag row(s)  |  "
                    f"{expected.name[:105]}"
                )

                with st.expander(placement_label):
                    render_status_badge(status)

                    # ----------------------------------------
                    # Placement summary header
                    # ----------------------------------------

                    placement_metrics = st.columns(5)

                    placement_metrics[0].metric(
                        "Placement ID",
                        placement_id,
                    )

                    placement_metrics[1].metric(
                        "Request",
                        expected.request_type or "-",
                    )

                    placement_metrics[2].metric(
                        "Format",
                        expected.fmt or "-",
                    )

                    placement_metrics[3].metric(
                        "Expected Creatives",
                        len(expected.creatives),
                    )

                    placement_metrics[4].metric(
                        "Tag Rows",
                        len(tag_records),
                    )

                    # ----------------------------------------
                    # Placement: TS vs Innovid
                    # ----------------------------------------

                    st.markdown(
                        "#### 1. Placement: Traffic Sheet vs Innovid"
                    )

                    placement_comparisons = [
                        comparison_row(
                            "Placement ID",
                            expected.placement_id,
                            (
                                actual.placement_id
                                if actual
                                else ""
                            ),
                        ),
                        comparison_row(
                            "Placement Name",
                            expected.name,
                            (
                                (
                                    actual.name_norm
                                    or actual.name
                                )
                                if actual
                                else ""
                            ),
                        ),
                        comparison_row(
                            "Site",
                            expected.site,
                            actual.site if actual else "",
                        ),
                        comparison_row(
                            "Dimensions",
                            expected.dims,
                            actual.dims if actual else "",
                            normalizer=norm_dims,
                        ),
                        comparison_row(
                            "Start Date",
                            expected.start,
                            actual.start if actual else "",
                        ),
                        comparison_row(
                            "End Date",
                            expected.end,
                            actual.end if actual else "",
                        ),
                        comparison_row(
                            "Decision Tree",
                            expected.group_name,
                            (
                                actual.group_name
                                if actual
                                else ""
                            ),
                            optional=(
                                not bool(expected.group_name)
                            ),
                        ),
                    ]

                    st.dataframe(
                        pd.DataFrame(
                            placement_comparisons
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                    # ----------------------------------------
                    # Creatives
                    # ----------------------------------------

                    st.markdown(
                        "#### 2. Creatives & Assignment"
                    )

                    creative_rows = []

                    if placement_match is not None:
                        for creative_link in creative_links:
                            expected_creative = (
                                creative_link.expected
                            )

                            actual_creative = (
                                creative_link.actual
                            )

                            creative_rows.append(
                                {
                                    "Intent": (
                                        expected_creative.intent
                                    ),
                                    "Expected Creative": (
                                        expected_creative.name
                                    ),
                                    "Found Creative": (
                                        (
                                            actual_creative.filename
                                            or actual_creative.name
                                        )
                                        if actual_creative
                                        else ""
                                    ),
                                    "Creative ID": (
                                        actual_creative.creative_id
                                        if actual_creative
                                        else (
                                            expected_creative.creative_id
                                        )
                                    ),
                                    "Match key": (
                                        creative_link.trace.winner
                                        or "-"
                                    ),
                                    "Confidence": (
                                        creative_link.confidence
                                    ),
                                    "Status": (
                                        actual_creative.state_label
                                        if actual_creative
                                        else "MISSING"
                                    ),
                                    "URL": (
                                        creative_link.url.result
                                        if creative_link.url
                                        else "NOT_VERIFIED"
                                    ),
                                    "Attribution": (
                                        creative_link.triangle.result
                                        if creative_link.triangle
                                        else "NOT_VERIFIED"
                                    ),
                                }
                            )

                    if creative_rows:
                        st.dataframe(
                            pd.DataFrame(creative_rows),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info(
                            "No individual creatives are "
                            "expected for this placement."
                        )

                    # ----------------------------------------
                    # URL and attribution
                    # ----------------------------------------

                    st.markdown(
                        "#### 3. URLs & Attribution"
                    )

                    url_links = [
                        creative_link
                        for creative_link in creative_links
                        if (
                            creative_link.url is not None
                            or creative_link.triangle is not None
                        )
                    ]

                    if not url_links:
                        st.info(
                            "No URL or attribution validations "
                            "were run for this placement."
                        )

                    for creative_index, creative_link in enumerate(
                        url_links,
                        start=1,
                    ):
                        creative_title = (
                            creative_link.expected.name
                            or (
                                creative_link.actual.filename
                                if creative_link.actual
                                else ""
                            )
                            or f"Creative {creative_index}"
                        )

                        url_result = (
                            creative_link.url.result
                            if creative_link.url
                            else "NOT_VERIFIED"
                        )

                        triangle_result = (
                            creative_link.triangle.result
                            if creative_link.triangle
                            else "NOT_VERIFIED"
                        )

                        with st.expander(
                            f"{STATUS_ICON.get('PASS' if url_result == 'MATCH' else 'REVIEW', '')} "
                            f"{creative_title[:120]}  |  "
                            f"URL: {url_result}  |  "
                            f"Attribution: {triangle_result}"
                        ):
                            if creative_link.url is not None:
                                st.write(
                                    "**URL Result:**",
                                    creative_link.url.result,
                                )

                                url_columns = st.columns(2)

                                with url_columns[0]:
                                    st.caption(
                                        "URL expected in Traffic Sheet"
                                    )
                                    st.code(
                                        creative_link.url.expected.raw
                                        or "Pending confirmation",
                                        language=None,
                                    )

                                with url_columns[1]:
                                    st.caption(
                                        "URL found in Innovid"
                                    )
                                    st.code(
                                        creative_link.url.actual.raw
                                        or "Pending confirmation",
                                        language=None,
                                    )

                                if creative_link.url.note:
                                    st.caption(
                                        creative_link.url.note
                                    )

                            if creative_link.triangle is not None:
                                triangle = (
                                    creative_link.triangle
                                )

                                st.write(
                                    "**Attribution Triangle:**",
                                    triangle.result,
                                )

                                triangle_columns = st.columns(3)

                                triangle_columns[0].metric(
                                    "CGEN in TS",
                                    triangle.ts or "-",
                                )

                                triangle_columns[1].metric(
                                    "Third Party ID",
                                    triangle.export or "-",
                                )

                                triangle_columns[2].metric(
                                    "sdid in URL",
                                    triangle.url or "-",
                                )

                                st.caption(
                                    triangle.note
                                    or "No additional detail."
                                )

                    # ----------------------------------------
                    # Extras
                    # ----------------------------------------

                    if (
                        placement_match is not None
                        and placement_match.actual_extra
                    ):
                        st.markdown(
                            "#### 4. Extra Creatives in Innovid"
                        )

                        extra_rows = []

                        for extra in (
                            placement_match.actual_extra
                        ):
                            extra_rows.append(
                                {
                                    "Creative ID": (
                                        extra.creative_id
                                    ),
                                    "Name or filename": (
                                        extra.filename
                                        or extra.name
                                    ),
                                    "Status": extra.state_label,
                                    "Running": (
                                        "Yes"
                                        if extra.running
                                        else "No"
                                    ),
                                    "Decision Tree": (
                                        extra.group_name
                                    ),
                                    "Third Party ID": (
                                        extra.third_party_id
                                    ),
                                }
                            )

                        st.dataframe(
                            pd.DataFrame(extra_rows),
                            use_container_width=True,
                            hide_index=True,
                        )

                    # ----------------------------------------
                    # Delivered tags
                    # ----------------------------------------

                    st.markdown(
                        "#### 5. Tag Files"
                    )

                    if not tag_records:
                        st.info(
                            "No Tag file containing this "
                            "Placement ID was uploaded."
                        )
                    else:
                        tag_summary_rows = []

                        for tag_record in tag_records:
                            tag_row = (
                                tag_record["link"].tag_row
                            )

                            tag_summary_rows.append(
                                {
                                    "File": (
                                        tag_record["file_name"]
                                    ),
                                    "Placement ID": (
                                        tag_row.placement_id
                                    ),
                                    "Placement Name": (
                                        tag_row.placement_name
                                    ),
                                    "Dimensions": (
                                        tag_row.dimensions
                                    ),
                                    "Third Party ID": (
                                        tag_row.third_party_id
                                    ),
                                    "Prisma ID": (
                                        tag_row.prisma_id
                                    ),
                                    "Tag Count": (
                                        tag_row.tag_count
                                    ),
                                    "Detected Types": ", ".join(
                                        sorted(
                                            {
                                                tag.tag_type
                                                for tag
                                                in tag_row.tags
                                            }
                                        )
                                    ),
                                }
                            )

                        st.dataframe(
                            pd.DataFrame(
                                tag_summary_rows
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

                        for tag_record in tag_records:
                            file_name = (
                                tag_record["file_name"]
                            )

                            tag_row = (
                                tag_record["link"].tag_row
                            )

                            with st.expander(
                                f"View Full Tags | {file_name}"
                            ):
                                tag_metadata_columns = (
                                    st.columns(4)
                                )

                                tag_metadata_columns[0].metric(
                                    "Placement ID",
                                    tag_row.placement_id,
                                )

                                tag_metadata_columns[1].metric(
                                    "Dimensions",
                                    tag_row.dimensions or "-",
                                )

                                tag_metadata_columns[2].metric(
                                    "Third Party ID",
                                    (
                                        tag_row.third_party_id
                                        or "-"
                                    ),
                                )

                                tag_metadata_columns[3].metric(
                                    "Prisma ID",
                                    tag_row.prisma_id or "-",
                                )

                                for tag in tag_row.tags:
                                    st.markdown(
                                        f"##### {tag.column_name} "
                                        f"| {tag.tag_type}"
                                    )

                                    tag_information = pd.DataFrame(
                                        [
                                            {
                                                "Field": (
                                                    "Campaign IDs"
                                                ),
                                                "Value": ", ".join(
                                                    tag.campaign_ids
                                                ),
                                            },
                                            {
                                                "Field": (
                                                    "Placement IDs"
                                                ),
                                                "Value": ", ".join(
                                                    tag.placement_ids
                                                ),
                                            },
                                            {
                                                "Field": "Hosts",
                                                "Value": ", ".join(
                                                    tag.hosts
                                                ),
                                            },
                                            {
                                                "Field": "Macros",
                                                "Value": ", ".join(
                                                    tag.macros
                                                ),
                                            },
                                            {
                                                "Field": "Widths",
                                                "Value": ", ".join(
                                                    tag.widths
                                                ),
                                            },
                                            {
                                                "Field": "Heights",
                                                "Value": ", ".join(
                                                    tag.heights
                                                ),
                                            },
                                        ]
                                    )

                                    st.dataframe(
                                        tag_information,
                                        use_container_width=True,
                                        hide_index=True,
                                    )

                                    st.code(
                                        tag.raw,
                                        language="html",
                                    )

                    # ----------------------------------------
                    # Placement findings
                    # ----------------------------------------

                    st.markdown(
                        "#### 6. Validations Run"
                    )

                    current_findings = placement_findings(
                        placement_id,
                        findings_buffer,
                    )

                    current_findings_df = (
                        findings_dataframe(
                            current_findings
                        )
                    )

                    if current_findings_df.empty:
                        st.info(
                            "No rule results are associated "
                            "with this placement."
                        )
                    else:
                        st.dataframe(
                            current_findings_df,
                            use_container_width=True,
                            hide_index=True,
                            height=min(
                                480,
                                80
                                + (
                                    len(
                                        current_findings_df
                                    )
                                    * 35
                                ),
                            ),
                        )

            if visible_count == 0:
                st.warning(
                    "No placements match the "
                    "selected filters."
                )
            else:
                st.caption(
                    f"Visible placements: {visible_count}"
                )

        # ====================================================
        # TAB: Findings
        # ====================================================

        with tab_attention:
            st.subheader(
                "Findings That Require Attention"
            )

            attention_findings = [
                finding
                for finding in findings_buffer.findings
                if finding.status.value != "PASS"
            ]

            attention_df = findings_dataframe(
                attention_findings
            )

            if attention_df.empty:
                st.success(
                    "No errors, reviews, or pending "
                    "validations were detected."
                )
            else:
                selected_attention_statuses = (
                    st.multiselect(
                        "Filter status",
                        options=[
                            "FAIL",
                            "REVIEW",
                            "NOT_VERIFIED",
                            "INFO",
                        ],
                        default=[
                            "FAIL",
                            "REVIEW",
                            "NOT_VERIFIED",
                            "INFO",
                        ],
                    )
                )

                filtered_attention_df = (
                    attention_df[
                        attention_df["Status"].isin(
                            selected_attention_statuses
                        )
                    ]
                )

                st.dataframe(
                    filtered_attention_df,
                    use_container_width=True,
                    hide_index=True,
                    height=620,
                )

                st.download_button(
                    "Download Findings CSV",
                    data=filtered_attention_df.to_csv(
                        index=False,
                        encoding="utf-8-sig",
                    ),
                    file_name="qa2_findings.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        # ====================================================
        # TAB: Rules Executed
        # ====================================================

        with tab_rules:
            st.subheader(
                "Rule Execution Coverage"
            )

            rules_dataframe = (
                rule_summary_dataframe(
                    findings_buffer
                )
            )

            if rules_dataframe.empty:
                st.warning(
                    "The Rule Engine did not emit any results."
                )
            else:
                st.dataframe(
                    rules_dataframe,
                    use_container_width=True,
                    hide_index=True,
                )

        # ====================================================
        # TAB: Files & Extraction
        # ====================================================

        with tab_files:
            st.subheader(
                "Document Understanding"
            )

            st.dataframe(
                files_dataframe,
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("#### Traffic Sheet")

            st.write(
                f"**Profile used:** {ts_result.profile}"
            )

            st.write(
                f"**Detected profile:** "
                f"{detected_profile}"
            )

            st.write(
                f"**Evidence:** {detection_evidence}"
            )

            st.write(
                f"**Worked placements:** "
                f"{len(ts_result.worked)}"
            )

            st.markdown("#### Scope Guard")

            scope_columns = st.columns(3)

            scope_columns[0].metric(
                "Result",
                match_result.scope_guard or "UNKNOWN",
            )

            scope_columns[1].metric(
                "Campaign ID TS",
                match_result.ts_campaign_id or "-",
            )

            scope_columns[2].metric(
                "Campaign ID Innovid",
                match_result.export_campaign_id or "-",
            )

            st.caption(
                match_result.scope_evidence
            )

            st.markdown(
                "#### Extraction Anomalies"
            )

            if all_anomaly_rows:
                st.dataframe(
                    pd.DataFrame(
                        all_anomaly_rows
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success(
                    "No extraction anomalies "
                    "were detected."
                )

        # ====================================================
        # TAB: Tag Coverage
        # ====================================================

        with tab_tags:
            st.subheader(
                "Tag File Coverage"
            )

            if not tag_matches:
                st.info(
                    "No Tag files were uploaded."
                )
            else:
                tag_file_summary = []

                for (
                    file_name,
                    tags_result,
                    tag_match_result,
                ) in tag_matches:
                    tag_file_summary.append(
                        {
                            "File": file_name,
                            "Campaign ID": (
                                tags_result.campaign_id
                            ),
                            "Sheet": tags_result.sheet,
                            "Placements": (
                                tags_result.distinct_placements
                            ),
                            "Materialized Tags": (
                                tags_result.total_tags
                            ),
                            "Rows In Scope": (
                                len(
                                    tag_match_result
                                    .matched_to_scope
                                )
                            ),
                            "Rows Out of Scope": (
                                len(
                                    tag_match_result
                                    .outside_scope
                                )
                            ),
                            "No Innovid Match": (
                                len(
                                    tag_match_result
                                    .missing_in_innovid
                                )
                            ),
                        }
                    )

                st.dataframe(
                    pd.DataFrame(
                        tag_file_summary
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown(
                    "#### Tag Placements "
                    "Outside Worked Scope"
                )

                if outside_scope_tag_rows:
                    st.dataframe(
                        pd.DataFrame(
                            outside_scope_tag_rows
                        ),
                        use_container_width=True,
                        hide_index=True,
                        height=500,
                    )
                else:
                    st.success(
                        "All placements found in Tags "
                        "belong to the worked scope."
                    )

    except Exception as error:
        st.error(
            "QA2 could not complete processing."
        )

        st.exception(error)

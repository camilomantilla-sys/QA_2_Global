from __future__ import annotations

import sys
import tempfile
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st


# Permitir imports desde la raiz del proyecto cuando Streamlit ejecuta ui/app.py.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.engine import run_rules
from core.matching import match
from parsers.innovid_export import parse_innovid_export
from parsers.ts_parser import detect_profile, parse_ts


warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl",
)


PROFILE_LABELS = {
    "AUTO": "Detección automática",
    "adobe_variante_a": "Adobe Variante A | 3P con Decision Tree",
    "adobe_variante_b": "Adobe Variante B | 1x1 / 3P directo",
    "wpp_standard": "WPP Standard | Unilever / Wendy's",
}


VERDICT_LABELS = {
    "PASSED": "APROBADO",
    "FAILED": "REQUIERE CORRECCIÓN",
    "BLOCKED": "BLOQUEADO",
    "NEEDS_REVIEW": "REVISIÓN REQUERIDA",
    "NO_CHECKS": "SIN VALIDACIONES",
}


VERDICT_COLORS = {
    "PASSED": "#16a34a",
    "FAILED": "#dc2626",
    "BLOCKED": "#991b1b",
    "NEEDS_REVIEW": "#d97706",
    "NO_CHECKS": "#64748b",
}


def save_uploaded_file(uploaded_file, directory: Path) -> Path | None:
    """Guarda temporalmente un archivo cargado y devuelve su Path."""

    if uploaded_file is None:
        return None

    safe_name = Path(uploaded_file.name).name
    destination = directory / safe_name
    destination.write_bytes(uploaded_file.getbuffer())

    return destination


def anomaly_rows(source: str, anomalies) -> list[dict]:
    rows = []

    for anomaly in anomalies:
        rows.append(
            {
                "Fuente": source,
                "Severidad": anomaly.severity,
                "Código": anomaly.code,
                "Mensaje": anomaly.message,
                "Referencia": str(anomaly.ref) if anomaly.ref else "",
            }
        )

    return rows


def finding_rows(findings) -> list[dict]:
    """Convierte Findings a una tabla legible para la interfaz."""

    rows = []

    for finding in findings.findings:
        rows.append(
            {
                "Status": finding.status.value,
                "Severity": finding.severity.value,
                "Rule_ID": finding.rule_id,
                "Domain": finding.domain.value,
                "Placement_ID": finding.placement_id,
                "Placement_Name": finding.placement_name,
                "Creative_ID": finding.creative_id,
                "Creative_Name": finding.creative_name,
                "Expected": finding.expected,
                "Actual": finding.actual,
                "Message": finding.message,
                "Reason": finding.reason,
                "Recommended_Action": finding.recommended_action,
                "Confidence": finding.confidence.value,
                "Source": str(finding.source) if finding.source else "",
                "Count": finding.count,
            }
        )

    return rows


def rule_summary_rows(findings) -> list[dict]:
    """Resumen de resultados agrupados por regla y status."""

    grouped = defaultdict(Counter)

    for finding in findings.findings:
        grouped[finding.rule_id][finding.status.value] += finding.count

    rows = []

    for rule_id in sorted(grouped):
        counts = grouped[rule_id]

        rows.append(
            {
                "Rule_ID": rule_id,
                "PASS": counts.get("PASS", 0),
                "FAIL": counts.get("FAIL", 0),
                "REVIEW": counts.get("REVIEW", 0),
                "NOT_VERIFIED": counts.get("NOT_VERIFIED", 0),
                "INFO": counts.get("INFO", 0),
                "Total": sum(counts.values()),
            }
        )

    return rows


def placement_detail_rows(match_result) -> list[dict]:
    """
    Vista operacional TS versus Innovid.

    Muestra explícitamente URLs, CGEN, Third Party ID y sdid.
    """

    rows = []

    for expected in match_result.only_expected:
        rows.append(
            {
                "Placement ID": expected.placement_id,
                "Request": expected.request_type,
                "Placement TS": expected.name,
                "Placement Innovid": "",
                "Dim TS": expected.dims,
                "Dim Innovid": "",
                "Grupo TS": expected.group_name,
                "Grupo Innovid": "",
                "Creative TS": "",
                "Creative Innovid": "",
                "Creative ID": "",
                "Intent": "",
                "Match Confidence": "NONE",
                "Estado": "PLACEMENT MISSING",
                "URL Result": "NOT VERIFIED",
                "URL TS": "",
                "URL Innovid": "",
                "Attribution": "NOT VERIFIED",
                "CGEN TS": expected.cgen,
                "Third Party ID": "",
                "sdid URL": "",
            }
        )

    for placement_match in match_result.matched:
        expected_placement = placement_match.expected
        actual_placement = placement_match.actual

        if not placement_match.creative_links:
            rows.append(
                {
                    "Placement ID": placement_match.placement_id,
                    "Request": expected_placement.request_type,
                    "Placement TS": expected_placement.name,
                    "Placement Innovid": (
                        actual_placement.name if actual_placement else ""
                    ),
                    "Dim TS": expected_placement.dims,
                    "Dim Innovid": (
                        actual_placement.dims if actual_placement else ""
                    ),
                    "Grupo TS": expected_placement.group_name,
                    "Grupo Innovid": (
                        actual_placement.group_name if actual_placement else ""
                    ),
                    "Creative TS": "",
                    "Creative Innovid": "",
                    "Creative ID": "",
                    "Intent": "",
                    "Match Confidence": placement_match.confidence,
                    "Estado": (
                        actual_placement.status if actual_placement else "MISSING"
                    ),
                    "URL Result": "",
                    "URL TS": "",
                    "URL Innovid": "",
                    "Attribution": "",
                    "CGEN TS": expected_placement.cgen,
                    "Third Party ID": (
                        actual_placement.third_party_id
                        if actual_placement
                        else ""
                    ),
                    "sdid URL": "",
                }
            )

        for creative_link in placement_match.creative_links:
            expected_creative = creative_link.expected
            actual_creative = creative_link.actual

            url_result = ""
            url_expected = ""
            url_actual = ""

            if creative_link.url is not None:
                url_result = creative_link.url.result
                url_expected = creative_link.url.expected.raw
                url_actual = creative_link.url.actual.raw

            triangle_result = ""
            triangle_ts = ""
            triangle_export = ""
            triangle_url = ""

            if creative_link.triangle is not None:
                triangle_result = creative_link.triangle.result
                triangle_ts = creative_link.triangle.ts
                triangle_export = creative_link.triangle.export
                triangle_url = creative_link.triangle.url

            rows.append(
                {
                    "Placement ID": placement_match.placement_id,
                    "Request": expected_placement.request_type,
                    "Placement TS": expected_placement.name,
                    "Placement Innovid": (
                        actual_placement.name if actual_placement else ""
                    ),
                    "Dim TS": expected_placement.dims,
                    "Dim Innovid": (
                        actual_placement.dims if actual_placement else ""
                    ),
                    "Grupo TS": expected_placement.group_name,
                    "Grupo Innovid": (
                        actual_placement.group_name if actual_placement else ""
                    ),
                    "Creative TS": expected_creative.name,
                    "Creative Innovid": (
                        (actual_creative.filename or actual_creative.name)
                        if actual_creative
                        else ""
                    ),
                    "Creative ID": (
                        actual_creative.creative_id
                        if actual_creative
                        else expected_creative.creative_id
                    ),
                    "Intent": expected_creative.intent,
                    "Match Confidence": creative_link.confidence,
                    "Estado": (
                        actual_creative.state_label
                        if actual_creative
                        else "CREATIVE MISSING"
                    ),
                    "URL Result": url_result,
                    "URL TS": url_expected,
                    "URL Innovid": url_actual,
                    "Attribution": triangle_result,
                    "CGEN TS": triangle_ts or expected_creative.cgen,
                    "Third Party ID": triangle_export,
                    "sdid URL": triangle_url,
                }
            )

        for extra in placement_match.actual_extra:
            rows.append(
                {
                    "Placement ID": placement_match.placement_id,
                    "Request": expected_placement.request_type,
                    "Placement TS": expected_placement.name,
                    "Placement Innovid": (
                        actual_placement.name if actual_placement else ""
                    ),
                    "Dim TS": expected_placement.dims,
                    "Dim Innovid": (
                        actual_placement.dims if actual_placement else ""
                    ),
                    "Grupo TS": expected_placement.group_name,
                    "Grupo Innovid": extra.group_name,
                    "Creative TS": "",
                    "Creative Innovid": extra.filename or extra.name,
                    "Creative ID": extra.creative_id,
                    "Intent": "EXTRA",
                    "Match Confidence": "",
                    "Estado": extra.state_label,
                    "URL Result": "",
                    "URL TS": "",
                    "URL Innovid": extra.clicktag_1,
                    "Attribution": "",
                    "CGEN TS": "",
                    "Third Party ID": extra.third_party_id,
                    "sdid URL": "",
                }
            )

    return rows


def show_verdict(verdict: str) -> None:
    label = VERDICT_LABELS.get(verdict, verdict)
    color = VERDICT_COLORS.get(verdict, "#64748b")

    st.markdown(
        f"""
        <div class="verdict-card" style="border-left: 10px solid {color};">
            <div class="verdict-caption">RESULTADO GENERAL</div>
            <div class="verdict-value" style="color: {color};">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="QA2 Post-Traffic",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
        .stApp {
            background-color: #f4f7fb;
        }

        .block-container {
            max-width: 1800px;
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }

        .main-title {
            color: white;
            background: linear-gradient(100deg, #4338ca, #2563eb, #0891b2);
            padding: 22px 28px;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(30, 64, 175, 0.18);
            margin-bottom: 16px;
        }

        .main-title h1 {
            margin: 0;
            font-size: 2rem;
            font-weight: 800;
        }

        .main-title p {
            margin: 6px 0 0 0;
            opacity: 0.92;
        }

        .verdict-card {
            background-color: white;
            border-radius: 14px;
            padding: 20px 24px;
            margin-top: 10px;
            margin-bottom: 18px;
            box-shadow: 0 5px 18px rgba(15, 23, 42, 0.08);
        }

        .verdict-caption {
            color: #64748b;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.08em;
        }

        .verdict-value {
            font-size: 2rem;
            line-height: 1.2;
            font-weight: 900;
            margin-top: 4px;
        }

        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #e2e8f0;
            padding: 15px;
            border-radius: 13px;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.05);
        }

        div[data-testid="stMetricLabel"] {
            font-weight: 700;
            color: #475569;
        }

        div[data-testid="stFileUploader"] {
            background: white;
            padding: 10px;
            border-radius: 12px;
        }

        .section-title {
            font-size: 1.15rem;
            font-weight: 800;
            color: #1e293b;
            margin-top: 14px;
            margin-bottom: 8px;
        }

        .input-status {
            background: white;
            border: 1px solid #dbeafe;
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 8px;
        }

        .input-status strong {
            color: #1d4ed8;
        }

        .stButton > button {
            width: 100%;
            border-radius: 10px;
            font-weight: 800;
            background: #2563eb;
            color: white;
            min-height: 48px;
        }

        .stButton > button:hover {
            border-color: #1d4ed8;
            color: white;
            background: #1d4ed8;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="main-title">
        <h1>INNOVID QA2 AUTOMATION</h1>
        <p>Validación post-traffic de Traffic Sheet versus implementación en Innovid</p>
    </div>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.header("Archivos de QA2")

    uploaded_ts = st.file_uploader(
        "1. Traffic Sheet",
        type=["xlsx", "xlsm"],
        help="Traffic Sheet de Adobe, Unilever, Wendy's o plantilla WPP.",
    )

    uploaded_pc = st.file_uploader(
        "2. Export Placement-Creative",
        type=["xlsx", "xlsm"],
        help="Export principal de Innovid con placements y creatives.",
    )

    uploaded_pl = st.file_uploader(
        "3. Export Placement, opcional",
        type=["xlsx", "xlsm"],
        help="Necesario para URLs de 1x1 y validación de píxeles a nivel placement.",
    )

    st.divider()

    selected_profile = st.selectbox(
        "Perfil de Traffic Sheet",
        options=list(PROFILE_LABELS),
        format_func=lambda value: PROFILE_LABELS[value],
        index=0,
    )

    analyze = st.button(
        "Analizar QA2",
        type="primary",
        use_container_width=True,
    )

    st.caption(
        "El perfil se detecta automáticamente. "
        "Puedes forzarlo si la plantilla es ambigua."
    )


if not analyze:
    st.info(
        "Carga una Traffic Sheet y un Export Placement-Creative, "
        "luego selecciona **Analizar QA2**."
    )

    st.subheader("Validaciones visibles")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            **Implementación**
            - Placement ID
            - Placement Name
            - Dimensiones
            - Fechas
            - Estado
            """
        )

    with col2:
        st.markdown(
            """
            **Creative y asignación**
            - Creative esperado
            - Creative en Innovid
            - Decision Tree
            - Extras activos
            - Desasignaciones
            """
        )

    with col3:
        st.markdown(
            """
            **URL y Attribution**
            - URL Traffic Sheet
            - Clicktag Innovid
            - CGEN TS
            - Third Party ID
            - sdid de la URL
            """
        )

    st.stop()


if uploaded_ts is None or uploaded_pc is None:
    st.error(
        "Debes cargar como mínimo una Traffic Sheet "
        "y un Export Placement-Creative."
    )
    st.stop()


with tempfile.TemporaryDirectory(prefix="qa2_") as temp_directory:
    temp_path = Path(temp_directory)

    ts_path = save_uploaded_file(uploaded_ts, temp_path)
    pc_path = save_uploaded_file(uploaded_pc, temp_path)
    pl_path = save_uploaded_file(uploaded_pl, temp_path)

    try:
        with st.spinner("Leyendo Traffic Sheet y exports de Innovid..."):
            detected_profile, detection_evidence = detect_profile(ts_path)

            profile_name = (
                None if selected_profile == "AUTO" else selected_profile
            )

            ts_result = parse_ts(
                ts_path,
                profile_name=profile_name,
            )

            pc_result = parse_innovid_export(pc_path)

            pl_result = (
                parse_innovid_export(pl_path)
                if pl_path is not None
                else None
            )

        anomaly_data = []
        anomaly_data.extend(anomaly_rows("Traffic Sheet", ts_result.anomalies))
        anomaly_data.extend(
            anomaly_rows("Export Placement-Creative", pc_result.anomalies)
        )

        if pl_result is not None:
            anomaly_data.extend(
                anomaly_rows("Export Placement", pl_result.anomalies)
            )

        fatal_anomalies = [
            row for row in anomaly_data
            if row["Severidad"] == "FATAL"
        ]

        if fatal_anomalies:
            st.error(
                "El análisis fue bloqueado por anomalías fatales de extracción."
            )
            st.dataframe(
                pd.DataFrame(fatal_anomalies),
                use_container_width=True,
                hide_index=True,
            )
            st.stop()

        with st.spinner("Ejecutando matching y reglas QA2..."):
            match_result = match(
                ts_result,
                pc_result,
                pl_result,
            )

            findings = run_rules(match_result)
            scorecard = findings.scorecard()

        if match_result.blocked:
            st.error(
                "El Campaign ID de la Traffic Sheet no corresponde "
                "con el Campaign ID del export."
            )

        show_verdict(scorecard.verdict)

        st.markdown(
            f"""
            <div class="input-status">
                <strong>Perfil usado:</strong> {ts_result.profile}<br>
                <strong>Perfil detectado:</strong> {detected_profile}<br>
                <strong>Evidencia:</strong> {detection_evidence}
            </div>
            """,
            unsafe_allow_html=True,
        )

        metric_columns = st.columns(6)

        with metric_columns[0]:
            st.metric(
                "Placements esperados",
                match_result.expected_total,
            )

        with metric_columns[1]:
            st.metric(
                "Placements encontrados",
                len(match_result.matched),
            )

        with metric_columns[2]:
            st.metric(
                "Placements faltantes",
                len(match_result.only_expected),
            )

        with metric_columns[3]:
            st.metric(
                "Errores",
                scorecard.errors,
            )

        with metric_columns[4]:
            st.metric(
                "Revisiones",
                scorecard.reviews,
            )

        with metric_columns[5]:
            st.metric(
                "No verificados",
                scorecard.not_verified,
            )

        tab_summary, tab_rules, tab_findings, tab_details, tab_inputs = st.tabs(
            [
                "Resumen",
                "Reglas ejecutadas",
                "Hallazgos",
                "Detalle TS vs Innovid",
                "Archivos y extracción",
            ]
        )

        with tab_summary:
            st.subheader("Cobertura QA2")

            total_creative_links = sum(
                len(pm.creative_links)
                for pm in match_result.matched
            )

            creative_matches = sum(
                1
                for pm in match_result.matched
                for creative_link in pm.creative_links
                if creative_link.actual is not None
            )

            url_checks = sum(match_result.url_counts.values())
            attribution_checks = sum(match_result.triangle_counts.values())

            coverage_columns = st.columns(4)

            with coverage_columns[0]:
                st.metric(
                    "Creative matches",
                    f"{creative_matches}/{total_creative_links}",
                )

            with coverage_columns[1]:
                st.metric(
                    "URLs validadas",
                    url_checks,
                )

            with coverage_columns[2]:
                st.metric(
                    "Attribution validada",
                    attribution_checks,
                )

            with coverage_columns[3]:
                st.metric(
                    "Extras activos",
                    match_result.extra_running_total,
                )

            st.subheader("Resultados por status")

            status_dataframe = pd.DataFrame(
                [
                    {
                        "Status": status,
                        "Total": total,
                    }
                    for status, total in scorecard.by_status.items()
                ]
            )

            st.dataframe(
                status_dataframe,
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Resultados URL")

            if match_result.url_counts:
                url_dataframe = pd.DataFrame(
                    [
                        {
                            "Resultado URL": result_name,
                            "Total": total,
                        }
                        for result_name, total
                        in sorted(match_result.url_counts.items())
                    ]
                )

                st.dataframe(
                    url_dataframe,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No se ejecutaron validaciones URL.")

            st.subheader("Triángulo de attribution")

            if match_result.triangle_counts:
                triangle_dataframe = pd.DataFrame(
                    [
                        {
                            "Resultado Attribution": result_name,
                            "Total": total,
                        }
                        for result_name, total
                        in sorted(match_result.triangle_counts.items())
                    ]
                )

                st.dataframe(
                    triangle_dataframe,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No se ejecutaron validaciones de attribution.")

        with tab_rules:
            st.subheader("Reglas ejecutadas")

            rule_rows = rule_summary_rows(findings)

            if rule_rows:
                st.dataframe(
                    pd.DataFrame(rule_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.warning("El Rule Engine no emitió resultados.")

        with tab_findings:
            st.subheader("Hallazgos QA2")

            all_finding_rows = finding_rows(findings)

            status_filter = st.multiselect(
                "Filtrar por status",
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
                ],
            )

            filtered_findings = [
                row
                for row in all_finding_rows
                if row["Status"] in status_filter
            ]

            if filtered_findings:
                st.dataframe(
                    pd.DataFrame(filtered_findings),
                    use_container_width=True,
                    hide_index=True,
                    height=520,
                )
            else:
                st.success(
                    "No existen hallazgos para los filtros seleccionados."
                )

            with st.expander("Mostrar también todos los PASS"):
                st.dataframe(
                    pd.DataFrame(all_finding_rows),
                    use_container_width=True,
                    hide_index=True,
                    height=500,
                )

        with tab_details:
            st.subheader("Detalle completo TS versus Innovid")

            detail_rows = placement_detail_rows(match_result)
            details_dataframe = pd.DataFrame(detail_rows)

            if details_dataframe.empty:
                st.warning("No hay placements para mostrar.")
            else:
                placement_options = sorted(
                    details_dataframe["Placement ID"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

                selected_placements = st.multiselect(
                    "Filtrar Placement ID",
                    options=placement_options,
                )

                intent_options = sorted(
                    value
                    for value in details_dataframe["Intent"]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                    if value
                )

                selected_intents = st.multiselect(
                    "Filtrar Intent",
                    options=intent_options,
                )

                visible_details = details_dataframe.copy()

                if selected_placements:
                    visible_details = visible_details[
                        visible_details["Placement ID"]
                        .astype(str)
                        .isin(selected_placements)
                    ]

                if selected_intents:
                    visible_details = visible_details[
                        visible_details["Intent"].isin(selected_intents)
                    ]

                st.dataframe(
                    visible_details,
                    use_container_width=True,
                    hide_index=True,
                    height=620,
                )

                st.download_button(
                    "Descargar detalle CSV",
                    data=visible_details.to_csv(
                        index=False,
                        encoding="utf-8-sig",
                    ),
                    file_name="qa2_detalle_ts_vs_innovid.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        with tab_inputs:
            st.subheader("Archivos procesados")

            input_rows = [
                {
                    "Tipo": "Traffic Sheet",
                    "Archivo": uploaded_ts.name,
                    "Perfil/Nivel": ts_result.profile,
                    "Filas": (
                        len(ts_result.placements.rows)
                        if ts_result.placements
                        else 0
                    ),
                },
                {
                    "Tipo": "Placement-Creative Export",
                    "Archivo": uploaded_pc.name,
                    "Perfil/Nivel": pc_result.level,
                    "Filas": len(pc_result.rows),
                },
            ]

            if uploaded_pl is not None and pl_result is not None:
                input_rows.append(
                    {
                        "Tipo": "Placement Export",
                        "Archivo": uploaded_pl.name,
                        "Perfil/Nivel": pl_result.level,
                        "Filas": len(pl_result.rows),
                    }
                )

            st.dataframe(
                pd.DataFrame(input_rows),
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Scope Guard")

            scope_guard_columns = st.columns(3)

            with scope_guard_columns[0]:
                st.metric("Resultado", match_result.scope_guard or "UNKNOWN")

            with scope_guard_columns[1]:
                st.metric(
                    "Campaign ID TS",
                    match_result.ts_campaign_id or "No declarado",
                )

            with scope_guard_columns[2]:
                st.metric(
                    "Campaign ID Innovid",
                    match_result.export_campaign_id or "No declarado",
                )

            st.caption(match_result.scope_evidence)

            st.subheader("Anomalías de extracción")

            if anomaly_data:
                st.dataframe(
                    pd.DataFrame(anomaly_data),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("No se detectaron anomalías de extracción.")

            st.subheader("Capacidades del export")

            capability_rows = []

            for capability, rules in pc_result.capabilities_on.items():
                capability_rows.append(
                    {
                        "Capacidad": capability,
                        "Estado": "ON",
                        "Reglas": rules,
                        "Motivo": "",
                    }
                )

            for capability, information in pc_result.capabilities_off.items():
                capability_rows.append(
                    {
                        "Capacidad": capability,
                        "Estado": "OFF",
                        "Reglas": information.get("rules", ""),
                        "Motivo": information.get("reason", ""),
                    }
                )

            if capability_rows:
                st.dataframe(
                    pd.DataFrame(capability_rows),
                    use_container_width=True,
                    hide_index=True,
                )

    except Exception as error:
        st.error("QA2 no pudo completar el análisis.")
        st.exception(error)
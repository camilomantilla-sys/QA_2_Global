from __future__ import annotations

import sys
import tempfile
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd  # type: ignore
import streamlit as st  # type: ignore


# ============================================================
# Proyecto e imports
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.engine import run_rules
from core.matching import match
from core.normalize import norm_compare, norm_dims
from core.tag_matching import match_tags
from parsers.innovid_export import parse_innovid_export
from parsers.innovid_tags import parse_innovid_tags
from parsers.ts_parser import detect_profile, parse_ts
from rules import tags as tag_rules


warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="openpyxl",
)


# ============================================================
# Constantes visuales
# ============================================================

PROFILE_LABELS = {
    "AUTO": "Detección automática",
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
    """Nombre corporativo visible sin exponer claves técnicas internas."""

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
    "PASS": "Aprobado",
    "FAIL": "Error",
    "REVIEW": "Revisión",
    "NOT_VERIFIED": "No verificable",
    "INFO": "Información",
}


STATUS_COLOR = {
    "PASS": "#16a34a",
    "FAIL": "#dc2626",
    "REVIEW": "#d97706",
    "NOT_VERIFIED": "#64748b",
    "INFO": "#2563eb",
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


# ============================================================
# Helpers de archivos
# ============================================================

def save_upload(
    uploaded_file,
    directory: Path,
    prefix: str,
) -> Path:
    """
    Guarda un UploadedFile en la carpeta temporal.

    El prefijo evita colisiones cuando dos archivos tienen el mismo nombre.
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
                "Fuente": source_name,
                "Severidad": anomaly.severity,
                "Código": anomaly.code,
                "Mensaje": anomaly.message,
                "Referencia": (
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
# Helpers de findings
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
                "Severidad": finding.severity.value,
                "Regla": finding.rule_id,
                "Dominio": finding.domain.value,
                "Placement ID": finding.placement_id,
                "Placement Name": finding.placement_name,
                "Creative ID": finding.creative_id,
                "Creative Name": finding.creative_name,
                "Mensaje": finding.message,
                "Esperado": finding.expected,
                "Encontrado": finding.actual,
                "Razón": finding.reason,
                "Acción recomendada": finding.recommended_action,
                "Confianza": finding.confidence.value,
                "Cantidad": finding.count,
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
                "Regla": rule_id,
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
# Helpers de comparación visual
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
        "Campo validado": field_name,
        "Esperado en Traffic Sheet": clean_value(expected),
        "Encontrado en Innovid": clean_value(actual),
        "Resultado visual": compare_value(
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
                RESULTADO GENERAL DEL QA2
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
# Configuración Streamlit
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
        .stApp {
            background-color: #f4f7fb;
        }

        .block-container {
            max-width: 1850px;
            padding-top: 1.2rem;
            padding-bottom: 3rem;
        }

        .qa-header {
            color: white;
            background:
                linear-gradient(
                    110deg,
                    #3730a3 0%,
                    #2563eb 55%,
                    #0891b2 100%
                );
            padding: 24px 30px;
            border-radius: 17px;
            box-shadow:
                0 12px 30px rgba(30, 64, 175, 0.20);
            margin-bottom: 18px;
        }

        .qa-header h1 {
            margin: 0;
            padding: 0;
            font-size: 2rem;
            font-weight: 900;
        }

        .qa-header p {
            margin: 7px 0 0 0;
            opacity: 0.92;
            font-size: 0.95rem;
        }

        .verdict-card {
            background: white;
            border-radius: 14px;
            padding: 19px 23px;
            margin: 10px 0 18px 0;
            box-shadow:
                0 5px 18px rgba(15, 23, 42, 0.08);
        }

        .verdict-caption {
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
        }

        .verdict-value {
            margin-top: 4px;
            font-size: 1.9rem;
            font-weight: 900;
        }

        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 13px;
            padding: 14px;
            box-shadow:
                0 3px 12px rgba(15, 23, 42, 0.05);
        }

        div[data-testid="stExpander"] {
            background: white;
            border: 1px solid #dbe3ef;
            border-radius: 12px;
            margin-bottom: 8px;
            overflow: hidden;
        }

        div[data-testid="stFileUploader"] {
            background: white;
            border-radius: 12px;
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
            border: 1px solid #dbeafe;
            border-radius: 12px;
            padding: 13px 16px;
            margin-bottom: 15px;
            line-height: 1.55;
        }

        .profile-card strong {
            color: #1d4ed8;
        }

        .section-note {
            background: #eff6ff;
            border-left: 5px solid #2563eb;
            border-radius: 9px;
            padding: 11px 14px;
            margin-bottom: 12px;
            color: #1e3a8a;
        }

        .stButton > button {
            width: 100%;
            min-height: 48px;
            border-radius: 10px;
            font-weight: 850;
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
            Validación de Traffic Sheet, Placement-Creative View,
            Placement View y archivos de Tags
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:
    st.header("Archivos del QA2")

    uploaded_ts = st.file_uploader(
        "1. Importar Traffic Sheet",
        type=["xlsx", "xlsm"],
        accept_multiple_files=False,
        key="qa2_ts",
    )

    st.markdown(
        """
        <div class="upload-help">
            Documento fuente del alcance, placements y cambios solicitados.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_pc = st.file_uploader(
        "2. Importar Innovid Placement-Creative View",
        type=["xlsx", "xlsm"],
        accept_multiple_files=False,
        key="qa2_pc",
    )

    st.markdown(
        """
        <div class="upload-help">
            Export con Creative_ID, asociación, estado,
            Decision Tree, Clicktag y Third Party ID.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_pl = st.file_uploader(
        "3. Importar Innovid Placement View",
        type=["xlsx", "xlsm"],
        accept_multiple_files=False,
        key="qa2_pl",
    )

    st.markdown(
        """
        <div class="upload-help">
            Opcional. Recomendado para 1x1, píxeles
            y validaciones de URL a nivel placement.
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_tags = st.file_uploader(
        "4. Importar archivos de Tags",
        type=["xlsx", "xlsm"],
        accept_multiple_files=True,
        key="qa2_tags",
    )

    st.markdown(
        """
        <div class="upload-help">
            Permite seleccionar varios archivos al mismo tiempo.
            En Windows usa Ctrl + clic o Shift + clic.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    selected_profile = st.selectbox(
        "Perfil de Traffic Sheet",
        options=list(PROFILE_LABELS),
        format_func=lambda value: PROFILE_LABELS[value],
        index=0,
    )

    analyze_button = st.button(
        "Analizar QA2",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# Pantalla inicial
# ============================================================

if not analyze_button:
    st.info(
        "Carga como mínimo la Traffic Sheet y el "
        "Innovid Placement-Creative View."
    )

    st.subheader("Flujo del análisis")

    flow_columns = st.columns(4)

    flow_columns[0].markdown(
        """
        **1. Traffic Sheet**

        Detecta cuenta, perfil, colores, scope y placements trabajados.
        """
    )

    flow_columns[1].markdown(
        """
        **2. Placement-Creative**

        Valida creativos, asociación, status, DTree, URL y attribution.
        """
    )

    flow_columns[2].markdown(
        """
        **3. Placement View**

        Complementa información de placements 1x1, URLs y píxeles.
        """
    )

    flow_columns[3].markdown(
        """
        **4. Tags**

        Valida IDs, dimensiones, Campaign ID y contenido entregado.
        """
    )

    st.stop()


if uploaded_ts is None or uploaded_pc is None:
    st.error(
        "Debes cargar la Traffic Sheet y el "
        "Innovid Placement-Creative View."
    )
    st.stop()


# ============================================================
# Procesamiento
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
            "Leyendo y comprendiendo la Traffic Sheet..."
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
            "Leyendo Innovid Placement-Creative View..."
        ):
            pc_result = parse_innovid_export(pc_path)

        # ----------------------------------------------------
        # Placement View
        # ----------------------------------------------------

        pl_result = None

        if pl_path is not None:
            with st.spinner(
                "Leyendo Innovid Placement View..."
            ):
                pl_result = parse_innovid_export(pl_path)

        # ----------------------------------------------------
        # Tags
        # ----------------------------------------------------

        tags_results = []

        if tag_paths:
            with st.spinner(
                f"Leyendo {len(tag_paths)} archivo(s) de Tags..."
            ):
                for original_name, tag_path in tag_paths:
                    tags_results.append(
                        (
                            original_name,
                            parse_innovid_tags(tag_path),
                        )
                    )

        # ----------------------------------------------------
        # Comprensión de archivos
        # ----------------------------------------------------

        file_rows = [
            {
                "Archivo": uploaded_ts.name,
                "Tipo esperado": "Traffic Sheet",
                "Tipo detectado": ts_result.profile,
                "Estado": (
                    "FATAL"
                    if result_is_fatal(ts_result)
                    else "OK"
                ),
                "Registros": (
                    len(ts_result.placements.rows)
                    if ts_result.placements
                    else 0
                ),
            },
            {
                "Archivo": uploaded_pc.name,
                "Tipo esperado": "Placement-Creative View",
                "Tipo detectado": (
                    pc_result.level
                    or "No reconocido"
                ),
                "Estado": (
                    "FATAL"
                    if result_is_fatal(pc_result)
                    else "OK"
                ),
                "Registros": len(pc_result.rows),
            },
        ]

        if pl_result is not None:
            file_rows.append(
                {
                    "Archivo": uploaded_pl.name,
                    "Tipo esperado": "Placement View",
                    "Tipo detectado": (
                        pl_result.level
                        or "No reconocido"
                    ),
                    "Estado": (
                        "FATAL"
                        if result_is_fatal(pl_result)
                        else "OK"
                    ),
                    "Registros": len(pl_result.rows),
                }
            )

        for file_name, tags_result in tags_results:
            file_rows.append(
                {
                    "Archivo": file_name,
                    "Tipo esperado": "Tags",
                    "Tipo detectado": (
                        f"Tags | hoja {tags_result.sheet}"
                        if tags_result.sheet
                        else "No reconocido"
                    ),
                    "Estado": (
                        "FATAL"
                        if result_is_fatal(tags_result)
                        else "OK"
                    ),
                    "Registros": len(tags_result.rows),
                }
            )

        files_dataframe = pd.DataFrame(file_rows)

        # ----------------------------------------------------
        # Anomalías
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

        # Validaciones explícitas de tipo de archivo.

        if (
            not result_is_fatal(pc_result)
            and pc_result.level != "placement_creative"
        ):
            all_anomaly_rows.append(
                {
                    "Fuente": "Placement-Creative View",
                    "Severidad": "FATAL",
                    "Código": "UI-WRONG-PC-FILE",
                    "Mensaje": (
                        "El archivo cargado no fue reconocido como "
                        "Placement-Creative View. Debe contener Creative_ID."
                    ),
                    "Referencia": uploaded_pc.name,
                }
            )

        if (
            pl_result is not None
            and not result_is_fatal(pl_result)
            and pl_result.level != "placement"
        ):
            all_anomaly_rows.append(
                {
                    "Fuente": "Placement View",
                    "Severidad": "FATAL",
                    "Código": "UI-WRONG-PL-FILE",
                    "Mensaje": (
                        "El archivo cargado no fue reconocido como "
                        "Placement View. No cargues aquí un archivo TAGS."
                    ),
                    "Referencia": uploaded_pl.name,
                }
            )

        fatal_rows = [
            row
            for row in all_anomaly_rows
            if row["Severidad"] == "FATAL"
        ]

        if fatal_rows:
            st.error(
                "El análisis fue bloqueado porque uno o más "
                "documentos no corresponden al formato esperado."
            )

            st.subheader("Comprensión de archivos")

            st.dataframe(
                files_dataframe,
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Problemas encontrados")

            st.dataframe(
                pd.DataFrame(fatal_rows),
                use_container_width=True,
                hide_index=True,
            )

            st.stop()

        # ----------------------------------------------------
        # Matching y reglas
        # ----------------------------------------------------

        with st.spinner(
            "Ejecutando matching y validaciones QA2..."
        ):
            match_result = match(
                ts_result,
                pc_result,
                pl_result,
            )

            # Primero ejecutamos reglas TS vs Innovid.
            findings_buffer = run_rules(match_result)

            tag_matches = []

            # Cada archivo de tags se procesa de forma independiente.
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

            scorecard = findings_buffer.scorecard()

        # ----------------------------------------------------
        # Header de resultados
        # ----------------------------------------------------

        show_verdict(scorecard.verdict)

        st.markdown(
            f"""
            <div class="profile-card">
                <strong>Perfil usado:</strong>
                {ts_result.profile}<br>
                <strong>Perfil detectado:</strong>
                {detected_profile}<br>
                <strong>Evidencia:</strong>
                {detection_evidence}<br>
                <strong>Scope Guard:</strong>
                {match_result.scope_guard or "UNKNOWN"}
            </div>
            """,
            unsafe_allow_html=True,
        )

        metric_columns = st.columns(7)

        metric_columns[0].metric(
            "Placements trabajados",
            match_result.expected_total,
        )

        metric_columns[1].metric(
            "Encontrados",
            len(match_result.matched),
        )

        metric_columns[2].metric(
            "Faltantes",
            len(match_result.only_expected),
        )

        metric_columns[3].metric(
            "Archivos de Tags",
            len(tags_results),
        )

        metric_columns[4].metric(
            "Errores",
            scorecard.errors,
        )

        metric_columns[5].metric(
            "Revisiones",
            scorecard.reviews,
        )

        metric_columns[6].metric(
            "No verificados",
            scorecard.not_verified,
        )

        # ----------------------------------------------------
        # Preparar datos por placement
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
                            "Archivo": file_name,
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
                            "Situación": (
                                "Fuera del scope trabajado"
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
                "Placements trabajados",
                "Hallazgos",
                "Reglas ejecutadas",
                "Archivos y extracción",
                "Cobertura de Tags",
            ]
        )

        # ====================================================
        # TAB: Placements trabajados
        # ====================================================

        with tab_workspace:
            st.subheader(
                "Placements trabajados en la solicitud"
            )

            st.markdown(
                """
                <div class="section-note">
                    Cada fila representa un placement del scope.
                    Usa la flecha para desplegar creativos,
                    URLs, attribution, tags y validaciones.
                </div>
                """,
                unsafe_allow_html=True,
            )

            filter_columns = st.columns([2, 1, 1])

            with filter_columns[0]:
                search_text = st.text_input(
                    "Buscar Placement ID o nombre",
                    placeholder=(
                        "Escribe un ID o una parte del nombre"
                    ),
                )

            with filter_columns[1]:
                status_filter = st.multiselect(
                    "Resultado",
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
                    "Tipo de solicitud",
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
                    f"{len(tag_records)} fila(s) de Tags  |  "
                    f"{expected.name[:105]}"
                )

                with st.expander(placement_label):
                    render_status_badge(status)

                    # ----------------------------------------
                    # Resumen superior del placement
                    # ----------------------------------------

                    placement_metrics = st.columns(5)

                    placement_metrics[0].metric(
                        "Placement ID",
                        placement_id,
                    )

                    placement_metrics[1].metric(
                        "Solicitud",
                        expected.request_type or "-",
                    )

                    placement_metrics[2].metric(
                        "Formato",
                        expected.fmt or "-",
                    )

                    placement_metrics[3].metric(
                        "Creativos esperados",
                        len(expected.creatives),
                    )

                    placement_metrics[4].metric(
                        "Filas de Tags",
                        len(tag_records),
                    )

                    # ----------------------------------------
                    # Placement TS vs Innovid
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
                    # Creativos
                    # ----------------------------------------

                    st.markdown(
                        "#### 2. Creativos y asignación"
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
                                    "Creative esperado": (
                                        expected_creative.name
                                    ),
                                    "Creative encontrado": (
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
                                    "Confianza": (
                                        creative_link.confidence
                                    ),
                                    "Estado": (
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
                            "No existen creativos individuales "
                            "esperados para este placement."
                        )

                    # ----------------------------------------
                    # URL y attribution
                    # ----------------------------------------

                    st.markdown(
                        "#### 3. URLs y attribution"
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
                            "No se ejecutaron validaciones "
                            "URL o attribution para este placement."
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
                                    "**Resultado de URL:**",
                                    creative_link.url.result,
                                )

                                url_columns = st.columns(2)

                                with url_columns[0]:
                                    st.caption(
                                        "URL esperada en Traffic Sheet"
                                    )
                                    st.code(
                                        creative_link.url.expected.raw
                                        or "Pendiente de confirmar",
                                        language=None,
                                    )

                                with url_columns[1]:
                                    st.caption(
                                        "URL encontrada en Innovid"
                                    )
                                    st.code(
                                        creative_link.url.actual.raw
                                        or "Pendiente de confirmar",
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
                                    "**Triángulo de attribution:**",
                                    triangle.result,
                                )

                                triangle_columns = st.columns(3)

                                triangle_columns[0].metric(
                                    "CGEN en TS",
                                    triangle.ts or "-",
                                )

                                triangle_columns[1].metric(
                                    "Third Party ID",
                                    triangle.export or "-",
                                )

                                triangle_columns[2].metric(
                                    "sdid en URL",
                                    triangle.url or "-",
                                )

                                st.caption(
                                    triangle.note
                                    or "Sin detalle adicional."
                                )

                    # ----------------------------------------
                    # Extras
                    # ----------------------------------------

                    if (
                        placement_match is not None
                        and placement_match.actual_extra
                    ):
                        st.markdown(
                            "#### 4. Creativos extra en Innovid"
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
                                    "Nombre o filename": (
                                        extra.filename
                                        or extra.name
                                    ),
                                    "Estado": extra.state_label,
                                    "Corriendo": (
                                        "Sí"
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
                    # Tags entregados
                    # ----------------------------------------

                    st.markdown(
                        "#### 5. Archivos de Tags"
                    )

                    if not tag_records:
                        st.info(
                            "No se cargó ningún archivo de Tags "
                            "que contenga este Placement ID."
                        )
                    else:
                        tag_summary_rows = []

                        for tag_record in tag_records:
                            tag_row = (
                                tag_record["link"].tag_row
                            )

                            tag_summary_rows.append(
                                {
                                    "Archivo": (
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
                                    "Cantidad de tags": (
                                        tag_row.tag_count
                                    ),
                                    "Tipos detectados": ", ".join(
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
                                f"Ver Tags completos | {file_name}"
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
                                                "Dato": (
                                                    "Campaign IDs"
                                                ),
                                                "Valor": ", ".join(
                                                    tag.campaign_ids
                                                ),
                                            },
                                            {
                                                "Dato": (
                                                    "Placement IDs"
                                                ),
                                                "Valor": ", ".join(
                                                    tag.placement_ids
                                                ),
                                            },
                                            {
                                                "Dato": "Hosts",
                                                "Valor": ", ".join(
                                                    tag.hosts
                                                ),
                                            },
                                            {
                                                "Dato": "Macros",
                                                "Valor": ", ".join(
                                                    tag.macros
                                                ),
                                            },
                                            {
                                                "Dato": "Widths",
                                                "Valor": ", ".join(
                                                    tag.widths
                                                ),
                                            },
                                            {
                                                "Dato": "Heights",
                                                "Valor": ", ".join(
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
                    # Findings del placement
                    # ----------------------------------------

                    st.markdown(
                        "#### 6. Validaciones ejecutadas"
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
                            "No existen resultados de reglas "
                            "asociados a este placement."
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
                    "No hay placements que coincidan "
                    "con los filtros seleccionados."
                )
            else:
                st.caption(
                    f"Placements visibles: {visible_count}"
                )

        # ====================================================
        # TAB: Hallazgos
        # ====================================================

        with tab_attention:
            st.subheader(
                "Hallazgos que requieren atención"
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
                    "No se detectaron errores, revisiones "
                    "o validaciones pendientes."
                )
            else:
                selected_attention_statuses = (
                    st.multiselect(
                        "Filtrar status",
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
                    "Descargar hallazgos CSV",
                    data=filtered_attention_df.to_csv(
                        index=False,
                        encoding="utf-8-sig",
                    ),
                    file_name="qa2_hallazgos.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        # ====================================================
        # TAB: Reglas ejecutadas
        # ====================================================

        with tab_rules:
            st.subheader(
                "Cobertura de reglas ejecutadas"
            )

            rules_dataframe = (
                rule_summary_dataframe(
                    findings_buffer
                )
            )

            if rules_dataframe.empty:
                st.warning(
                    "El Rule Engine no emitió resultados."
                )
            else:
                st.dataframe(
                    rules_dataframe,
                    use_container_width=True,
                    hide_index=True,
                )

        # ====================================================
        # TAB: Archivos y extracción
        # ====================================================

        with tab_files:
            st.subheader(
                "Comprensión de documentos"
            )

            st.dataframe(
                files_dataframe,
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("#### Traffic Sheet")

            st.write(
                f"**Perfil usado:** {ts_result.profile}"
            )

            st.write(
                f"**Perfil detectado:** "
                f"{detected_profile}"
            )

            st.write(
                f"**Evidencia:** {detection_evidence}"
            )

            st.write(
                f"**Placements trabajados:** "
                f"{len(ts_result.worked)}"
            )

            st.markdown("#### Scope Guard")

            scope_columns = st.columns(3)

            scope_columns[0].metric(
                "Resultado",
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
                "#### Anomalías de extracción"
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
                    "No se detectaron anomalías "
                    "de extracción."
                )

        # ====================================================
        # TAB: Cobertura Tags
        # ====================================================

        with tab_tags:
            st.subheader(
                "Cobertura de archivos de Tags"
            )

            if not tag_matches:
                st.info(
                    "No se cargaron archivos de Tags."
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
                            "Archivo": file_name,
                            "Campaign ID": (
                                tags_result.campaign_id
                            ),
                            "Hoja": tags_result.sheet,
                            "Placements": (
                                tags_result.distinct_placements
                            ),
                            "Tags materializados": (
                                tags_result.total_tags
                            ),
                            "Filas dentro de scope": (
                                len(
                                    tag_match_result
                                    .matched_to_scope
                                )
                            ),
                            "Filas fuera de scope": (
                                len(
                                    tag_match_result
                                    .outside_scope
                                )
                            ),
                            "Sin match Innovid": (
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
                    "#### Placements de Tags "
                    "fuera del scope trabajado"
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
                        "Todos los placements encontrados "
                        "en Tags pertenecen al scope trabajado."
                    )

    except Exception as error:
        st.error(
            "QA2 no pudo completar el procesamiento."
        )

        st.exception(error)

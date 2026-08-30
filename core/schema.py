"""
Contratos de campo para exports de Innovid.

Cambiar un alias es cambiar UNA linea, no buscar indices en cinco lugares.
"""
from __future__ import annotations

from core.extraction import FieldSpec, SheetSpec

# ---------------------------------------------------------------- Innovid

INNOVID_METADATA_LABELS = [
    "campaign", "campaignid", "mediabuyer", "mediabuyeremail",
    "exporttype", "exportdate", "advertiser", "startdate", "enddate",
]

# --- export Placement-Creative (Adobe 3P con Dtree, 1x1/3P directo, vistas)
_PC_FIELDS = [
    FieldSpec("enabled", ["Enabled"], required=True, kind="bool"),
    FieldSpec("site_id", ["Site_ID"], kind="id"),
    FieldSpec("placement_id", ["Placement_ID"], required=True, kind="id"),
    FieldSpec("creative_id", ["Creative_ID"], required=True, kind="id"),
    FieldSpec("site", ["Site"], required=True),
    FieldSpec("placement_name", ["Placement"], required=True),
    FieldSpec("dimensions", ["Dimensions"], required=True, kind="dims"),
    FieldSpec("legacy_dtree", ["Legacy_Decision_Tree"], kind="bool"),
    FieldSpec("group_name", ["Decision_Tree_Name"]),
    FieldSpec("group_id", ["Decision_Tree_ID"], kind="id"),
    FieldSpec("filename", ["Filename"]),
    FieldSpec("placement_type", ["Placement_Type"], required=True),
    FieldSpec("placement_creative_id", ["Placement_Creative_ID"], kind="id"),
    FieldSpec("start_date", ["Start_Date"], required=True, kind="date"),
    FieldSpec("end_date", ["End_Date"], required=True, kind="date"),
    FieldSpec("third_party_id", ["Third_Party_ID"], kind="id"),
    FieldSpec("creative_name", ["Creative_Name"]),
    FieldSpec("clicktag_count", ["ClickTags"], kind="number"),
    FieldSpec("rotation", ["Rotation"], kind="number"),
    FieldSpec("clicktag", ["Clicktag"], kind="url", multi=True),
    FieldSpec("third_party_impression", ["Third_Party_Impression"], kind="url", multi=True),
    FieldSpec("third_party_survey", ["Third_Party_Survey"], kind="url", multi=True),
    FieldSpec("creative_group", ["Creative_Group"], multi=True),
    # Status puede faltar en Innovid Current Views.
    # La ausencia desactiva las reglas de estado mediante Capability Profile,
    # pero no bloquea las demás validaciones disponibles.
    FieldSpec("status", ["Status"], required=False),
    FieldSpec("stopped", ["Stopped"], kind="bool"),
    FieldSpec("ad_type", ["Ad_Type"]),
    FieldSpec("creative_type", ["Creative_Type"]),
]

INNOVID_PLACEMENT_CREATIVE = SheetSpec(
    sheet_aliases=["Import"],
    header_mode="fixed_row",
    header_row=10,
    signature_min_matches=6,
    fields=_PC_FIELDS,
    metadata_labels=INNOVID_METADATA_LABELS,
    metadata_scan_rows=9,
    # Un creativo real siempre tiene Filename o Creative_Name.
    # Solo se exige a las filas que declaran Creative_ID: las filas de
    # cabecera de placement no lo tienen y deben conservarse (bug B34).
    entity_identity_any=["filename", "creative_name"],
    entity_identity_when=["creative_id"],
)

# --- export nivel Placement (URL de 1x1 + integracion de pixel)
_PL_FIELDS = [
    FieldSpec("site_id", ["Site_ID"], kind="id"),
    FieldSpec("placement_id", ["Placement_ID"], required=True, kind="id"),
    FieldSpec("site", ["Site"], required=True),
    FieldSpec("placement_name", ["Placement"], required=True),
    FieldSpec("dimensions", ["Dimensions"], required=True, kind="dims"),
    FieldSpec("start_date", ["Start_Date"], required=True, kind="date"),
    FieldSpec("end_date", ["End_Date"], required=True, kind="date"),
    FieldSpec("placement_type", ["Placement_Type"], required=True),
    # Status puede faltar en Innovid Current Views.
    # La ausencia desactiva las reglas de estado mediante Capability Profile,
    # pero no bloquea las demás validaciones disponibles.
    FieldSpec("status", ["Status"], required=False),
    FieldSpec("hidden", ["Hidden"], kind="bool"),
    FieldSpec("stopped", ["Stopped"], kind="bool"),
    FieldSpec("booked_units", ["Booked_Units"], kind="number"),
    FieldSpec("package_id", ["Package_ID"], kind="id"),
    FieldSpec("package_name", ["Package_Name"]),
    FieldSpec("third_party_id", ["Third_Party_ID"], kind="id"),
    FieldSpec("content_category", ["Content_Category"]),
    FieldSpec("strategy", ["Strategy"]),
    FieldSpec("clicktag", ["Clicktag"], kind="url", multi=True),
    FieldSpec("third_party_impression", ["Third_Party_Impression"], kind="url", multi=True),
    FieldSpec("third_party_survey", ["Third_Party_Survey"], kind="url", multi=True),
    FieldSpec("placement_target", ["Placement_Target"]),
    FieldSpec("delivered_impressions", ["Delivered_Impressions"], kind="number"),
    FieldSpec("percent_delivered", ["Percent_Delivered"], kind="number"),
]

INNOVID_PLACEMENT = SheetSpec(
    sheet_aliases=["Import"],
    header_mode="fixed_row",
    header_row=10,
    signature_min_matches=6,
    fields=_PL_FIELDS,
    metadata_labels=INNOVID_METADATA_LABELS,
    metadata_scan_rows=9,
)

# ---------------------------------------------------------------- capability profile

CAPABILITIES: dict[str, dict] = {
    "SCOPE":             {"needs": ["placement_id"],               "rules": "SCP-001..007"},
    "IDENTITY":          {"needs": ["placement_name", "site"],     "rules": "IDN-001..005"},
    "DATES":             {"needs": ["start_date", "end_date"],     "rules": "DTE-001..005"},
    "DIMENSIONS":        {"needs": ["dimensions"],                 "rules": "DIM-001..004"},
    "STATUS":            {"needs": ["status"],                     "rules": "STA-001..002"},
    "ENABLED":           {"needs": ["enabled"],                    "rules": "STA-003..004"},
    "GROUP":             {"needs": ["group_name"],                 "rules": "GRP-001..007"},
    "CREATIVE":          {"needs": ["creative_id"],                "rules": "CRE-001..007"},
    "ROTATION":          {"needs": ["rotation"],                   "rules": "CRE-008"},
    "URL":               {"needs": ["clicktag"],                   "rules": "URL-001..004"},
    "ATTRIBUTION":       {"needs": ["third_party_id", "clicktag"], "rules": "ATR-001..003"},
    "PIXEL_INTEGRATION": {"needs": ["third_party_impression"],     "rules": "PXL-010..015"},
}

CAPABILITY_HINTS = {
    "ATTRIBUTION": "Re-exportar incluyendo Third_Party_ID.",
    "ROTATION": "Re-exportar incluyendo Rotation.",
    "PIXEL_INTEGRATION": "Se requiere el export a nivel Placement (campana completa).",
    "GROUP": "Sin Decision_Tree_Name: se valida como asignacion directa.",
    "URL": "Para 1x1 de Adobe se requiere el export a nivel Placement.",
}
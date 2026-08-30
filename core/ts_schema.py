"""
Contratos de campo para Traffic Sheets.

Principios de negocio confirmados:
  - Training Guide, QA Results y Prisma Output NUNCA son relevantes para QA2.
  - Campaign Information: solo importan campaign id/name/start/end + sites.
  - Adobe Variante B: TODA la info de trafficking vive en Placements.
  - 1x1 site-served: sin creativo declarado (N/A o vacio) es lo ESPERADO.
  - Adobe: la URL vive en Creative Rotations, NO en Landing Pages.
  - WPP (Unilever/Wendy's): Landing Pages SI usa colores para swaps de URL.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.extraction import FieldSpec, SheetSpec

# Hojas que nunca entran al scope de QA2, en ninguna cuenta
NEVER_IN_SCOPE = ["Training Guide", "QA Results", "Prisma Output"]

# Tipos de implementacion
IMPL_SITE_SERVED_1X1 = "SITE_SERVED_1X1"
IMPL_THIRD_PARTY = "THIRD_PARTY"
IMPL_UNKNOWN = "UNKNOWN"

# Formatos derivados de dimensiones
FMT_SITE_SERVED = "1x1"
FMT_VIDEO = "video"
FMT_DISPLAY = "display"
FMT_UNKNOWN = "sin_dims"

_VIDEO_DIMS = {"1920x1080", "1280x720", "640x360", "1080x1920",
               "854x480", "3840x2160", "0x0"}

def format_from_dims(value: object) -> str:
    """
    Deriva el formato de las dimensiones.
    Asi lo identifica el operador cuando filtra en la TS.
    """
    from core.normalize import norm_dims
    d = norm_dims(value)
    if not d:
        return FMT_UNKNOWN
    if d == "1x1":
        return FMT_SITE_SERVED
    if d in _VIDEO_DIMS:
        return FMT_VIDEO
    try:
        w_s, h_s = d.split("x")
        w, h = int(w_s), int(h_s)
        if w >= 640 and h >= 360 and abs((w / h) - 16 / 9) < 0.08:
            return FMT_VIDEO
    except (ValueError, ZeroDivisionError):
        pass
    return FMT_DISPLAY

# ---------------------------------------------------------------- Placements

_TS_PLACEMENT_FIELDS = [
    FieldSpec("site", ["Site Name", "Site"], required=True),
    FieldSpec("placement_id", ["Placement ID"], required=True, kind="id"),
    FieldSpec("placement_name", ["Placement Name"], required=True),
    FieldSpec("start_date", ["Start Date"], required=True, kind="date"),
    FieldSpec("end_date", ["End Date"], required=True, kind="date"),
    FieldSpec("dimensions", ["Dimensions"], required=True, kind="dims"),
    FieldSpec("group_name", ["Creative Rotation", "Creative Rotation Name",
                             "Decision Tree", "Dtree"]),
    FieldSpec("creative_names", ["Creative Names"]),
    FieldSpec("lp_ref", ["Landing Page"]),
    FieldSpec("vendors", ["Vendors / Pixels", "Vendors/Pixels"]),
    FieldSpec("rotation_weight", ["Creative Rotation %", "Rotation %"]),
    FieldSpec("cgen", ["CGEN", "CGENS"], kind="id"),
    FieldSpec("extra_requirements", ["Additional Requirements"]),
]

_PLACEMENT_INTENT = [
    "placement_id", "placement_name", "start_date", "end_date",
    "dimensions", "group_name", "creative_names", "lp_ref",
    "rotation_weight", "cgen",
]

TS_PLACEMENTS = SheetSpec(
    sheet_aliases=["Placements"],
    header_mode="signature",
    signature_scan_rows=15,
    signature_min_matches=4,
    fields=_TS_PLACEMENT_FIELDS,
)

# ---------------------------------------------------------------- Creative Rotations

_TS_ROTATION_FIELDS = [
    FieldSpec("group_name", ["Creative Rotation Name"], required=True),
    FieldSpec("creative_name", ["Creative Name"], required=True),
    FieldSpec("universal_ad_id", ["Universal Ad-ID (Video/Audio Only)",
                                  "Universal Ad-ID"], kind="id"),
    FieldSpec("creative_id", ["Creative ID"], kind="id"),
    FieldSpec("creative_type", ["Creative Type"]),
    FieldSpec("dims_or_duration", ["Dimensions / Durations",
                                    "Dimensions/Durations"]),
    FieldSpec("rotation_weight", ["Rotation (%) or Even"]),
    FieldSpec("sequence", ["Sequential"]),
    FieldSpec("start_date", ["Start Date"], kind="date"),
    FieldSpec("end_date", ["End Date"], kind="date"),
    FieldSpec("lp_url", ["Landing Page Name"], kind="url"),
    FieldSpec("companion", ["Companion Banner (For Video Only)",
                            "Companion Banner (Video/Audio Only)",
                            "Companion Banner"]),
    FieldSpec("companion_id", ["Companion Banner ID (For Video Only)",
                               "Companion Banner ID (Video/Audio Only)",
                               "Companion Banner ID"], kind="id"),
    FieldSpec("creative_links", ["Creative Links / Sharepoint Folder"]),
    FieldSpec("status_of_rotation", ["STATUS OF ROTATION (PBU)",
                                     "STATUS OF ROTATION"]),
    FieldSpec("cgen", ["CGENS", "CGEN"], kind="id"),
    FieldSpec("as_campaign", ["CAMPAIGN"]),
    FieldSpec("as_source", ["SOURCE"]),
    FieldSpec("as_content", ["CONTENT"]),
    FieldSpec("rich_media_click", ["Rich Media Click Out Event/s"]),
]

_ROTATION_INTENT = [
    "group_name", "creative_name", "creative_id", "universal_ad_id",
    "start_date", "end_date", "lp_url", "cgen", "rotation_weight",
    "status_of_rotation",
]

TS_ROTATIONS = SheetSpec(
    sheet_aliases=["Creative Rotations", "Creative Rotation"],
    header_mode="signature",
    signature_scan_rows=15,
    signature_min_matches=4,
    fields=_TS_ROTATION_FIELDS,
    fill_down=["group_name"],
    ignore_row_patterns=[
        r"^\d{1,2}\.\d{1,2}\.\d{2,4}\s+UPDATE$",
        r"^Options to denote",
        r"^Example .* Rotation$",
        r"Default .* Ad$",
        r"^\[object Object\]$",
    ],
    entity_identity_any=["creative_name", "creative_id"],
)

# ---------------------------------------------------------------- Landing Pages

_TS_LP_FIELDS = [
    FieldSpec("lp_name", ["Landing Page Name"], required=True),
    FieldSpec("lp_url", ["Landing Page URL"], required=True, kind="url"),
    FieldSpec("as_content", ["as_content"]),
    FieldSpec("io", ["IO"]),
    FieldSpec("fmt", ["Format"]),
]

_LP_INTENT = ["lp_name", "lp_url"]

TS_LANDING_PAGES = SheetSpec(
    sheet_aliases=["Landing Pages", "Landing Page"],
    header_mode="signature",
    signature_scan_rows=15,
    signature_min_matches=2,
    fields=_TS_LP_FIELDS,
    fill_down=["lp_name"],
)

# ---------------------------------------------------------------- Campaign Info

# Solo lo que un revisor de QA2 necesita
CAMPAIGN_INFO_LABELS = [
    "campaignid", "campaignname", "campaignstart", "campaignend",
]

TS_CAMPAIGN_INFO = SheetSpec(
    sheet_aliases=["Campaign Information", "Campaign Info"],
    header_mode="labels",
    metadata_labels=CAMPAIGN_INFO_LABELS,
    metadata_scan_rows=45,
)

# Etiqueta que abre la tabla de sites y contactos
SITE_TABLE_ANCHORS = ["sitename", "sitecontactemail"]

# ---------------------------------------------------------------- perfil

@dataclass
class TSProfile:
    name: str
    placements: SheetSpec
    rotations: SheetSpec | None
    campaign_info: SheetSpec
    intent_fields: dict[str, list[str]] = field(default_factory=dict)
    url_source: str = "rotations"
    creatives_in_placements: bool = False
    landing_pages_in_scope: bool = False
    propagate_from_rotations: bool = False     # <-- NUEVA
    notes: str = ""

ADOBE_A = TSProfile(
    name="adobe_variante_a",
    placements=TS_PLACEMENTS,
    rotations=TS_ROTATIONS,
    campaign_info=TS_CAMPAIGN_INFO,
    intent_fields={"placements": _PLACEMENT_INTENT, "rotations": _ROTATION_INTENT},
    url_source="rotations",
    creatives_in_placements=False,
    landing_pages_in_scope=False,
    # Adobe declara el trabajo en Placements. Creative Rotations acumula
    # color historico de solicitudes anteriores: propagar inflaria el scope.
    propagate_from_rotations=False,
    notes="3P con Decision Tree. Landing Pages NO es fuente de verdad.",
)

ADOBE_B = TSProfile(
    name="adobe_variante_b",
    placements=TS_PLACEMENTS,
    rotations=None,
    campaign_info=TS_CAMPAIGN_INFO,
    intent_fields={"placements": _PLACEMENT_INTENT},
    url_source="placements",
    creatives_in_placements=True,
    landing_pages_in_scope=False,
    propagate_from_rotations=False,
    notes="1x1 / 3P directo. TODO el trafficking vive en Placements.",
)

WPP_STANDARD = TSProfile(
    name="wpp_standard",
    placements=TS_PLACEMENTS,
    rotations=TS_ROTATIONS,
    campaign_info=TS_CAMPAIGN_INFO,
    intent_fields={"placements": _PLACEMENT_INTENT,
                   "rotations": _ROTATION_INTENT,
                   "landing_pages": _LP_INTENT},
    url_source="landing_pages",
    creatives_in_placements=False,
    landing_pages_in_scope=True,
    # WPP declara los swaps en Creative Rotations y Landing Pages,
    # con los placements en blanco. Aqui la propagacion es obligatoria.
    propagate_from_rotations=True,
    notes="Plantilla WPP. Landing Pages SI usa colores para swaps de URL.",
)

PROFILES = {p.name: p for p in (ADOBE_A, ADOBE_B, WPP_STANDARD)}
"""
Analisis de los archivos de tags, fila por fila y columna por columna.

Lo que habia hasta ahora era un conteo por archivo ("45 placements, 225
tags") y las reglas TAG-0xx sueltas entre los demas findings. Ninguna de
las dos cosas responde lo que se pregunta quien hace el QA delante de un
archivo de tags:

  - Estan todos los placements que pide la Traffic Sheet.
  - Cada fila trae las columnas que le tocan por su tipo: un 1x1 lleva
    impresion y click, un display lleva sus tags de display, un video
    lleva su VAST.
  - Y, cuando hace falta mirar uno, poder ver el tag entero.

Camilo: "realmente todos se envian, entonces es muy dificil analizarlos
todos, por eso validamos con los screenshots que algunos sirvan y ya que
esten todos los placements que dice la ts en esos tags."

De ahi que esto no juzgue el contenido de cada tag -- eso ya lo hacen las
reglas TAG-001..011 -- sino la COBERTURA: que no falte ninguna fila y que
a ninguna fila le falte una columna.

Las columnas que se esperan no estan escritas a mano en ningun lado: se
deducen del propio archivo. Si en un archivo veinte filas de display
traen `js_https`, `if_https`, `async_https` e `ins`, y una sola trae tres
de las cuatro, esa es la que hay que mirar. Asi no hay que perseguir el
catalogo de columnas de Innovid cada vez que cambia.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from core.normalize import norm_dims, norm_key
from parsers.innovid_tags import (
    TAG_1X1_CLICK,
    TAG_1X1_IMPRESSION,
    TAG_DISPLAY_ASYNC,
    TAG_DISPLAY_IFRAME,
    TAG_DISPLAY_INS,
    TAG_DISPLAY_JS,
    TAG_DV_HTML,
    TAG_DV_VAST,
    TAG_PIXEL,
    TAG_PIXEL_HTML,
    TAG_VIDEO_VAST,
)

# Familias de placement, en el orden en que se muestran.
ONE_BY_ONE = "1x1"
DISPLAY = "Display"
VIDEO = "Video"
AUDIO = "Audio"
UNKNOWN = "Unknown"

FAMILIES = (ONE_BY_ONE, DISPLAY, VIDEO, AUDIO, UNKNOWN)

DISPLAY_TYPES = frozenset({
    TAG_DISPLAY_JS,
    TAG_DISPLAY_IFRAME,
    TAG_DISPLAY_ASYNC,
    TAG_DISPLAY_INS,
})

# En un 1x1 la impresion puede venir como pixel o como el "ftrack 1x1
# imp" de Adobe. Son el mismo papel con dos nombres segun la cuenta.
IMPRESSION_TYPES = frozenset({
    TAG_1X1_IMPRESSION,
    TAG_PIXEL,
    TAG_PIXEL_HTML,
})

CLICK_TYPES = frozenset({TAG_1X1_CLICK})

VAST_TYPES = frozenset({TAG_VIDEO_VAST})

# El tag de DoubleVerify viaja como una columna mas del archivo de
# Innovid, pero no lo lleva todo placement: solo los que la TS pide con
# DV. Su ausencia la juzga la reconciliacion de DV Omni, no esto.
VERIFICATION_TYPES = frozenset({TAG_DV_VAST, TAG_DV_HTML})


def _family(dimensions: str, filled_types: set[str], columns: set[str]) -> str:
    """
    A que tipo de placement corresponde una fila.

    Primero por lo que la fila trae puesto, que es lo que de verdad
    dice que es; las dimensiones solo deciden cuando la fila viene
    vacia, que es justo el caso en que hay que nombrarla igual.
    """
    dims = norm_dims(dimensions)

    if dims == "1x1":
        return ONE_BY_ONE

    if filled_types & DISPLAY_TYPES:
        return DISPLAY

    if filled_types & VAST_TYPES:
        # El audio sale por el mismo VAST; lo distingue la columna.
        if any("audio" in name.casefold() for name in columns):
            return AUDIO
        return VIDEO

    if filled_types & (IMPRESSION_TYPES | CLICK_TYPES):
        return ONE_BY_ONE

    # Fila sin un solo tag: queda por las dimensiones, y si tampoco hay,
    # sin familia. Las dos cosas se reportan.
    if dims in ("", "0x0"):
        return UNKNOWN
    return DISPLAY


def _required_missing(family: str, filled_types: set[str]) -> list[str]:
    """
    Lo que a una fila le falta para servir, por su tipo.

    Es el minimo de sentido, no el conteo de columnas: un 1x1 sin click
    no mide clicks, un video sin VAST no se puede pedir. Que falte una
    de las cuatro variantes de display es otra cosa -- eso sale por
    comparacion con sus hermanas, mas abajo.
    """
    # Una fila con un placement ID y ni un tag es el caso que mas
    # duele encontrar tarde: el archivo la lista, pero no entrega
    # nada. Se ve venir antes de mirar de que tipo era.
    if not filled_types:
        return ["any tag at all"]

    if family == ONE_BY_ONE:
        missing = []
        if not filled_types & IMPRESSION_TYPES:
            missing.append("impression tag")
        if not filled_types & CLICK_TYPES:
            missing.append("click tag")
        return missing

    if family == DISPLAY:
        return [] if filled_types & DISPLAY_TYPES else ["display tag"]

    if family in (VIDEO, AUDIO):
        return [] if filled_types & VAST_TYPES else ["VAST tag"]

    return []


def _column_order(columns: list[str], name: str) -> int:
    """Posicion de una columna en el orden del archivo."""
    key = norm_key(name)
    for index, column in enumerate(columns):
        if norm_key(column) == key:
            return index
    return len(columns)


@dataclass
class TagRowAnalysis:
    """Una fila del archivo de tags, ya juzgada."""
    file_name: str
    sheet: str
    row: int
    placement_id: str
    placement_name: str = ""
    third_party_id: str = ""
    dimensions: str = ""
    prisma_id: str = ""
    family: str = UNKNOWN
    filled: dict[str, str] = field(default_factory=dict)
    missing_columns: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    in_ts: bool | None = None

    @property
    def tag_count(self) -> int:
        return len(self.filled)

    @property
    def status(self) -> str:
        if self.missing_required:
            return "FAIL"
        if self.missing_columns or self.in_ts is False:
            return "REVIEW"
        return "PASS"

    @property
    def note(self) -> str:
        parts = []
        if self.missing_required == ["any tag at all"]:
            parts.append(
                "This row carries a Placement ID but not a single tag"
            )
        elif self.missing_required:
            family = "row" if self.family == UNKNOWN else self.family
            parts.append(
                f"A {family} placement with no "
                + " and no ".join(self.missing_required)
            )
        if self.missing_columns:
            parts.append(
                "Empty where every other "
                f"{self.family} row in this file has a tag: "
                + ", ".join(self.missing_columns)
            )
        if self.in_ts is False:
            parts.append("This placement is not in the Traffic Sheet")
        return ". ".join(parts)


@dataclass
class FamilySummary:
    """El panel de arriba, una linea por tipo de placement."""
    family: str
    rows: int = 0
    placements: int = 0
    tags: int = 0
    complete: int = 0
    incomplete: int = 0
    failed: int = 0
    columns: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.failed:
            return "FAIL"
        return "REVIEW" if self.incomplete else "PASS"


@dataclass
class TagAnalysis:
    rows: list[TagRowAnalysis] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    families: list[FamilySummary] = field(default_factory=list)
    # Placements que la TS pide trabajar y no aparecen en ningun
    # archivo de tags. Es la mitad de la validacion que Camilo hace a
    # mano: "que esten todos los placements que dice la ts".
    missing_from_tags: list[dict] = field(default_factory=list)
    ts_worked: int = 0
    ts_covered: int = 0

    @property
    def total_tags(self) -> int:
        return sum(row.tag_count for row in self.rows)

    @property
    def placements(self) -> int:
        return len({row.placement_id for row in self.rows if row.placement_id})

    @property
    def incomplete(self) -> list[TagRowAnalysis]:
        return [row for row in self.rows if row.status != "PASS"]

    @property
    def coverage_known(self) -> bool:
        """Si no hubo TS legible, no se puede hablar de cobertura."""
        return self.ts_worked > 0


def _worked_placements(ts_result) -> dict[str, str]:
    """Los placements que la solicitud pide trabajar, con su nombre."""
    from parsers.ts_parser import REQ_NOT_WORKED

    if ts_result is None or not getattr(ts_result, "scope", None):
        return {}

    worked = {
        placement_id
        for placement_id, scope in ts_result.scope.items()
        if scope.request_type != REQ_NOT_WORKED
    }

    names: dict[str, str] = {placement_id: "" for placement_id in worked}

    if getattr(ts_result, "placements", None):
        for row in ts_result.placements.rows:
            placement_id = str(row.values.get("placement_id") or "").strip()
            if placement_id in names and not names[placement_id]:
                names[placement_id] = str(
                    row.values.get("placement_name") or ""
                ).strip()

    return names


def analyse_tags(tags_results, ts_result=None) -> TagAnalysis:
    """
    Junta todos los archivos de tags en un solo analisis.

    `tags_results` es la lista de (nombre de archivo, TagsResult) tal
    como la arma la app.
    """
    analysis = TagAnalysis()

    columns: list[str] = []
    rows: list[TagRowAnalysis] = []
    # (archivo, familia) -> con que frecuencia se llena cada columna.
    seen: dict[tuple[str, str], Counter] = defaultdict(Counter)
    group_rows: dict[tuple[str, str], int] = defaultdict(int)

    for file_name, result in tags_results or []:
        file_columns = list(getattr(result, "tag_columns", {}) or {})
        for name in file_columns:
            # Dos cuentas escriben la misma columna distinto ("DISQO" y
            # "disqo"). Son la misma columna: dos en la tabla serian
            # dos huecos donde no hay ninguno.
            if norm_key(name) not in {norm_key(c) for c in columns}:
                columns.append(name)

        for row in result.rows:
            filled = {
                tag.column_name: tag.raw
                for tag in row.tags
                if not tag.is_empty
            }
            filled_types = {
                tag.tag_type for tag in row.tags if not tag.is_empty
            }
            family = _family(row.dimensions, filled_types, set(file_columns))

            analysed = TagRowAnalysis(
                file_name=file_name,
                sheet=result.sheet,
                row=row.row,
                placement_id=row.placement_id,
                placement_name=row.placement_name,
                third_party_id=row.third_party_id,
                dimensions=row.dimensions,
                prisma_id=row.prisma_id,
                family=family,
                filled=filled,
                missing_required=_required_missing(family, filled_types),
            )
            rows.append(analysed)

            key = (file_name, family)
            group_rows[key] += 1
            for name in filled:
                seen[key][name] += 1

    # Segunda pasada: una columna se espera en un grupo cuando la
    # llenan TODAS sus filas menos esta. Con "la mayoria" bastaria para
    # ensuciar el informe cada vez que una cuenta manda dos formatos
    # revueltos en el mismo archivo.
    for analysed in rows:
        key = (analysed.file_name, analysed.family)
        total = group_rows[key]
        if total < 2:
            continue
        for name, times in seen[key].items():
            if name in analysed.filled:
                continue
            # Columnas de verificacion aparte: DV no va en todos los
            # placements y su ausencia no es un hueco.
            if times == total - 1:
                analysed.missing_columns.append(name)
        analysed.missing_columns.sort(key=lambda c: _column_order(columns, c))

    worked = _worked_placements(ts_result)
    in_tags = {row.placement_id for row in rows if row.placement_id}

    if worked:
        for analysed in rows:
            if analysed.placement_id:
                analysed.in_ts = analysed.placement_id in worked
        analysis.ts_worked = len(worked)
        analysis.ts_covered = len(set(worked) & in_tags)
        analysis.missing_from_tags = [
            {
                "Placement ID": placement_id,
                "Placement Name": name or "-",
            }
            for placement_id, name in sorted(worked.items())
            if placement_id not in in_tags
        ]

    analysis.rows = rows
    analysis.columns = columns

    for family in FAMILIES:
        family_rows = [row for row in rows if row.family == family]
        if not family_rows:
            continue
        used: list[str] = []
        for row in family_rows:
            for name in row.filled:
                if norm_key(name) not in {norm_key(u) for u in used}:
                    used.append(name)
        analysis.families.append(
            FamilySummary(
                family=family,
                rows=len(family_rows),
                placements=len(
                    {r.placement_id for r in family_rows if r.placement_id}
                ),
                tags=sum(r.tag_count for r in family_rows),
                complete=len([r for r in family_rows if r.status == "PASS"]),
                incomplete=len([r for r in family_rows if r.status != "PASS"]),
                failed=len([r for r in family_rows if r.status == "FAIL"]),
                columns=sorted(
                    used, key=lambda c: _column_order(columns, c)
                ),
            )
        )

    return analysis


def _same_column(filled: dict[str, str], name: str) -> str:
    """La misma columna escrita con otras mayusculas."""
    key = norm_key(name)
    for column, raw in filled.items():
        if norm_key(column) == key:
            return raw
    return ""


def import_table(analysis: TagAnalysis) -> list[dict]:
    """
    El archivo de tags tal como se importaria, con el veredicto delante.

    Camilo: "la estructura me gustaria con todas las columnas de tags,
    literal como si fuera importar los tags". De ahi que las columnas de
    tag salgan enteras y en el orden del archivo: esta tabla se lee, se
    filtra y se copia.
    """
    table = []
    for row in analysis.rows:
        record = {
            "Status": row.status,
            "File": row.file_name,
            "Row": row.row,
            "Placement ID": row.placement_id,
            "Placement Name": row.placement_name,
            "Third Party ID": row.third_party_id,
            "Dimensions": row.dimensions,
            "Type": row.family,
            "Tags": row.tag_count,
            "QA Note": row.note,
        }
        for name in analysis.columns:
            record[name] = row.filled.get(name, "") or _same_column(
                row.filled, name
            )
        table.append(record)
    return table


def dv_table(dv_result) -> list[dict]:
    """El archivo de DV Pinnacle, fila por fila."""
    if dv_result is None:
        return []

    table = []
    for row in dv_result.rows:
        has_display = bool(row.display_tag.strip())
        has_video = bool(row.video_tag.strip())
        table.append(
            {
                "Status": "PASS" if row.has_tag else "FAIL",
                "Row": row.row,
                "Placement ID": row.placement_id,
                "Placement Name": row.placement_name,
                "Has Display Tag": "Yes" if has_display else "No",
                "Has Video Tag": "Yes" if has_video else "No",
                "QA Note": (
                    "" if row.has_tag
                    else "This row carries no DV tag at all"
                ),
                "Display Site-Served Tag": row.display_tag,
                "Video Site-Served Tag": row.video_tag,
            }
        )
    return table

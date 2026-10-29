# QA2 — Referencia técnica

**Para:** desarrolladores que mantienen QA2 y asistentes de código
(por ejemplo, GitHub Copilot) que necesitan entender el proyecto antes
de proponer un cambio.

**Cómo usar este documento:** cada sección responde una pregunta concreta
y señala el archivo y la función donde está la respuesta. Para buscar
una función por nombre, usa [`MAPA_DEL_CODIGO.md`](MAPA_DEL_CODIGO.md),
que se genera desde el código. Para el catálogo completo de reglas y
las trampas de Streamlit, usa [`GUIA_TECNICA.md`](GUIA_TECNICA.md).
Para la revisión de seguridad, [`SEGURIDAD.md`](SEGURIDAD.md).

---

## Índice

1. [Qué hace QA2, en términos de negocio](#1-qué-hace-qa2-en-términos-de-negocio)
2. [Glosario](#2-glosario)
3. [El recorrido completo de una corrida](#3-el-recorrido-completo-de-una-corrida)
4. [Lectura de archivos (`parsers/`)](#4-lectura-de-archivos-parsers)
5. [Colores e intención](#5-colores-e-intención)
6. [Emparejamiento TS contra Innovid (`core/matching.py`)](#6-emparejamiento-ts-contra-innovid)
7. [Hallazgos y veredictos (`core/findings.py`, `core/verdict.py`)](#7-hallazgos-y-veredictos)
8. [Reglas (`rules/`)](#8-reglas)
9. [Conciliaciones especializadas](#9-conciliaciones-especializadas)
10. [Archivos JSON de configuración](#10-archivos-json-de-configuración)
11. [Acceso a Innovid y Playwright](#11-acceso-a-innovid-y-playwright)
12. [Reportes: Excel, PDF y hoja QA](#12-reportes-excel-pdf-y-hoja-qa)
13. [La interfaz (`ui/app_v2.py`)](#13-la-interfaz)
14. [Rutas, variables de entorno y archivos que escribe](#14-rutas-variables-de-entorno-y-archivos-que-escribe)
15. [Pruebas](#15-pruebas)
16. [Empaquetado y distribución](#16-empaquetado-y-distribución)
17. [Recetas de cambios frecuentes](#17-recetas-de-cambios-frecuentes)
18. [Preguntas frecuentes](#18-preguntas-frecuentes)

---

## 1. Qué hace QA2, en términos de negocio

En Ad Operations, cada solicitud de campaña llega como una **Traffic
Sheet (TS)**: un Excel donde el cliente pide placements, creativos,
fechas, landing pages y píxeles. Alguien lo implementa en **Innovid**
(Campaign Manager, antes Flashtalking). Después, otra persona hace el
**segundo QA**: compara la TS contra lo que quedó en Innovid.

QA2 automatiza ese segundo QA:

| Entra | Sale |
|---|---|
| La TS (`.xlsx` / `.xlsm`) | Un hallazgo por cada comprobación: PASS, FAIL, REVIEW, NOT_VERIFIED o INFO |
| El export *Placement-Creative View* de Innovid (obligatorio) | Dos veredictos: Implementation y Tags & pixels |
| El export *Placement View* (recomendado) | Un Excel y un PDF con la marca, la evidencia y las firmas |
| Los archivos de tags entregados (opcional) | Un *session bundle* para pasarle la revisión a otra persona |
| Los exports de DV Pinnacle (opcional) | |
| Una consulta a Innovid con la sesión del analista (opcional) | |

Resultado medido: 55 segundos para una solicitud de 156 placements,
contra unos 5 minutos por decision set a mano.

Cuentas con soporte: Adobe (con sus campañas), Unilever, Wendy's y
BlackRock. Formatos de TS: Adobe Variante A (Decision Tree), Adobe
Variante B (Direct & Site-Served) y WPP Standard.

## 2. Glosario

| Término | Qué significa en QA2 |
|---|---|
| **TS / Traffic Sheet** | El Excel de la solicitud. Pestañas que importan: *Campaign Information*, *Placements*, *Creative Rotations*, *Landing Pages* |
| **Placement** | Un espacio publicitario comprado en un sitio. Se identifica por `Placement ID` |
| **Creative** | Una pieza (imagen, video, HTML). Se identifica por `Creative_ID`, `Universal Ad-ID` o nombre de archivo |
| **Creative Rotation / Decision Tree (DTree)** | El grupo de creativos que rota en un placement. En el export: `Decision_Tree_Name` |
| **Decision Set (DSet)** | Dentro de un DTree, la regla que reparte creativos con fechas y pesos. Solo se ve por la API de Innovid |
| **Rotation weight** | El porcentaje de cada creativo en la rotación |
| **1x1 / site-served** | Placement donde el sitio sirve el creativo; Innovid solo pone un píxel 1x1. La TS dice `N/A` en el creativo |
| **Clicktag** | La URL a la que lleva el clic. Se compara con la landing page de la TS |
| **CGEN / CGENS** | Código de atribución de Adobe. Debe coincidir en la TS, en el `Third_Party_ID` de Innovid y en el parámetro `sdid` de la URL (el "triángulo") |
| **Vendor / píxel** | Medición de terceros (DV, DISQO, iSpot, Dynata...). Va en las columnas *Third Party Survey* o *Third Party Impression* |
| **DV Pinnacle / DV Omni** | Productos de DoubleVerify: Pinnacle entrega tags envueltos; Omni va como columna en el archivo de tags |
| **Tags** | El archivo que se entrega al sitio con el código de cada placement |
| **Scope / alcance trabajado** | Lo que la TS pide cambiar en esta solicitud. Lo demás es contexto |
| **Finding / hallazgo** | El resultado de una comprobación, con su evidencia |
| **Session bundle** | Un `.zip` con los archivos cargados y las elecciones del analista, para que quien revisa no vuelva a subir nada |

## 3. El recorrido completo de una corrida

```
 Traffic Sheet        Placement-Creative      Placement View     Tags / DV Pinnacle
      |                      |                      |                    |
 parse_ts()       parse_innovid_export()   parse_innovid_export()  parse_innovid_tags()
 parsers/ts_parser   parsers/innovid_export        |              parse_dv_tags()
      |                      |                      |                    |
      +----------+-----------+----------------------+                    |
                 v                                                       |
        match(ts, export_pc, export_pl)  -> MatchResult                  |
        core/matching.py                                                 |
                 |                                                       |
                 |-- (opcional) fetch_campaign() -> reconcile()          |
                 |   core/innovid_api.py   core/innovid_reconciliation.py|
                 v                                                       v
        run_rules(match_result, innovid_reconciliation=..., ts_result=...)
        core/engine.py  -> FindingsBuffer
                 |
                 |-- + reconciliaciones de tags, píxeles, DV y default ads
                 |     (cada una con su evaluate() sobre el mismo buffer)
                 v
        verdicts_by_scope()  core/verdict.py
                 |
        build_qa_rows()  build_excel_report()  build_pdf_report()
```

En la interfaz, la secuencia vive en la sección *Processing* de
`ui/app_v2.py`. Resumida, con los nombres reales:

```python
ts_result = cached_parse_ts(ts_bytes, ts_name, profile)        # parsers/ts_parser.parse_ts
pc_result = cached_parse_innovid_export(pc_bytes, pc_name)     # parsers/innovid_export
pl_result = cached_parse_innovid_export(pl_bytes, pl_name)     # opcional
match_result = match(ts_result, pc_result, pl_result)          # core/matching.match

innovid_result = cached_fetch_innovid(campaign_id, worked_ids, refresh=run_clicked)
innovid_reconciliation = reconcile_innovid(match_result, innovid_result)

findings_buffer = run_rules(
    match_result,
    account=selected_account,
    innovid_reconciliation=innovid_reconciliation,
    ts_result=ts_result,
)

# Después, cada conciliación especializada agrega sus hallazgos
# al mismo buffer: adobe_pixels, adobe_tag_policy, tag_coverage,
# dv_tags, dv_omni, pixels y defaults.
```

`run_rules()` también acepta esas conciliaciones como argumentos
(`adobe_pixel_reconciliation=`, `pixel_reconciliation=`, etc.). Así lo
usan el CLI y las pruebas. La interfaz las evalúa aparte porque
algunas dependen de archivos opcionales.

**Primera función para leer:** `run_rules()` en `core/engine.py`. Es la
lista completa y ordenada de lo que QA2 comprueba.

## 4. Lectura de archivos (`parsers/`)

Los parsers leen y normalizan. **No deciden** si algo está bien o mal.

### Traffic Sheet — `parsers/ts_parser.py`

```python
def parse_ts(path: Path, profile_name: str | None = None) -> TSResult
```

1. Separa las pestañas en alcance, fuera de alcance y ocultas
   (`_split_sheets`).
2. Detecta el formato con `detect_profile()`: `adobe_variante_a`,
   `adobe_variante_b` o `wpp_standard` (definidos en `core/ts_schema.py`,
   `PROFILES`). El analista puede forzarlo en la interfaz.
3. Lee *Campaign Information* (Campaign ID, sitios).
4. Lee *Placements*, *Creative Rotations* y *Landing Pages* con
   `core/extraction.py`, capturando el **color de relleno** de cada celda.
5. Arma el alcance: qué placements y creativos se trabajaron
   (`_build_groups`, `_build_scope`).

El resultado (`TSResult`) guarda las pestañas leídas, el perfil,
el alcance y una lista de `anomalies`. Una anomalía `FATAL` (por
ejemplo, un encabezado borrado) bloquea la corrida con `EXT-000`.

**Cómo se encuentran las columnas.** Cada campo se declara una vez,
con sus posibles nombres, en `core/ts_schema.py`:

```python
FieldSpec("placement_id", ["Placement ID"], required=True, kind="id"),
FieldSpec("group_name", ["Creative Rotation", "Creative Rotation Name",
                         "Decision Tree", "Dtree"]),
FieldSpec("cgen", ["CGEN", "CGENS"], kind="id"),
```

Si una TS trae la columna con otro nombre, se agrega el alias ahí, en
una línea. El encabezado se busca por "firma": la fila con más nombres
reconocidos dentro de las primeras 15.

### Exports de Innovid — `parsers/innovid_export.py`

```python
def parse_innovid_export(path: Path, sheet_name: str | None = None) -> ExportResult
```

Lee la pestaña `Import`, con el encabezado en la fila 10 y los
metadatos (Campaign ID, fechas, anunciante) en las filas 1 a 9. Los
campos están en `core/schema.py` (`_PC_FIELDS`): `Placement_ID`,
`Creative_ID`, `Decision_Tree_Name`, `Clicktag`, `Third_Party_ID`,
`Third_Party_Impression`, `Third_Party_Survey`, `Status`, `Enabled`,
entre otros. Sirve igual para *Placement-Creative View* y *Placement View*.

### Tags — `parsers/innovid_tags.py`

```python
def parse_innovid_tags(path: Path) -> TagsResult
```

Lee el archivo de tags tal como se entrega: una fila por placement y
una columna por tipo de tag. Clasifica cada columna
(`_classify_tag_header`), extrae URLs y hosts y anota problemas
estructurales. `core/tag_analysis.py` lo resume para el panel de tags.

### DV Pinnacle — `parsers/dv_tags.py`

```python
def parse_dv_tags(path: Path) -> DVTagsResult
def merge_dv_results(results: list[DVTagsResult]) -> DVTagsResult | None
```

Admite varios archivos (un archivo por partner) y los junta.

### Utilidades de normalización

| Archivo | Para qué |
|---|---|
| `core/normalize.py` | Textos, IDs (`clean_id`), dimensiones (`norm_dims`, `dims_match`), pesos (`normalize_weights`) |
| `core/dates.py` | Fechas ambiguas (día/mes) de una columna entera: `resolve_date_column` |
| `core/urls.py` | URLs por componentes (`parse_url`, `compare_urls`) y el triángulo CGEN (`check_triangle`) |
| `core/provenance.py` | `CellRef`: de qué archivo, hoja, fila y columna salió cada valor |

## 5. Colores e intención

En la TS, **el color de relleno es la solicitud**. `core/colors.py`
convierte el color en una familia con `classify(rgb)`, que trabaja en
HSV para tolerar verdes y amarillos pálidos:

| Color | Constante | Significado | Qué hace QA2 |
|---|---|---|---|
| Verde | `GREEN` | Nuevo, o valor nuevo de un cambio | Debe existir y estar activo en Innovid |
| Rojo | `RED` | Quitar, o valor viejo de un cambio | Debe estar desasignado o detenido |
| Amarillo | `YELLOW` | En espera | Fuera de alcance, sin hallazgos |
| Gris | `GREY` | No trabajado | Fuera de alcance, sin hallazgos |
| Blanco | `WHITE` | Contexto existente | Se muestra; no se juzga salvo que tenga hijos trabajados |
| Otro | `UNKNOWN` | No se adivina | REVIEW |

**Se pinta la celda, no la fila.** Si solo está pintada la celda de
*Rotation %*, solo se pidió cambiar el peso. Eso se guarda en
`ExpectedCreative.intent_fields`, y las reglas preguntan con
`core/intent.py`:

```python
from core.intent import requested

if requested(creative, "dates"):   # ¿se pidió cambiar las fechas?
    ...                            # entonces se comparan
```

Aspectos disponibles: `rotation`, `dates`, `url`, `name`, `identity`,
`sequence`. La existencia del creativo se valida siempre.

## 6. Emparejamiento TS contra Innovid

```python
def match(ts, export_pc, export_pl=None) -> MatchResult
```

Pasos:

1. **Scope guard.** Compara el Campaign ID de la TS con el del export.
   Si difieren, lo anota (`scope_guard = "MISMATCH"`) pero sigue: en
   Adobe la TS declara el ID de Prisma, que nunca coincide con el de
   Innovid.
2. **Expected:** `build_expected(ts)` arma un `ExpectedPlacement` por
   placement trabajado, con sus `ExpectedCreative`.
3. **Actual:** `build_actual(export_pc, export_pl)` arma un
   `ActualPlacement` por placement del export, con sus `ActualCreative`.
4. **Placements:** se emparejan por `Placement ID`. Sin pareja, el
   placement va a `only_expected`.
5. **Creativos** (`_match_creatives`), en este orden de llaves:

| Llave | Confianza |
|---|---|
| `creative_id` igual | HIGH |
| `universal_ad_id` igual al `Creative_ID` | HIGH |
| Nombre de archivo o nombre normalizado, un solo candidato | MEDIUM |
| Nombre normalizado, varios candidatos | LOW |

6. **Comparación** (`compare_placement`): URLs, triángulo CGEN, extras
   que siguen corriendo (`extra_running`) o detenidos (`extra_stopped`).

Cada enlace guarda un `MatchTrace` con las llaves probadas, la que
ganó y las descartadas. Así se puede explicar cualquier emparejamiento.

**Regla clave:** sin un emparejamiento fuerte no hay FAIL. Un FAIL con
confianza menor que HIGH se convierte en REVIEW (ver sección 7).

Estructuras principales:

```python
@dataclass
class PlacementMatch:
    placement_id: str
    expected: ExpectedPlacement        # lo que pide la TS
    actual: ActualPlacement | None     # lo que hay en Innovid
    confidence: str                    # HIGH | MEDIUM | LOW | NONE
    creative_links: list[CreativeLink] # un enlace por creativo esperado
    actual_extra: list[ActualCreative] # en Innovid y no en la TS
    url: URLComparison | None
    triangle: AttributionTriangle | None

@dataclass
class MatchResult:
    scope_guard: str                   # OK | MISMATCH | UNKNOWN
    matched: list[PlacementMatch]
    only_expected: list[ExpectedPlacement]
    only_actual_in_scope: list[ActualPlacement]
    ...
```

`ActualCreative.running` decide si un creativo está corriendo: no lo
está si `Enabled = No` o si `Status` es Disabled, Inactive o Paused.

## 7. Hallazgos y veredictos

### El hallazgo

Todo resultado es un `Finding` (`core/findings.py`). Campos principales:

| Campo | Ejemplo |
|---|---|
| `rule_id` | `"URL-001"` |
| `domain` | `Domain.URL` |
| `status` | `Status.FAIL` |
| `severity` | `Severity.ERROR` |
| `message` | `"Clicktag differs from the TS landing page"` |
| `placement_id`, `creative_id`, nombres | IDs de la entidad |
| `expected`, `actual` | Lo que pedía la TS y lo que hay |
| `reason`, `recommended_action` | Por qué y qué hacer |
| `confidence` | `HIGH`, `MEDIUM`, `LOW`, `NONE` |
| `evidence` | Valores crudos y normalizados de ambos lados, con su origen |

`finding_id` es determinista: el mismo hallazgo da el mismo ID en cada
corrida.

### Cómo emite una regla

Las reglas no crean `Finding` a mano. Usan el `FindingsBuffer`:

```python
buffer.pass_(rule_id, domain, message, **campos)
buffer.fail(rule_id, domain, message, **campos)
buffer.review(rule_id, domain, message, **campos)
buffer.not_verified(rule_id, domain, message, **campos)
buffer.info(rule_id, domain, message, **campos)
buffer.blocker(rule_id, domain, message, **campos)   # FAIL con severidad BLOCKER
```

Antes de guardar, el buffer aplica tres controles:

1. **Capacidad** (`_gate_capability`): si la regla declaró
   `requires=[Capability.X]` y ese insumo no está, el hallazgo baja a
   `NOT_VERIFIED`.
2. **Confianza** (`_gate_confidence`): un FAIL con confianza menor que
   HIGH baja a `REVIEW`.
3. **Coherencia** (`_enforce_coherence`): PASS siempre con severidad
   NONE, FAIL con ERROR o BLOCKER, REVIEW con WARN.

### El veredicto

`Scorecard.verdict` (`core/findings.py`):

```
BLOCKED       hay al menos un BLOCKER
FAILED        hay al menos un FAIL           (se muestra "REQUIRES CORRECTION")
NEEDS_REVIEW  hay REVIEW o NOT_VERIFIED      (se muestra "REVIEW REQUIRED")
PASSED        solo PASS e INFO
NO_CHECKS     no hubo comprobaciones
```

`core/verdict.py` lo calcula dos veces:

| Alcance | Dominios |
|---|---|
| Implementation | Todos menos `Pixel` y `Tag` |
| Tags & pixels | `Pixel` y `Tag` |

El veredicto general es el peor de los dos. La separación existe porque
un píxel que el vendor aún no manda no significa que la implementación
esté mal.

## 8. Reglas

Una familia por archivo en `rules/`. Cada módulo expone `evaluate(...)`.
El catálogo completo, con el detalle de cada ID, está en
[`GUIA_TECNICA.md`](GUIA_TECNICA.md) §4. Resumen:

| Archivo | IDs | Qué analiza | Recibe |
|---|---|---|---|
| `placements.py` | PLC-001, 002, 007 | El placement existe; la desasignación se aplicó; la rotación tiene creativos de su tamaño | `MatchResult` |
| `naming.py` | PLC-006 | El Placement Name coincide | `MatchResult` |
| `creatives.py` | CRE-001, 002 | Cada creativo pedido está (o ya no está); el 1x1 site-served tiene su píxel | `MatchResult` |
| `rotation.py` | ROT-001 | El cambio de rotación se aplicó | `MatchResult` |
| `urls.py` | URL-001, 002, 003 | Clicktag contra landing page | `MatchResult` |
| `attribution.py` | ATR-001, 002 | Triángulo CGEN (solo cuentas con CGEN) | `MatchResult` + cuenta |
| `dtree.py`, `dset.py` | TRK-001, 002 | Decision Tree y Decision Set correctos | `MatchResult` |
| `innovid.py` | INV-001 a 004 | Fechas del creativo en el DSet, pesos, Verification Partner | `InnovidReconciliation` |
| `tags.py` | TAG-001 a 011, 014 | Estructura del archivo de tags | `TagMatchResult` |
| `tag_coverage.py` | TAG-013 | Todos los placements pedidos están en el archivo de tags | conciliación |
| `adobe_tag_policy.py` | TAG-012 | Columnas de Adobe: FTRACK, No FTRACK, Clicktag, Protected | conciliación |
| `pixels.py` | PIX-002 | Píxel de cada vendor en su columna | conciliación |
| `adobe_pixels.py` | PIX-A01 | Píxeles oficiales de Adobe (DISQO, iSpot) | conciliación |
| `dv_tags.py` | DV-001, 002 | Tags de DV Pinnacle | conciliación |
| `dv_omni.py` | DV-003 | Columnas de DV Omni en los tags | conciliación |
| `defaults.py` | DEF-001 | El default ad es el mismo por dimensión | conciliación |

Una regla completa y real, `rules/dtree.py`:

```python
def evaluate(match_result, buffer):
    for pm in match_result.matched:
        for cl in pm.creative_links:
            if cl.triangle is None:
                continue
            expected = getattr(cl.triangle, "expected_dtree", None)
            actual = getattr(cl.triangle, "actual_dtree", None)
            if not expected and not actual:
                continue
            if expected == actual:
                buffer.pass_(rule_id="TRK-001", domain=Domain.ATTRIBUTION,
                             message="DTree is correct",
                             placement_id=pm.placement_id)
            else:
                buffer.fail(rule_id="TRK-001", domain=Domain.ATTRIBUTION,
                            message="DTree mismatch",
                            placement_id=pm.placement_id,
                            expected=expected, actual=actual)
```

## 9. Conciliaciones especializadas

Cuando una comprobación necesita cruzar más de dos fuentes, primero se
**concilia** en `core/` y después una regla convierte el resultado en
hallazgos. Así la lógica se prueba sin el buffer.

| Conciliación | Función | Fuentes que cruza | Regla |
|---|---|---|---|
| Innovid API | `core/innovid_reconciliation.reconcile(match_result, innovid_result)` | MatchResult + API de Innovid | `rules/innovid.py` |
| Píxeles de vendor | `core/pixel_reconciliation.reconcile_pixels(ts_result, placement_view, account)` | TS (*Vendors / Pixels*) + Placement View + `vendor_pixels.json` | `rules/pixels.py` |
| Píxeles de Adobe | `core/adobe_pixel_reconciliation.reconcile_adobe_pixels(...)` | TS + Placement View + tags + `vendor_pixels_adobe.json` | `rules/adobe_pixels.py` |
| Política de tags Adobe | `core/adobe_tag_policy_reconciliation.reconcile_adobe_tag_policy(ts_result, inventory)` | TS + inventario de tags | `rules/adobe_tag_policy.py` |
| Cobertura de tags | `core/tag_coverage_reconciliation.reconcile_tag_coverage(ts_result, inventory)` | TS + inventario de tags | `rules/tag_coverage.py` |
| DV Pinnacle | `core/dv_reconciliation.reconcile_dv_tags(...)` | TS + exports de DV | `rules/dv_tags.py` |
| DV Omni | `core/dv_omni_reconciliation.reconcile_dv_omni(ts_result, placement_view, tag_inventory)` | TS + Placement View + tags | `rules/dv_omni.py` |
| Default ads | `core/default_ads.reconcile_default_ads(ts_result, placement_creative)` | TS + Placement-Creative | `rules/defaults.py` |

El inventario de tags (`core/tag_inventory.py`, `TagInventory`) junta
varios archivos de tags en una sola vista por Placement ID.

## 10. Archivos JSON de configuración

Viven en `config/`. Son **tablas editables desde la app** y no llevan
secretos ni datos de cliente. Se pueden compartir por SharePoint con
`QA2_CONFIG_DIR` (sección 14). Si un archivo falta, QA2 usa los valores
de fábrica que trae el código.

### `config/vendor_pixels.json` — vendors por cuenta

Lista de objetos. Lo lee `core/pixel_reconciliation.load_vendors()`.

```json
{
  "account": "",
  "name": "DV Monitoring",
  "ts_terms": ["dv", "doubleverify"],
  "host_terms": ["doubleverify.com"],
  "column": "third_party_survey",
  "formats": ["display"],
  "site_exceptions": [],
  "official_pixel": "",
  "note": "Placement-level pixel, Display only. ..."
}
```

| Campo | Qué hace |
|---|---|
| `account` | Cuenta a la que aplica. Vacío = todas |
| `name` | Nombre que aparece en el hallazgo |
| `ts_terms` | Cómo aparece el vendor en la columna *Vendors / Pixels* de la TS |
| `host_terms` | Cómo se reconoce su píxel en Innovid (dominio). Si está vacío y hay `official_pixel`, se deriva de esa URL |
| `column` | Dónde debe estar: `third_party_survey` o `third_party_impression` |
| `formats` | A qué formatos aplica: `display`, `video`, `1x1` |
| `site_exceptions` | Sitios donde nunca aplica, aunque la TS lo pida |
| `official_pixel` | URL de referencia con macros. Si existe, el píxel encontrado se compara contra ella (`pixel_matches_official`) |
| `note` | Explicación para quien lee la tabla |

### `config/vendor_pixels_adobe.json` — píxeles oficiales de Adobe

Lista de objetos. Lo lee `core/adobe_pixel_reconciliation.load_adobe_vendor_rows()`.

```json
{
  "name": "DISQO",
  "campaign": "Adobe Acrobat",
  "official_pixel": "https://track.activemetering.com/pixel/v1/all/pixel.gif?cid=...&creativeId=[%creativeID%]&placementId=[%placementID%]...",
  "note": "Adobe Acrobat Q3 FT Universal."
}
```

`campaign` vacío significa que aplica a todas las campañas de Adobe.
Si la evidencia encontrada no tiene la misma estructura que el píxel
oficial, un PASS baja a REVIEW (`_flag_official_pixel_drift`).

### `config/team_roster.json` — equipo por cuenta

```json
{
  "Unilever": ["Nombre Apellido", "..."],
  "Adobe": ["..."],
  "Support": ["None"]
}
```

Llena los selectores de *Implemented by* y de quien firma. Lo lee
`core/team_roster.py`.

### Archivos que NO son configuración compartida

| Archivo | Formato | Notas |
|---|---|---|
| `config/innovid_session.json` | `storage_state` de Playwright: `{"cookies": [...], "origins": [...]}` | Equivale a la contraseña mientras no vence. Fuera de Git, local siempre |
| `config/innovid_credentials.env` | Líneas `INNOVID_USERNAME=...`, `INNOVID_PASSWORD=...`, opcional `INNOVID_LOGIN_URL=...` | Vía de respaldo, no recomendada. Fuera de Git, local siempre |
| `.streamlit/config.toml` | TOML | `address = "localhost"`, XSRF activo, telemetría apagada. Hay pruebas que lo vigilan |

## 11. Acceso a Innovid y Playwright

### Por qué existe

Tres datos no vienen en ningún export: el **Verification Partner** del
placement, el **peso de rotación** de cada creativo y las **fechas del
creativo dentro del decision set**. La interfaz de Innovid los lee de
una API interna. QA2 los pide de la misma forma, con la sesión del
analista. La conexión es opcional: sin ella, esas comprobaciones salen
`NOT_VERIFIED`.

### Qué es Playwright aquí

Una librería de Microsoft que controla un Chromium. QA2 la usa para
dos cosas: abrir una ventana para que el analista inicie sesión, y
hacer consultas desde una página ya autenticada. El Chromium viene
dentro del paquete (`browsers/`); `core/innovid_login.ensure_browser_path()`
apunta `PLAYWRIGHT_BROWSERS_PATH` a esa carpeta.

### Funciones (`core/innovid_api.py`)

| Función | Qué hace |
|---|---|
| `establish_session()` | Abre Chromium **visible**. El analista inicia sesión a mano. Espera a que la API responda bien y guarda `innovid_session.json` |
| `fetch_campaign(campaign_id, credentials, placement_ids, headless=True)` | Abre Chromium **en segundo plano** con la sesión guardada y lee la campaña. Nunca lanza excepción: los errores van en `.errors` |
| `_api_get_json(page, url, csrf_token, method, body)` | Hace la consulta **dentro de la página**, con `fetch()` y la cabecera `X-Csrf-Token` |
| `parse_summary_response()` / `parse_dset_response()` | Convierten la respuesta JSON en `InnovidPlacement` / `InnovidCreativeNode`. Funciones puras, probadas sin navegador |
| `session_is_saved()`, `session_expires_at()`, `session_has_expired()` | Estado de la sesión guardada |
| `load_credentials()` | Lee `innovid_credentials.env` si existe (vía de respaldo) |
| `redact_url()`, `redact_body()` | Limpian URLs y cuerpos antes de registrarlos: descartan URLs de login y ocultan valores |
| `diagnose_session()`, `record_api_calls()` | Diagnóstico desde la terminal (`check_innovid_connection.py`) |

`core/innovid_login.start_innovid_login()` lanza el inicio de sesión
como subproceso desde la app y espera unos segundos para saber si la
ventana abrió de verdad.

### Las llamadas

| Método | URL | Trae |
|---|---|---|
| `POST` | `https://api.flashtalking.net/cm/v1/ui/campaigns/{id}/summary?fields=...` | Una fila por placement y creativo: estado, fechas, clicktag, píxeles, Verification Partner, peso, IDs de DTree y DSet. Paginado de 500, máximo 40 páginas |
| `GET` | `https://api.flashtalking.net/dt/v1/ui/dset/{modernDtreeId}` | Los nodos del decision set: creativo, fechas, peso, default |

El `POST` es una consulta: el cuerpo solo lleva paginación y filtros.
Ninguna llamada crea, modifica ni borra nada. Solo se consultan los
decision sets de los placements trabajados.

El corazón de la consulta, tal como corre dentro de la página:

```javascript
async ([url, method, body, csrf]) => {
    const headers = { 'Accept': 'application/json',
                      'X-Requested-With': 'XMLHttpRequest' };
    if (csrf) headers['X-Csrf-Token'] = csrf;
    const options = { method, headers, credentials: 'include' };
    ...
    const response = await fetch(url, options);
    return { status: response.status, text: await response.text() };
}
```

### Errores y qué significan

| Respuesta | Causa probable | Qué hace QA2 |
|---|---|---|
| 401 | La sesión venció | Pide iniciar sesión otra vez |
| 403 | Token CSRF viejo, o la cuenta no ve esa campaña | Recarga la página y reintenta **una** vez; si sigue, lo informa |
| 5xx | Problema de Innovid | Lo informa como problema del lado de Innovid |
| Fallos repetidos del mismo tipo | La API limita o algo cambió | Para tras 3 (`GIVE_UP_AFTER_FAILED_LOOKUPS`) |

### Caché

`cached_fetch_innovid()` en la interfaz guarda la respuesta una hora
(`INNOVID_CACHE_SECONDS = 3600`). Solo el botón *Run QA2* vuelve a
consultar; aprobar o filtrar reutiliza lo descargado. Una respuesta
totalmente fallida no se guarda.

### Desde la terminal

```bash
python check_innovid_connection.py --login          # iniciar sesión a mano
python check_innovid_connection.py 323492           # probar la lectura de una campaña
python check_innovid_connection.py 323492 --show    # lo mismo, viendo el navegador
python check_innovid_connection.py --diagnose       # revisar la sesión guardada
```

## 12. Reportes: Excel, PDF y hoja QA

| Archivo | Función | Qué produce |
|---|---|---|
| `core/qa_export.py` | `build_qa_rows(match_result, findings, innovid_reconciliation, ...)` | La hoja QA: una fila por creativo, TS contra Innovid, con estado y notas de firma |
| `core/excel_report.py` | `build_excel_report(...)` | Excel con resumen, hoja QA, tags y evidencia, con la marca |
| `core/pdf_report.py` | `build_pdf_report(...)` | PDF con veredicto, firmas, métricas y evidencia. Los metadatos van en `ReportMeta` |
| `core/report_name.py` | `report_filename(...)` | Nombre del archivo: `Fecha_QA_Report_CampaignName` |

Las firmas manuales ("MANUALLY Approved by ...") convierten un REVIEW en
PASS con la nota de quién lo aprobó y por qué. Se marcan en morado en el
Excel.

## 13. La interfaz

Todo lo visible está en `ui/app_v2.py`. Streamlit vuelve a ejecutar el
archivo entero en cada clic, así que el orden del archivo es el orden de
la página. El docstring del módulo lista las secciones.

Conceptos que hay que saber antes de tocarla:

- **Caché de lectura:** `cached_parse_ts`, `cached_parse_innovid_export`,
  `cached_parse_innovid_tags` y `cached_parse_dv_tags` evitan releer los
  archivos en cada clic.
- **`reuse(slot, signature, build)`:** construye el Excel y el PDF solo
  cuando cambia el estado (por ejemplo, una firma nueva).
- **`st.session_state`:** guarda las firmas, la caché de Innovid y si ya
  se corrió el QA (`qa2_has_run`).
- **Session bundle:** *Save session bundle* arma un `.zip` con los
  archivos cargados y un `manifest.json` (perfil, cuenta, campaña,
  quién implementó, fecha). Quien revisa lo carga en *Load a saved
  session*. No lleva credenciales.
- **Trampas de Streamlit** (pestañas que ejecutan todo, expanders,
  reruns): [`GUIA_TECNICA.md`](GUIA_TECNICA.md) §6.

## 14. Rutas, variables de entorno y archivos que escribe

`core/paths.py` decide dónde lee y escribe QA2. Lee el entorno en cada
llamada, así que basta reiniciar la app después de cambiar una variable.

| Variable | Para qué | Por defecto |
|---|---|---|
| `QA2_CONFIG_DIR` | Carpeta de las tablas compartidas (vendors, Adobe, roster) | `config/` del proyecto |
| `QA2_OUTPUT_DIR` | Carpeta del log de corrida y de la evidencia | `logs/` del proyecto |
| `PLAYWRIGHT_BROWSERS_PATH` | Dónde está Chromium | `browsers/` del paquete, si existe |

```python
shared_config_path("vendor_pixels.json")                  # lee la compartida, si no la local
shared_config_path("vendor_pixels.json", for_write=True)  # escribe en la compartida
shared_config_path("innovid_session.json")                # SIEMPRE local
```

QA2 escribe solo esto: `logs/qa_run.log` (etapas y tiempos, sin datos de
cliente), el archivo de PID para *Stop QA2.bat* (`core/pidfile.py`), las
tablas cuando alguien las edita y la sesión de Innovid. Los reportes los
descarga el analista donde elija.

## 15. Pruebas

```bash
python -m pytest tests/                       # todas
python -m pytest tests/test_innovid_api.py    # un archivo
python -m pytest tests/ -k "csrf"             # por palabra en el nombre
```

Requisitos: `pip install -r requirements.txt -r requirements-dev.txt`.

Cómo están organizadas:

- **Un archivo por comportamiento.** El docstring del archivo cuenta el
  caso real que lo originó. La lista completa, con lo que protege cada
  uno, está en [`MAPA_DEL_CODIGO.md`](MAPA_DEL_CODIGO.md#pruebas-tests).
- **Nombres que afirman algo:** `test_a_missing_pixel_does_not_sink_the_implementation`.
- **Fixtures:** `tests/fixtures/`. Las TS reales no se suben (llevan
  datos de cliente); se suben solo sus resúmenes `.expected.json`.
- **Seguridad:** `tests/test_config_locations.py` vigila localhost,
  telemetría, XSRF, hosts salientes, credenciales fuera de Git y del
  paquete, y que ningún archivo nombre un proveedor de IA o un correo
  personal.
- **Innovid sin red:** las pruebas de `test_innovid_*.py` usan respuestas
  JSON guardadas, funciones puras o un servidor falso en `127.0.0.1` con
  un Chromium real. Nunca llaman a Innovid. Si no hay Chromium instalado,
  esas pruebas se saltan con un motivo (`tests/_browser.py`).

## 16. Empaquetado y distribución

| Comando | Produce | Cuándo |
|---|---|---|
| `python scripts/build_bundle.py` | `dist/QA2-<versión>-windows.zip` (~500 MB): Python portátil, librerías, Chromium y el código | Cambios en arranque, `.bat`, `requirements.txt` o el lock |
| `python scripts/package_release.py --update` | `dist/QA2-<versión>-update.zip` (~600 KB): solo código | Cambios de reglas o de interfaz |

Los dos excluyen las credenciales, la sesión y las hojas de cálculo, y
se niegan a terminar si encuentran una. El paso a paso está en
[`COMANDOS.md`](COMANDOS.md). Antes de empaquetar: subir `VERSION` y
anotar el cambio arriba de [`CHANGELOG.md`](CHANGELOG.md); la app
muestra los dos.

## 17. Recetas de cambios frecuentes

### Agregar o cambiar una regla
1. Busca la familia en `rules/` (sección 8). Familia nueva = archivo
   nuevo + una línea en `run_rules()` (`core/engine.py`).
2. Emite con el buffer (sección 7). Si falta el insumo, `not_verified()`,
   nunca `pass_()`.
3. Escribe la prueba en `tests/`.
4. `python -m pytest tests/` y anota en `CHANGELOG.md`.

### Una TS trae una columna con otro nombre
Agrega el alias en el `FieldSpec` correspondiente de `core/ts_schema.py`.
Para exports de Innovid, en `core/schema.py`.

### Agregar un vendor de píxeles
Desde la app (tabla editable de vendors) o en `config/vendor_pixels.json`
(sección 10). No hace falta tocar código.

### Actualizar un píxel oficial de Adobe
Desde la app o en `config/vendor_pixels_adobe.json`.

### Una cuenta nueva sin CGEN
Agrégala a `NON_CGEN_ACCOUNTS` en `core/urls.py`.

### Un formato nuevo de TS
Nuevo `TSProfile` en `core/ts_schema.py`, agregado a `PROFILES`, y una
pista para `detect_profile()` en `parsers/ts_parser.py`. Prueba con una
fixture en `tests/test_ts_reading.py`.

### Innovid cambió su API
Todo está en `core/innovid_api.py`: URLs (`CM_BASE`, `DT_BASE`), campos
(`SUMMARY_FIELDS`) y parseo (`parse_summary_response`,
`parse_dset_response`). `check_innovid_connection.py --record` muestra,
limpias, las llamadas que hace la interfaz de Innovid.

### Después de cualquier cambio de código
```bash
python -m pytest tests/
python scripts/generate_code_map.py      # actualiza MAPA_DEL_CODIGO.md
```

## 18. Preguntas frecuentes

### Funcionamiento

**¿Por qué un hallazgo salió REVIEW y no FAIL?**
Porque el emparejamiento no tuvo confianza HIGH (por ejemplo, el
creativo se encontró por nombre y había dos parecidos), o porque la
regla lo marca como algo que una persona debe mirar. El campo
`degrade_reason` dice cuál fue.

**¿Por qué salió NOT_VERIFIED?**
Faltaba el insumo: por ejemplo, el peso de rotación sin Innovid
conectado, o los píxeles sin Placement View. El motivo está en `reason`.

**¿Por qué un placement no aparece en el reporte?**
No está en el alcance trabajado: su color era gris o amarillo, o es
blanco sin nada trabajado debajo.

**¿Qué pasa si la TS y el export tienen distinto Campaign ID?**
Se anota como evidencia y el emparejamiento sigue por Placement ID. En
Adobe es normal: la TS usa el ID de Prisma.

**¿Por qué un 1x1 no pide decision set?**
Porque en site-served el creativo va directo al placement y hereda sus
fechas. Ver `is_site_served_1x1()` en `core/matching.py`.

**¿Cómo decide QA2 si un creativo está corriendo?**
`ActualCreative.running`: no corre si `Enabled = No` o si su `Status`
es Disabled, Inactive o Paused.

**¿Cómo se comparan las URLs?**
Por componentes (`core/urls.compare_urls`): host en minúsculas, ruta
normalizada, parámetros como conjunto (el orden no importa) y sin
fragmento.

**¿Qué es el triángulo CGEN?**
Para Adobe, el CGEN debe coincidir en tres lugares: la TS, el
`Third_Party_ID` de Innovid y el parámetro `sdid` de la URL.
`check_triangle()` dice cuál de los tres no coincide.

### Seguridad y accesos

**¿QA2 puede modificar algo en Innovid?**
No. Solo hace un `POST` de consulta y un `GET`. No hay ninguna llamada
que escriba.

**¿Con qué permisos entra a Innovid?**
Con los del analista que inició sesión. No hay cuenta de servicio ni
llave de API.

**¿Dónde queda la contraseña?**
En el método recomendado, en ningún lado: el analista la escribe en la
página de Mediaocean y QA2 no la lee. Solo se guarda la sesión, en
`config/innovid_session.json`, local y fuera de Git.

**¿Qué sale de la máquina?**
Solo las consultas a `api.flashtalking.net` y el login en
`uam-login.mediaocean.com` / `campaign-manager.flashtalking.net`. Una
prueba falla si el código empieza a llamar a otro host.

**¿Usa IA en tiempo de ejecución?**
No. Las reglas son Python determinista.

**¿Qué guarda el log?**
Etapas y tiempos. Las URLs de login se descartan y los cuerpos se
reducen a nombres de campo.

### Operación

**La ventana de inicio de sesión no abre.**
Casi siempre falta Chromium en el paquete. `core/innovid_login.missing_browser_reason()`
explica la causa. Con el paquete completo no debería pasar.

**Innovid responde 401.**
La sesión venció. Iniciar sesión otra vez desde la app.

**Innovid responde 403.**
QA2 ya reintentó una vez. Si sigue, la cuenta no tiene acceso a esa
campaña, o la sesión se guardó antes de que Innovid terminara de cargar:
iniciar sesión otra vez y dejar que cargue una campaña.

**¿Cómo comparto las tablas con el equipo?**
Con `QA2_CONFIG_DIR` apuntando a una carpeta sincronizada de SharePoint
(sección 14).

**¿Cómo actualizo la app del equipo?**
`package_release.py --update` para cambios de código, `build_bundle.py`
para cambios de arranque o dependencias. Ver [`COMANDOS.md`](COMANDOS.md).

**Algo falla en la máquina de alguien.**
Pedir `logs/qa_run.log`, o que corra `DIAGNOSTICO QA2.bat` y mande
`logs/diagnostico.txt`.

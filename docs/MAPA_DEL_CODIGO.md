# QA2 — Mapa del código

Índice generado automáticamente desde el código por `scripts/generate_code_map.py`. No se edita a mano: después de cambiar el código se vuelve a generar con `python scripts/generate_code_map.py`.

Para entender **cómo** encaja todo, empieza por [`REFERENCIA_TECNICA.md`](REFERENCIA_TECNICA.md). Este mapa responde **dónde** está cada cosa.

## `core/` — Motor: emparejamiento, conciliaciones, hallazgos, veredicto, reportes

### `core/__init__.py`

Motor de QA2: todo lo que no es interfaz ni lectura de archivos. *(17 lineas)*

### `core/adobe_no_ftrack_reconciliation.py`

Adobe No Ftrack tag reconciliation. *(495 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `NoFtrackResult` |  |
| clase | `NoFtrackCheck` |  |
| clase | `NoFtrackReconciliation` |  |
| funcion | `_normalize_column(value: object) -> str` | Normalize tag column names |
| funcion | `_is_no_ftrack(value: object) -> bool` | Detect No Ftrack requirements using normalized business text |
| funcion | `_populated_columns(inventory: TagInventory, placement_id: str) -> tuple[set[str], list[str], list[str]]` | Return only populated tag cells for one Placement ID |
| funcion | `_has_pixel(columns: set[str]) -> bool` | Detect the operational Pixel column for No Ftrack |
| funcion | `_has_update_clicktag(columns: set[str]) -> bool` |  |
| funcion | `_has_static_clicktag(columns: set[str]) -> bool` |  |
| funcion | `_has_ftrack_impression(columns: set[str]) -> bool` |  |
| funcion | `_has_ftrack_click(columns: set[str]) -> bool` |  |
| funcion | `_worked_no_ftrack_placements(ts_result) -> dict[str, dict]` | Materialize one record per worked placement that requires No Ftrack |
| funcion | `reconcile_adobe_no_ftrack(ts_result, inventory: TagInventory) -> NoFtrackReconciliation` |  |

### `core/adobe_pixel_reconciliation.py`

Adobe pixel reconciliation. *(923 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `adobe_vendor_config_path(*, for_write: bool=False) -> Path` |  |
| funcion | `_default_adobe_vendor_rows() -> list[dict]` | Los pixeles oficiales que Adobe tiene hoy, de fabrica |
| funcion | `load_adobe_vendor_rows() -> list[dict]` |  |
| funcion | `save_adobe_vendor_rows(rows: list[dict]) -> None` |  |
| funcion | `_official_pixels(campaign: str='') -> dict[str, str]` | {vendor name -> official pixel}, skipping blanks |
| funcion | `_evidence_value(evidence_line: str) -> str` | "row 12 \| third_party_impression \| <url>" -> "<url>" |
| clase | `PixelResult` |  |
| clase | `PixelRequirement` |  |
| clase | `AdobePixelCheck` |  |
| clase | `AdobePixelReconciliation` |  |
| funcion | `_normalized_text(value: object) -> str` |  |
| funcion | `_contains_any(value: object, terms: Iterable[str]) -> bool` |  |
| funcion | `classify_vendor_requirements(value: object) -> set[PixelRequirement]` | Classify Traffic Sheet Vendors / Pixels |
| funcion | `_tag_source_has_disqo(source: TagSourceRow) -> tuple[bool, list[str]]` |  |
| funcion | `_inventory_has_disqo(inventory: TagInventory, placement_id: str) -> tuple[bool, list[str], list[str]]` |  |
| funcion | `_row_disqo_evidence(row) -> list[str]` | Find DISQO evidence in one parsed Innovid Placement View row |
| funcion | `_placement_export_disqo_index(placement_export) -> dict[str, list[str]]` |  |
| funcion | `_worked_vendor_data(ts_result) -> dict[str, dict]` | Build one vendor requirement record per worked Placement ID |
| funcion | `reconcile_adobe_pixels(ts_result, placement_export, tag_inventory: TagInventory, campaign: str='') -> AdobePixelReconciliation` | Reconcile Adobe pixel requirements by worked Placement ID |
| funcion | `_flag_official_pixel_drift(result: AdobePixelReconciliation, campaign: str='') -> AdobePixelReconciliation` | Downgrades a PASS to REVIEW when the evidence that made it pass doesn't structurally match the official pixel on record for that requirement (config/vendor_pixels_adobe.json) |

### `core/adobe_tag_policy_reconciliation.py`

Adobe tag column policy: Ftrack / No Ftrack / Clicktag / Protected. *(284 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `TagPolicyCheck` |  |
| clase | `TagPolicyReconciliation` |  |
| funcion | `_normalize_column(value: object) -> str` |  |
| funcion | `_is_pixel_column(column: str) -> bool` |  |
| funcion | `_is_static_clicktag(column: str) -> bool` |  |
| funcion | `_is_update_clicktag(column: str) -> bool` |  |
| funcion | `_is_ftrack_impression(column: str) -> bool` |  |
| funcion | `_is_ftrack_click(column: str) -> bool` |  |
| funcion | `_is_protected(column: str) -> bool` |  |
| funcion | `_populated_slots(inventory: TagInventory, placement_id: str) -> tuple[set[str], list[str]]` |  |
| funcion | `_worked_policy_placements(ts_result) -> dict[str, dict]` |  |
| funcion | `reconcile_adobe_tag_policy(ts_result, inventory: TagInventory) -> TagPolicyReconciliation` |  |

### `core/colors.py`

Resolucion y clasificacion de colores de relleno. *(220 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `read_workbook_theme(path: Path) -> dict[int, str]` | Extrae el clrScheme del workbook: {indice_theme: 'RRGGBB'} |
| funcion | `apply_tint(rgb: str, tint: float) -> str` | Algoritmo de tint de Excel: modifica luminosidad en HLS |
| funcion | `resolve_rgb(token: str \| None, theme_map: dict[int, str] \| None=None) -> str \| None` | Normaliza el token de openpyxl a RRGGBB |
| funcion | `classify(rgb: str \| None) -> tuple[str, str]` | Clasifica por familia |
| clase | `ColorResolver` | Resuelve y cachea la familia de cada token de fill de un workbook |
| clase | `ColorInfo` | Un fill distinto encontrado DENTRO de la data region |
| funcion | `inventory_region(cells_by_field: list[tuple[str, str, object]], resolver: ColorResolver) -> dict[str, ColorInfo]` | Inventaria fills solo dentro de la data region |

### `core/dates.py`

Motor de fechas. Ataca los bugs B3 y B23. *(172 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `DateColumnResult` | Resultado de resolver una columna completa de fechas |
| funcion | `_from_native(value: object) -> date \| None` |  |
| funcion | `_parts(text: str) -> tuple[int, int, int] \| None` |  |
| funcion | `_fix_year(y: int) -> int` |  |
| funcion | `_build(a: int, b: int, c: int, order: str) -> date \| None` |  |
| funcion | `resolve_date_column(raw_values: list[object], hint: str \| None=None) -> DateColumnResult` | Resuelve una columna de fechas completa |
| funcion | `excel_serial_to_date(serial: float) -> date \| None` | Serial de Excel (base 1900, con el bug historico del 29-feb-1900) |

### `core/default_ads.py`

Consistencia del default ad. *(147 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `DefaultAdCheck` |  |
| clase | `DefaultAdReconciliation` |  |
| funcion | `_creative_name(row) -> str` |  |
| funcion | `_landing_page(row) -> str` |  |
| funcion | `reconcile_default_ads(ts_result, placement_creative) -> DefaultAdReconciliation` |  |

### `core/dv_omni_reconciliation.py`

DV Omni / DV Monitoring+Blocking tag-column reconciliation (DV-003). *(278 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_format_of(dims: object) -> str` |  |
| clase | `DVOmniCheck` |  |
| clase | `DVOmniReconciliation` |  |
| funcion | `_column_content(inventory: TagInventory, placement_id: str, tag_type: str) -> str` | Raw content of the placement's doubleverify_vast/html cell, or "" |
| funcion | `_has_any_row(inventory: TagInventory, placement_id: str) -> bool` |  |
| funcion | `reconcile_dv_omni(ts_result, placement_view, tag_inventory: TagInventory) -> DVOmniReconciliation` |  |

### `core/dv_reconciliation.py`

DV Pinnacle site-served tag reconciliation (DV-001). *(177 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `DVCheck` |  |
| clase | `DVReconciliation` |  |
| funcion | `_worked_dv_data(ts_result) -> dict[str, dict]` |  |
| funcion | `reconcile_dv_tags(ts_result, tag_inventory, dv_result: DVTagsResult \| None) -> DVReconciliation` |  |

### `core/dv_subtype.py`

DV (DoubleVerify) sub-type detection, shared by every DV-related check. *(87 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_normalized(value: object) -> str` |  |
| funcion | `is_dv(vendor_raw: object) -> bool` |  |
| funcion | `dv_subtype(vendor_raw: object) -> str \| None` | Return OMNI / MONITORING / MONITORING_BLOCKING / INTEGRATION / UNDETERMINED, or None if the text doesn't mention DV at all |

### `core/engine.py`

Orquestador principal del Rule Engine QA2. *(140 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_fatal_extraction(ts_result) -> list` | Las anomalias FATAL de la lectura, de la hoja y de sus pestanas |
| funcion | `run_rules(match_result, tags_result, adobe_pixel_reconciliation, adobe_tag_policy_reconciliation, pixel_reconciliation, dv_omni_reconciliation, default_ad_reconciliation, innovid_reconciliation, account, ts_result) -> FindingsBuffer` |  |

### `core/excel_report.py`

Branded multi-tab Excel export of a QA2 run. *(625 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_excel_safe(value)` |  |
| funcion | `_write_table(ws: Worksheet, df: pd.DataFrame, start_row: int=1, status_col: str \| None=None) -> int` | Write a dataframe as a styled, filterable table |
| funcion | `_blank(value, fallback: str='') -> str` |  |
| funcion | `_summary_sheet(wb: Workbook, meta: ReportMeta, logo_path: Path \| None)` |  |
| funcion | `_qa_sheet(wb: Workbook, qa_rows: list[dict]) -> None` | El entregable en horizontal: una fila por creativo, los dos lados en columnas pareadas |
| funcion | `_audit_tab(ws) -> None` | Oculta, no borrada |
| funcion | `_colour_legend(ws, row: int) -> None` | Que significa cada color, debajo de la tabla |
| funcion | `_tags_sheet(wb, summary_rows, tags_df, coverage) -> None` | Los tags como se importarian, con el veredicto delante |
| funcion | `_evidence_sheet(wb: Workbook, images: list[tuple[str, bytes]]) -> None` | Los pantallazos de que los tags sirven, dentro del entregable |
| funcion | `build_excel_report(meta, findings_df, rules_df, files_df, placements_df, tag_coverage_df, logo_path, qa_rows, tags_df, tag_summary_rows, tag_coverage_counts, dv_tags_df, evidence_images) -> bytes` | Render the full branded QA2 workbook and return it as XLSX bytes |

### `core/extraction.py`

Capa de EXTRACCION (L1). Aqui estaba el bloqueo original. *(631 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `FieldSpec` | Contrato de un campo canonico |
| clase | `SheetSpec` | Como se lee una hoja concreta |
| clase | `SheetGrid` | La hoja completa, celda por celda, con provenance |
| funcion | `_fill_rgb(cell_obj: Any) -> str \| None` | Extrae el relleno solido como token |
| funcion | `read_sheet(path, sheet_name, capture_fill, max_rows_cap, skip_hidden) -> tuple[SheetGrid, list[Anomaly]]` | Lee una hoja completa |
| funcion | `list_sheets(path: Path, only_visible: bool=False) -> list[str]` | Lista hojas |
| funcion | `sheet_states(path: Path) -> dict[str, str]` | {nombre: 'visible' \| 'hidden' \| 'veryHidden'} |
| clase | `HeaderResult` |  |
| funcion | `find_header_row(grid: SheetGrid, spec: SheetSpec) -> tuple[HeaderResult, list[Anomaly]]` |  |
| clase | `ColumnMap` |  |
| funcion | `map_columns(grid: SheetGrid, header_row: int, spec: SheetSpec) -> tuple[ColumnMap, list[Anomaly]]` | Mapea columnas POR NOMBRE |
| funcion | `_blank_headers_with_data(grid: SheetGrid, header_row: int) -> list[tuple[int, int]]` | Columnas con datos cuyo encabezado esta vacio |
| funcion | `_column_letter(col: int) -> str` | 1 -> A, 27 -> AA |
| funcion | `_column_has_data(grid: SheetGrid, col: int, header_row: int, sample: int=_SAMPLE) -> int` | Cuantas celdas con texto hay bajo esa columna |
| funcion | `check_empty_required(grid: SheetGrid, cmap: ColumnMap, spec: SheetSpec, first_data_row: int, last_row: int) -> list[Anomaly]` | Regla EXT-001: una columna requerida presente pero 100% vacia es una ANOMALIA DE EXTRACCION, no un hallazgo de QA |
| funcion | `column_fill_rates(grid: SheetGrid, cmap: ColumnMap, spec: SheetSpec, data_rows: list[int]) -> dict[str, float]` | % de celdas con valor real por campo canonico |
| funcion | `classify_row(grid: SheetGrid, row: int, cmap: ColumnMap, spec: SheetSpec, primary_key: str) -> tuple[str, str]` | Clasifica una fila ANTES de convertirla en dato |
| funcion | `resolve_sheet(available: list[str], aliases: list[str]) -> str \| None` | Encuentra la hoja por alias |

### `core/findings.py`

core/findings.py — Esquema canónico de hallazgos del motor QA2. *(570 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `Status` | Veredicto del check |
| clase | `Severity` | Impacto operativo |
| clase | `Domain` |  |
| clase | `Phase` | Pre-QA valida la fuente; QA2 valida la implementación (#7) |
| clase | `Confidence` |  |
| clase | `EntityType` |  |
| clase | `Capability` | Qué puede verificar el motor con los insumos recibidos |
| clase | `CapabilityState` |  |
| clase | `CapabilityRegistry` | Declara una sola vez qué se puede verificar; las reglas consultan |
| clase | `SourceRef` | De dónde salió el dato |
| clase | `Evidence` | RAW y NORMALIZED de ambos lados (#10) |
| clase | `Finding` |  |
| clase | `FindingsBuffer` | Punto único de emisión |
| clase | `Scorecard` | NOT_VERIFIED es categoría propia: 100% PASS con 40 checks no verificados NO es un QA aprobado |

### `core/innovid_api.py`

Innovid Campaign Manager API client (the UI-only fields). *(2135 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `InnovidAuthError` | Login failed, or the session wasn't usable for API calls |
| clase | `InnovidCredentials` |  |
| clase | `InnovidPlacement` | One row of the campaign summary -- placement level |
| clase | `InnovidCreativeNode` | One creative inside a decision set, with the two things the exports never carry: its own flight dates and its rotation weight |
| clase | `InnovidFetchResult` |  |
| funcion | `load_credentials(path: Path \| None=None) -> InnovidCredentials \| None` | Reads config/innovid_credentials.env (KEY=value lines) |
| funcion | `_text(value) -> str` | Flattens whatever the API puts in a cell into a plain string |
| funcion | `summary_field_names(payload: dict) -> list[str]` | The field names present in a /summary response |
| funcion | `count_levels(payload: dict, into: dict[str, dict[str, int]]) -> dict` | Groups the response's rows by `level`, counting how many rows each level has and which fields carry a value on them |
| funcion | `count_filled_fields(payload: dict, into: dict[str, int]) -> dict[str, int]` | Adds to `into` the number of rows carrying a value for each field |
| funcion | `parse_summary_response(payload: dict) -> list[InnovidPlacement]` | Turns a /summary response into placement rows |
| funcion | `count_node_fields(payload: dict, into: dict[str, int]) -> dict[str, int]` | Counts how many decision-set nodes carry a value for each field |
| funcion | `_serving_id(serving) -> str` | The creative id out of a node's `serving` |
| funcion | `_serving_name(serving) -> str` |  |
| funcion | `parse_dset_response(payload: dict) -> list[InnovidCreativeNode]` | Turns a /dset/{id} response into one row per creative node |
| funcion | `_summary_url(campaign_id: str) -> str` |  |
| funcion | `_summarise_dset_failures(failures: list[tuple[str, str]], attempted: int) -> list[str]` | Collapses per-decision-set failures into one line per kind of failure, with a few example ids |
| funcion | `_dset_mismatch(dset: dict, asked_for: str, expected_name: str) -> str` | Describes how a decision set response fails to be the one asked for, or "" when it matches |
| funcion | `_dset_url(dtree_id: str) -> str` |  |
| funcion | `_venv_python_hint() -> str` | The full path of the interpreter running QA2, for pasting into a terminal |
| funcion | `_launch_browser(playwright, headless: bool)` | Starts Chromium, turning the two failures people actually hit into instructions instead of tracebacks |
| funcion | `session_is_saved(session_path: Path \| None=None) -> bool` |  |
| funcion | `session_expires_at(session_path: Path \| None=None) -> datetime \| None` | Cuando caduca la sesion guardada, leyendo solo el archivo |
| funcion | `session_has_expired(session_path: Path \| None=None) -> bool` | True solo cuando consta que caduco |
| funcion | `redact_url(url: str) -> str` | Prepares a recorded URL for someone to paste somewhere |
| funcion | `redact_body(url: str, body: str \| None) -> str` | Summarises a request body as keys, with values shown only for the keys that describe the request |
| funcion | `record_api_calls(campaign_id, credentials, session_path, timeout_ms) -> list[str]` | Opens Innovid in a normal window and writes down which API calls its own interface makes while a person clicks around |
| funcion | `diagnose_session(campaign_id: str, session_path: Path \| None=None, headless: bool=True) -> list[str]` | Reports why a saved session can't call Innovid's API |
| funcion | `establish_session(session_path: Path \| None=None, login_url: str=APP_ORIGIN, timeout_ms: int=300000) -> str` | Opens a normal browser window and waits for a human to sign in, then saves the session so later runs don't have to |
| funcion | `_csrf_from_page(page) -> str` | Lee el token CSRF de donde Innovid lo guarda: sessionStorage |
| funcion | `_csrf_from_cookies(context) -> str` | Ultimo recurso: una cookie CSRF, pero solo de Innovid |
| funcion | `_wait_for_csrf(page, captured: dict, timeout_ms: int) -> bool` | Waits for the app to make an API call of its own, which is where the CSRF token comes from |
| funcion | `_looks_like_sign_in(page) -> bool` | True when the browser is showing a sign-in rather than the app -- either a password box, or a URL that left the Innovid domain for an identity provider |
| funcion | `_wait_until_window_closed(page, timeout_ms: int) -> bool` | Blocks until the person closes the browser window, or the time runs out |
| funcion | `_wait_for_api_cookies(api_ok: dict, timeout_ms: int, page) -> bool` | Waits until Innovid's API has answered the app at least once |
| funcion | `_wait_until_signed_in(page, timeout_ms: int) -> bool` | True once the browser is sitting on Innovid itself with no password box in sight |
| funcion | `fetch_campaign(campaign_id, credentials, placement_ids, headless, timeout_ms, session_path) -> InnovidFetchResult` | Reads a campaign from Innovid's API using a browser session |
| funcion | `_login(page, credentials: InnovidCredentials, timeout_ms: int) -> None` | Drives the sign-in, handling both shapes we can hit: one page with both boxes, and the two-step flow (address, Next, then password) that corporate SSO uses |
| funcion | `_submit_step(page, box, timeout_ms: int=20000) -> None` | Moves one step forward in the sign-in |
| funcion | `_moved_on(page, box, before_url: str, timeout_ms: int=4000) -> bool` | True once the sign-in has advanced without a navigation: the box that was just filled left the page, as happens on single-page forms that swap the screen in place |
| funcion | `_wait_for_any(page, selectors, timeout_ms: int)` | Waits until any one of `selectors` is attached to the page |
| funcion | `_safe_title(page) -> str` |  |
| funcion | `_describe_inputs(page) -> str` | Lists the input boxes on the page by their identifying attributes |
| funcion | `_first_visible(page, selectors)` |  |
| funcion | `_api_get_json(page, url: str, csrf_token: str, method: str='GET', body=None, _retried: bool=False)` | Runs the API call inside the logged-in page, so the session cookie rides along automatically and we only have to add the CSRF header |

### `core/innovid_login.py`

Arrancar el inicio de sesion de Innovid, y saber si arranco. *(184 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `LoginStart` |  |
| funcion | `bundled_browser_dir(root: Path) -> Path \| None` | La carpeta de navegadores del paquete, si este es un paquete |
| funcion | `ensure_browser_path(root: Path \| None=None) -> Path \| None` | Pone PLAYWRIGHT_BROWSERS_PATH en ESTE proceso, si el paquete trae navegador propio |
| funcion | `missing_browser_reason(root: Path) -> str` | Por que no hay navegador, dicho para quien lo va a leer |
| funcion | `start_innovid_login(root: Path \| None=None, settle: float=SETTLE_SECONDS) -> LoginStart` | Lanza check_innovid_connection.py --login y mira si sobrevivio |

### `core/innovid_reconciliation.py`

Lo que la Traffic Sheet pide contra lo que Innovid realmente tiene. *(534 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `CreativeFlightCheck` | Un creativo de la TS frente a su nodo en el decision set |
| clase | `VerificationPartnerCheck` |  |
| clase | `InnovidReconciliation` | Todo lo que se pudo comparar, y todo lo que no |
| funcion | `_dates_differ(left: date \| None, right: date \| None) -> bool` | Solo compara cuando ambos lados existen |
| funcion | `reconcile(match_result, innovid_result) -> InnovidReconciliation` | Cruza los placements trabajados de la TS con lo que trajo Innovid |
| funcion | `_normalize_weights(out: InnovidReconciliation) -> None` | Lleva los pesos de los dos lados a porcentajes, placement por placement |
| funcion | `_asks_for_dv_blocking(pm) -> bool` | Si la TS pide DV Blocking en este placement |
| funcion | `_is_site_served_1x1(pm) -> bool` | Un 1x1 de tracking servido por el sitio |
| funcion | `_expected_creatives(pm) -> list` | Los creativos que la TS declara para el placement |
| funcion | `_compare_creatives(pid, expected, nodes, out, export_ids=None) -> None` |  |
| funcion | `_node_date(value: str) -> date \| None` |  |
| funcion | `flights_by_creative(reconciliation) -> dict[tuple[str, str], CreativeFlightCheck]` | Indice (placement, nombre normalizado) -> lo que Innovid tiene |

### `core/intent.py`

Que se pidio cambiar de un creativo, campo por campo. *(60 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `requested(creative, aspect: str) -> bool` | ¿La TS pidio cambiar este aspecto de este creativo? |
| funcion | `rotation_only(creative) -> bool` | ¿Lo unico que se pidio fue la rotacion? |

### `core/matching.py`

Matching Engine. *(1179 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_as_date(value: object) -> date \| None` | Deja pasar solo fechas reales |
| funcion | `norm_creative(value: object) -> str` | Forma canonica para comparar nombres de creativo y filenames |
| clase | `ExpectedCreative` |  |
| clase | `ExpectedPlacement` |  |
| clase | `ActualCreative` |  |
| clase | `ActualPlacement` |  |
| clase | `MatchTrace` |  |
| clase | `CreativeLink` |  |
| clase | `PlacementMatch` |  |
| clase | `MatchResult` |  |
| funcion | `build_expected(ts) -> dict[str, ExpectedPlacement]` | Expected Model, solo con los placements TRABAJADOS |
| funcion | `build_actual(export_pc, export_pl=None) -> dict[str, ActualPlacement]` | Actual Model desde los exports de Innovid |
| funcion | `_match_group(ep: ExpectedPlacement, ap: ActualPlacement, ts_declares_groups: bool=True) -> tuple[str, MatchTrace]` | ts_declares_groups: la TS de este perfil TIENE columna de grupo |
| funcion | `is_site_served_1x1(expected) -> bool` | Un 1x1 de tracking servido por el sitio |
| funcion | `placement_clicktags(ap: ActualPlacement) -> list[str]` | Los clicktags que gobiernan el placement |
| funcion | `_tracker_cgen(ap: ActualPlacement) -> str` | El CGEN que Innovid tiene para un placement site-served |
| funcion | `_match_creatives(ep: ExpectedPlacement, ap: ActualPlacement) -> tuple[list[CreativeLink], list[ActualCreative]]` |  |
| funcion | `compare_placement(pm: PlacementMatch, res: 'MatchResult') -> None` | Empareja los creativos de un placement y compara URL y atribucion |
| funcion | `match(ts, export_pc, export_pl=None) -> MatchResult` |  |

### `core/normalize.py`

Normalizacion. Regla de oro: raw se conserva, normalizado es derivado. *(292 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `norm_text(value: str \| None) -> str` | Trim + colapso de espacios |
| funcion | `norm_compare(value: str \| None) -> str` | Forma canonica para comparar: sin case, sin espacios sobrantes |
| funcion | `norm_key(value: str \| None) -> str` | Llave para matchear nombres de columna |
| funcion | `clean_id(value: object) -> str` | IDs siempre como string |
| funcion | `split_platform_id(value: str \| None) -> tuple[str, str \| None]` | 'FY26_Stock_AU_Display_DV360_C1_V3 (288292)' -> ('FY26_..._V3', '288292') |
| funcion | `site_names_match(left: object, right: object) -> bool` | ¿Son el mismo site escrito distinto? |
| funcion | `is_dimensions(value: object) -> bool` | Si el valor normalizado es de verdad un ancho por alto |
| funcion | `dims_match(left: object, right: object) -> bool` | Compara dimensiones tolerando como se declara el video |
| funcion | `norm_dims(value: object) -> str` | '160 x 600' / '160X600' / '160×600' -> '160x600' |
| funcion | `dims_from_name(name: str \| None) -> str \| None` | Ultimo recurso: extraer dimensiones del nombre del placement |
| funcion | `to_bool(value: object) -> bool \| None` | 'Yes'/'No' de Innovid |
| funcion | `normalize_weights(values, removed=None) -> list[str]` | Pesos de rotacion de un grupo, en porcentajes que suman 100 |
| funcion | `_label(number: float) -> str` |  |

### `core/paths.py`

Where QA2 reads and writes its own files. *(106 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `project_root() -> Path` | The QA2 folder itself -- the parent of core/ |
| funcion | `local_config_dir() -> Path` | <project>/config |
| funcion | `_env_dir(name: str) -> Path \| None` |  |
| funcion | `config_dir() -> Path` | Where shared tables are written: QA2_CONFIG_DIR if it is set, otherwise the local config folder |
| funcion | `shared_config_path(name: str, *, for_write: bool=False) -> Path` | The file to use for one of the shared tables |
| funcion | `output_dir() -> Path` | Where the run log goes: QA2_OUTPUT_DIR, else <project>/logs |

### `core/pdf_report.py`

Branded PDF export of a QA2 run. *(734 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_register_brand_fonts() -> tuple[str, str]` | Registers the WPP typeface with ReportLab and returns the (regular, bold) font names to use |
| clase | `ReportMeta` | Everything needed to render the report header/summary |
| funcion | `_styles()` |  |
| funcion | `_header_flowables(meta: ReportMeta, styles, logo_path: Path \| None)` |  |
| funcion | `_verdict_flowable(meta: ReportMeta, styles)` |  |
| funcion | `_signoff_flowable(meta: ReportMeta, styles)` |  |
| funcion | `_info_flowable(meta: ReportMeta, styles)` |  |
| funcion | `_esc(text: str) -> str` | Escape user-typed text before it goes into reportlab markup |
| funcion | `_blank(value: str \| None, width: int=28) -> str` | Render a filled value, or an underscored blank line to fill by hand |
| funcion | `_blank_date(value: date \| None) -> str` |  |
| funcion | `_record_flowable(meta: ReportMeta, styles)` |  |
| funcion | `_metrics_flowable(meta: ReportMeta, styles)` |  |
| funcion | `_df_to_table(df: pd.DataFrame, styles, col_widths=None, status_col: str \| None=None, max_rows: int=400)` |  |
| funcion | `_evidence_flowables(evidence_images: list[tuple[str, bytes]], styles)` |  |
| funcion | `_footer(canvas, doc)` |  |
| funcion | `build_pdf_report(meta, findings_df, rules_df, files_df, placements_df, evidence_images, logo_path) -> bytes` | Render the full branded QA2 report and return it as PDF bytes |

### `core/pidfile.py`

QA2 deja escrito su numero de proceso, para que se le pueda encontrar. *(110 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `pid_path(root: Path \| None=None) -> Path` | Siempre junto a la app, nunca en QA2_OUTPUT_DIR |
| funcion | `write_pid(root: Path \| None=None) -> Path \| None` | Anota el proceso actual |
| funcion | `read_pid(root: Path \| None=None) -> int \| None` | El PID anotado, o None si no hay o no se entiende |
| funcion | `clear_pid(root: Path \| None=None) -> None` |  |
| funcion | `is_running(root: Path \| None=None) -> bool` | ¿El QA2 de ESTA carpeta sigue vivo? |
| funcion | `_alive(pid: int) -> bool` | Si ese PID sigue siendo un python |

### `core/pixel_reconciliation.py`

Pixeles de vendor declarados en la TS vs. lo que Innovid tiene. *(580 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_pixel_skeleton(url: str) -> str` | Pixel URL con cada macro reemplazado por un token comun, para comparar |
| funcion | `pixel_matches_official(found: str, official: str) -> bool` | True si el pixel encontrado coincide con el oficial una vez se ignoran los macros de ambos lados |
| funcion | `_host_from_pixel(url: str) -> str` | El dominio de una URL de pixel, para derivar host_terms automaticamente |
| clase | `Vendor` | name            nombre legible que se muestra en el hallazgo account         cuenta/campana a la que aplica esta fila ("" = todas) ts_terms        como aparece nombrado en "Vendors / Pixels" host_terms      como se reconoce su pixel dentro del tag |
| funcion | `vendor_config_path(*, for_write: bool=False) -> Path` |  |
| funcion | `_vendor_to_dict(vendor: Vendor) -> dict` |  |
| funcion | `_dict_to_vendor(data: dict) -> Vendor` |  |
| funcion | `default_vendor_rows() -> list[dict]` | The shipped defaults, as plain dicts -- used to seed the config file |
| funcion | `load_vendor_rows() -> list[dict]` | Raw rows from config/vendor_pixels.json, or the shipped defaults if the file doesn't exist yet or fails to parse |
| funcion | `save_vendor_rows(rows: list[dict]) -> None` | Writes the vendor table back to config/vendor_pixels.json |
| funcion | `load_vendors() -> tuple[Vendor, ...]` | Vendor table reconcile_pixels() actually uses: config file, else defaults |
| funcion | `official_pixel_for(name: str, account: str='') -> str` | The official_pixel value configured for a vendor row by name, e.g |
| clase | `PixelCheck` |  |
| clase | `PixelReconciliation` |  |
| funcion | `placement_format(dims: object) -> str` |  |
| funcion | `_declared(vendor: Vendor, vendor_raw: str) -> bool` |  |
| funcion | `_pixels_in(row, column: str) -> list[str]` |  |
| funcion | `reconcile_pixels(ts_result, placement_view, account: str='') -> PixelReconciliation` |  |

### `core/provenance.py`

Provenance: cada valor extraido conserva su origen exacto. *(66 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `CellRef` | Coordenada absoluta de una celda |
| clase | `Cell` | Una celda leida, con todo lo necesario para auditarla |
| clase | `Anomaly` | Problema de EXTRACCION, no de QA |

### `core/qa_export.py`

La hoja QA del entregable: una fila por creativo, TS contra Innovid. *(408 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_dset_name(check, ts_name: str) -> str` | Como se llama el creativo DENTRO del decision set, y solo cuando no se llama igual que en la Traffic Sheet |
| funcion | `_percent(value: str) -> float \| None` |  |
| funcion | `cells_agree(left: object, right: object) -> bool` | ¿Los dos lados dicen lo mismo? |
| funcion | `_bare(value: str) -> str` | El nombre sin el id final ni la extension |
| funcion | `_worst_status(statuses) -> str` |  |
| funcion | `_span(start, end) -> str` |  |
| funcion | `_text(value) -> str` |  |
| funcion | `build_qa_rows(match_result, findings=(), innovid_reconciliation=None) -> list[dict]` | Una fila por creativo trabajado, mas una por placement sin creativos declarados (una solicitud de landing page o de 1x1 es asi, y dejarla fuera borraria del entregable un placement que si se trabajo) |
| funcion | `_flights_index(reconciliation) -> dict` |  |
| funcion | `_partners_index(reconciliation) -> dict[str, str]` |  |
| funcion | `_findings_index(findings) -> dict` | Hallazgos por (placement, creativo) |
| funcion | `_notes(index: dict, key: tuple) -> set` |  |

### `core/release.py`

Which version of QA2 this is, and what changed in it. *(65 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `qa2_version() -> str` | The contents of VERSION, or "dev" if it isn't there |
| funcion | `changelog_path() -> Path` |  |
| funcion | `release_notes(limit: int=60) -> str` | The most recent version's entry from the changelog, as markdown |

### `core/report_name.py`

Como se llama el archivo que alguien se descarga. *(53 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `safe_part(value: str) -> str` | Un trozo de nombre de archivo que Windows si acepta |
| funcion | `report_filename(extension: str, campaign: str='', when: date \| datetime \| None=None) -> str` | <fecha>_QA_Report_<campana>.<extension> |

### `core/review.py`

Agrupado de hallazgos para la revision de QA2. *(77 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_reason_key(finding) -> str` | El mensaje sin los nombres que cambian de una fila a otra |
| funcion | `group_review_findings(findings: Iterable) -> dict[tuple[str, str], list]` | Agrupa por (regla + estado, motivo) conservando el orden |
| funcion | `bulk_groups(findings: Iterable) -> dict[str, list]` | Los grupos que vale la pena aprobar en bloque, etiquetados para el selector |

### `core/schema.py`

Contratos de campo para exports de Innovid. *(129 lineas)*

### `core/tag_analysis.py`

Analisis de los archivos de tags, fila por fila y columna por columna. *(472 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_family(dimensions: str, filled_types: set[str], columns: set[str]) -> str` | A que tipo de placement corresponde una fila |
| funcion | `_required_missing(family: str, filled_types: set[str]) -> list[str]` | Lo que a una fila le falta para servir, por su tipo |
| funcion | `_column_order(columns: list[str], name: str) -> int` | Posicion de una columna en el orden del archivo |
| clase | `TagRowAnalysis` | Una fila del archivo de tags, ya juzgada |
| clase | `FamilySummary` | El panel de arriba, una linea por tipo de placement |
| clase | `TagAnalysis` |  |
| funcion | `_worked_placements(ts_result) -> dict[str, str]` | Los placements que la solicitud pide trabajar, con su nombre |
| funcion | `analyse_tags(tags_results, ts_result=None) -> TagAnalysis` | Junta todos los archivos de tags en un solo analisis |
| funcion | `_same_column(filled: dict[str, str], name: str) -> str` | La misma columna escrita con otras mayusculas |
| funcion | `import_table(analysis: TagAnalysis) -> list[dict]` | El archivo de tags tal como se importaria, con el veredicto delante |
| funcion | `dv_table(dv_result) -> list[dict]` | El archivo de DV Pinnacle, fila por fila |

### `core/tag_coverage_reconciliation.py`

Tag file coverage (TAG-013). *(114 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `TagCoverageCheck` |  |
| clase | `TagCoverageReconciliation` |  |
| funcion | `_worked_1x1_with_vendor(ts_result) -> dict[str, dict]` |  |
| funcion | `reconcile_tag_coverage(ts_result, inventory: TagInventory) -> TagCoverageReconciliation` |  |

### `core/tag_inventory.py`

Inventario consolidado de múltiples archivos de Tags. *(186 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `TagSourceRow` |  |
| clase | `TagInventory` |  |
| funcion | `build_tag_inventory(paths: list[Path]) -> TagInventory` |  |
| funcion | `build_tag_inventory_from_results(named_results) -> TagInventory` | Build one consolidated TagInventory from already parsed tag files |

### `core/tag_matching.py`

Matching de archivos de tags contra el resultado TS vs Innovid. *(126 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `TagPlacementLink` |  |
| clase | `TagMatchResult` |  |
| funcion | `match_tags(match_result: MatchResult, tags_result: TagsResult) -> TagMatchResult` |  |

### `core/team_roster.py`

Team roster: who's on each account's team. *(104 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `roster_path(*, for_write: bool=False) -> Path` |  |
| funcion | `default_roster() -> dict[str, list[str]]` |  |
| funcion | `load_roster() -> dict[str, list[str]]` |  |
| funcion | `save_roster(roster: dict[str, list[str]]) -> None` |  |
| funcion | `base_account(value: str) -> str` | La cuenta a la que pertenece lo que se eligio en el selector |
| funcion | `names_for_account(roster: dict[str, list[str]], account: str) -> list[str]` | Roster for one account plus Support, deduped, order preserved |

### `core/ts_schema.py`

Contratos de campo para Traffic Sheets. *(280 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `not_for_innovid(header: str) -> str` | Para quien es esa columna, si no es para nosotros |
| funcion | `format_from_dims(value: object) -> str` | Deriva el formato de las dimensiones |
| clase | `TSProfile` |  |

### `core/ts_snapshot.py`

Lo que QA leyo de una Traffic Sheet, en forma comparable. *(167 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_plain(value)` | Tuplas a listas, recursivamente |
| funcion | `_ours(cmap) -> list` | Columnas sin mapear que si nos tocaban |
| funcion | `_theirs(cmap) -> list` | Columnas de la TS estandar dirigidas a otra herramienta |
| funcion | `_sheet(sheet) -> dict[str, Any] \| None` | Como leyo la app una hoja |
| funcion | `summarise_ts(result) -> dict[str, Any]` | El resumen completo de una lectura, listo para comparar |
| funcion | `differences(expected: dict, actual: dict, path: str='') -> list[str]` | En que se diferencian dos lecturas, campo a campo |

### `core/urls.py`

URL and attribution engine. *(276 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `account_uses_cgen(account: str) -> bool \| None` | False cuando la cuenta elegida no maneja CGEN; None cuando no se eligio cuenta o no la conocemos -- ahi decide la hoja |
| clase | `ParsedURL` |  |
| funcion | `parse_url(value: object) -> ParsedURL` |  |
| clase | `URLComparison` |  |
| funcion | `compare_urls(expected: object, actual: object) -> URLComparison` |  |
| clase | `AttributionTriangle` | Three vertices that must match: ts       = CGENS declared in the Traffic Sheet export   = Third_Party_ID of the row in Innovid url      = sdid param extracted from the ClickTag |
| funcion | `check_triangle(ts_cgen: object, export_tpid: object, url_value: object) -> AttributionTriangle` |  |

### `core/verdict.py`

El veredicto, y por que hay dos. *(173 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `final_verdict(scorecard: Scorecard) -> str` |  |
| funcion | `scope_of(finding) -> str` | A cual de los dos pertenece un hallazgo |
| funcion | `split_findings(findings) -> dict[str, list]` | Los hallazgos repartidos en los dos alcances |
| funcion | `scorecards_by_scope(findings) -> dict[str, Scorecard]` | Un Scorecard por alcance |
| funcion | `verdicts_by_scope(findings) -> dict[str, str]` |  |
| funcion | `_worse(left: str, right: str) -> str` |  |
| funcion | `headline(findings) -> str` | Una frase que diga cual de los dos hay que mirar |
| funcion | `_look_at_the_tags(tags: str) -> str` |  |
| funcion | `_tags_only(tags: str) -> str` |  |
| funcion | `overall(findings) -> str` | El peor de los dos, que es el veredicto de la solicitud |

## `parsers/` — Lectura de los archivos que sube el analista

### `parsers/__init__.py`

Lectura de los archivos que sube el analista. *(13 lineas)*

### `parsers/dv_tags.py`

Parser for DoubleVerify (DV) Pinnacle site-served tag exports. *(209 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `DVTagRow` |  |
| clase | `DVTagsResult` |  |
| funcion | `parse_dv_tags(path: Path) -> DVTagsResult` |  |
| funcion | `merge_dv_results(results: list[DVTagsResult]) -> DVTagsResult \| None` | Varios archivos de DV Pinnacle leidos como uno solo |

### `parsers/innovid_export.py`

Parser del export de Innovid Campaign Manager. *(363 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `norm_compare_sheet(name: str) -> str` |  |
| clase | `ExportRow` |  |
| clase | `ExportResult` |  |
| funcion | `_detect_level(grid, header_row: int) -> str` | Placement-Creative si existe la columna Creative_ID en el header |
| funcion | `_read_metadata(grid, spec: SheetSpec) -> dict[str, str]` | Metadata de las filas 1-9, por ETIQUETA (nunca por posicion) |
| funcion | `_row_type(vals: dict[str, object], level: str, group_visible: dict[str, bool]) -> tuple[str, str]` | Devuelve (tipo, motivo) |
| funcion | `parse_innovid_export(path: Path, sheet_name: str \| None=None) -> ExportResult` |  |

### `parsers/innovid_tags.py`

Parser de archivos de tags exportados desde Innovid. *(572 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `clean_tag_issues(issues: list[str]) -> list[str]` | Elimina falsos hallazgos generados por dimensiones embebidas    Ejemplos ignorados: WIDTH: esperado=1 embebido=['0'] HEIGHT: esperado=1 embebido=['0'] |
| clase | `TagValue` |  |
| clase | `TagRow` |  |
| clase | `TagsResult` |  |
| funcion | `_cell_text(value: object) -> str` |  |
| funcion | `_find_header(ws, scan_rows: int=40) -> int \| None` |  |
| funcion | `_select_sheet(wb) -> tuple[str, int \| None]` |  |
| funcion | `_read_metadata(ws, header_row: int) -> dict[str, str]` |  |
| funcion | `_classify_tag_header(header: str) -> str` |  |
| funcion | `_extract_urls(raw: str) -> list[str]` |  |
| funcion | `_extract_hosts(urls: list[str]) -> list[str]` |  |
| funcion | `_unique_matches(pattern: re.Pattern, raw: str) -> list[str]` |  |
| funcion | `_parse_tag_value(column_name: str, raw: str) -> TagValue` |  |
| funcion | `parse_innovid_tags(path: Path) -> TagsResult` |  |

### `parsers/ts_parser.py`

Parser de Traffic Sheets. *(974 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| clase | `TSRow` |  |
| clase | `GroupScope` | Un grupo/rotacion con intencion de cambio |
| clase | `PlacementScope` |  |
| clase | `TSSheetResult` |  |
| clase | `TSResult` |  |
| funcion | `_split_sheets(path: Path) -> tuple[list[str], list[str], list[str]]` |  |
| funcion | `detect_profile(path: Path) -> tuple[str, str]` | Senal 1: columna CGEN/CGENS en Placements O en Creative Rotations -> Adobe |
| funcion | `_row_own(colors: dict) -> set` | Los colores que describen a ESTA fila |
| funcion | `_impl_type(vals: dict[str, object]) -> str` |  |
| funcion | `_repair_wpp_combined_rotation_header(grid, header_row: int, cmap: ColumnMap, spec: SheetSpec, anomalies: list[Anomaly]) -> None` | Repara una variante defectuosa de WPP donde los encabezados 'Creative Rotation' y 'Creative Name' fueron combinados |
| funcion | `_parse_sheet(path, sheet_name, spec, intent_fields, resolver, primary_key, skip_hidden) -> tuple[TSSheetResult, list[tuple[str, str, Cell]]]` |  |
| funcion | `_build_groups(sr: TSSheetResult \| None) -> dict[str, GroupScope]` | Agrupa creativos por rotacion y detecta que rotaciones se trabajaron |
| funcion | `_merge_hidden_lp_refs(groups: dict[str, GroupScope], sr: TSSheetResult \| None) -> None` | Anade al mapa grupo -> landing page las filas ocultas de rotaciones |
| funcion | `_build_lp_worked(sr: TSSheetResult \| None) -> set[str]` | Landing pages con color -> se trabajo su URL |
| funcion | `_build_scope(sr, groups, lp_worked, propagate) -> dict[str, PlacementScope]` | El scope de QA2 = placements con color propio U placements que apuntan a grupos con color U placements que apuntan a landing pages con color |
| funcion | `parse_ts(path: Path, profile_name: str \| None=None) -> TSResult` |  |

## `rules/` — Reglas de QA, una familia por archivo

### `rules/__init__.py`

Las reglas de QA2, una familia por archivo. *(12 lineas)*

### `rules/adobe_pixels.py`

Official Adobe pixel findings. *(286 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_text(value: Any) -> str` | Return a clean printable value without changing source content |
| funcion | `_status(check: Any) -> str` | Read the reconciliation status safely |
| funcion | `_value(check: Any, *attribute_names: str, default: Any='') -> Any` | Return the first available non-empty attribute |
| funcion | `_evidence_text(check: Any) -> str` | Build a short traceability description for the finding |
| funcion | `evaluate(reconciliation, buffer: FindingsBuffer) -> None` | Convert Adobe DISQO reconciliation checks into official findings |

### `rules/adobe_tag_policy.py`

TAG-012 -- politica de columnas de tags de Adobe. *(48 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(reconciliation, buffer)` |  |

### `rules/attribution.py`

ATR-001 / ATR-002 -- atribucion (CGEN). *(187 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_cgen_values(match_result) -> int` | Cuantos CGEN con valor trae la TS |
| funcion | `evaluate(match_result, buffer, account: str='')` | El triangulo de atribucion se apoya en el CGEN que declara la TS, y solo Adobe lo maneja |
| funcion | `_evaluate_placement_triangle(pm, buffer)` | ATR-002 -- la atribucion de un placement sin creativos propios |

### `rules/creatives.py`

CRE-001 / CRE-002 -- creativos del placement. *(250 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(match_result, buffer)` |  |
| funcion | `_evaluate_site_served_tracker(pm, buffer) -> None` | CRE-002 -- el 1x1 de un placement site-served |

### `rules/defaults.py`

DEF-001 -- el default ad es consistente. *(48 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(reconciliation, buffer)` |  |

### `rules/dset.py`

TRK-002 -- el Decision Set asignado es el que pide la TS. *(38 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(match_result, buffer)` |  |

### `rules/dtree.py`

TRK-001 -- el Decision Tree asignado es el que pide la TS. *(38 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(match_result, buffer)` |  |

### `rules/dv_omni.py`

DV-003 -- columnas de DV Omni / Monitoring+Blocking en los tags. *(41 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(reconciliation, buffer)` |  |

### `rules/dv_tags.py`

DV-001 / DV-002 -- tags de DoubleVerify Pinnacle. *(61 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(reconciliation, buffer)` |  |

### `rules/innovid.py`

Hallazgos de lo que solo Innovid sabe. *(496 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(reconciliation, buffer)` |  |
| funcion | `_flight_dates(reconciliation, buffer)` |  |
| funcion | `_rotation_weights(reconciliation, buffer)` |  |
| funcion | `_verification_partner(reconciliation, buffer)` |  |
| funcion | `_unchecked(reconciliation, buffer)` |  |
| funcion | `_differs(expected, actual) -> bool` | Una fecha que un lado declara y el otro no TAMBIEN es diferencia |
| funcion | `_span(start, end) -> str` |  |
| funcion | `_same_weight(expected: str, actual: str) -> bool` | Los dos lados llegan ya como porcentaje del mismo reparto, pero no con la misma precision: la TS sale de una formula de Excel y trae 13,33%, mientras que en Innovid se escribe a mano y solo admite enteros, 13% |

### `rules/naming.py`

PLC-006 -- el Placement Name de Innovid coincide con el de la TS. *(84 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_is_retired(pm) -> bool` | El placement ya no esta sirviendo, por TS o por Innovid |
| funcion | `evaluate(match_result, buffer)` |  |

### `rules/pixels.py`

PIX-002 -- el pixel de cada vendor esta en su columna. *(71 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(reconciliation, buffer)` |  |

### `rules/placements.py`

PLC-001 / PLC-002 / PLC-007 -- existencia y estado de los placements. *(169 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(match_result, buffer)` |  |
| funcion | `_evaluate_rotation_dims(ep, buffer)` | PLC-007 -- la rotacion que el placement declara no es de su tamano |
| funcion | `_evaluate_disassignment(pm, buffer)` | PLC-002 - desasignacion de placement |

### `rules/rotation.py`

ROT-001 -- la rotacion que se pidio cambiar. *(96 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_weights_label(creatives) -> str` | Los pesos pedidos, en porcentaje y sin repetir |
| funcion | `_requested_rotation(creative) -> bool` | ¿La TS pinto la celda de rotacion de este creativo? |
| funcion | `evaluate(match_result, buffer)` |  |

### `rules/tag_coverage.py`

TAG-013 -- cobertura del archivo de tags. *(39 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `evaluate(reconciliation, buffer)` |  |

### `rules/tags.py`

QA2 rules for tag files. *(501 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_date_text(value: object) -> str` |  |
| funcion | `evaluate(tag_match: TagMatchResult, buffer: FindingsBuffer) -> None` |  |
| funcion | `_clicked_url(raw: str) -> str` | A donde manda un click tag de 1x1 |
| funcion | `_landing_page_in_click_tag(link, buffer: FindingsBuffer) -> None` | TAG-014 -- el tag dice a donde va el click, y la TS tambien |

### `rules/urls.py`

URL-001 / URL-002 / URL-003 -- landing pages y clicktags. *(395 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_actual_urls(ap) -> list[str]` | Clicktags que Innovid tiene realmente para el placement |
| funcion | `evaluate_placement_urls(match_result, buffer)` | URL-002 - swap de solo URL |
| funcion | `_is_retired(pm) -> bool` | El placement ya no sirve: la TS lo desasigna, o Innovid lo apago |
| funcion | `evaluate_direct_placement_urls(match_result, buffer)` | URL-003 -- la landing page de un placement sin creativos propios |
| funcion | `evaluate(match_result, buffer)` |  |

## `ui/` — Interfaz (Streamlit)

### `ui/__init__.py`

Interfaz de QA2 (Streamlit). Todo lo visible vive en app_v2.py. *(1 lineas)*

### `ui/app_v2.py`

Interfaz de QA2 (Streamlit). *(5783 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `logo_path() -> Path \| None` |  |
| funcion | `professional_profile_name(profile_name: str) -> str` | Corporate-facing name that avoids exposing internal technical keys |
| clase | `_RestoredUpload` | Stand-in for Streamlit's UploadedFile, built from bytes stored in a QA session bundle -- exposes just the surface the app actually touches (.name, .size, .getbuffer(), .getvalue()) so a restored file can be passed anywhere a live upload is expected |
| funcion | `_workbook_path(directory: str, file_name: str, file_bytes: bytes) -> Path` | Writes the upload to disk under a name that matches what it actually is |
| funcion | `cached_parse_ts(file_bytes: bytes, file_name: str, profile_name: str \| None)` | Cached by file content + profile -- every widget interaction after the first run used to re-parse the whole TS from scratch (openpyxl is slow on a large workbook), even for something as unrelated as ticking a checkbox |
| funcion | `stale_modules() -> list[str]` | Files that changed on disk after the code from them was loaded |
| funcion | `running_version() -> str` | Which commit the repository is on |
| funcion | `running_checkout() -> tuple[str, str]` | De que carpeta y de que rama sale el codigo que se esta ejecutando |
| funcion | `trace(stage: str) -> None` | Una linea por etapa, en disco |
| funcion | `sign_findings(findings, note: str) -> int` | Marca como firmado todo lo que se le pase |
| funcion | `clear_signatures() -> None` | Lo mismo al reves |
| funcion | `reuse(slot: str, signature, build)` | Construye algo caro una sola vez por cada estado distinto |
| funcion | `cached_fetch_innovid(campaign_id: str, placement_ids: tuple[str, ...], refresh: bool=False)` | Reads the campaign from Innovid, reusing a good answer |
| funcion | `cached_parse_innovid_export(file_bytes: bytes, file_name: str)` |  |
| funcion | `cached_parse_innovid_tags(file_bytes: bytes, file_name: str)` |  |
| funcion | `cached_parse_dv_tags(file_bytes: bytes, file_name: str)` |  |
| funcion | `person_selector(label: str, account: str, state_key: str) -> str` | Dropdown of who did this, straight from "Team by account" -- so nobody has to type a teammate's name by hand |
| funcion | `peek_campaign_name(uploaded_file) -> str` | Reads just the Campaign Name cell from a TS's Campaign Information sheet, without running the full parse_ts pipeline (colors, scope, placements...) |
| funcion | `anomaly_rows(source_name: str, result) -> list[dict]` |  |
| funcion | `result_is_fatal(result) -> bool` |  |
| funcion | `placement_findings(placement_id: str, findings_buffer)` |  |
| funcion | `placement_status(placement_id: str, findings_buffer) -> str` |  |
| funcion | `findings_dataframe(findings) -> pd.DataFrame` |  |
| funcion | `apply_review_overrides(findings, overrides: dict, approved_by: str='')` | Turns an approved REVIEW, FAIL or NOT_VERIFIED finding into PASS, carrying the QA's observation forward as the reason a human can read later |
| funcion | `rule_summary_dataframe(findings_buffer) -> pd.DataFrame` |  |
| funcion | `clean_value(value) -> str` |  |
| funcion | `compare_value(expected, actual, *, normalizer=None, optional: bool=False, fuzzy: bool=False) -> str` |  |
| funcion | `comparison_row(field_name, expected, actual, normalizer, optional, fuzzy) -> dict` |  |
| funcion | `render_status_badge(status: str) -> None` |  |
| funcion | `show_verdict(verdict: str, findings=None) -> None` |  |
| funcion | `brand_font_css() -> str` | @font-face rules for the WPP typeface, embedded as base64 so Streamlit doesn't need to serve the files |

## `cli/` — Herramientas de linea de comandos

### `cli/__init__.py`

Herramientas de linea de comandos para diagnosticar un archivo sin abrir la interfaz. *(13 lineas)*

### `cli/colors.py`

CLI: Calibrador de colores. *(191 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `main(ts, sheets, token, limit) -> None` |  |

### `cli/match.py`

CLI: Matching Preview. *(327 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `main(ts_path, export, export_placement, profile, show) -> None` |  |

### `cli/preview.py`

CLI: Extraction Preview. *(248 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `main(export, sheet, show_rows) -> None` |  |

### `cli/tags.py`

CLI: Preview y QA estructural de archivos de Tags. *(295 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `main(tags, show) -> None` |  |

### `cli/ts.py`

CLI: Extraction Preview de Traffic Sheet. *(284 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_sheet_panels(name: str, sr, show_rows: int) -> None` |  |
| funcion | `main(ts, profile, show_rows) -> None` |  |

## `scripts/` — Arranque, empaquetado y diagnosticos

### `scripts/__init__.py`

Scripts de soporte: arranque, empaquetado y diagnosticos. *(13 lineas)*

### `scripts/build_bundle.py`

Construye el paquete que se le entrega al equipo: QA2 con Python adentro. *(454 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `host_platform() -> str` |  |
| funcion | `python_exe(bundle: Path, target: str) -> Path` |  |
| funcion | `version() -> str` |  |
| funcion | `fetch_python(bundle: Path, target: str) -> None` | Descarga y extrae el interprete dentro del paquete |
| funcion | `lock_path(target: str) -> Path` |  |
| funcion | `install_requirements(bundle: Path, target: str, innovid: bool) -> None` | Instala las librerias, y fija cuales |
| funcion | `local_browser_cache() -> Path \| None` | Donde esta ya el Chromium de esta maquina, si esta |
| funcion | `required_browsers(bundle: Path, target: str) -> list[str]` | Que revisiones exactas pide el Playwright de este paquete |
| funcion | `install_chromium(bundle: Path, target: str) -> bool` | El navegador de Playwright, dentro del paquete |
| funcion | `trim(bundle: Path, target: str) -> None` | Quita lo que solo servia para construir |
| funcion | `copy_app(bundle: Path) -> int` | El codigo, con las mismas reglas que el zip de solo codigo |
| funcion | `guard(bundle: Path) -> None` | Lo unico por lo que vale la pena abortar |
| funcion | `archive(bundle: Path, name: str) -> Path` |  |
| funcion | `build(target: str, innovid: bool, keep: bool) -> Path` |  |
| funcion | `main() -> None` |  |

### `scripts/check_project.py`

Comprobacion rapida: los modulos principales importan sin error. *(7 lineas)*

### `scripts/diagnose_adobe_clicktag_requirements.py`

Diagnostic test for Adobe Click tag only requirements. *(410 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_normalize_tag_column(value: object) -> str` | Normalize operational tag column names |
| funcion | `populated_columns_for_placement(inventory, placement_id: str) -> tuple[set[str], list[str], list[str]]` | Return populated tag cells for one Placement ID |
| funcion | `_normalized_tag_column_name(value: object) -> str` | Normalize a tag column without losing its operational meaning |
| funcion | `_populated_tag_columns(inventory, placement_id: str) -> tuple[set[str], list[str]]` | Return only columns whose cell is populated for this Placement ID |
| funcion | `normalized_column(value: str) -> str` |  |
| funcion | `get_tag_paths() -> list` | Find every delivered tag file under the real Adobe test case |
| funcion | `is_clicktag_only(value: object) -> bool` |  |
| funcion | `main() -> None` |  |

### `scripts/diagnose_adobe_ftrack_requirements.py`

Adobe Ftrack requirements diagnostic. *(426 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `get_tag_paths() -> list` |  |
| funcion | `normalize_column(value: object) -> str` |  |
| funcion | `requires_ftrack(value: object) -> bool` | Detect a positive Ftrack requirement |
| funcion | `populated_columns_for_placement(inventory, placement_id: str) -> tuple[set[str], list[str], list[str]]` |  |
| funcion | `is_ftrack_impression(column: str) -> bool` |  |
| funcion | `is_ftrack_click(column: str) -> bool` |  |
| funcion | `main() -> None` |  |

### `scripts/diagnose_adobe_no_ftrack_requirements.py`

Diagnostico manual: requisitos de tags Adobe No FTRACK sobre un caso local. *(193 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `get_tag_paths() -> list` | Find all delivered tag files recursively |
| funcion | `main() -> None` |  |

### `scripts/diagnose_adobe_pixel_findings.py`

Diagnostico manual: hallazgos de pixeles de Adobe sobre un caso local. *(167 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `get_tag_paths() -> list[Path]` |  |
| funcion | `main() -> None` |  |

### `scripts/diagnose_adobe_protected_requirements.py`

PIX-A05 | Adobe Protected diagnostic. *(481 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `get_tag_paths() -> list` | Return all tag workbooks in the Adobe regression case |
| funcion | `normalize_column(value: object) -> str` | Normalize tag column names for family detection |
| funcion | `requires_protected(value: object) -> bool` | Return True when Vendors / Pixels requests Protected |
| funcion | `get_worked_ids(ts_result) -> set` | Return canonical worked placements, excluding context rows |
| funcion | `source_sheet(source) -> str` | Read the originating worksheet without assuming one attribute |
| funcion | `populated_columns_for_placement(inventory, placement_id: str) -> tuple[set[str], list[str], list[str]]` | Return: - normalized populated columns - original populated column names - source evidence |
| funcion | `is_ftrack_impression(column: str) -> bool` | Identify a populated Ftrack impression column |
| funcion | `is_ftrack_click(column: str) -> bool` | Identify a populated Ftrack click column |
| funcion | `is_protected_column(column: str) -> bool` | Identify all supported Protected tag column variants |
| funcion | `main() -> None` |  |

### `scripts/diagnose_adobe_tag_requirements.py`

Diagnostic of Adobe tag requirements. *(468 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `get_tag_paths() -> list[Path]` | Return all supported tag files from the configured folders |
| funcion | `classify_vendor(value: object) -> set[str]` | Classify the Vendors / Pixels text from the Traffic Sheet |
| funcion | `main() -> None` |  |

### `scripts/diagnose_tags.py`

Diagnostico manual: lee todos los archivos de tags de data/tags y resume problemas. *(143 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `main() -> None` |  |

### `scripts/diagnose_wpp_urls.py`

Diagnóstico de resolución URL para Traffic Sheets WPP. *(248 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `extract_first_url(value: object) -> str` |  |
| funcion | `find_traffic_sheet() -> Path` |  |
| funcion | `main() -> None` |  |

### `scripts/export_copilot_context.py`

Arma los archivos de conocimiento para un agente de Copilot sin acceso al repo. *(188 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `candidates() -> list[str]` |  |
| funcion | `assign(paths: list[str]) -> dict[str, list[str]]` |  |
| funcion | `render(title: str, files: list[str]) -> str` |  |
| funcion | `guard(groups: dict[str, list[str]]) -> None` |  |
| funcion | `build() -> dict[str, list[str]]` |  |
| funcion | `main() -> None` |  |

### `scripts/generate_code_map.py`

Genera docs/MAPA_DEL_CODIGO.md: el indice de todo el codigo de QA2. *(153 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_first_paragraph(doc: str \| None) -> str` |  |
| funcion | `_first_line(doc: str \| None) -> str` |  |
| funcion | `_signature(node: ast.FunctionDef \| ast.AsyncFunctionDef) -> str` |  |
| funcion | `_cell(text: str) -> str` |  |
| funcion | `describe_module(path: Path) -> list[str]` |  |
| funcion | `describe_tests() -> list[str]` |  |
| funcion | `build() -> str` |  |
| funcion | `main() -> None` |  |

### `scripts/inventory_test_cases.py`

Inventario automático de fixtures QA2 reales. *(208 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `short_error(error: Exception) -> str` |  |
| funcion | `fatal_messages(result) -> str` |  |
| funcion | `try_tags(path: Path) -> dict \| None` |  |
| funcion | `try_export(path: Path) -> dict \| None` |  |
| funcion | `try_ts(path: Path) -> dict \| None` |  |
| funcion | `classify(path: Path) -> dict` | Orden de detección: 1 |
| funcion | `main() -> None` |  |

### `scripts/package_release.py`

Builds the zip that goes to the team. *(292 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_dist() -> Path` | Todo lo que se arma queda en dist/, y solo ahi |
| funcion | `_version() -> str` |  |
| funcion | `_reason(path: Path) -> str` | Why this file is not going in, or "" if it is |
| funcion | `app_files(root: Path=ROOT, skip: Path \| None=None) -> list[Path]` | Los archivos del proyecto que si viajan, y por que se quedan los demas |
| funcion | `build(destination: Path \| None=None) -> Path` | El zip de solo codigo, para quien ya tiene Python |
| funcion | `build_update(destination: Path \| None=None) -> Path` | El zip pequeno: solo el codigo, para actualizar un paquete que ya esta instalado |
| funcion | `main() -> None` |  |

### `scripts/reconcile_adobe_pixels.py`

Diagnostico manual: conciliacion de pixeles de Adobe sobre un caso local. *(235 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `get_tag_paths() -> list[Path]` |  |
| funcion | `main() -> None` |  |

### `scripts/regression_adobe_clicktag.py`

Regresion manual: el diagnostico de clicktag de Adobe sigue imprimiendo lo esperado. *(78 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `main() -> None` |  |

### `scripts/run_rules.py`

Corre el motor de reglas sobre una TS y un export locales, sin interfaz. *(90 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `main()` |  |

### `scripts/run_tag_inventory.py`

Diagnostico manual: inventario consolidado de tags sobre un caso local. *(202 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `tag_paths() -> list` |  |
| funcion | `main() -> None` |  |

### `scripts/run_tags_qa.py`

Corre el QA de tags sobre archivos locales, sin interfaz. *(157 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `main() -> None` |  |

### `scripts/start_qa2.py`

Arranca QA2: anota su PID, abre el navegador, y avisa si no levanta. *(271 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_answers(port: int) -> bool` |  |
| funcion | `_tell(message: str) -> None` | Un aviso que se ve aunque no haya consola |
| funcion | `_free_port(start: int) -> int \| None` | El primer puerto que nadie tenga, a partir del siguiente al suyo |
| funcion | `_watch(port: int, log: Path) -> None` |  |
| funcion | `_open_log(log: Path)` | El log, abierto ANTES que nada |
| funcion | `_note(handle, text: str) -> None` | Al log siempre; y a la consola tambien, si la hay |
| funcion | `_header(handle, port: int) -> None` | Lo que hace falta saber para entender un arranque fallido, sin tener que pedirlo por chat |
| funcion | `main() -> int` |  |
| funcion | `_start(port: int, log: Path, handle) -> int` |  |

## raíz — Archivos en la raiz

### `check_innovid_connection.py`

Checks that QA2 can talk to Innovid, before wiring any of it into the app. Run it once after filling in config/innovid_credentials.env: *(464 lineas)*

| Tipo | Nombre | Que hace |
| --- | --- | --- |
| funcion | `_record_what_innovid_asks_for(campaign_id: str) -> int` | Watches Innovid's own interface to learn an endpoint QA2 can't find on its own |
| funcion | `_sign_in_by_hand() -> int` | Opens a normal browser window so the sign-in happens the usual way -- SSO, verification code and all -- and keeps the session |
| funcion | `main() -> int` |  |

## Pruebas (`tests/`)

Cada archivo prueba un comportamiento. Se corren todas con `python -m pytest tests/`, o una sola con `python -m pytest tests/<archivo>.py`.

| Archivo | Pruebas | Que protege |
| --- | --- | --- |
| `test_adobe_direct.py` | 8 | Adobe Direct / Site-Served: lo que se revisa cuando no hay creativos |
| `test_adobe_official_pixels.py` | 9 | Los pixeles oficiales de Adobe: uno universal y uno por linea de negocio |
| `test_attribution_account.py` | 12 | Quien elige la cuenta manda sobre si hay atribucion que revisar |
| `test_blackrock_greys.py` | 6 | En BlackRock un placement ocupa varias filas, y no todas valen igual |
| `test_bundle.py` | 47 | El paquete que se entrega trae su propio Python |
| `test_concept_name_noise.py` | 8 | Setenta revisiones que firmar, y un Excel que las desmentia |
| `test_config_locations.py` | 25 | Where QA2 keeps things, pinned |
| `test_copilot_export.py` | 3 | The Copilot knowledge export carries all the code and never a secret |
| `test_creative_dimensions.py` | 9 | El tamano al que se sirve un creativo, y por que no se veia |
| `test_creative_name_two_sources.py` | 11 | La app hacia firmar una discrepancia que el Excel desmentia |
| `test_creative_removal.py` | 6 | Un creativo en rojo tiene que dejar de correr |
| `test_default_ads_and_dims.py` | 8 | El default ad de BlackRock, y la rotacion que no es del tamano del placement |
| `test_disqo_by_placement_type.py` | 10 | Donde se espera el pixel de DISQO depende de como se trafica |
| `test_dset_last_resort.py` | 9 | placementDecisionSetId es el ultimo recurso, no una fuente mas |
| `test_dv_multiple_partners.py` | 12 | Una campana puede tener mas de un partner, y DV entrega un archivo por cada uno |
| `test_excel_signed_off.py` | 16 | Los tres colores del Excel, y la celda de firma que sobraba |
| `test_extraction_hidden_rows.py` | 6 | Una fila oculta no se lee |
| `test_group_colour_does_not_decide.py` | 12 | El color de la celda del grupo no decide el de un creativo |
| `test_hidden_landing_page_chain.py` | 12 | La tabla que dice a que landing page apunta un grupo puede estar oculta |
| `test_hidden_rotations.py` | 6 | Una hoja de rotaciones filtrada sigue siendo una hoja con datos |
| `test_innovid_api.py` | 8 | Parser tests for core/innovid_api |
| `test_innovid_cache.py` | 0 | La cache de la app no debe guardar fallos |
| `test_innovid_cache_policy.py` | 11 | Que se guarda en el cache de Innovid y que no |
| `test_innovid_csrf.py` | 0 | El 403 que salio en pruebas: sesion valida, token ausente |
| `test_innovid_csrf_rotation.py` | 0 | Un token que rota: el capturado al inicio queda viejo enseguida |
| `test_innovid_csrf_source.py` | 0 | La situacion real en pruebas: la sesion trae DOS tokens csrf |
| `test_innovid_diagnose.py` | 0 | El diagnostico debe informar sin exponer nada |
| `test_innovid_field_shapes.py` | 61 | Field shapes in Innovid's /summary response |
| `test_innovid_login_start.py` | 17 | El boton de iniciar sesion tiene que decir cuando no arranco |
| `test_innovid_reconciliation.py` | 46 | La Traffic Sheet contra lo que Innovid realmente tiene |
| `test_innovid_rule_scope.py` | 11 | Dos cosas que QA marcaba y estaban bien traficadas |
| `test_innovid_session.py` | 0 | El 401 que salio en pruebas con una sesion guardada |
| `test_innovid_session_expiry.py` | 8 | Que exista el archivo de sesion no es que la sesion sirva |
| `test_intent_fields.py` | 10 | La celda pintada manda: se valida lo que se pidio |
| `test_missing_creative_noise.py` | 5 | Un creativo que no esta en Innovid es UN problema, no tres |
| `test_no_window_launch.py` | 12 | El equipo abre QA2 con doble clic y nada mas |
| `test_one_by_one_placements.py` | 13 | Un 1x1 va asignado directo al placement |
| `test_portable_tests.py` | 8 | Las pruebas tienen que correr en la maquina de quien las corre |
| `test_qa_export.py` | 24 | La hoja QA del entregable: una fila por creativo, TS contra Innovid |
| `test_report_naming.py` | 9 | Como se llama el archivo que alguien se descarga, y que pestanas del Excel se ven |
| `test_review_approve_buttons.py` | 15 | Como se firma el QA2, y por que ya no es un boton |
| `test_review_bulk_groups.py` | 7 | Aprobar en bloque lo que es una sola decision |
| `test_review_panel_reasons.py` | 5 | "70 to review", y nada mas |
| `test_review_panel_scope.py` | 7 | Que entra al panel de aprobacion y que no |
| `test_rotation_not_verified.py` | 12 | Una rotacion que nadie comparo no puede salir en verde |
| `test_row_scope_colour.py` | 6 | Que color deja una fila fuera de alcance, y cual no |
| `test_run_trace.py` | 17 | El rastro en disco de cada pasada |
| `test_scope_guard_verdict.py` | 13 | La implementacion y los tags no son lo mismo, y no pueden compartir veredicto |
| `test_site_served_row.py` | 5 | El 1x1 de un site-served no tenia fila, y el nombre de Innovid no era el mismo en la app que en el Excel |
| `test_site_served_tracker.py` | 6 | Un 1x1 de Adobe: la TS dice N/A y QA2 no comprobaba nada |
| `test_startup_leaves_a_trace.py` | 5 | "Solo me dice que no le abre nada." |
| `test_tag_analysis.py` | 17 | Que se ve de un archivo de tags |
| `test_tag_landing_page.py` | 12 | La landing page viaja dentro del click tag de un 1x1 |
| `test_ts_reading.py` | 3 | Que lee QA de cada Traffic Sheet, formato por formato |
| `test_ts_rotation_filters.py` | 5 | Que filas de Creative Rotations se descartan |
| `test_two_installations.py` | 10 | Dos carpetas de QA2 en la misma maquina, y la que se veia no era la que se habia abierto |
| `test_ui_stale_modules.py` | 0 | La app debe darse cuenta de que corre codigo viejo |
| `test_unreadable_sheet.py` | 12 | Una hoja que no se pudo leer nunca puede acabar en PASSED |
| `test_video_duration_dims.py` | 9 | "Dims or Duration" a veces trae la duracion, y eso no es una dimension |
| `test_weight_normalization.py` | 21 | Un peso de rotacion es relativo, y cada fuente lo guarda a su manera |

Total: 665 funciones de prueba en 60 archivos (algunas se parametrizan y corren varias veces).

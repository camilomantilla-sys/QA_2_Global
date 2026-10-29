# QA2 — Guía técnica

Para quien tenga que mantener, corregir o ampliar QA2 sin haberlo
escrito. Asume Python; no asume conocer este proyecto.

**Índice**

1. [El recorrido de una corrida](#1-el-recorrido-de-una-corrida)
2. [Los archivos que importan](#2-los-archivos-que-importan)
3. [Conceptos que hay que entender antes de tocar nada](#3-conceptos-que-hay-que-entender-antes-de-tocar-nada)
4. [Catálogo de reglas](#4-catálogo-de-reglas)
5. [Cómo agregar o cambiar una regla](#5-cómo-agregar-o-cambiar-una-regla)
6. [Trampas conocidas](#6-trampas-conocidas)

---

## 1. El recorrido de una corrida

```
Traffic Sheet (.xlsx)        exports de Innovid (.csv)      archivos de tags
        │                             │                            │
        ▼                             ▼                            ▼
 parsers/ts_parser.py        parsers/innovid_export.py     parsers/innovid_tags.py
        │                             │                            │
        └──────────────┬──────────────┘                            │
                       ▼                                           │
              core/matching.py  ── match() ──▶ MatchResult         │
                       │                                           │
                       │        core/innovid_api.py (opcional)     │
                       │        lee de Innovid lo que ningún       │
                       │        export trae                        │
                       ▼                                           ▼
              core/engine.py ── run_rules() ──────────────────────┘
                       │
                       ▼
              core/findings.py ── FindingsBuffer
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ui/app_v2.py   core/pdf_report  core/excel_report
```

**La función que hay que leer primero es `run_rules()` en
`core/engine.py`.** Cabe en una pantalla y es literalmente la lista de
todo lo que QA2 comprueba, en orden. Si algo aparece en el reporte,
salió de una de esas llamadas.

## 2. Los archivos que importan

| Archivo | Qué hace | Cuándo lo vas a tocar |
|---|---|---|
| `core/engine.py` | Orquesta todas las reglas | Al agregar una familia de reglas nueva |
| `core/matching.py` | Cruza TS contra Innovid y arma los pares a comparar | Cuando el cruce se equivoca |
| `core/findings.py` | El `FindingsBuffer`: cómo se emite, degrada y deduplica cada hallazgo | Casi nunca. Es el contrato |
| `parsers/ts_parser.py` | Lee la Traffic Sheet, incluidos los colores | Cuando llega una TS con una forma nueva |
| `parsers/innovid_export.py` | Lee los exports de placements y placement-creative | Cuando cambia el export |
| `parsers/innovid_tags.py` | Lee los archivos de tags | Cuando llega un formato de tags nuevo |
| `core/innovid_api.py` | Entra a Innovid con Playwright y lee lo que solo está en la UI | Cuando Innovid cambia su API |
| `core/tag_analysis.py` | El panel de cobertura de tags | Para cambiar ese panel |
| `ui/app_v2.py` | Toda la interfaz | Constantemente |
| `rules/*.py` | Una familia de reglas por archivo | Al cambiar qué se valida |

### `core/engine.py`

- **`run_rules(match_result, tags_result=None, ..., account="", ts_result=None)`**
  Llama a cada módulo de `rules/` y devuelve el `FindingsBuffer`. Las
  reconciliaciones opcionales (Innovid, píxeles, DV) se pasan como
  argumento y, si vienen en `None`, esa familia de reglas simplemente no
  corre. Es a propósito: Innovid es un servicio externo que tiene días
  malos, y un QA que se cae entero porque una API no respondió no sirve.
- **`_fatal_extraction(ts_result)`**
  Junta las anomalías FATAL de la hoja **y de cada pestaña**. Existe
  porque mirar solo las de arriba dejaba fuera justo las que dicen que
  una pestaña no se pudo leer. Alimenta el `EXT-000`, que bloquea la
  corrida: verde sobre algo que nadie leyó es el peor resultado posible.

### `core/matching.py`

El archivo más denso y el que más se toca. Lo importante:

- **`match(ts_result, export, ...)`** — el punto de entrada. Arma un
  `PlacementMatch` por placement con sus `creative_links`.
- **`compare_placement(pm, res)`** — la comparación de un placement
  contra su fila del export. Se extrajo de `match()` precisamente para
  poder probarla con un placement armado a mano.
- **`_prefer(field, value)`** — clausura dentro del merge de filas.
  Cuando el mismo placement aparece varias veces en la TS (un pedido
  viejo en gris y el actual en blanco), decide con qué valor quedarse:
  gana el que está **en alcance**. Sin esto, un pedido viejo pisaba el
  actual. Cada campo lleva su bandera `<campo>_in_scope`.
- **`placement_clicktags(ap)`** — los clicktags del placement, sean
  propios o los de sus creativos corriendo.
- **`_tracker_cgen(ap)`** — el `third_party_id` de la fila TRACKER. **El
  `Third_Party_ID` del Placement View no es un CGEN**; usarlo como
  respaldo producía falsos FAIL de atribución.
- **`is_site_served_1x1(expected)`** — compartida con
  `innovid_reconciliation`. En 1x1 los creativos van directo al
  placement, sin decision set.

El bloque de URL/triángulo a nivel de placement se calcula **después**
del bucle de creativos, y solo si ningún creativo aportó URL. En 1x1 no
hay creativo que la tenga, así que sin ese bloque la validación de URL y
CGEN de Adobe no ocurría.

### `parsers/ts_parser.py`

- Detecta el perfil de la TS recorriendo **toda** la grilla. Antes
  miraba una muestra, y una TS con las primeras filas ocultas se leía
  como si no tuviera rotaciones. Las filas ocultas nunca llegan al
  parser.
- Traduce el color de cada celda a una **intención** (ver §3).

### `core/findings.py`

- **`FindingsBuffer`** — punto único de emisión. Aplica, en este orden:
  1. **Gate de capacidad** — si falta un insumo, el hallazgo sale
     `NOT_VERIFIED`, no `FAIL` y no en silencio.
  2. **Gate de confianza** — un `FAIL` con confianza menor que `HIGH`
     baja a `REVIEW`.
  3. Coherencia entre `Status` y `Severity`.
  4. Deduplicación por `finding_id`.
- **`Finding.finding_id`** — sha1 de (`rule_id`, `domain`,
  `entity_type`, `placement_id`, `creative_id`, `creative_name`,
  `expected`, `actual`). Determinista: el mismo hallazgo tiene el mismo
  id entre corridas, que es lo que permite que una firma sobreviva a
  volver a correr.
- Métodos de emisión: `pass_()`, `fail()`, `review()`,
  `not_verified()`, `info()`, `blocker()`.

### `ui/app_v2.py`

Un solo archivo grande. Lo que hay que saber para no romperlo está en §6.

- **`trace(stage)`** — escribe `qa_run.log` con marca de tiempo. Es la
  herramienta de diagnóstico: cuando la app se queda pegada, el log dice
  hasta dónde llegó, que es justo lo que no se adivina desde un
  screenshot. Nunca falla: un diagnóstico que rompe la app no sirve.
- **`reuse(slot, signature, build)`** — memoriza el PDF y el Excel. Sin
  esto se reconstruían en cada interacción y la pasada se hacía tan
  larga que el clic siguiente se perdía.
- **`sign_findings(...)`** — la firma. Escribe en `review_overrides`,
  que se aplica al `findings_buffer` al principio de la pasada.

## 3. Conceptos que hay que entender antes de tocar nada

### Los colores son intenciones

La Traffic Sheet se pinta. QA2 lee ese color y lo convierte en qué se
pidió:

| Color | Intención |
|---|---|
| Verde | Ya implementado / confirmado |
| Blanco | Pedido actual |
| Rojo | Quitar |
| Gris | Fuera de alcance (`"SCOPE_EXCLUDED"`) |
| Amarillo | Revisar |

Ojo con el nombre: `"SCOPE_EXCLUDED"` en `ts_parser` es una cadena, y
`core.colors.SCOPE_EXCLUDED` es un **conjunto de colores**. No son lo
mismo.

Un campo pintado significa que **solo ese campo** se pidió. Es lo que
hace `intent_fields`: si en una fila solo está pintada la celda de URL,
no se está pidiendo cambiar el nombre.

### La escalera de veredictos

```
BLOCKED  >  FAILED  >  NEEDS_REVIEW  >  PASSED
```

`NEEDS_REVIEW` cubre tanto los `REVIEW` como los `NOT_VERIFIED`. Un
`NOT_VERIFIED` no es un aprobado: es "esto no se pudo comprobar", y
tiene que verse.

### Dos veredictos, no uno

La misma escalera se calcula **dos veces**, sobre dos mitades de los
hallazgos (`core/verdict.py`):

| Alcance | Dominios |
|---|---|
| **Implementation** | todo lo demás: `Scope`, `Identity`, `Dates`, `Dimensions`, `Creative`, `Rotation`, `URL`, `Attribution`, `Cardinality`, `Structure`, `Ingestion` |
| **Tags & pixels** | `Pixel`, `Tag` |

Porque no se arreglan igual: un creativo mal asignado lo corrige AdOps
en Innovid; un píxel que no ha llegado se espera. Con un solo veredicto,
un vendor que todavía no mandó su píxel teñía de rojo un trafficking
perfecto.

**El veredicto que manda sigue siendo el peor de los dos** — con los
tags mal el QA no está aprobado. Lo que aporta la separación es decir
*cuál* de los dos hay que mirar, y eso sale como una frase encima de
todo: *"The implementation is fine. Take a look at the tags and
pixels."* Cuando los dos están bien, no dice nada.

### Lo que no se pudo comprobar nunca pasa en verde

La regla de oro del proyecto. Si falta el insumo, el hallazgo sale
`NOT_VERIFIED` con el motivo. El caso que lo originó: una solicitud de
355 cambios de rotación cerró en verde sin haber comparado ni uno,
porque el porcentaje vive dentro del decision set y el export dice
literalmente `"Decision Tree"` en la columna Rotation.

### 1x1 no es display

En site-served 1x1 los creativos van **directo al placement**: no hay
decision set, el creativo hereda las fechas del placement, el CGEN está
a nivel de creativo en el `Third_Party_ID` de placement-creative, y el
Creative Rotation Name de la TS es solo una guía para el traficante. Un
placement puede aparecer duplicado en el export porque tiene más de un
creativo. `0x0` y `1920x1080` significan lo mismo.

## 4. Catálogo de reglas

Estado: `PASS` · `FAIL` · `REVIEW` · `NOT_VERIFIED` · `INFO` · `BLOCKED`.

### Ingesta — `core/engine.py`, `core/extraction.py`

| ID | Qué comprueba | Si falla |
|---|---|---|
| `EXT-000` | La TS se pudo leer | **BLOCKED**. La corrida no continúa |
| `EXT-001` | Una columna requerida existe pero está 100% vacía | FATAL. Casi siempre es un error de exportación |

### Placements — `rules/placements.py`, `rules/naming.py`

| ID | Qué comprueba | Notas |
|---|---|---|
| `PLC-001` | El placement de la TS existe en Innovid | El más básico |
| `PLC-002` | La desasignación se confirmó: el placement está detenido | Solo en pedidos de remoción |
| `PLC-006` | El Placement Name coincide | En `rules/naming.py` |
| `PLC-007` | La rotación que el placement declara tiene al menos un creativo de su dimensión | REVIEW. Salta cuando el filtro por dimensión se lleva **todos** los creativos pedidos: la TS nombró una rotación de otro tamaño |

### Creativos y rotación — `rules/creatives.py`, `rules/rotation.py`

| ID | Qué comprueba | Notas |
|---|---|---|
| `CRE-001` | El creativo existe en el export | Encontrar el creativo es verdad; que la rotación quedó como se pidió, no |
| `CRE-002` | El pixel 1x1 está asignado, en un placement site-served | Adobe: la TS dice `N/A` porque el creativo lo sirve el publisher. Sin esto el placement se quedaba sin ninguna comprobación de creativo |
| `CRE-008` | La rotación (capacidad `ROTATION`) | |
| `ROT-001` | El cambio de rotación pedido se aplicó | Sin Innovid conectado sale `NOT_VERIFIED`, nunca `PASS` |

### URLs — `rules/urls.py`

| ID | Qué comprueba |
|---|---|
| `URL-001` | La URL de la TS coincide con el clicktag de Innovid |
| `URL-002` | La landing page nueva está viva en Innovid |
| `URL-003` | URLs de placements directos. Un clicktag huérfano sobre un placement retirado es `INFO`, no `FAIL` |

Mensajes que se ven seguido: *"TS declares a URL, but Innovid has no
Clicktag"*, *"The URL could not be parsed correctly"*.

### Atribución — `rules/attribution.py`

| ID | Qué comprueba |
|---|---|
| `ATR-001` | El triángulo CGEN a nivel de creativo |
| `ATR-002` | El triángulo a nivel de placement (`_evaluate_placement_triangle`) |

Solo corre para cuentas que manejan CGEN — hoy Adobe. `run_rules` pasa
`account=` justamente para eso.

### Decision trees y sets — `rules/dtree.py`, `rules/dset.py`

| ID | Qué comprueba |
|---|---|
| `TRK-001` | El Decision Tree es el correcto |
| `TRK-002` | El Decision Set es el correcto |

### Lo que solo sabe Innovid — `rules/innovid.py`

Ningún export trae estos tres campos; hasta ahora se revisaban abriendo
la interfaz a mano.

| ID | Qué comprueba |
|---|---|
| `INV-001` | Fechas de vuelo del creativo dentro del decision set |
| `INV-002` | Peso de rotación del creativo |
| `INV-003` | Verification Partner configurado en el placement |
| `INV-004` | |

Los creativos blancos entran como contexto pero no generan hallazgos,
igual que en el resto de QA2.

### Tags — `rules/tags.py`

| ID | Qué comprueba | Estado |
|---|---|---|
| `TAG-001` | El archivo de tags declara el Campaign ID correcto | |
| `TAG-002` | El Placement ID del tag existe en Innovid | |
| `TAG-003` | El Placement ID pertenece al alcance trabajado | |
| `TAG-004` | El Placement Name del tag coincide | |
| `TAG-005` | Dimensiones | |
| `TAG-006` | Third Party ID en el archivo de tags | **Retirada.** Eso no se valida en los tags |
| `TAG-007` | Placement ID embebido en el tag | Desactivada |
| `TAG-008` | Campaign ID embebido en el tag | |
| `TAG-009` | Dimensiones embebidas | |
| `TAG-010` | El tag no está vacío | |
| `TAG-011` | El placement no está duplicado dentro del archivo | |
| `TAG-014` | La landing page dentro del click tag de 1x1 | Ver abajo |

**`TAG-014`** es la única regla que mira el **destino** dentro del
archivo entregado, y la única que juzga el artefacto que el sitio
realmente recibe sin pasar por Innovid. El click tag de Flashtalking
tiene esta forma:

```
.../click/8/<campaign>;<placement>;<creative>;211;0/?gdpr=…&force_transparent=true&url=<landing page>
```

La landing page es **la cola**, no un parámetro parseable: trae su
propio `?` y sus propios `&` adentro. Por eso `_clicked_url()` corta en
el último `&url=` y se queda con todo lo que sigue, en vez de usar un
parser de query strings.

La regla habla solo donde hay evidencia, lo que resuelve el caso de
Adobe sin lista de excepciones: `Update_Clicktag1` pone un identificador
en el mismo parámetro (`&url=45754586`) y se deja en paz; los que mandan
`ftrack 1x1 click` sin `url=` no generan nada; los que sí mandan
`Static_Clicktag1` con la landing page se comprueban.

Reglas de tags en otros archivos:

| ID | Archivo | Qué comprueba |
|---|---|---|
| `TAG-012` | `rules/adobe_tag_policy.py` | Política de columnas de Adobe (FTRACK / Protected) |
| `TAG-013` | `rules/tag_coverage.py` | Los tags de este placement se entregaron |

### Píxeles — `rules/pixels.py`, `rules/adobe_pixels.py`

| ID | Qué comprueba |
|---|---|
| `PIX-002` | El píxel del vendor está en su columna (Third Party Survey / Third Party Impression) |
| `PIX-A01` | DISQO en Adobe, según el tipo de placement |

`PIX-A01` es el que más cuesta. **La fuente de la evidencia depende del
tipo de placement:**

- **Site-served 1x1** — basta una columna DISQO poblada en el archivo de
  tags entregado.
- **Third Party** — basta una implementación reconocida de DISQO o Active
  Metering en `Third_Party_Impression` **de Innovid**, no en los tags.

FTRACK y Protected no generan `PIX-A01`: tienen reglas de aplicabilidad
distintas. Lo marcado N/A se excluye a propósito.

### DV — `rules/dv_tags.py`, `rules/dv_omni.py`

| ID | Qué comprueba |
|---|---|
| `DV-001` | El tag de DV Pinnacle se generó y entregó |
| `DV-002` | Placements que están en el archivo de DV pero no en el alcance (`INFO`) |
| `DV-003` | DV Omni |

`DV-001` no exige tags cuando el pedido no es de placement nuevo: los
tags se descargan cuando los placements **se crean**; un swap o una
desasignación no genera ninguno.

### Default ads — `rules/defaults.py`

| ID | Qué comprueba |
|---|---|
| `DEF-001` | El default ad de esta dimensión es el mismo que en el resto de los placements |

### Tablas editables

Estas tres no son reglas sino configuración, y se editan **dentro de la
app**, sin tocar código:

| Tabla | Archivo | En la app |
|---|---|---|
| Vendors / píxeles por cuenta | `config/vendor_pixels.json` | Pixels by account |
| Píxeles oficiales de Adobe | `config/vendor_pixels_adobe.json` | Adobe pixels |
| Roster del equipo | `config/team_roster.json` | Team |

Con `QA2_CONFIG_DIR` apuntando a SharePoint, la edición queda compartida
para todo el equipo (ver [`SEGURIDAD.md`](SEGURIDAD.md) §5).

## 5. Cómo agregar o cambiar una regla

1. **Encuentra la familia.** Una regla de URL va en `rules/urls.py`, una
   de tags en `rules/tags.py`. Familia nueva = archivo nuevo, más una
   línea en `run_rules()`.
2. **Escribe la comprobación.** Cada módulo de reglas expone
   `evaluate(...)` y recibe el `buffer`. Emite con `buffer.pass_()`,
   `buffer.fail()`, `buffer.review()` o `buffer.not_verified()`.
3. **Decide qué pasa si falta el insumo.** Esta es la parte que se
   olvida. Si la comprobación no se puede hacer, va `not_verified()` con
   el motivo — **nunca** `pass_()` y nunca silencio.
4. **Escribe la prueba primero si puedes.** Un archivo por tema en
   `tests/`, nombres de test que digan la afirmación en palabras:
   `test_a_removed_placement_is_not_a_missing_one`.
5. **Corre todo:** `pytest tests/`.
6. **Anota el cambio** en [`CHANGELOG.md`](CHANGELOG.md).

Ejemplo mínimo:

```python
# rules/mi_regla.py
from core.findings import Domain, EntityType

RULE_ID = "XXX-001"


def evaluate(match_result, buffer):
    for pm in match_result.placements:
        common = dict(
            rule_id=RULE_ID,
            domain=Domain.PLACEMENT,
            entity_type=EntityType.PLACEMENT,
            placement_id=pm.placement_id,
            placement_name=pm.expected.name,
        )
        if pm.algo_que_falta:
            buffer.not_verified(
                message="No se pudo comprobar: falta X.", **common
            )
        elif pm.esta_bien:
            buffer.pass_(message="X es correcto.", **common)
        else:
            buffer.fail(
                message="X no coincide.",
                expected=pm.expected.x,
                actual=pm.actual.x,
                recommended_action="Ajustar X en Innovid.",
                **common,
            )
```

## 6. Trampas conocidas

Cada una costó una sesión entera de depuración.

### Streamlit vuelve a correr el script entero en cada interacción

No es una app con estado que reacciona a eventos: cada clic vuelve a
ejecutar `app_v2.py` de arriba abajo. De ahí se sigue todo lo demás.

### `st.tabs` ejecuta el cuerpo de **todas** las pestañas

Se vea cuál se vea. Un panel pesado escondido en la pestaña 4 se
construye igual. Por eso la app usa `st.segmented_control` y dibuja solo
la sección elegida.

### `st.expander` ejecuta su cuerpo esté abierto o cerrado

Mismo problema. Por eso la lista de placements dibuja solo el que está
abierto.

### Mientras corre una pasada, Streamlit no atiende la siguiente interacción

Un clic durante una pasada **se pierde**. Si una pasada tarda, el botón
de firma "no funciona" sin que haya nada roto en el código de la firma.
Fue la causa de tres sesiones de diagnóstico. El log
(`qa_run.log`) es lo que lo resuelve.

### `st.rerun()` descarta la pasada en curso

Puesto **encima** de un botón, se come el clic de ese botón. Los
manejadores de firma llaman a `st.rerun()` **después** de firmar, nunca
antes. `tests/test_review_approve_buttons.py` fija esto: falla si
aparece un `st.rerun()` antes de los controles de firma.

### El peso de la página es un límite real

44 placements con su cuerpo desplegado no los pinta el navegador. La
lista se dibuja entera (72 filas en 15 ms); el cuerpo, solo el abierto.

### Módulos de prueba que son scripts

Cinco archivos de `tests/` (`test_innovid_csrf*.py`,
`test_innovid_session.py`, `test_innovid_diagnose.py`) no tienen
funciones `test_`: corren enteros al importarse y **reescriben globales
del módulo `innovid_api`** para apuntar a un servidor falso. Si no las
devuelven a su valor, contaminan todo lo que corra después — pasaba
justo eso, y seis pruebas de otro archivo fallaban solo en la corrida
completa. Cada uno guarda los valores reales en `_REAL_ENDPOINTS` y los
restaura tras `srv.shutdown()`. **Si agregas otro script así, haz lo
mismo.**

---

*¿Falta algo aquí? Agrégalo. Esta guía solo sirve si se mantiene al día
con el código.*

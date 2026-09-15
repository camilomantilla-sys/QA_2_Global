# QA2 — Nota de seguridad

**Para:** revisión de IT / seguridad de la información antes del lanzamiento
**Aplicación:** QA2 — automatización del QA de Traffic Sheets contra Innovid/Flashtalking
**Última revisión:** 2026-09-15

---

## 1. Qué es QA2, en una frase

Una herramienta de escritorio que lee la Traffic Sheet y los exports que el
equipo ya descarga a mano, los compara, y escribe un reporte. Se dibuja en el
navegador porque está hecha con Streamlit, pero **no es un sitio web**: corre
en la máquina de quien la usa y en ninguna otra.

## 2. Dónde corre

| | |
|---|---|
| Ejecución | Local, en el equipo del analista |
| Servidor | Ninguno. No hay despliegue, no hay host, no hay base de datos |
| Puerto | `localhost:8501`, **enlazado solo a la interfaz local** |
| Cuentas | Ninguna cuenta propia. QA2 no tiene usuarios, ni login propio, ni directorio |

El enlace a `localhost` está fijado a propósito en `.streamlit/config.toml`:

```toml
[server]
address = "localhost"
enableCORS = true
enableXsrfProtection = true
```

Streamlit **no** trae ese `address` por defecto: sin él escucharía en todas las
interfaces, y cualquiera en la red corporativa podría abrir la sesión de QA de
otra persona. Está puesto explícitamente, y hay una prueba automática que
falla si alguien lo quita (`tests/test_config_locations.py`).

## 3. Qué sale de la máquina

QA2 no tiene cliente HTTP propio. No hay `requests`, `httpx`, `urlopen` ni
sockets en el código de la aplicación. El único tráfico saliente lo genera
Playwright manejando un Chromium local, y va a cuatro destinos, todos de
Innovid/Flashtalking:

| Destino | Para qué |
|---|---|
| `uam-login.mediaocean.com` | El login corporativo que el analista ya usa a diario |
| `campaign-manager.flashtalking.net` | Origen de la aplicación de Innovid |
| `api.flashtalking.net/cm/v1/ui` | Campos que solo existen en la interfaz (fechas de vuelo, pesos de rotación, Verification Partner) |
| `api.flashtalking.net/dt/v1/ui` | Decision trees / decision sets |

Es decir: **QA2 lee de Innovid exactamente lo que el analista leería abriendo
Innovid**, con su propia sesión y sus propios permisos. No amplía el acceso de
nadie; automatiza la lectura.

Lo que **no** ocurre:

- No hay telemetría. `gatherUsageStats = false` en la configuración de Streamlit.
- No se sube ninguna Traffic Sheet, ningún export y ningún tag a ningún servicio.
- No hay analítica, ni *crash reporting*, ni llamadas a terceros.
- No hay servicios de IA en tiempo de ejecución. QA2 no llama a ningún modelo;
  las reglas son código Python determinista (ver §7).

Hay una prueba que enumera los hosts alcanzables desde el código y falla si
aparece uno nuevo, para que agregar un destino sea una decisión deliberada y no
algo que llegue con un copy-paste.

## 4. Datos: qué se guarda y dónde

| Dato | Dónde queda | En Git |
|---|---|---|
| Traffic Sheets y exports cargados | En memoria durante la corrida | No |
| Reporte PDF / Excel | Solo donde el usuario elija guardarlo | No |
| Log de corrida (`qa_run.log`) | Carpeta `logs/`, o `QA2_OUTPUT_DIR` | No (gitignored) |
| Tablas de vendors y roster | `config/*.json`, o `QA2_CONFIG_DIR` | Sí — son configuración, sin datos de cliente |
| **Contraseña de Innovid** | `config/innovid_credentials.env` | **No** (gitignored) |
| **Cookies de sesión de Innovid** | `config/innovid_session.json` | **No** (gitignored) |

El log de corrida guarda marcas de tiempo y etapas (`parsing TS`, `building the
Excel`), no contenido de cliente. Cuando QA2 registra una petición a Innovid
para diagnóstico, el cuerpo pasa por `redact_body()`, que muestra los nombres de
los campos y no sus valores.

### Las credenciales no se pueden mover

Esto es deliberado y vale la pena subrayarlo. Los dos archivos sensibles —la
contraseña y las cookies, que valen lo mismo que la contraseña hasta que
expiran— **no se pueden redirigir a una carpeta compartida**, por más que se
configure el entorno. Resuelven siempre a la carpeta local del proyecto:

```python
# core/paths.py
LOCAL_ONLY_FILES = ("innovid_credentials.env", "innovid_session.json")
```

Un drive compartido es justamente donde no deben estar. Hay dos pruebas que lo
verifican: que no se redirigen, y que no están en Git.

## 5. Almacenamiento compartido (SharePoint)

Lo que el equipo comparte son las **tablas editables**: la de vendors/píxeles
por cuenta, la de píxeles de Adobe, y el roster del equipo. Antes cada quien
tenía su copia; ahora pueden vivir en una carpeta única.

Una biblioteca de SharePoint sincronizada con OneDrive es, en Windows, una
carpeta normal. Así que basta apuntar una variable de entorno:

```
QA2_CONFIG_DIR = C:\Users\<usuario>\WPP Media\QA2 - Documentos\config
QA2_OUTPUT_DIR = C:\Users\<usuario>\WPP Media\QA2 - Documentos\evidencia
```

Con eso:

- Quien edite la tabla de vendors en la app, la guarda en SharePoint.
- El siguiente que corra QA2 la lee de ahí.
- El control de acceso y el versionado los pone SharePoint, no QA2.
- Si la carpeta está vacía, QA2 sigue funcionando con los valores que trae el
  proyecto, y empieza a usar la compartida en cuanto alguien guarde por primera
  vez. No hay una migración que coordinar.

Sin esas variables, todo queda local exactamente como hoy.

## 6. Editable, y por quién

El código es Python plano en el repositorio de la cuenta
(`camilomantilla-sys/qa_2_global`). No está compilado, no está ofuscado, no
depende de ningún servicio de nadie. Cualquier persona del equipo con Python
puede leerlo, cambiarlo y correrlo.

Tres niveles de edición, de menor a mayor:

1. **Sin tocar código** — las tablas de vendors, píxeles de Adobe y roster se
   editan dentro de la app y se guardan en SharePoint.
2. **Una regla** — cada regla vive en su propio archivo bajo `rules/`, con su
   prueba al lado en `tests/`. La guía está en
   [`GUIA_TECNICA.md`](GUIA_TECNICA.md).
3. **El motor** — `core/matching.py` y `parsers/ts_parser.py`. También
   documentados en la guía.

Hay 39 archivos de pruebas automáticas. Cualquier cambio se valida con
`pytest tests/` antes de distribuirse.

## 7. La pregunta sobre asistentes de IA

QA2 se escribió con ayuda de un asistente de programación (Claude Code), igual
que cualquier equipo usa hoy un autocompletado o un asistente de IDE. Vale
aclarar exactamente qué implica y qué no:

**En tiempo de ejecución no hay ninguna IA.** QA2 no llama a ningún modelo, no
manda datos a ningún proveedor de IA y no necesita conexión a ninguno. Si se
apagara mañana cualquier servicio de IA, QA2 seguiría corriendo idéntico. Las
reglas son comparaciones deterministas escritas en Python: el mismo insumo da
el mismo resultado siempre, y ese resultado se puede auditar leyendo el código.

**En el código que se distribuye no aparece ningún asistente.** Se verificó
sobre todo el árbol: cero menciones de Claude, Anthropic o cualquier otro
proveedor en `core/`, `rules/`, `parsers/`, `ui/`, `cli/`, `scripts/` y
`config/`. Hay una prueba (`test_the_shipped_code_names_no_ai_assistant`) que lo
mantiene así.

**Dónde sí aparece:** en los *mensajes de commit* del historial de Git, que
llevan la línea `Co-Authored-By:` y un enlace de sesión. Es la atribución de
autoría estándar de la herramienta —el equivalente a firmar quién escribió cada
cambio—, vive en los metadatos del repositorio y no en el producto. No viaja en
el paquete que se distribuye al equipo (ver `scripts/package_release.py`, que
empaqueta el árbol de archivos sin el historial).

Si IT prefiere que el historial tampoco lo lleve, se puede reescribir para
quitar esas líneas de los mensajes. Es un cambio cosmético sobre metadatos y no
toca una sola línea de código; conviene decidirlo antes del lanzamiento porque
reescribir el historial después obliga a todos a volver a clonar.

## 8. Dependencias

Todas de PyPI, todas de uso común, fijadas en `requirements.txt`:

| Paquete | Para qué |
|---|---|
| `streamlit` | La interfaz |
| `pandas`, `openpyxl` | Leer y escribir Excel |
| `reportlab`, `fonttools` | El PDF del reporte |
| `playwright` | El navegador que entra a Innovid |
| `typer`, `rich` | La versión de línea de comandos |
| `brotli` | Descomprimir respuestas de Innovid |

Ninguna es un paquete oscuro ni de un solo autor. Se instalan en un entorno
virtual dentro de la carpeta del proyecto (`.venv/`), no en el Python del
sistema.

## 9. Resumen para el revisor

| Pregunta | Respuesta |
|---|---|
| ¿Expone un servicio en la red? | No. Solo `localhost`. |
| ¿Sube datos de cliente a algún lado? | No. |
| ¿Guarda credenciales? | Sí, las de Innovid del propio analista, en un archivo local fuera de Git, que no se puede mover a una carpeta compartida. |
| ¿Amplía los permisos de alguien? | No. Lee Innovid con la sesión del usuario. |
| ¿Tiene telemetría? | No, desactivada explícitamente. |
| ¿Usa IA en ejecución? | No. Reglas deterministas en Python. |
| ¿Se puede auditar? | Sí. Código fuente completo, 39 archivos de pruebas. |
| ¿Quién lo mantiene? | El equipo, con la guía técnica en `docs/GUIA_TECNICA.md`. |

---

*Las afirmaciones de esta nota que se pueden verificar automáticamente están
cubiertas por `tests/test_config_locations.py`. Si alguna deja de ser cierta,
la suite falla.*

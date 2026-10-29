# Léeme primero: por dónde leer QA2 y cómo prepararse en seguridad

Esta guía es el punto de partida para quien abre la carpeta de QA2 en
VS Code y quiere entender el proyecto: qué leer, en qué orden, y cómo
prepararse para responder preguntas de seguridad ante dirección o IT.

## 1. La ruta de lectura

Abre la carpeta en VS Code. Para leer un `.md` con formato, ábrelo y
presiona `Ctrl+Shift+V` (vista previa). `Ctrl+P` busca cualquier archivo
por nombre.

| Orden | Archivo | Qué te deja | Tiempo |
|---|---|---|---|
| 1 | [`README.md`](../README.md) | Qué es QA2, cómo funciona una corrida, principios de diseño, archivos clave, seguridad resumida | 15 min |
| 2 | [`docs/SEGURIDAD.md`](SEGURIDAD.md) | La nota de seguridad completa, pensada para IT. Es la base de cualquier conversación de seguridad | 20 min |
| 3 | [`docs/REFERENCIA_TECNICA.md`](REFERENCIA_TECNICA.md) | El manual completo: cada parte con sus funciones y código. Lee primero §1 a §3, §11 (Innovid y Playwright) y §18 (preguntas frecuentes) | 1 h |
| 4 | [`docs/MAPA_DEL_CODIGO.md`](MAPA_DEL_CODIGO.md) | El índice de todo: cada archivo, clase y función. No se lee de corrido; se consulta con `Ctrl+F` | Consulta |
| 5 | [`docs/GUIA_TECNICA.md`](GUIA_TECNICA.md) | Catálogo de reglas y trampas conocidas de Streamlit | 30 min |
| 6 | [`docs/copilot/GUIA_AGENTE_COPILOT.md`](copilot/GUIA_AGENTE_COPILOT.md) | Cómo armar el agente de Copilot y pegar sus cambios sin romper nada | 10 min |

### Dónde está cada cosa en la carpeta

```
README.md                      Empieza aquí
docs/                          Toda la documentación
  LEEME_PRIMERO.md             Esta guía
  SEGURIDAD.md                 Seguridad (para IT y dirección)
  REFERENCIA_TECNICA.md        Manual técnico completo
  MAPA_DEL_CODIGO.md           Índice de funciones (se genera solo)
  GUIA_TECNICA.md              Reglas y trampas
  copilot/                     Agente de Copilot: instrucciones y guía
.github/copilot-instructions.md   Reglas para Copilot dentro de VS Code
core/                          El motor
  paths.py                     Dónde se guarda cada archivo (credenciales siempre locales)
  innovid_api.py               Toda la conexión a Innovid con Playwright
  innovid_login.py             Abre la ventana de inicio de sesión desde la app
  matching.py                  Empareja la Traffic Sheet contra Innovid
  findings.py, verdict.py      Hallazgos y veredictos
parsers/                       Leen la Traffic Sheet, los exports y los tags
rules/                         Las reglas de QA, una familia por archivo
ui/app_v2.py                   Toda la interfaz
config/                        Tablas editables (JSON) y, solo en tu PC, la sesión de Innovid
.streamlit/config.toml         Fija la app a localhost
tests/                         Las pruebas automáticas
tests/test_config_locations.py Las pruebas que garantizan la seguridad
```

### Si solo tienes 30 minutos antes de una reunión

1. `docs/SEGURIDAD.md` §9 (la tabla de resumen para el revisor).
2. `docs/REFERENCIA_TECNICA.md` §11 (Innovid y Playwright).
3. `docs/REFERENCIA_TECNICA.md` §18, la parte "Seguridad y accesos".
4. La sección 3 de esta guía (las preguntas difíciles).

## 2. Seguridad en cinco ideas

Si solo recuerdas cinco cosas, que sean estas. Cada una tiene dónde
comprobarla en el código.

1. **Corre solo en el PC del analista.** No hay servidor, base de datos
   ni cuentas propias. La app escucha solo en `localhost:8501`
   (`.streamlit/config.toml`) y una prueba falla si alguien quita esa
   línea.
2. **Solo habla con Innovid.** No hay cliente HTTP propio en el código.
   El único tráfico lo genera Playwright hacia el login de Mediaocean y
   los dominios de Flashtalking. Una prueba enumera los hosts del
   código y falla si aparece uno nuevo. No hay telemetría
   (`gatherUsageStats = false`).
3. **Lee, no escribe.** Con Innovid hay exactamente dos consultas: un
   `POST` de búsqueda a `/summary` (el cuerpo solo lleva paginación y
   filtros) y un `GET` a `/dset/`. Ninguna crea, modifica ni borra
   (`core/innovid_api.py`).
4. **Usa los permisos del analista, nada más.** El analista inicia
   sesión a mano en una ventana de Chromium, con su login de siempre.
   QA2 ve lo mismo que esa persona vería en Innovid; si no tiene acceso
   a una campaña, Innovid responde 403 y QA2 lo informa.
5. **Las credenciales no se mueven.** `config/innovid_session.json`
   (las cookies, que valen lo mismo que la contraseña hasta que vencen)
   y `config/innovid_credentials.env` están fuera de Git, fuera del
   paquete y no se pueden redirigir a SharePoint
   (`core/paths.LOCAL_ONLY_FILES`). Hay pruebas para ambas cosas.

Y una sexta para cuando pregunten por IA: **QA2 no usa IA al
ejecutarse.** Las reglas son Python determinista: el mismo insumo da
siempre el mismo resultado.

## 3. Las preguntas difíciles

Practica responderlas en voz alta. Al lado va dónde está el respaldo.

**¿Qué es Playwright y por qué una herramienta de pruebas entra a Innovid?**
Es una librería de Microsoft, de código abierto y de uso muy extendido,
que controla un navegador Chromium. QA2 la usa como "un navegador que
lee": abre una ventana para que el analista inicie sesión y luego, con
esa sesión, consulta los tres datos que no vienen en ningún export
(Verification Partner, peso de rotación y fechas del creativo en el
decision set). Respaldo: `docs/REFERENCIA_TECNICA.md` §11.

**¿QA2 se salta la seguridad de Innovid?**
No. No adivina contraseñas, no usa cuentas de servicio y no evita el
login: la persona inicia sesión a mano en la página oficial. Las
consultas llevan la misma cookie y el mismo token CSRF que usa la
interfaz de Innovid. Respaldo: `establish_session()` y `_api_get_json()`
en `core/innovid_api.py`.

**¿La API que usa es oficial?**
Es la API interna que usa la propia interfaz web de Innovid, no una API
pública documentada. Por eso puede cambiar sin aviso. Si cambia, QA2 no
falla en silencio: esas comprobaciones salen `NOT_VERIFIED` y el
resto del QA sigue funcionando con los exports. Si IT o legal preguntan
si los términos de Innovid lo permiten, la respuesta honesta es que
conviene confirmarlo con el contacto de Innovid; lo que sí se puede
afirmar es que solo lee lo que el analista ya ve en pantalla. Respaldo:
`docs/REFERENCIA_TECNICA.md` §11, "Errores y qué significan".

**¿Qué pasa si se roban el portátil de un analista?**
El riesgo es `config/innovid_session.json`: mientras no venza, da acceso
a Innovid como ese analista, igual que un navegador con la sesión
abierta. Protecciones: el archivo nunca sale de esa carpeta (ni a Git,
ni al paquete, ni a SharePoint), la sesión vence sola, y la protección
del equipo en sí (cifrado del disco, bloqueo de pantalla) es la del
estándar corporativo. Qué hacer: cerrar la sesión de Innovid de esa
cuenta o cambiar la contraseña, lo que invalida las cookies. Respaldo:
`docs/SEGURIDAD.md` §4.

**¿Dónde queda la contraseña?**
En el flujo recomendado, en ningún lado: el analista la escribe en la
página de login y QA2 solo guarda las cookies de la sesión. Existe una
vía de respaldo con `config/innovid_credentials.env`, que no se
recomienda y que, si se usa, también queda solo en ese PC y fuera de
Git. Respaldo: `load_credentials()` en `core/innovid_api.py`.

**¿Qué datos de cliente se guardan?**
Las Traffic Sheets y los exports se leen en memoria durante la corrida.
El reporte queda solo donde el usuario lo guarde. El log
(`logs/qa_run.log`) guarda etapas y tiempos; cuando registra una
consulta a Innovid, limpia la URL y el cuerpo con `redact_url()` y
`redact_body()`. Respaldo: `docs/SEGURIDAD.md` §4.

**¿Alguien en la red puede abrir mi QA2?**
No. La app escucha solo en `localhost`. Streamlit, por defecto,
escucharía en todas las interfaces; por eso está fijado en
`.streamlit/config.toml` y hay una prueba que lo vigila. Respaldo:
`docs/SEGURIDAD.md` §2.

**¿Qué instala en el PC?**
Python con las librerías de `requirements.txt` dentro de la carpeta del
proyecto (`.venv/`), y un Chromium dentro de `browsers/`. No toca el
Python del sistema ni instala servicios. Respaldo: `docs/SEGURIDAD.md`
§8.

**¿Cómo sabemos que todo esto sigue siendo cierto mañana?**
Las afirmaciones que se pueden comprobar con código están cubiertas por
`tests/test_config_locations.py`: localhost, hosts permitidos, archivos
que no se mueven, archivos que no están en Git y que el repositorio no
nombra proveedores de IA ni correos personales. Si alguien rompe una,
`python -m pytest tests/` falla antes de distribuir.

**¿Usar Copilot para editar QA2 expone algo?**
El agente recibe el código y la documentación, que no tienen datos de
cliente ni credenciales; `scripts/export_copilot_context.py` se niega a
terminar si se cuela la sesión, las credenciales o una hoja de cálculo.
Copilot no ejecuta nada ni entra a Innovid: propone código, una persona
lo revisa, lo pega y corre las pruebas. Lo que nunca se le pasa está en
`docs/copilot/GUIA_AGENTE_COPILOT.md` §5.

**¿Quién lo mantiene si el autor no está?**
El código es Python plano, sin compilar, con la referencia técnica, el
mapa del código y las pruebas automáticas. Cualquier persona con Python
puede leerlo y cambiarlo, y las pruebas le dicen si rompió algo.

## 4. Verifícalo tú mismo en VS Code

Comprobar con tus ojos da otra seguridad al hablar. Con `Ctrl+Shift+F`
(buscar en todos los archivos):

| Busca | Dónde lo vas a ver | Qué demuestra |
|---|---|---|
| `address = "localhost"` | `.streamlit/config.toml` | Solo escucha en tu PC |
| `gatherUsageStats` | `.streamlit/config.toml` | Telemetría apagada |
| `LOCAL_ONLY_FILES` | `core/paths.py` | Las credenciales no se mueven |
| `flashtalking.net` | `core/innovid_api.py` | Los únicos destinos externos |
| `def redact_body` | `core/innovid_api.py` | Qué se limpia antes de registrar |
| `innovid_session` | `.gitignore` | La sesión no va a Git |
| `def test_` | `tests/test_config_locations.py` | Cada garantía y su prueba |

Y en la terminal:

```bash
python -m pytest tests/test_config_locations.py -v
```

Muestra, una por una, las pruebas de seguridad con su nombre en
palabras.

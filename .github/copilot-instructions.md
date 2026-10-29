# Instrucciones para asistentes de código en QA2

QA2 es una aplicación interna de WPP Media (Ad Operations) que automatiza
el segundo QA de implementaciones en Innovid. Compara la Traffic Sheet
(Excel de la solicitud) con los exports de Innovid y, opcionalmente, con
la API interna de Innovid, y entrega hallazgos y un reporte Excel/PDF.

Antes de proponer un cambio, lee:

- `docs/REFERENCIA_TECNICA.md`: cómo funciona todo, con funciones y ejemplos.
- `docs/MAPA_DEL_CODIGO.md`: dónde está cada función (generado desde el código).
- `docs/GUIA_TECNICA.md`: catálogo de reglas y trampas de Streamlit.
- `docs/SEGURIDAD.md`: garantías de seguridad que no se pueden romper.

## Stack

Python 3.11+, Streamlit (interfaz), pandas y openpyxl (Excel), Playwright
(Chromium para Innovid), ReportLab (PDF), pytest (pruebas). Corre en
local, en Windows, desde un paquete portátil.

## Arquitectura en una línea por carpeta

- `parsers/`: leen archivos. No deciden si algo está bien o mal.
- `core/matching.py`: empareja TS contra Innovid (`match()` → `MatchResult`).
- `core/*_reconciliation.py`: cruces de varias fuentes.
- `rules/`: una familia de reglas por archivo; cada una expone `evaluate(...)`.
- `core/engine.py`: `run_rules()` llama a todas las reglas en orden.
- `core/findings.py`: `Finding` y `FindingsBuffer`, el contrato de salida.
- `core/verdict.py`: dos veredictos (Implementation y Tags & pixels).
- `ui/app_v2.py`: toda la interfaz.

## Reglas que el código siempre respeta

1. **Lo que no se pudo comprobar nunca pasa en verde.** Si falta el
   insumo, se emite `buffer.not_verified(...)` con el motivo. Nunca
   `pass_()` por defecto y nunca silencio.
2. **Las reglas emiten por el buffer**: `pass_`, `fail`, `review`,
   `not_verified`, `info`, `blocker`. No se construyen `Finding` a mano.
3. **Sin emparejamiento fuerte no hay FAIL.** El buffer baja a REVIEW
   los FAIL con confianza menor que HIGH.
4. **El color de la celda es la intención.** Verde = nuevo, rojo =
   quitar, gris y amarillo = fuera de alcance, blanco = contexto. Se
   pregunta con `core.intent.requested(creative, aspecto)`.
5. **Los parsers no juzgan y las reglas no leen archivos ni red.**
6. **Las columnas se declaran una vez** en `core/ts_schema.py` (TS) y
   `core/schema.py` (Innovid). Un nombre nuevo de columna es un alias ahí.
7. **Textos de la interfaz y de los reportes en inglés.** Comentarios y
   documentación pueden ir en español.

## Seguridad (no negociable)

- La app escucha solo en `localhost` (`.streamlit/config.toml`).
- El único tráfico externo es hacia Innovid/Flashtalking y el login de
  Mediaocean. No agregues clientes HTTP, telemetría ni servicios
  externos. `tests/test_config_locations.py` falla si aparece un host nuevo.
- Las llamadas a Innovid son de **solo lectura**. No agregues llamadas
  que creen, modifiquen o borren.
- `config/innovid_session.json` y `config/innovid_credentials.env` nunca
  van a Git, al paquete, a los logs ni a una carpeta compartida
  (`core/paths.LOCAL_ONLY_FILES`). Nunca pidas ni muestres su contenido.
- Al registrar una llamada a Innovid, pasa la URL por `redact_url()` y el
  cuerpo por `redact_body()`.
- Las Traffic Sheets, exports y tags tienen datos de cliente: no se
  suben al repositorio.

## Cómo trabajar un cambio

1. Ubica el archivo con `docs/MAPA_DEL_CODIGO.md`.
2. Escribe o ajusta la prueba en `tests/` (un archivo por
   comportamiento; el nombre del test afirma algo en palabras).
3. Haz el cambio.
4. Corre `python -m pytest tests/`. Las 662 pruebas deben pasar.
5. Corre `python scripts/generate_code_map.py` para actualizar el mapa.
6. Anota el cambio arriba de `docs/CHANGELOG.md`.

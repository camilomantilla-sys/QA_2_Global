# Cómo armar y usar el agente de QA2 en Copilot

Copilot no tiene acceso al repositorio ni a VS Code. Todo lo que sabe
de QA2 es lo que se le sube. Esta guía explica qué subirle, cómo
pedirle cambios y cómo pegarlos en VS Code sin romper nada.

## 1. Generar los archivos de conocimiento

En la carpeta de QA2, desde Git Bash:

```bash
source .venv/Scripts/activate
python scripts/generate_code_map.py        # mapa del código al día
python scripts/export_copilot_context.py   # arma los archivos para el agente
```

Quedan **fuera del proyecto**, en la carpeta `QA2_contexto_copilot`
que se crea al lado de la carpeta de QA2 (si quieres otra ruta:
`python scripts/export_copilot_context.py --out "C:/otra/carpeta"`).
Así no se mezclan con el código ni con los paquetes de `dist/`. Son 12 archivos
`.md` (1,7 MB en total). Cada uno junta documentación o código por tema,
y cada archivo del proyecto va con su ruta como título
(`## ARCHIVO: core/urls.py`). El script se niega a terminar si se cuela
la sesión de Innovid, las credenciales o una hoja de cálculo.

| Archivo | Qué lleva | Prioridad |
|---|---|---|
| `QA2_01_documentacion.md` | Instrucciones de código, README, referencia técnica, seguridad, guía técnica | 1 |
| `QA2_02_mapa_del_codigo.md` | Cada módulo, clase y función con su firma | 1 |
| `QA2_03_motor.md` | Hallazgos, emparejamiento, veredicto, colores, normalización, rutas | 1 |
| `QA2_08_reglas.md` | Todas las reglas | 1 |
| `QA2_07_parsers.md` | Lectura de TS, exports y tags | 2 |
| `QA2_04_conciliaciones.md` | Píxeles, Adobe, DV, tags, default ads | 2 |
| `QA2_05_innovid_playwright.md` | Conexión a Innovid y Playwright | 2 |
| `QA2_06_reportes.md` | Excel, PDF y hoja QA | 2 |
| `QA2_09_interfaz.md` | `ui/app_v2.py` completo | 3 |
| `QA2_10_arranque_config_scripts.md` | `.bat`, configuración, JSON, scripts, CLI | 3 |
| `QA2_11_pruebas.md` | Todas las pruebas | 3 |
| `QA2_12_historial_y_operacion.md` | Changelog, reglas originales, instalación, comandos | 3 |

Si el agente limita la cantidad de archivos, sube primero los de
prioridad 1, luego los de 2 y así.

## 2. Crear el agente

En Copilot, crea un agente nuevo (los nombres de los botones pueden
cambiar según la versión):

1. **Nombre:** QA2 — Asistente técnico.
2. **Descripción:** Responde preguntas sobre el código, la seguridad y
   el funcionamiento de QA2, y propone cambios listos para pegar en VS Code.
3. **Instrucciones:** pega el bloque de
   [`INSTRUCCIONES_AGENTE.md`](INSTRUCCIONES_AGENTE.md).
4. **Conocimiento:** sube los archivos de `QA2_contexto_copilot`.
5. Si el agente tiene la opción de usar solo el conocimiento cargado (y
   no la web), actívala. Las respuestas salen más precisas.

## 3. Cómo pedirle cosas

### Preguntas

> ¿Qué pasa si Innovid responde 403 durante una corrida?

> ¿Qué regla revisa que el clicktag coincida con la landing page, y qué compara exactamente?

> ¿Dónde se guarda la sesión de Innovid y qué impide que llegue a SharePoint?

### Cambios

Usa esta plantilla:

> **Quiero:** [lo que debe pasar, en palabras de negocio].
> **Ejemplo:** [un caso concreto, con datos inventados si son de cliente].
> **Archivo actual:** [pega aquí el archivo que vas a cambiar, si lo sabes].
> Entrégame el código completo para pegar, dónde va, y la prueba.

Pegar el archivo actual importa: el agente conoce el código de cuando
se generaron sus archivos. Si cambiaste algo después, pégale la
versión nueva.

### Errores

> Al correr QA2 me sale este error: [pega el mensaje completo].
> Este es el final de logs/qa_run.log: [pega las últimas líneas].

## 4. Pegar un cambio en VS Code sin romper nada

1. Abre el archivo que dice el agente (`Ctrl+P` y escribe el nombre).
2. Busca la función con `Ctrl+Shift+O` (lista de símbolos del archivo).
3. Selecciona la función completa, desde `def` hasta antes de la
   siguiente función, y pega el reemplazo.
4. Agrega o ajusta la prueba que te dio.
5. En la terminal:
   ```bash
   python -m pytest tests/
   ```
   Si algo falla, pégale al agente la salida completa de pytest.
6. Cuando todo esté en verde:
   ```bash
   python scripts/generate_code_map.py
   git add -A
   git commit -m "Lo que cambiaste, en una línea"
   git push origin main
   ```
7. Vuelve a generar los archivos del agente
   (`python scripts/export_copilot_context.py`) y reemplázalos en el
   agente cuando hayas hecho varios cambios.

Si un cambio salió mal y quieres volver atrás antes de hacer commit:

```bash
git checkout -- ruta/del/archivo.py     # descarta los cambios de ese archivo
```

## 5. Qué nunca le pasas al agente

- `config/innovid_session.json` ni `config/innovid_credentials.env`.
- Contraseñas, cookies, tokens o capturas donde se vean `Cookie`,
  `Authorization` o `X-Csrf-Token`.
- Traffic Sheets, exports o archivos de tags reales. Si necesita ver la
  forma de un archivo, pásale los nombres de las columnas o una fila
  con datos inventados.
- Reportes con datos de cliente.

## 6. Una demo de cinco minutos

1. **Pregunta de funcionamiento:** *"¿Cómo decide QA2 que un creativo
   está corriendo?"* Debe citar `ActualCreative.running` en
   `core/matching.py`.
2. **Pregunta de seguridad:** *"¿Puede QA2 modificar una campaña en
   Innovid?"* Debe decir que no, que solo hay un POST de consulta y un
   GET, y citar `core/innovid_api.py`.
3. **Cambio pequeño en vivo:** *"Agrega el alias 'Placement Id' a la
   columna placement_id de la Traffic Sheet."* Debe ir a
   `core/ts_schema.py`. Pegas el cambio y corres `python -m pytest tests/`
   en pantalla.

Así se ve el ciclo completo: pregunta, cambio, pruebas en verde.

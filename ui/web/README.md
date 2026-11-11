# Interfaz nueva de QA2 (`ui/web`)

Reemplazo de la interfaz de Streamlit, paso a paso. Mientras no cubra
todo, las dos conviven: Streamlit en `localhost:8501` y esta en
`127.0.0.1:8502`.

```bash
python -m ui.web          # o doble clic en "QA2 nueva interfaz.bat"
```

## Qué hay

| Archivo | Para qué |
|---|---|
| `server.py` | Servidor local con `http.server` (librería estándar, nada que instalar). Sirve la página y responde `/api/...` |
| `session.py` | La solicitud en curso (TS, exports, tags, DV), en memoria. `overview()` es el paso 2 y `run()` corre el QA |
| `summary.py` | Convierte la lectura del parser (`parse_ts`) en lo que muestra el paso 1 |
| `results.py` | Hallazgos → veredicto, conteos y el porqué de cada uno (paso 5). `RULE_TITLES` dice qué mira cada regla |
| `static/index.html` | Toda la página: estilos, pasos y lógica del navegador |

La cadena del QA (leer, decir qué es cada archivo, cruzar y correr las
reglas) **no** está aquí: vive en `core/pipeline.py` y la usan las dos
interfaces. Una regla nueva se conecta allí una sola vez.

## API local

| Ruta | Para qué |
|---|---|
| `POST /api/traffic-sheet` | Paso 1. Lee la TS y la deja en la sesión |
| `POST /api/file?slot=pc\|pl\|tags\|dv` | Paso 2. Lee un export y devuelve qué es cada archivo y la cobertura |
| `POST /api/remove` | Quita un archivo del paso 2 (`{"slot", "name"}`) |
| `GET /api/files` | El estado del paso 2 |
| `GET /api/innovid` · `POST /api/innovid/sign-in` | Paso 3. Si hay sesión de Innovid guardada; abrir el inicio de sesión |
| `GET /api/accounts` · `POST /api/run` | Paso 4. Cuentas y correr (`{"account", "innovid"}`) |
| `GET /api/results` | Paso 5. El último resultado |
| `POST /api/reset` | Start over: olvida todo |

## Estado

| Paso | Estado |
|---|---|
| 1. Traffic Sheet: lo que QA2 entendió | Hecho |
| 2. Exports de Innovid | Hecho |
| 3. Revisión contra Innovid | Hecho |
| 4. Correr el QA | Hecho |
| 5. Resultados | Hecho. Falta: firmar revisiones (QA2 Review), PDF/Excel y session bundle, que siguen en Streamlit |

## Seguridad

Las mismas promesas que la app de Streamlit, escritas en `server.py` y
vigiladas por `tests/test_web_server.py`:

- Escucha solo en `127.0.0.1`; no es configurable.
- Rechaza peticiones con otro `Host` (evita DNS rebinding).
- Los POST exigen la cabecera `X-QA2` y un `Origin` local.
- Solo sirve la página y una lista cerrada de archivos (logo y fuentes).
- Cada archivo se escribe en una carpeta temporal mientras se lee y se
  borra al terminar. La solicitud en curso queda solo en memoria hasta
  Start over o hasta cerrar la ventana. No se registra nada de su
  contenido.
- La página no carga nada de internet.

## Para agregar un paso

1. Un endpoint nuevo en `Handler.do_POST` que llame al motor de siempre.
2. Su vista en `static/index.html` (sección `data-view`).
3. Su prueba en `tests/test_web_server.py`, con datos inventados.

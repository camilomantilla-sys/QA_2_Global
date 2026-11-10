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
| `summary.py` | Convierte la lectura del parser (`parse_ts`) en lo que muestra el paso 1 |
| `static/index.html` | Toda la página: estilos, pasos y lógica del navegador |

## Estado

| Paso | Estado |
|---|---|
| 1. Traffic Sheet: lo que QA2 entendió | Hecho |
| 2. Exports de Innovid | Pendiente |
| 3. Revisión contra Innovid | Pendiente |
| 4. Correr el QA | Pendiente |
| 5. Resultados y reportes | Pendiente |

## Seguridad

Las mismas promesas que la app de Streamlit, escritas en `server.py` y
vigiladas por `tests/test_web_server.py`:

- Escucha solo en `127.0.0.1`; no es configurable.
- Rechaza peticiones con otro `Host` (evita DNS rebinding).
- Los POST exigen la cabecera `X-QA2` y un `Origin` local.
- Solo sirve la página y una lista cerrada de archivos (logo y fuentes).
- La Traffic Sheet se escribe en una carpeta temporal mientras se lee y
  se borra al terminar. No se registra nada de su contenido.
- La página no carga nada de internet.

## Para agregar un paso

1. Un endpoint nuevo en `Handler.do_POST` que llame al motor de siempre.
2. Su vista en `static/index.html` (sección `data-view`).
3. Su prueba en `tests/test_web_server.py`, con datos inventados.

# QA2 en Apps Script · prueba de la fase 1

Antes de portar cualquier regla, esta prueba responde dos preguntas:

1. ¿Google lee una Traffic Sheet igual que el Python de QA2? Eso incluye
   textos, fechas, colores de relleno, color de letra, links, filas
   ocultas y celdas combinadas.
2. ¿Cuánto tarda? Apps Script corta cualquier ejecución a los 6 minutos.

Solo lee. Para leer el .xlsx, Google hace una copia temporal en formato
Google Sheets y la manda a la papelera al terminar. El archivo original
no se toca.

## Archivos

| Archivo | Qué es |
|---|---|
| `Code.gs` | La parte de Google: el menú, la conversión, la lectura y la pestaña con los tiempos |
| `snapshot.js` | La lectura en sí, como la hace `core/extraction.py` + `core/colors.py`. Corre igual en Google y en Node (pruebas en `tests/test_apps_script_poc.py`) |
| `appsscript.json` | El manifiesto: activa los servicios avanzados Drive y Sheets |

Del lado Python:

- `scripts/ts_snapshot.py`: la misma lectura, con el código de QA2.
- `scripts/compare_ts_snapshots.py`: pone las dos lecturas lado a lado,
  celda por celda.

## Instalarlo (una vez, unos 5 minutos)

1. En Drive, crea una carpeta y sube los archivos a probar: las TS de
   Wendy's 330328, Unilever 305807 y BlackRock 311907, y el Excel de la
   extensión de 330328.
2. En esa misma carpeta: **Nuevo → Hojas de cálculo de Google**. Ponle
   de nombre "QA2 prueba".
3. En la hoja: **Extensiones → Apps Script**.
4. En el editor:
   - Abre `Código.gs`, borra lo que tiene y pega `Code.gs`.
   - **+ → Secuencia de comandos**, ponle de nombre `Snapshot` y pega `snapshot.js`.
   - **Configuración del proyecto** (el engranaje) → marca *Mostrar el
     archivo de manifiesto "appsscript.json"*. Vuelve al editor, abre
     `appsscript.json` y reemplaza todo por `appsscript.json`.
   - Guarda (Ctrl+S).
5. Vuelve a la hoja y recárgala. Arriba aparece el menú **QA2 test**.

## Usarlo

1. **QA2 test → Read a file from Drive…** y pega el link del archivo.
2. La primera vez Google pide permisos. Pide Drive completo porque
   necesita abrir tu archivo y crear la copia temporal. La versión final
   puede limitarse a los archivos que elijas con un selector; eso queda
   para la revisión de seguridad.
3. Al terminar aparecen dos cosas:
   - una pestaña **Test · nombre del archivo** con lo que tardó cada paso;
   - un archivo **QA2_test_nombre.json** en la misma carpeta.
4. Repite con cada archivo. Descarga los JSON y súbelos al hilo: con
   eso se hace la comparación contra el Python.

Si la empresa tiene bloqueados los servicios avanzados de Google (Drive
API o Sheets API), el menú da error al leer. Hay que avisarlo, porque
cambia cómo se arma la versión final.

## Compararlo (lado Python)

```
python scripts/ts_snapshot.py "TS.xlsx" -o TS.python.json
python scripts/compare_ts_snapshots.py TS.python.json QA2_test_TS.json -o comparacion.md
```

Las TS reales no se guardan en el repositorio. La comparación se corre
fuera de él.

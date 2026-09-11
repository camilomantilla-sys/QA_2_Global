# Traffic Sheets de prueba

Deja aquí las TS que quieras fijar: viejas, nuevas, de cada cuenta.

Las hojas de cálculo **no se suben a git** — llevan nombres de campaña,
de placement y de sitio, que son datos de cliente. Lo que sí se sube es
el `<nombre>.expected.json` de cada una: solo estructura y conteos,
ni un valor de celda.

    python tests/test_ts_reading.py

La primera vez escribe el resumen de cada TS nueva. Revísalo: ahí se ve
lo que QA entendió — qué columnas mapeó, cuáles no, cuántas filas leyó,
cómo interpretó las fechas y los colores. Cuando esté bien, sube el JSON.

A partir de ahí, cualquier cambio en el parser que altere la lectura de
una de estas TS sale por pantalla, campo a campo.

Para ver una TS en detalle, sin fijar nada:

    python -m cli.ts --ts "tests/fixtures/ts/<archivo>.xlsx"

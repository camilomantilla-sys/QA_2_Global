# Innovid Extractor

Solo el recorrido por Innovid, sin el resto de QA2. No lee la Traffic
Sheet ni los exports y no corre reglas: saca la información de Innovid
y la deja en un Excel por campaign.

No importa nada de QA2. La carpeta se puede copiar a cualquier lado y
sigue funcionando.

## Cómo se usa

1. Doble clic en **Innovid Extractor.bat**.
2. Si no hay sesión guardada (o venció), se abre una ventana de Innovid:
   inicias sesión y abres cualquier campaign. La ventana se cierra sola.
   El extractor nunca ve la contraseña.
3. Escribes uno o varios Campaign ID separados por espacio y Enter.
4. Al terminar se abre la carpeta `output` con un Excel por campaign.
   Enter vacío para salir.

Para iniciar sesión otra vez a propósito:
`python extractor.py --login`.

## Qué trae el Excel

| Hoja | Contenido |
|---|---|
| Summary | Cuántos placements, creativos y decision sets leyó, **cuánto tardó cada paso** y lo que no se pudo leer |
| Placements | Status, fechas, Verification Partner y decision set de cada placement |
| Creatives | Por creativo: URL de clic, píxeles y, desde su decision set, fechas propias, peso y si es default |
| Decision sets | Cada creativo dentro de cada decision set, tal como lo tiene Innovid |
| Media Filters | Remove VPAID por site |

## Qué Python usa

El .bat busca en este orden: el `.venv` de esta carpeta, el Python de
QA2 si la carpeta está dentro de QA2 (solo para correr), y si no hay
ninguno crea el suyo la primera vez (Playwright + openpyxl + Chromium).

## Seguridad

- `session/innovid_session.json` vale lo mismo que la contraseña
  mientras no venza. Se queda en este equipo: no se comparte ni se sube
  al repositorio (está en `.gitignore`).
- Solo habla con Innovid (`campaign-manager.flashtalking.net` y
  `api.flashtalking.net`), igual que QA2.
- Sigue siendo un programa que corre en el equipo de quien lo usa.

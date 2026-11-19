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

---

# Extensión de Chrome (prototipo)

`chrome_extension/` hace el mismo recorrido desde Chrome: sin Python, sin
terminal y sin sesión guardada aparte. Usa la sesión de la pestaña de
Innovid que ya tienes abierta y descarga el mismo Excel (con
"Read with: Chrome extension" en la hoja Summary).

## Cargarla (una vez)

1. Abre `chrome://extensions`.
2. Activa **Modo de desarrollador** (arriba a la derecha). Si sale gris o
   "administrado por tu organización", la empresa lo bloquea: se necesita IT.
3. **Cargar descomprimida** → elige la carpeta
   `innovid_extractor/chrome_extension`.
4. Fija el ícono (la pieza de rompecabezas → el pin).

## Usarla

1. Entra a Innovid como siempre y abre un campaign.
2. Clic en el ícono → el Campaign ID ya viene puesto → **Extract**.
3. El Excel queda en Descargas. Con varios IDs, la pestaña de Innovid
   pasa de uno a otro.

**Qué leer:** "All" (todo el campaign), "Placements" (pegas la
columna de Placement IDs o códigos P de la TS) o "Decision sets"
(IDs o nombres). Es una u otra, no las dos. Solo se leen esos decision sets y el Excel trae
solo esos placements. Lo que no exista en el campaign sale en la hoja
Summary. Vacío = todo el campaign.

Los decision sets se piden de a 4 al tiempo. El reloj de la ventanita
muestra cuánto va y cuánto tardó cada campaign.

Se puede cerrar la ventanita mientras trabaja: el avance sigue y se ve al
abrirla otra vez. **Actualizarla:** `git pull` y, en `chrome://extensions`, el botón de
recargar (flecha circular) de la tarjeta de la extensión. No hay que
quitarla ni volver a cargarla. La versión se ve en esa misma tarjeta.

**Permisos:** al instalarla no pide ningún sitio. Entra a la pestaña de
Innovid solo cuando das clic en el ícono estando ahí (permiso "activeTab").
Si pones varios Campaign ID, Chrome pregunta una vez por
`campaign-manager.flashtalking.net` para poder mover la pestaña de un
campaign a otro. Chrome escribe cualquier permiso de sitio como "leer y
cambiar", pero la extensión solo deja salir cuatro lecturas (el summary,
los decision sets y los sites); cualquier otra petición se rechaza antes de
salir del navegador. La librería de Excel (SheetJS, licencia Apache 2.0)
va dentro de la carpeta: no se descarga nada de internet.

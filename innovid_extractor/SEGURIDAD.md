# Innovid Extractor · seguridad

Qué protege el código, qué no puede proteger por sí solo y qué le toca a
IT y a GitHub. La preocupación principal es que alguien saque datos de
campañas hacia afuera de la empresa.

## Lo primero: la carpeta sola no abre nada

No trae usuario, contraseña ni sesión. Para leer un campaign hace falta
una cuenta de Innovid con acceso a ese cliente: Innovid decide qué deja
ver, no el extractor.

## Qué cubre el código

| Medida | Extensión de Chrome | Extractor de Python |
|---|---|---|
| Solo lectura: únicamente 4 llamadas permitidas (summary, decision sets, sites); cualquier otra se rechaza antes de salir | Sí | Sí (desde esta versión) |
| Solo habla con Innovid (`campaign-manager.flashtalking.net`, `api.flashtalking.net`) | Sí | Sí |
| No guarda sesión propia | Sí: usa la de la pestaña abierta | No: ver la fila siguiente |
| Sesión guardada cifrada con la cuenta de Windows (DPAPI): copiada a otro equipo u otro usuario no abre y se borra | No aplica | Sí |
| La sesión se olvida sola a las 12 horas; `--logout` la borra al momento | No aplica | Sí |
| Una sesión guardada por una versión anterior (sin cifrar) se borra al arrancar | No aplica | Sí |
| Costos y tarifas (Booked_Cost, Media_Cost_*, Flashtalking_Cost*, Cost_Cap_Period) no se escriben en el Excel | Sí | No los lee |
| El Excel dice en Summary que es interno y confidencial | Sí | Sí |
| Sin permisos de sitio al instalar (activeTab) | Sí | No aplica |
| Sin librerías descargadas de internet al usarlo | Sí (SheetJS va dentro) | No: el .bat instala Playwright y openpyxl la primera vez |

## Qué no puede cubrir el código (y quién sí)

1. **Una copia modificada.** El candado de solo lectura vive en el mismo
   código. Quien edite la carpeta puede quitarlo, hacer que escriba en
   Innovid o que mande datos a otro servidor, con la sesión de quien la
   tenga instalada. En modo desarrollador Chrome no avisa de esos
   cambios.
   *Quién:* IT, instalando la extensión por política (force-install)
   desde una fuente única y firmada, y bloqueando el modo desarrollador
   para el resto. Mientras tanto: la extensión se actualiza solo con
   `git pull` de este repositorio. Nunca se carga una copia que llegue
   por chat, correo o un .zip.
2. **El Excel que sale.** Una vez descargado, nada impide reenviarlo.
   *Quién:* las políticas de la empresa (DLP, etiquetas de
   confidencialidad). El Excel ya dice que es confidencial y no trae
   costos.
3. **El código como mapa de la API interna de Innovid.** Sin una cuenta
   no sirve, pero no debe ser público.
   *Quién:* GitHub. El repositorio debe ser **privado**, idealmente dentro
   de la organización de la empresa, con la rama `main` protegida (solo
   cambios revisados).
4. **El computador de quien lo usa.** Si alguien ya controla ese equipo
   y esa sesión de Windows, puede usar lo que esa persona puede usar.
   Ninguna herramienta local lo evita.

## Qué hacer si se sospecha un mal uso

- Cerrar sesión en Innovid (invalida las sesiones activas) y cambiar la
  contraseña.
- Extractor de Python: `python extractor.py --logout`, o borrar la
  carpeta `session`.
- Extensión: en `chrome://extensions`, quitarla y volver a cargarla desde
  el repositorio.

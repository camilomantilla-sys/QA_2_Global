# QA2 — Instalación

Hay dos formas de tener QA2, y casi todo el mundo necesita la primera.

---

# A. Para el equipo — el paquete

**No hay que instalar nada.** Ni Python, ni permisos de administrador,
ni pedirle nada a IT. El paquete trae todo dentro.

### 1. Descargar y extraer

1. Abre el enlace de SharePoint que te compartieron.
2. Descarga `QA2-<versión>-windows.zip`.
3. **Extráelo.** Clic derecho sobre el .zip → **Extraer todo**.

   > Este es el único paso donde se equivoca la gente. Doble clic sobre
   > el .zip solo deja *mirar* adentro. Si intentas abrir QA2 desde ahí,
   > no arranca y parece que está roto.

4. Deja la carpeta en un sitio estable: `Documentos\QA2`, por ejemplo.
   No en Descargas, que se limpia sola.

   > **No la pongas dentro de OneDrive.** Son miles de archivos pequeños
   > y OneDrive intentará sincronizarlos todos. Los archivos de trabajo
   > sí van a SharePoint; el programa no.

### 2. Abrir

Doble clic en **`run_qa2.bat`**.

Tu navegador se abre solo en `http://localhost:8501`. La primera vez
tarda unos segundos; no hay instalación que esperar.

**Deja abierta la ventana negra mientras trabajas.** Es QA2 corriendo;
si la cierras, se detiene.

Si prefieres que no aparezca ninguna ventana, usa
`Launch QA2 (Silent).vbs`, y `Stop QA2.vbs` para detenerlo.

### 3. Conectar con Innovid (una vez, opcional)

QA2 funciona sin esto. Conectado, además comprueba tres cosas que no
están en ningún export y que hoy se revisan abriendo Innovid a mano:

- las fechas de vuelo del creativo dentro del decision set,
- el peso de rotación,
- el Verification Partner del placement.

Sin conexión, esas tres salen como **no verificadas** — que no es lo
mismo que aprobadas — y el resto del QA corre igual.

Para conectarlo:

1. En la carpeta de QA2, entra a `config\`.
2. Crea un archivo llamado **`innovid_credentials.env`**.

   > Con el Bloc de notas, al guardar elige *Tipo: Todos los archivos*,
   > o quedará como `innovid_credentials.env.txt` y no servirá.

3. Escribe dentro tus credenciales, una por línea:

   ```
   INNOVID_USER=tu.correo@wppmedia.com
   INNOVID_PASSWORD=tu-contraseña
   ```

4. Guarda y abre QA2. La primera vez abrirá un navegador para iniciar
   sesión; después la recuerda.

**Sobre ese archivo:**

- Es **tuyo**. QA2 entra a Innovid con tu sesión y tus permisos, igual
  que si abrieras Innovid tú. No amplía el acceso de nadie.
- No sale de tu máquina. No se sube a ningún repositorio ni a
  SharePoint, y **no se puede redirigir a una carpeta compartida** por
  más que se configure el entorno. Es a propósito.
- No viaja dentro del paquete que se distribuye.
- Si tu contraseña rota, actualiza el archivo y borra
  `config\innovid_session.json`.

### 4. Tu primer QA

En la barra lateral, de arriba abajo:

| | Archivo | ¿Obligatorio? |
|---|---|---|
| 1 | Traffic Sheet (.xlsx) | Sí |
| 2 | Placement-Creative View | Sí |
| 3 | Placement View | Recomendado |
| 4 | Cuenta y perfil | Sí |
| 5 | Archivos de tags | Si los hay |
| 6 | Tags de DV Pinnacle | Si la campaña lleva DV. **Puedes subir varios: uno por partner** |

Pulsa **Run QA**. Cuando termine, arriba sale el veredicto y el panel
de firma; abajo, la lista de placements trabajados. Las descargas de
PDF y Excel están arriba.

**Save session bundle** empaqueta todo lo que subiste más tus
selecciones en un .zip. Déjalo en la misma carpeta de SharePoint que la
Traffic Sheet: quien haga el QA2 lo carga desde *"Load a saved
session"* y va directo a revisar y firmar.

### Si algo no funciona

| Qué ves | Qué pasa |
|---|---|
| La ventana negra se abre y se cierra sola | Estás corriendo QA2 desde dentro del .zip. Extrae la carpeta primero. |
| "Python was not found" | Falta la carpeta `python\` — el .zip se extrajo a medias. Vuelve a extraerlo entero. |
| El navegador no abre solo | Ábrelo tú en `http://localhost:8501`. |
| "Restart QA2" en la barra lateral | Alguien actualizó los archivos con QA2 abierto. Cierra la ventana negra y vuelve a abrir. |
| Innovid pide iniciar sesión cada vez | Borra `config\innovid_session.json`. |
| Se queda cargando y no aparece el botón de firma | Manda `logs\qa_run.log`. |

**Cuando algo falle, manda `logs\qa_run.log`.** Guarda la hora de cada
etapa de la corrida y es la diferencia entre adivinar y saber. No lleva
datos de cliente: solo marcas de tiempo y nombres de etapa.

---

# B. Para quien arma el paquete

Se hace **una vez por versión**, en una máquina Windows.

```
python scripts/build_bundle.py
```

Deja `dist\QA2-<versión>-windows.zip` con su SHA-256. Descarga un
Python portable, le instala las librerías, le mete el Chromium de
Playwright, copia el código y comprime. Tarda unos minutos.

Opciones:

```
python scripts/build_bundle.py --no-innovid    # ~300 MB menos, sin Chromium
python scripts/build_bundle.py --keep-folder   # deja dist\ para mirar adentro
```

### Lo que hay que saber

- **Se arma en la plataforma a la que va.** Las ruedas de pandas y
  numpy son binarias y Chromium es un ejecutable: el paquete de Windows
  se arma en Windows. El script lo comprueba y lo dice en vez de armar
  algo que no arranca.
- **Necesita Python en esa máquina** — pero solo quien arma, no quien
  usa.
- **Las versiones quedan fijadas.** La primera vez se escribe
  `requirements-lock-windows.txt` con lo que se instaló. **Commitéalo.**
  A partir de ahí, armar el paquete otra vez da exactamente lo mismo.
  `requirements.txt` dice `pandas>=2.2.0`, que está bien para
  desarrollar y mal para un paquete: sin el lock, armarlo dos meses
  después trae otras versiones y el equipo termina corriendo algo que
  nunca pasó las pruebas.
- **Para subir una librería:** borra el lock, vuelve a armar, corre
  `pytest tests/`, y commitea el lock nuevo.
- **Si Chromium no se puede descargar** (proxy corporativo bloqueando
  `cdn.playwright.dev`), el paquete se arma igual y lo dice al final. El
  script reutiliza un Chromium ya instalado en la máquina **si es la
  revisión exacta** que pide el Playwright del paquete — nunca una
  distinta, porque eso produce un paquete que arranca y falla al abrir
  el navegador.

### Actualizaciones

Casi todos los cambios son de código y no tocan ni el intérprete ni las
librerías. Para esos:

```
python scripts/package_release.py --update
```

Deja un zip de ~600 KB. Quien ya tiene QA2 lo descomprime **encima** de
su carpeta y dice que sí a reemplazar. `python\` y `browsers\` no van
dentro, así que no se tocan.

Cuando cambia `requirements.txt` o el lock, eso no alcanza: hay que
armar y repartir el paquete completo otra vez.

### Antes de subirlo

```
pytest tests/
python scripts/build_bundle.py
```

Extrae el zip en otra carpeta y ábrelo como lo haría el equipo. Es la
única forma de saber que lo que vas a repartir arranca.

---

# C. Para quien desarrolla

Un clon del repositorio con Python del sistema:

```
git clone <repo> && cd QA_2_Global
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
streamlit run ui/app_v2.py
```

`run_qa2.bat` sirve para las dos cosas: si encuentra `python\` usa el
Python del paquete, y si no, el del sistema con su `.venv`.

Las tablas compartidas pueden vivir en SharePoint:

```bat
setx QA2_CONFIG_DIR "%USERPROFILE%\WPP Media\QA2 - Documentos\config"
setx QA2_OUTPUT_DIR "%USERPROFILE%\WPP Media\QA2 - Documentos\evidencia"
```

Cierra y vuelve a abrir la consola para que tomen efecto.

---

*Novedades de cada versión: barra lateral → **What's new in QA2**, o
`docs/CHANGELOG.md`.*

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

   Si el asistente falla —*"No se tiene acceso a la carpeta comprimida"*,
   *"No se puede completar el Asistente"*— ver
   [Si no deja extraer el .zip](#si-no-deja-extraer-el-zip) más abajo.
   Es lo más común y se arregla en un minuto.

4. Deja la carpeta en un sitio estable: `Documentos\QA2`, por ejemplo.
   No en Descargas, que se limpia sola.

   > **No la pongas dentro de OneDrive.** Son miles de archivos pequeños
   > y OneDrive intentará sincronizarlos todos. Los archivos de trabajo
   > sí van a SharePoint; el programa no.

### 2. Abrir

Doble clic en **`QA2.bat`**.

No deja ninguna ventana. Tu navegador se abre solo en
`http://localhost:8501` en unos segundos — no hay nada que instalar ni
que esperar.

Para cerrarlo, doble clic en **`Stop QA2.bat`**.

| Archivo | Para qué |
|---|---|
| **`QA2.bat`** | Abrir QA2. Es el único que necesitas |
| `Stop QA2.bat` | Cerrarlo |
| `run_qa2.bat` | Abrirlo **con** ventana, para ver qué pasa si algo falla |

> Si QA2 no levanta, te sale un aviso diciéndolo y dónde quedó escrito
> el error (`logs\qa2_startup.log`). Si necesitas ver más, abre
> `run_qa2.bat`: ese deja la ventana con todo lo que Streamlit imprime.

> Había también unos lanzadores `.vbs`. Se quitaron: la directiva de
> seguridad de WPP bloquea Windows Script Host —*"This script is
> blocked by IT policy"*— así que en la mayoría de las máquinas del
> equipo no arrancaban. Todo se hace con `.bat`, que no está
> bloqueado.

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

### Si no deja extraer el .zip

El Explorador dice *"No se tiene acceso a la carpeta comprimida (en
zip)"* o *"No se puede completar el Asistente"*. Casi siempre es una de
estas tres, en este orden:

**1. El archivo no está descargado de verdad.** Si llegó por OneDrive,
Teams o SharePoint, puede ser un marcador en la nube — el icono es una
nubecita, no un check. El Explorador no puede abrir lo que todavía no
está.

> Clic derecho en el .zip → **Conservar siempre en este dispositivo**.
> Esperar a que el icono cambie a un check verde.

**2. Windows lo bloqueó por venir de fuera.**

> Clic derecho en el .zip → **Propiedades**. Si abajo aparece una
> casilla **Desbloquear**, marcarla → **Aplicar**.

**3. La descarga se cortó.** Un archivo de ~500 MB por SharePoint falla
en silencio de vez en cuando, y es la causa más difícil de ver: el
archivo está ahí, pesa casi lo mismo, y no avisa de nada.

> En PowerShell, en la carpeta donde está el .zip:
>
> ```powershell
> (Get-Item "QA2-1.0.1-windows.zip").Length
> certutil -hashfile "QA2-1.0.1-windows.zip" SHA256
> ```
>
> Compara **los dos** con lo que envió quien lo compartió. Los bytes
> tienen que ser idénticos, no parecidos. Si no coinciden, ese archivo
> no sirve: descárgalo otra vez.

Una pista que suele delatarlo sin comparar nada: en Propiedades, si
**Creado** y **Modificado** están separados por minutos, la descarga
estuvo escribiendo todo ese rato y puede haberse quedado a medias.

Resuelto eso, **no uses el asistente del Explorador**. Abre PowerShell
en la carpeta donde está el .zip (clic derecho en la carpeta →
*Abrir en Terminal*) y:

```powershell
tar -xf "QA2-1.0.0-windows.zip"
```

`tar` viene incluido en Windows 10 y 11. Aguanta las rutas largas del
navegador que lleva QA2 dentro —que es donde el asistente se atasca— y
además es bastante más rápido.

### Si algo no funciona

| Qué ves | Qué pasa |
|---|---|
| La ventana negra se abre y se cierra sola | Estás corriendo QA2 desde dentro del .zip. Extrae la carpeta primero. |
| "Python was not found" | Falta la carpeta `python\` — el .zip se extrajo a medias. Vuelve a extraerlo entero. |
| El navegador no abre solo | Ábrelo tú en `http://localhost:8501`. |
| "Restart QA2" en la barra lateral | Alguien actualizó los archivos con QA2 abierto. Cierra la ventana negra y vuelve a abrir. |
| "This script is blocked by IT policy" | Estás abriendo un `.vbs` de una versión vieja. Usa `run_qa2.bat`. |
| Innovid pide iniciar sesión cada vez | Borra `config\innovid_session.json`. |
| Se queda cargando y no aparece el botón de firma | Manda `logs\qa_run.log`. |

### Cómo desinstalar (y por qué Windows no deja)

QA2 se desinstala borrando su carpeta. No toca el registro ni el PATH.

Pero el Explorador suele negarse, y no es que haya algo abierto: la
carpeta lleva Chromium dentro, y sus rutas pasan de los 260 caracteres
que Windows aguanta. Falla justo al borrar.

Desde Git Bash, en la carpeta que contiene la de QA2:

```bash
mkdir -p vacia
cmd //c "robocopy vacia QA2-1.0.0-windows /MIR" > /dev/null
rmdir vacia QA2-1.0.0-windows
```

`robocopy` sincroniza una carpeta vacía encima —eso vacía el árbol sin
toparse con el límite— y `rmdir` quita el cascarón.

Si aun así no deja, quedó un proceso suelto. Ciérralo con
**`Stop QA2.bat`**, o a mano:

```bash
tasklist | grep -i python        # ver si hay alguno
taskkill //F //IM python.exe     # cerrarlo
```

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

Deja un zip de ~600 KB. Ese zip **no trae carpeta adentro**, a
propósito: quien ya tiene QA2 lo abre, selecciona todo (`Ctrl+A`) y lo
arrastra a su carpeta, diciendo que sí a reemplazar.

`python\`, `browsers\`, `config\innovid_credentials.env` y `logs\` no
van dentro, así que no se tocan — nadie pierde su sesión de Innovid al
actualizar.

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
pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium
streamlit run ui/app_v2.py
```

`requirements-dev.txt` es solo `pytest`, aparte a propósito: el paquete
que recibe el equipo corre QA2, no las pruebas.

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

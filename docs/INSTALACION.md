# QA2 — Instalación y primer uso

Para quien recibe QA2 por primera vez. Diez minutos la primera vez,
segundos las siguientes.

---

## Antes de empezar

Necesitas **Python 3.10 o superior** instalado.

Para comprobarlo, abre PowerShell o el Símbolo del sistema y escribe:

```
python --version
```

Si responde `Python 3.10.x` o superior, listo. Si dice que no reconoce
el comando, instálalo desde [python.org/downloads](https://www.python.org/downloads/)
y **marca la casilla "Add Python to PATH"** en la primera pantalla del
instalador. Es la casilla que casi todo el mundo pasa por alto y la
única que importa.

No necesitas permisos de administrador ni instalar nada más. QA2 se
instala sus propias dependencias en una carpeta suya, sin tocar el
Python del sistema.

## 1. Descargar

1. Abre el enlace de SharePoint que te compartieron.
2. Descarga `QA2-<versión>.zip`.
3. **Descomprímelo antes de usarlo.** Doble clic sobre el .zip solo lo
   deja *ver*; hay que hacer clic derecho → **Extraer todo**. Si abres
   QA2 desde dentro del zip sin extraer, no arranca.
4. Deja la carpeta en un sitio estable: `Documentos\QA2`, por ejemplo.
   No la dejes en Descargas, donde se borra sola.

> **No pongas la carpeta de QA2 dentro de OneDrive.** El entorno que
> QA2 se crea son miles de archivos pequeños y OneDrive intentará
> sincronizarlos todos. Los archivos de trabajo sí van a SharePoint;
> el programa no.

## 2. Arrancar

Doble clic en **`run_qa2.bat`**.

La primera vez tarda un minuto: se está creando su entorno e instalando
lo que necesita. Verás texto corriendo en una ventana negra. Es normal.

Cuando termine, tu navegador se abre solo en `http://localhost:8501`.

**Deja la ventana negra abierta mientras trabajas.** Es QA2 corriendo;
si la cierras, se detiene. Para cerrarlo al terminar, cierra esa
ventana.

Si prefieres que no aparezca ninguna ventana, usa
`Launch QA2 (Silent).vbs`, y `Stop QA2.vbs` para detenerlo.

## 3. Conectar con Innovid (opcional, una vez)

QA2 funciona sin esto. Conectado, además comprueba tres cosas que no
están en ningún export y que hoy se revisan abriendo Innovid a mano:

- las fechas de vuelo del creativo dentro del decision set,
- el peso de rotación,
- el Verification Partner del placement.

Sin conexión, esas comprobaciones salen como *no verificadas* — que no
es lo mismo que aprobadas — y el resto del QA corre igual.

### Cómo conectarlo

1. Dentro de la carpeta de QA2, entra a `config\`.
2. Crea un archivo llamado **`innovid_credentials.env`** (Bloc de notas
   sirve; cuida que no quede `.env.txt`).
3. Escribe dentro tus credenciales de Innovid, una por línea:

   ```
   INNOVID_USER=tu.correo@wppmedia.com
   INNOVID_PASSWORD=tu-contraseña
   ```

4. Guarda y arranca QA2. La primera vez abrirá un navegador para
   iniciar sesión; después guarda la sesión y ya no lo pide.

**Sobre este archivo:**

- No sale de tu máquina. No se sube a ningún repositorio ni a
  SharePoint — está excluido a propósito, y no se puede redirigir a una
  carpeta compartida por más que se configure el entorno.
- No va dentro del zip que se distribuye.
- Es **tuyo**: QA2 entra a Innovid con tu sesión y tus permisos, igual
  que si abrieras Innovid tú. No amplía el acceso de nadie.
- Si tu contraseña rota, actualiza el archivo y borra
  `config\innovid_session.json` para que vuelva a iniciar sesión.

Para verificar la conexión sin correr un QA completo:

```
python check_innovid_connection.py
```

## 4. Correr tu primer QA

En la barra lateral, de arriba abajo:

| | Archivo | ¿Obligatorio? |
|---|---|---|
| 1 | Traffic Sheet (.xlsx) | Sí |
| 2 | Placement-Creative View | Sí |
| 3 | Placement View | Recomendado |
| 4 | Cuenta y perfil | Sí |
| 5 | Archivos de tags | Si los hay |
| 6 | Tags de DV Pinnacle | Si la campaña lleva DV. **Puedes subir varios: uno por partner** |

Pulsa **Run QA**. Cuando termine:

- Arriba sale el veredicto y el panel de firma.
- Abajo, la lista de placements trabajados. Haz clic en uno para ver su
  detalle.
- Las descargas de PDF y Excel están arriba.

### Guardar la sesión para el QA2

**Save session bundle** empaqueta todos los archivos que subiste más
tus selecciones en un solo .zip. Déjalo en la misma carpeta de
SharePoint que la Traffic Sheet: quien haga el QA2 lo carga desde
*"Load a saved session"* y va directo a revisar y firmar, sin volver a
subir nada.

## 5. Tablas compartidas (opcional)

Las tablas de vendors, píxeles de Adobe y roster pueden vivir en una
carpeta única de SharePoint en vez de una copia por máquina. Quien las
edite en la app las comparte con todo el equipo.

Sincroniza la biblioteca con OneDrive y define dos variables:

```bat
setx QA2_CONFIG_DIR "%USERPROFILE%\WPP Media\QA2 - Documentos\config"
setx QA2_OUTPUT_DIR "%USERPROFILE%\WPP Media\QA2 - Documentos\evidencia"
```

Cierra y vuelve a abrir la consola para que tomen efecto, y reinicia
QA2. Si la carpeta está vacía, QA2 sigue funcionando con lo que trae y
empieza a usar la compartida en cuanto alguien guarde por primera vez.

## Si algo no funciona

| Qué ves | Qué pasa |
|---|---|
| "python no se reconoce como un comando" | Python no está instalado, o no se marcó "Add Python to PATH". Reinstala marcando esa casilla. |
| La ventana negra se abre y se cierra sola | Estás corriendo QA2 desde dentro del .zip. Extrae la carpeta primero. |
| El navegador no abre solo | Ábrelo tú en `http://localhost:8501`. |
| "Restart QA2" en la barra lateral | Alguien actualizó los archivos con QA2 abierto. Cierra la ventana negra y vuelve a arrancar. |
| Innovid pide iniciar sesión cada vez | Borra `config\innovid_session.json` y arranca de nuevo. |
| Se queda cargando y no aparece el botón de firma | Manda `logs\qa_run.log`: dice exactamente hasta dónde llegó. |

Ese último punto es el importante. **Cuando algo falle, manda
`logs\qa_run.log`.** Guarda la hora de cada etapa de la corrida y es la
diferencia entre adivinar y saber. No contiene datos de cliente: solo
marcas de tiempo y nombres de etapa.

---

*Novedades de cada versión: barra lateral → **What's new in QA2**, o
`docs/CHANGELOG.md`.*

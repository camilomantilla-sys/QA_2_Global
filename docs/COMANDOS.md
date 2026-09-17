# QA2 — Comandos

Para copiar y pegar. Todo sale en `dist/`.

> **Estos comandos son para Git Bash** (la ventana que dice `MINGW64`),
> que es donde se clona el repositorio. Ahí `%USERPROFILE%` no existe
> y las rutas van con `/`, no con `\`. Si abres la carpeta desde
> Explorador con *clic derecho → Git Bash Here*, ya estás en el sitio
> y no hace falta ningún `cd`.

---

## Una sola vez, en tu máquina

`pytest` no viene con la aplicación — el paquete que recibe el equipo
corre QA2, no las pruebas. Instálalo una vez:

```bash
cd ~/Downloads/QA_2_Global
git pull origin claude/tag-url-validation-5adcd4
source .venv/Scripts/activate
pip install -r requirements-dev.txt
python -m streamlit run ui/app_v2.py
```

> El `git pull` va **antes** a propósito: `requirements-dev.txt` llegó
> en un commit, así que instalarlo sin haberlo traído falla con
> *"Could not open requirements file"*.

---

## Actualizar (lo normal)

Cambió el código — una regla, un arreglo, una columna. **No** cambió
`requirements.txt` ni el lock.

```bash
cd ~/Downloads/QA_2_Global
git pull origin claude/tag-url-validation-5adcd4
source .venv/Scripts/activate
python -m pytest tests/
rm -rf dist
python scripts/package_release.py --update
```

> `rm -rf dist` antes de armar: si no, un zip de una corrida anterior
> se queda ahí al lado del nuevo y a la hora de subirlo hay dos, con
> nombres parecidos y sin forma de saber cuál es cuál.

> Mira lo que imprime `git pull`. Si dice **`Already up to date`** ya
> tienes lo último. Si dice `Updating <algo>..<algo>`, fíjate en que el
> segundo sea el commit que esperabas: armar el zip antes de haber
> traído el cambio deja un zip viejo con nombre nuevo, y no hay forma
> de notarlo mirando el archivo.

Deja `dist\QA2-<versión>-update.zip`, unos 600 KB.

**Lo que le dices a tu equipo** — tres pasos:

1. Extraer el .zip donde sea (*Extraer todo* está bien)
2. Cerrar QA2 si lo tienen abierto
3. Doble clic a **`ACTUALIZAR QA2.bat`** que viene dentro

Ese .bat busca su carpeta de QA2, le dice qué va a reemplazar, pregunta
antes, y deja intactos `python\`, `browsers\`, `config\` y `logs\` —
nadie pierde su sesión de Innovid al actualizar.

> Antes las instrucciones eran "abre el zip y arrastra el contenido", y
> eso no es lo que hace la gente: le dan a *Extraer todo*, que crea una
> carpeta con el nombre del zip, y la actualización se queda ahí sin
> aplicarse — **sin dar ningún error**, porque la carpeta existe y los
> archivos están. Pasó en la primera entrega real.

---

## Paquete completo

La primera vez, o cuando cambió `requirements.txt` o
`requirements-lock-windows.txt`.

```bash
cd ~/Downloads/QA_2_Global
git pull origin claude/tag-url-validation-5adcd4
source .venv/Scripts/activate
python -m pytest tests/
python scripts/build_bundle.py
```

Deja `dist\QA2-<versión>-windows.zip`, unos 500 MB. Tarda varios
minutos: descarga un Python portable, le instala las librerías y le
mete Chromium.

**Cómo se instala:** se extrae en una carpeta nueva y se abre
`run_qa2.bat`. No hay nada que instalar.

Variantes:

```bash
python scripts/build_bundle.py --no-innovid    #  ~300 MB menos, sin Chromium
python scripts/build_bundle.py --keep-folder   #  deja dist/ sin borrar, para mirar adentro
```

---

## ¿Cuál de los dos?

```bash
git diff --name-only <lo-que-ya-repartiste>..HEAD | grep requirements
```

- **No sale nada** → `--update` (600 KB)
- **Sale algo** → paquete completo (500 MB)

Si no te acuerdas de qué versión repartiste, mira el `VERSION` dentro
de la carpeta que tiene tu equipo.

---

## Al compartir el paquete completo

Dile a quien lo recibe que si el Explorador se queja al extraer
—*"No se tiene acceso a la carpeta comprimida"*— hay tres cosas que
mirar y un comando que casi siempre funciona. Está en
[`INSTALACION.md`](INSTALACION.md#si-no-deja-extraer-el-zip).

Resumen: que el archivo esté descargado de verdad (no un marcador de
OneDrive), desbloqueado en Propiedades, completo — y después
`tar -xf "QA2-<versión>-windows.zip"` en PowerShell en vez del
asistente.

Y pásales **el tamaño en bytes y el SHA-256** junto al enlace. Es la
única forma de que noten una descarga truncada antes de pelearse media
hora con ella — el archivo llega, pesa casi lo mismo, y no avisa de
nada.

El SHA-256 lo imprime `build_bundle.py` al terminar. El tamaño exacto:

```bash
stat -c %s dist/QA2-<versión>-windows.zip
```

Quien lo recibe comprueba los dos con:

```powershell
(Get-Item "QA2-<versión>-windows.zip").Length
certutil -hashfile "QA2-<versión>-windows.zip" SHA256
```

## Antes de subir cualquiera de los dos

```bash
python -m pytest tests/
```

Y con el paquete completo, extráelo en **otra** carpeta y ábrelo como
lo haría tu equipo. Es la única forma de saber que lo que vas a
repartir arranca.

---

## Zip de solo código, sin intérprete

> **Este NO es el paquete del equipo.** Lleva el código y nada más, así
> que quien lo abra necesita Python instalado y el inicio de sesión de
> Innovid no va a arrancar: sin navegador dentro, la app se comporta
> como una copia de desarrollo. Es para otro desarrollador, o para leer
> el código.
>
> El del equipo es `python scripts/build_bundle.py`, y sale
> `QA2-<versión>-windows.zip`. **El nombre con la plataforma es el que
> lleva Python adentro.**

```bash
python scripts/package_release.py     #  sale QA2-<version>-source.zip
```

---

## Publicar una versión

```bash
#  1. subir el numero
echo 1.1.0 > VERSION

#  2. anotar que cambio, arriba del todo
notepad docs/CHANGELOG.md

#  3. commit y push
git add -A
git commit -m "Version 1.1.0"
git push -u origin claude/tag-url-validation-5adcd4

#  4. armar y repartir
#     un arreglo de reglas o de la interfaz: basta el parche
python scripts/package_release.py --update

#     si cambio el arranque, los .bat, requirements.txt o el lock:
#     el parche NO alcanza, hay que rearmar el paquete entero
python scripts/build_bundle.py
```

La app lee los dos: el número sale en la barra lateral, y la entrada
más nueva del changelog aparece en **What's new in QA2**. Por eso vale
la pena subir el número aunque el cambio sea pequeño — es como el
equipo se entera.

---

## Si algo sale mal en la máquina de alguien

Pídele `logs/qa_run.log`. Guarda la hora de cada etapa y dice hasta
dónde llegó la corrida, incluida la versión que estaba corriendo. No
lleva datos de cliente.

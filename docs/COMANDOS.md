# QA2 — Comandos

Para copiar y pegar. Todo sale en `dist\`.

---

## Actualizar (lo normal)

Cambió el código — una regla, un arreglo, una columna. **No** cambió
`requirements.txt` ni el lock.

```bat
cd %USERPROFILE%\Downloads\QA_2_Global
git pull origin claude/tag-url-validation-5adcd4
pytest tests/
python scripts/package_release.py --update
```

Deja `dist\QA2-<versión>-update.zip`, unos 600 KB.

**Cómo se instala:** quien ya tiene QA2 lo descomprime **encima** de su
carpeta y dice que sí a reemplazar. `python\` y `browsers\` no van
dentro del zip, así que no se tocan.

---

## Paquete completo

La primera vez, o cuando cambió `requirements.txt` o
`requirements-lock-windows.txt`.

```bat
cd %USERPROFILE%\Downloads\QA_2_Global
git pull origin claude/tag-url-validation-5adcd4
pytest tests/
python scripts/build_bundle.py
```

Deja `dist\QA2-<versión>-windows.zip`, unos 500 MB. Tarda varios
minutos: descarga un Python portable, le instala las librerías y le
mete Chromium.

**Cómo se instala:** se extrae en una carpeta nueva y se abre
`run_qa2.bat`. No hay nada que instalar.

Variantes:

```bat
python scripts/build_bundle.py --no-innovid    ::  ~300 MB menos, sin Chromium
python scripts/build_bundle.py --keep-folder   ::  deja dist\ sin borrar, para mirar adentro
```

---

## ¿Cuál de los dos?

```bat
git diff --name-only <lo-que-ya-repartiste>..HEAD | findstr requirements
```

- **No sale nada** → `--update` (600 KB)
- **Sale algo** → paquete completo (500 MB)

Si no te acuerdas de qué versión repartiste, mira el `VERSION` dentro
de la carpeta que tiene tu equipo.

---

## Antes de subir cualquiera de los dos

```bat
pytest tests/
```

Y con el paquete completo, extráelo en **otra** carpeta y ábrelo como
lo haría tu equipo. Es la única forma de saber que lo que vas a
repartir arranca.

---

## Zip de solo código, sin intérprete

Para alguien que ya tiene Python y quiere el proyecto, no el paquete:

```bat
python scripts/package_release.py
```

---

## Publicar una versión

```bat
::  1. subir el numero
echo 1.1.0 > VERSION

::  2. anotar que cambio, arriba del todo
notepad docs\CHANGELOG.md

::  3. commit y push
git add -A
git commit -m "Version 1.1.0"
git push -u origin claude/tag-url-validation-5adcd4

::  4. armar y repartir
python scripts/package_release.py --update
```

La app lee los dos: el número sale en la barra lateral, y la entrada
más nueva del changelog aparece en **What's new in QA2**. Por eso vale
la pena subir el número aunque el cambio sea pequeño — es como el
equipo se entera.

---

## Si algo sale mal en la máquina de alguien

Pídele `logs\qa_run.log`. Guarda la hora de cada etapa y dice hasta
dónde llegó la corrida, incluida la versión que estaba corriendo. No
lleva datos de cliente.

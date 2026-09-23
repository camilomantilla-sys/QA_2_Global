# QA2 — Registro de cambios

Qué cambió, cuándo y por qué. Se lee de arriba hacia abajo: lo más
nuevo primero.

**Cómo leer esto.** Cada versión dice qué cambió para quien usa QA2, no
qué líneas se tocaron. Si algo que hacías antes ahora se hace distinto,
está marcado **Cambio de comportamiento**.

**Cómo mantenerlo.** Cada cambio que el equipo vaya a notar se anota
aquí antes de distribuirse. Un cambio interno que nadie percibe no
necesita entrada.

---

## 1.0.0 — Lanzamiento · 2026-09-15

Primera versión que se entrega al equipo.

### Preparación para el lanzamiento

- **Configuración compartida en SharePoint.** Las tablas de vendors,
  píxeles de Adobe y roster pueden vivir en una carpeta única: se apunta
  `QA2_CONFIG_DIR` a una biblioteca sincronizada y quien edita la tabla
  en la app la comparte con todo el equipo. Si la carpeta está vacía,
  QA2 sigue con los valores que trae y empieza a usarla en cuanto
  alguien guarde. No hay migración que coordinar.
- **El log de corrida se puede mover** con `QA2_OUTPUT_DIR`.
- **La contraseña y las cookies de Innovid no se pueden mover.**
  Resuelven siempre a la carpeta local, sin importar cómo esté
  configurado el entorno. Es a propósito, y hay pruebas que lo fijan.
- **La app escucha solo en `localhost`.** Streamlit no trae ese ajuste
  por defecto: sin él, cualquiera en la red podría abrir la sesión de QA
  de otra persona.
- **Documentación:** nota de seguridad para revisión de IT
  ([`SEGURIDAD.md`](SEGURIDAD.md)), guía técnica de reglas y funciones
  ([`GUIA_TECNICA.md`](GUIA_TECNICA.md)), este registro, y un empaquetador
  para distribuir al equipo (`scripts/package_release.py`).
- **Pruebas:** seis que fallaban solo en la corrida completa ya no
  fallan. Cinco módulos de prueba reescribían globales de `innovid_api`
  y no los devolvían, contaminando lo que corriera después.

### Dos veredictos: la implementacion y los tags

    "yo implemento bien para adobe, pasa el QA y se puede demorar 2
     dias en recibir pixels pero ya envie tags, entonces es diferente
     la implementacion a los tags"

Un pixel que llega dos dias despues de enviar los tags no significa
que el trafficking este mal. Metidos en un solo veredicto, un vendor
que todavia no ha mandado su pixel teñia de rojo un reporte donde los
placements, los creativos, las fechas y las URLs estaban perfectos — y
quien lo recibia no sabia si tenia que rehacer la implementacion o
solo esperar un correo.

Ahora se cuentan por separado:

| | qué incluye |
|---|---|
| **Implementation** | placements, creativos, fechas, dimensiones, rotación, URLs, atribución. Lo que hizo AdOps y lo que AdOps puede arreglar |
| **Tags & pixels** | lo que se entrega y lo que ponen terceros. Un fallo aquí casi nunca se arregla volviendo a Innovid |

**El veredicto general sigue siendo el peor de los dos:** con los tags
mal, el QA no está aprobado. Lo que cambia es que ahora el reporte dice
*cuál* de los dos falla, con una frase delante:

> **The implementation is fine.** Take a look at the tags and pixels.

Y cuando los dos están bien, no dice nada: una frase que no aporta es
una frase que se aprende a saltar.

Sale en la app, en el Excel y en el PDF, con las mismas palabras — las
etiquetas de veredicto viven ahora en un solo sitio (`core/verdict.py`)
en vez de estar copiadas en tres.

### Un arranque que falla ya deja rastro

    "solo me dice que no le abre nada"

Doble clic, y nada. Ni ventana, ni navegador, ni error, ni archivo que
mirar. La causa no era de ese paquete: era de diseño.

`QA2.bat` arranca con **pythonw.exe, que no tiene consola**, y
`start_qa2.py` importaba medio QA2 **antes** de abrir el log. Cualquier
fallo ahi --un archivo que no llego en el .zip, un permiso, un
import-- no tenia donde escribirse. El proceso moria en silencio.

Ahora lo primero que hace es abrir el log, y **todo** lo demas va
dentro de un try que escribe ahi lo que pase y lo enseña en un cuadro
de dialogo. El log empieza diciendo de que copia se trata:

    QA2 1.0.1 arrancando  2026-09-23 17:40:12
      carpeta      C:\Users\...\QA2-1.0.1-windows
      interprete   ...\python\pythonw.exe
      python\      si
      browsers\    si
      puerto       8501

### `DIAGNOSTICO QA2.bat`

Y para cuando **ni el log existe** --porque el .bat no llego a lanzar
python-- hay un archivo nuevo en la carpeta. Doble clic, y deja en
`logs\diagnostico.txt` la version, que hay en la carpeta, que procesos
de python corren, quien tiene el puerto 8501 y el ultimo arranque.

Si no hay log, lo dice y da el motivo mas probable: **el .zip llego
bloqueado por Windows**. Clic derecho en el .zip → Propiedades →
Desbloquear, y volver a extraer.

Un archivo que mandar, en vez de diez mensajes preguntando que sale en
pantalla.

### Dos carpetas de QA2, y la que se veia no era la que abriste

    "intenté correr esa version vieja que nunca la borré y me corre la
     mas reciente"

La gente conserva la carpeta de la version anterior. Al arrancar, QA2
miraba si **alguien** contestaba en el puerto 8501 y, si si, abria el
navegador ahi y se salia — sin comprobar **de quien** era ese puerto.

Asi que si tenias abierta una version y hacias doble clic en otra
carpeta, se abria la primera. Sin un aviso. La carpeta que abriste
nunca arranco, y la version que estabas mirando no era la que creias.

Ahora se pregunta de quien es el puerto: cada carpeta deja escrito su
PID, y eso lo responde.

- Es **el nuestro** → se abre el navegador sobre el, como antes.
- Es **de otra carpeta** → QA2 arranca en su propio puerto y abre ese.

**Y `run_qa2.bat` ya no abre el navegador.** Lo hacia a los 6 segundos
y siempre en el 8501: antes de que el servidor contestara, y sobre la
copia de otra carpeta si esa tenia el puerto. Lo abre la app, cuando el
servidor responde de verdad y en el puerto que de verdad tomo.

> **Para saber que version estas viendo:** el numero esta en la barra
> lateral, abajo. Si no coincide con la carpeta que abriste, estabas
> mirando otra.

### Los pixeles oficiales de Adobe, ya cargados

La tabla venia vacia y habia que escribirla a mano. Ahora trae los
siete que Adobe usa hoy:

| Vendor | Campaña | |
|---|---|---|
| iSpot | *(en blanco)* | universal: el mismo para todo Adobe |
| DISQO | Adobe Acrobat | |
| DISQO | Adobe Firefly | |
| DISQO | Adobe Everyone Can | Photoshop, Brand Specific |
| DISQO | Adobe STE | Student |
| DISQO | Adobe PGA | |
| DISQO | Adobe MLB | |

**La columna Campaña es la etiqueta que se elige arriba en "Account /
Campaign"** — no tiene que coincidir con el nombre de la campaña en la
Traffic Sheet, que cambia cada trimestre. Por eso son nombres cortos y
estables. Una fila sin campaña aplica a todas; una con campaña gana
sobre la de su mismo vendor cuando se elige esa linea.

Si no se elige linea de negocio, **DISQO no se comprueba**: sin saber
cual es, no hay un pixel correcto contra el que comparar, y adivinar
marcaria como drift un pixel que esta bien. iSpot si, porque es el
mismo siempre.

**Solo 3P.** Un site-served 1x1 no lleva el pixel oficial de Adobe: lo
pone el sitio en su propio tag, con sus macros, asi que la URL no
tiene por que parecerse a la de referencia. Compararla solo producia
un REVIEW sobre algo bien traficado.

**Y elegir una linea de negocio ya no vacia los desplegables de "By".**
El roster se buscaba por clave exacta, asi que "Adobe Acrobat" no
encontraba al equipo de Adobe. Una etiqueta que empieza por el nombre
de una cuenta pertenece a esa cuenta.

### El panel de firma dice de que son

Decia `70 to review` y nada mas: para saber de que eran habia que
bajar a la tabla y leer fila por fila. Y el selector de grupos solo
aparecia con **dos** motivos o mas, asi que en el caso tipico --los 70
con la misma diferencia de fechas-- la unica opcion visible era "Sign
off all", que tampoco dice que se esta firmando.

Ahora, encima de los botones:

> **What is waiting for a signature**
> - **70** · has no end date in Innovid, and the Traffic Sheet closes
>   it on 2026-12-28  (INV-001 [REVIEW])

Y el selector de grupos sale **tambien con un solo grupo**, porque el
nombre del grupo es la explicacion. Con varios motivos se pueden
firmar unos si y otros no, como antes.

### Cual de los dos nombres de Innovid es cual

La columna se llamaba `Innovid Creative Name` a secas, y Innovid tiene
dos etiquetas para el mismo creativo. Ahora el encabezado lo dice:

| columna | de donde sale |
|---|---|
| `Innovid Creative Name (Export)` | el export Placement-Creative |
| `Innovid Creative Name (Decision Set)` | el nodo dentro del decision set, solo si se llama distinto |

Lo mismo en la app: `Innovid Creative (Export)`.

### El 1x1 de Adobe ya no avisa de unas fechas que no existen

    "dice Creative dates were not checked: Innovid did not return this
     placement... aca adopta las fechas del placement entonces es como
     una falsa alerta"

Un 1x1 site-served no tiene decision set, y la API a veces ni devuelve
el placement: **no hay arbol que pedir**. Eso salia como
`NOT_VERIFIED`, un aviso sobre algo que no existe.

Ya se trataba bien el caso "el placement vuelve pero sin nodos";
faltaba el de "el placement no vuelve". Ahora los dos dicen lo mismo:

> Site-served 1x1: the creative is assigned to the placement and runs
> on its dates, so there is no decision set to check

Un placement de display que no vuelve **sigue** saliendo
`NOT_VERIFIED`: ahi si falta algo que mirar.

**Y el borde de los botones de Excel y PDF** pasa al mismo azul del
boton que lanza el QA.

### Un creativo sin fecha de fin pasaba en verde

    "hay un mismatch de fechas de creativo y no me salio la opcion
     para firmar eso"

En la campaña de Vaseline la TS cierra el **2026-12-28** y en Innovid
el creativo no tiene fecha de fin: corre **ongoing**. El Excel pintaba
el par en naranja, pero la regla daba **PASS** — asi que el reporte
marcaba una diferencia que no habia forma de firmar.

**Cambio de comportamiento.** Antes esto pasaba en verde a proposito
("sin fecha en Innovid no hay nada que contradiga a la TS"). Ya no:
cualquier fecha de fin que la TS declare y que Innovid no lleve sale
como **REVIEW** — se ve, se firma, y las dos caras dicen lo mismo. No
es FAIL, porque firmarlo es justo lo que se quiere poder hacer.

El hallazgo dice **el hecho**, no la consecuencia: que Innovid no
lleva esa fecha. Si el placement cierra el mismo dia, lo para igual —
y eso es lo que hay que mirar antes de firmar, asi que va en la accion
recomendada y no en el mensaje.

Y tiene **su propio motivo**, para que la firma en bloque funcione:

> `INV-001 [REVIEW] · has no end date in Innovid, so it keeps serving
> after the flight closes (70)`

Con el mensaje generico estos quedaban revueltos con los creativos que
corren desplazados un dia, que no se firman con el mismo criterio.

Sin ninguna fecha pedida en la TS sigue siendo `NOT_VERIFIED`: ahi de
verdad no hay nada que comparar.

### Los creativos que la app mostraba distintos del Excel

El export trae **dos nombres** por creativo, y en Unilever son
distintos:

| campo del export | valor |
|---|---|
| `Creative_Name` | `OLD-LOTION-GOOD-RUN_LOTION_20OZ-PUMP_..._300X600` |
| `Filename` | `VAS_Cherry_Lotion_PopCultureEnthusiasts1_..._300x600` |

El Excel pedia el primero — el limpio, a proposito, porque `Filename`
arrastra el sello de subida de Innovid. La app pedia el segundo. Asi
que el mismo creativo se leia `OLD-LOTION-GOOD-RUN` en el Excel y
`VAS_Cherry_Lotion` en la app, al lado de una columna de TS que decia
`OLD-LOTION-GOOD-RUN`. Parecia que QA2 habia emparejado el creativo
equivocado. Las dos caras piden ahora el mismo nombre.

### El 1x1 de Adobe ya tiene fila

La seccion "2. Creatives & Assignment" salia **vacia** en un
site-served: la TS dice `N/A` en Creative Names, asi que no hay
creativo esperado. Pero Innovid si tiene algo asignado — el pixel de
la cuenta — y es lo unico que hay que mirar ahi. Camilo: "me trae
espacios en blanco, me gustaria que trajera asi fuera el N/A de la TS".

| Intent | TS Creative | Innovid Creative |
|---|---|---|
| `1x1` | `N/A (site-served)` | `1x1.gif` |

Solo cuando no hay nada mas que enseñar: si la TS declaro creativos,
manda lo que se pidio.

### 70 revisiones que firmar, y un Excel que las desmentia

    "me lo flaggea en 2. Creative & Assignments, pero en el excel
     descargado me lo compara con el placement creative export y ahi
     si hace match... pierdo tiempo validando manualmente que todo
     esta bien"

El caso real, de la campaña de Vaseline:

| dónde | cómo se llama |
|---|---|
| Traffic Sheet | `CHERRY-HYDRATION_LOTION_20OZ-PUMP_..._160X600_...` · ID 6398957 |
| export Placement-Creative | **el mismo nombre** |
| dentro del decision set | `VAS_Cherry_Lotion_LapsedBuyers1_Static_Display_160x600_082726.jpg` |

Son **dos etiquetas de Innovid para el mismo creative id**: el archivo
en el export, el concepto dentro del decision set. `INV-004` comparaba
solo contra la del decision set, asi que salto en los **70 creativos**
de la solicitud -- 70 revisiones que firmar a mano -- mientras el Excel,
que compara contra el export, enseñaba las dos columnas de nombre
iguales y en verde. Sin nada que explicara por que se habia firmado
algo.

**La lectura estaba bien. Lo que estaba mal era comparar contra una
sola etiqueta.** Si el nombre de la TS concuerda con **alguna** de las
dos, hay dos hechos independientes diciendo que es el creativo
correcto: el id y ese nombre. No hay nada que decidir, y `INV-004` se
calla.

Sigue sonando cuando no concuerda con **ninguna** de las dos. Ese aviso
importa: el Creative ID lo teclea una persona, y un id mal escrito
emparejaria con el creativo equivocado sin que nada mas lo delatara.

**Y el nombre del decision set ya no hay que ir a buscarlo a Innovid.**
Hay una columna nueva en el Excel —`Innovid Creative Name (Decision
Set)`— y la misma en la app, que se llenan **solo** cuando el decision
set lo llama distinto. En blanco quiere decir "lo llama igual".

### El mismo creativo, marcado en la app y en verde en el Excel

    "si en un lado me muestra el creativo dentro del DS y en otro el
     del export, pierdo tiempo validando manualmente que todo esta
     bien"

Innovid tiene dos vistas del mismo creativo y no siempre lo llama
igual: dentro del **decision set** suele mostrar el nombre del
concepto, y en el **export Placement-Creative** el del archivo. QA2
comparaba contra el decision set en la app y contra el export en el
Excel, asi que el mismo creativo salia marcado en una pantalla y en
verde en la otra. Se firmaba una discrepancia que el reporte
desmentia.

Ahora las dos vistas cuentan, y en el orden correcto. El enganche es
el **creative id**, no el nombre — pero hasta ahora el unico id que se
probaba era el que escribe la Traffic Sheet, y hay cuentas enteras que
no llenan esa columna (las de Adobe casi nunca). Sin id declarado se
caia al nombre, que es justo el que no coincide.

El export **si** trae el id que Innovid le dio al creativo, y es el
mismo con el que el decision set identifica su nodo. Asi que se
intenta en tres pasos:

1. el Creative ID que declara la Traffic Sheet
2. el nombre del archivo
3. **el id de Innovid, tomado del export**

Con el tercero, las fechas y la rotacion dentro del decision set **se
leen de verdad**. Es el caso comun, y ahora se comprueba en vez de
quedarse sin comprobar.

Solo cuando ninguno de los tres encuentra el nodo -- el creativo esta
asignado pero no hay nodo que leer -- se dice lo que pasa de verdad —

> is assigned in Innovid, but the decision set does not show it under
> that name, so its flight dates and rotation inside the decision set
> could not be read

Sale como **NOT_VERIFIED**, no como fallo: esta asignado, y lo que no
se pudo leer son sus fechas y su rotacion dentro del decision set. Lo
que no se pudo comprobar nunca pasa en verde.

Un creativo que no esta en **ninguna** de las dos vistas sigue siendo
un fallo, y uno en rojo sigue confirmando la remocion.

### El 1x1 de Adobe: `N/A` no es un nombre que falte

En Adobe el 1x1 lo sirve el publisher, asi que el creativo nunca pasa
por Innovid y la TS escribe `N/A` en Creative Names. Eso no generaba
ningun creativo esperado, y el placement se quedaba **sin una sola
comprobacion de creativo**: la seccion salia vacia y el reporte
cerraba limpio.

Comparar el nombre no dice nada -- `1x1.gif` es el mismo para toda la
cuenta. Que este asignado, si. La regla nueva es **`CRE-002`**: si el
pixel esta, PASS; si no esta, FAIL; si el placement no volvio en el
export, NOT_VERIFIED.

### Dos zips a un guion de distancia

`package_release.py` dejaba `QA2-1.0.1.zip` en la misma carpeta que
`QA2-1.0.1-windows.zip`, y terminaba diciendo "subelo a SharePoint y
manda el link". Pero ese zip lleva el codigo y **nada mas**: quien lo
abre necesita Python instalado, y sin navegador dentro el inicio de
sesion de Innovid no arranca.

Se subio el que no era, y la app arranco como copia de desarrollo.

- El zip de codigo ahora se llama `QA2-<version>-**source**.zip`.
- Y al terminar dice lo que es, en vez de mandar a repartirlo:

      THIS IS NOT THE PACKAGE FOR THE TEAM.
      ...
      The package for the team, with Python and Chromium inside:

        python scripts/build_bundle.py

**Regla para no volver a equivocarse:** el que lleva la plataforma en
el nombre --`QA2-1.0.1-windows.zip`-- es el del equipo.

### "Stop QA2.bat" no detenia QA2

    "pues lo pare intente borrar no pude... sigue sin dejarme borrar"

`QA2.bat` arranca con **pythonw.exe** -- es lo que hace que no deje
ventana, y es como abre QA2 todo el equipo. Pero el detector de "esta
corriendo" filtraba por `IMAGENAME eq python.exe`, que es otro
programa.

Asi que "Stop QA2.bat" contestaba **"QA2 no esta corriendo"**, borraba
el archivo del PID y dejaba la app viva. Con la carpeta abierta, que
Windows entonces no deja ni borrar ni reemplazar.

Lo mismo en otros dos sitios, con el mismo origen:

- `run_qa2.bat` no veia la instancia abierta y arrancaba una segunda.
- `ACTUALIZAR QA2.bat` daba via libre y copiaba encima de una app
  abierta -- justo lo que ese chequeo existia para impedir.

Los tres cuentan ahora `pythonw.exe` igual que `python.exe`.

### El paquete no encontraba su propio navegador

    "Playwright has no browser on this machine... me esta saliendo
     esto en el ultimo zip extraido"

Dos cosas, y las dos se arreglaron.

**La de fondo.** `PLAYWRIGHT_BROWSERS_PATH` solo la ponia
`run_qa2.bat`, la version con ventana. `QA2.bat` --el que usa el
equipo-- no. Y el chequeo contra Innovid abre Chromium **dentro** del
proceso de la app, no en un subproceso al que se le pueda pasar el
entorno: un paquete completo abierto con doble clic buscaba el
navegador en la carpeta del usuario, donde no hay nada.

Ahora la app lo deduce sola de su propia carpeta al arrancar, asi que
vale igual para `QA2.bat`, para `run_qa2.bat`, para el CLI y para quien
lo lance de otra manera. Si alguien pone la variable a mano, esa manda.

**La del mensaje.** El zip de actualizacion es un parche: el codigo y
nada mas, para caer **encima** de una instalacion que ya existe.
Extraido por su cuenta arranca --hay Python en la maquina-- pero sin
interprete propio ni navegador, y lo unico que decia era "corre
`pip install`", que no tiene nada que ver. Ahora lo dice:

> This folder is the QA2 update, not QA2 itself: it carries the code
> and nothing else. Extract it over your existing QA2 folder and run
> "ACTUALIZAR QA2.bat" from there, or ask for the full package.

### El default viejo, en gris, volvia a la app

    "sigue teniendo el problema de que me trae grises a la app... me
     trae el current default, el default viejo en gris"

BlackRock retira el default viejo pintandolo de GRIS y escribe el nuevo
debajo, en blanco. La recuperacion de filas ocultas -- la de la entrada
de abajo -- se traia el gris de vuelta como contexto blanco: el default
retirado volvia a exigirse en Innovid, donde ya no esta porque termino,
y salia como creativo faltante.

Recuperar es rellenar lo que no se alcanzo a leer, no revivir lo que la
TS descarto a proposito. Una fila gris ya no se recupera, este oculta o
no.

**En la app:** el default ad ahora dice `DEFAULT` en la columna Intent,
en vez de un blanco que se leia igual que el contenido del decision set.
El default no lo declara el placement: se engancha por dimension.

### Nueva regla `PLC-007` — la rotacion que no es del tamano del placement

    "no me esta trayendo el creativo correcto... el creativo que debe
     estar rotando al 100 me lo lleva a extra creatives"

Los creativos de un grupo se filtran por dimension a proposito: un
grupo de Adobe trae los 5 tamanos y un placement de 160x600 solo sirve
los suyos. Pero cuando el filtro se lleva **todos** los creativos
pedidos, el placement se queda sin nada que comparar -- y eso no se
decia. El hueco lo tapaba el default ad, que se engancha por dimension,
y la fila se leia como si estuviera revisada.

Paso con dos placements cuyas rotaciones quedaron cruzadas en la TS: el
de 300x600 nombrando la rotacion de 300x250 y al reves. Innovid corria
el creativo correcto; la TS era la que estaba mal, y el creativo bueno
aparecia en "extra creatives" sin ninguna explicacion.

Ahora sale un REVIEW que dice cual es:

> The creative rotation this placement declares has no creative of its
> dimension, so nothing that was requested could be compared.
> Expected: A 300x600 creative in "Ticker Search Banner 300x250 - Tax"

Cuando el grupo trae varios tamanos y al placement le queda el suyo, no
dice nada: eso es el filtro haciendo su trabajo.

### Los creativos de un decision set oculto salian como "extra"

    "los creativos blancos existentes que andan activos me los lee
     como extra creatives... deberia salir en creatives and
     assignment no?"

Si. Un creativo blanco no es parte del cambio, pero SI es el contenido
del Decision Set. Sin el, el placement se queda sin ningun creativo
esperado y todo lo que Innovid tiene sale como "extra creative": sin
comparacion, sin fechas y sin URL.

`build_expected` ya lo hacia bien -- pero en "TS_Q2-Q4 2026 Co
Marketing" las 67 filas de Creative Rotations estan ocultas, asi que no
habia ninguno que tomar. De esa hoja ya se recuperaba el mapa grupo →
landing page; faltaban los creativos.

En un swap de SOLO landing page eso significaba que no se comparaba
**ninguna** landing page, que es lo unico que se pedia revisar. Con los
56 creativos recuperados: 0 extras y **28 de 28 URLs comparadas**.

De una fila oculta se toma unicamente el creativo, y siempre como
contexto blanco. Ni un verde ni un rojo: una fila oculta no es parte de
la solicitud, y esa regla no se toca. Y lo que si se leyo manda -- lo
oculto solo rellena lo que falta.

### Un creativo rojo se leia como verde

    "me sigue leyendo creativos en rojo como si fueran verdes"

El decision set "AV Display Unit 300x600" lleva dos filas -- una ROJA
con el creativo que sale y una VERDE con el que entra -- y la celda del
nombre del grupo esta **fusionada entre las dos**, pintada de verde.

El intent de cada fila se calculaba mirando todos los colores, incluida
esa celda compartida:

    fams = {GREEN, RED}  ->  intent = "SWAP"  ->  se resuelve GREEN

Asi que el creativo que habia que QUITAR se leia como uno que se queda.
Tres veces en esa solicitud, las tres al reves.

La celda del grupo es literalmente la misma celda para todas las filas
del decision set: habla del grupo, no del creativo. Ahora decide el
color propio de la fila. `_row_own()` --que ya existia y ya la excluia--
se usa tambien para el verde y el rojo, no solo para el gris.

Sin color propio el grupo si puede hablar, pero solo en verde o rojo:
un decision set nuevo va en verde con sus creativos en blanco y esos si
se piden. En gris no -- el primer intento de arreglar esto dejo cuatro
placements de Dove fuera de alcance sin que nadie lo pidiera, y el
guard de snapshots lo atrapo.

### QA2 se abre con doble clic y sin ventana

    "yo no quiero que mi amiga tenga que abrir ninguna terminal ni
     nada solo abrir la app"

**`QA2.bat`** es ahora el unico archivo que el equipo necesita. Arranca
con `pythonw.exe` --que viene dentro del paquete y corre sin consola--
y no deja ninguna ventana. El navegador lo abre QA2 cuando el servidor
responde de verdad, no al lanzarlo: una pestana en blanco apuntando a
un servidor que todavia no existe no la arregla nadie.

Arrancar sin ventana tiene un precio, y es el que hundio al lanzador
`.vbs`: sin consola, un fallo no se ve por ningun lado. Aqui un hilo
vigila el puerto, y si el servidor no responde lo dice en un cuadro de
dialogo --con ctypes, no con Windows Script Host, que esta bloqueado--
y apunta a `logs/qa2_startup.log`, donde queda escrito todo lo que
Streamlit imprimio.

Abrir QA2 dos veces ya no arranca un segundo: abre el navegador al que
ya esta corriendo.

`run_qa2.bat` se queda como la version **con** ventana, para cuando hay
que ver que pasa.

### Fuera los .vbs: la directiva de IT los bloquea

La companera de Camilo abrio el lanzador y le salio:

    This script is blocked by IT policy
    Codigo: 800A802E

Windows Script Host esta bloqueado por directiva corporativa. No es su
maquina: es politica de WPP, y le habria pasado a buena parte de los
treinta. Los `.vbs` estaban muertos como forma de arrancar QA2.

Se quitaron los tres --`Launch QA2 (Silent).vbs`, `Stop QA2.vbs` y
`run_qa2_silent.bat`, que solo existia para el primero-- y queda
`run_qa2.bat` para abrir y **`Stop QA2.bat`** para cerrar. Los `.bat`
no los bloquea nadie.

Encontrar QA2 para pararlo era el problema de fondo, y ya van tres
formas fallidas: por puerto (se mueve al de al lado si el 8501 esta
ocupado), con `wmic` (Windows 11 ya no lo trae) y desde un `.vbs` (esta
directiva). Ahora **la app deja su PID escrito** en `logs/qa2.pid` y los
`.bat` lo leen con `tasklist` y `taskkill`, que son parte de Windows
desde siempre.

Lo anota `scripts/start_qa2.py`, que arranca Streamlit en el mismo
proceso: asi el PID escrito es exactamente el que hay que matar.
Ponerlo dentro de `app_v2.py` no bastaba --ese codigo corre en la
primera sesion, o sea cuando alguien abre la pagina-- y hasta entonces
el servidor estaba arriba sin que nadie pudiera encontrarlo. Y quien
lee ese PID comprueba siempre que siga siendo un python, porque un
numero viejo puede haberlo reutilizado Windows para otra cosa.

### Streamlit pedia un correo y se quedaba bloqueado

La causa de verdad, y habria afectado a los treinta la primera vez que
abrieran QA2. Streamlit, en su primer arranque, pregunta por consola:

    Welcome to Streamlit!
    ... please enter your email address below.
    Email: _

Y se queda ahi hasta que alguien pulse Enter. En la ventana negra se ve
--y confunde, porque no parece parte de QA2--; en el lanzador
silencioso no hay ventana donde escribir y QA2 no arranca nunca.

`headless = true` en `.streamlit/config.toml` lo salta. Va en la
configuracion y no en los lanzadores para que tambien lo salte quien
arranque `streamlit run ui/app_v2.py` a mano.

A cambio Streamlit ya no abre el navegador solo, asi que lo abren los
lanzadores -- que ademas es mejor, porque el silencioso espera a que el
servidor responda de verdad antes de abrirlo.

### El lanzador silencioso esperaba para siempre

Una companera de Camilo abrio `Launch QA2 (Silent).vbs` en el paquete,
le salio **"Setting up QA2 for the first time"** y espero diez minutos
a un navegador que no iba a abrirse nunca.

Dos cosas, las dos del mismo tipo:

- **El mensaje miraba si existe `.venv`**, que es cosa de una copia de
  desarrollo. El paquete tiene `python\` con su interprete dentro y no
  instala nada. Le anunciaba un minuto de espera que no existia.
- **Corria el .bat oculto y no volvia a mirar.** Sin ventana, cualquier
  fallo es silencioso: el que no tiene Python salia con un codigo de
  error que nadie iba a leer jamas.

Ahora reconoce el paquete y no anuncia instalacion ninguna; espera a
que el servidor responda de verdad antes de abrir el navegador; y si no
responde, lo dice y sugiere abrir `run_qa2.bat`, que si deja ventana.

El .bat ya no abre el navegador --lo abre el .vbs, que es quien sabe si
arranco-- y deja escrito el motivo cuando muere.

### El inicio de sesion de Innovid no decia cuando fallaba

Camilo, probando el paquete descargado de SharePoint: "nunca se me abre
la pestana para iniciar sesion". Y la app, tan tranquila:

    A browser window is opening. Sign in, open a campaign...

Ese texto era fijo. El boton lanzaba el proceso y lo anunciaba sin
mirar si seguia vivo, asi que cuando moria al instante --lo que pasa si
el paquete se armo sin Chromium-- se quedaba esperando una ventana que
no iba a llegar nunca. Sin error, sin log, sin nada.

Ahora se espera unos segundos: un navegador que va a abrirse se abre en
ese tiempo, y un fallo tambien ocurre en ese tiempo. Si el proceso
murio, se dice por que y se puede ver lo que imprimio.

El motivo se escribe segun a quien va dirigido: a quien recibio un zip
sin navegador se le dice que pida un paquete completo --y que **el
resto de QA2 funciona igual**-- y no un `pip install` que no puede
ejecutar; a quien tiene una copia de desarrollo se le da el comando.

Y el navegador del paquete se le pasa a Playwright explicitamente en
vez de confiar en heredarlo del lanzador: quien arrancara QA2 de otra
forma se quedaba sin navegador, otra vez sin explicacion.

### QA2 se estaba multiplicando

Once `python.exe` vivos despues de un dia de pruebas, y con ellos
abiertos Windows no dejaba ni borrar la carpeta de QA2 -- sus archivos
estaban en uso. Dos cosas que se alimentaban:

- **Cerrar la ventana negra no detiene el proceso.** Sigue vivo con el
  puerto 8501 tomado, asi que el siguiente arranque se va al 8502.
- **`Stop QA2.vbs` mataba lo que escuchara en el 8501**, que para
  entonces ya no era el suyo.

Cada vuelta dejaba uno mas.

Ahora `Stop QA2.vbs` los busca por lo que ejecutan --los python que
corren `app_v2`-- y no por donde escuchan, asi que los para todos
corra en el puerto que corra, y dice cuantos eran. Otro Python que la
persona tenga abierto no se toca: un `taskkill /IM python.exe` habria
resuelto esto y matado de paso lo que hubiera al lado.

Y los lanzadores ya no arrancan un segundo QA2: si encuentran uno
corriendo, abren el navegador al que ya esta.

### La actualizacion se aplica sola

El zip de update trae ahora **`ACTUALIZAR QA2.bat`** en la raiz. Se
extrae donde sea, se hace doble clic, y el resto lo hace el .bat: busca
la carpeta de QA2, avisa si esta abierta (con QA2 corriendo Windows no
deja reemplazar sus archivos), dice que va a tocar y que no, y pregunta
antes.

Las instrucciones eran "abre el zip y arrastra el contenido", y eso no
es lo que hace la gente: le dan a Extraer todo, que crea una carpeta
con el nombre del zip, y la actualizacion se queda ahi sin aplicarse.
**Sin dar ningun error** -- la carpeta existe, los archivos estan, y
QA2 sigue con la version vieja. Paso en la primera entrega real.

### Windows lee el texto distinto que Linux

`read_text()` sin `encoding` usa **cp1252 en Windows** y UTF-8 en
Linux: el mismo archivo, dos resultados. Los comentarios del codigo
llevan acentos y comillas tipograficas, asi que leer `app_v2.py` en
cp1252 revienta:

    UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d

Aqui nunca paso. Arreglado en los 23 sitios que lo hacian --no solo en
el que fallo-- y `test_portable_tests.py` ahora falla si alguien vuelve
a escribir un `read_text()` o un `write_text()` sin decir la
codificacion.

### `pytest tests/` nunca habia corrido fuera de una maquina

Camilo lo corrio en Windows y no fallaron unas pruebas: no corrio
NINGUNA de las 488.

    Failed to launch chromium because executable doesn't exist at
    \opt\pw-browsers\chromium-1194\chrome-linux\chrome
    INTERNALERROR> SystemExit: 1

Dos fallos encadenados. Seis archivos de prueba traian la ruta del
navegador del contenedor donde se escribio el codigo, copiada de uno a
otro; en Windows no existe. Y esos archivos son scripts que terminaban
en `sys.exit(1)`: bajo pytest, un SystemExit durante la RECOLECCION no
es un fallo, es un INTERNALERROR que descarta la corrida entera.

El paso que protege lo que se le entrega al equipo solo funcionaba en
la maquina donde esa ruta existia, y salia verde, que es la peor forma
de estar roto.

- Ya no se le dice a Playwright donde esta el navegador: lo sabe, y
  honra `PLAYWRIGHT_BROWSERS_PATH`. Sin navegador instalado, esos
  archivos se saltan con el motivo y el comando para instalarlo.
- `sys.exit(1)` pasa a `AssertionError`, que pytest reporta como lo que
  es y deja correr al resto.
- Las rutas absolutas del repositorio y `.venv/bin` (que en Windows es
  `.venv/Scripts`) tambien estaban fijas. Arregladas.
- `tests/test_portable_tests.py` mira el texto de los demas archivos y
  falla si vuelve a aparecer cualquiera de las cuatro cosas. Es barato:
  no lanza nada.

### Firmar sin evidencia no es firmar

Los dos encontrados abriendo el Excel de una corrida real, ya desde el
paquete instalado.

- **El tamano al que se sirve un creativo no se veia.** Las unicas
  columnas de dimensiones eran las del PLACEMENT, iguales en todas sus
  filas, asi que un creativo pedido a 728x90 y servido a 720x50 salia
  con las mismas dos celdas que uno correcto. Debajo estaba la causa
  real: `ActualCreative` ni siquiera leia la dimension --el export la
  trae por fila y se descartaba--, asi que el dato no existia ni para
  compararlo ni para mostrarlo. Camilo: "la idea es firmar pero que se
  evidencie la diferencia". Ahora hay **TS Creative Dims / Innovid
  Creative Dims**, y cuando la TS declara una duracion ("15s", video)
  el lado de Innovid queda en blanco en vez de inventar un desacuerdo.
- **El morado solo aparecia cuando dos columnas llenas no coincidian.**
  Pero se firma mucho mas que eso: una rotacion que no se pudo comparar
  deja la columna de Innovid vacia, y un NOT_VERIFIED firmado tiene los
  dos lados iguales. En esos casos la firma quedaba solo en Notes, que
  obliga a leer fila por fila --justo lo que un color evita. Ahora la
  celda de **Status** lleva el morado siempre que la fila este firmada,
  y un par a medio llenar tambien. Un par que de verdad coincide sigue
  verde: lo firmado era otra cosa.

### Actualizar sin repartir 500 MB otra vez

`python scripts/package_release.py --update` arma un zip de ~600 KB con
el codigo y nada mas. Casi todos los cambios son de codigo, y volver a
repartir el paquete entero por seis megas de Python es un impuesto que
nadie paga dos veces.

Ese zip **no trae carpeta adentro**, a diferencia del completo: se abre,
se selecciona todo y se arrastra a la carpeta de QA2. Con carpeta no se
superponia con nada --la instalada se llama `QA2-1.0.0-windows` y el zip
traia `QA2-1.0.0`-- asi que extraerlo dejaba una carpeta nueva al lado y
la aplicacion sin actualizar, **sin dar ningun error**.

El interprete, el navegador, las credenciales y los logs no van dentro
del zip: nadie pierde su sesion de Innovid al actualizar.

`pytest` paso a `requirements-dev.txt`. No estaba en ningun sitio, asi
que `pytest tests/` fallaba en una copia recien clonada -- y no debe
estar en `requirements.txt`, porque el paquete del equipo corre QA2, no
las pruebas.

Cuando cambia `requirements.txt` o el lock, esto no alcanza y hay que
repartir el paquete completo.

### El paquete trae Python adentro

Quien recibe QA2 **no instala nada**. Ni Python, ni permisos de
administrador, ni pedirle nada a IT: se extrae el zip y se hace doble
clic. Era el bloqueador real del lanzamiento --"yo no voy a poner a
descargar python a 30 personas"-- y en una maquina corporativa
probablemente ni podrian.

- `scripts/build_bundle.py` arma el paquete: descarga un Python
  portable (python-build-standalone, el mismo que usa uv), le instala
  las librerias, le mete el Chromium de Playwright y comprime todo. Se
  hace una vez por version, en una maquina Windows.
- `run_qa2.bat` usa el Python del paquete si esta, y el del sistema con
  su `.venv` si no. El mismo archivo sirve para el equipo y para quien
  desarrolla.
- **Las versiones quedan fijadas** en `requirements-lock-<plataforma>.txt`.
  `requirements.txt` dice `pandas>=2.2.0`, que esta bien para
  desarrollar y mal para un paquete: sin el lock, armarlo dos meses
  despues trae otras versiones y el equipo corre algo que nunca paso
  las pruebas, en silencio.
- El Chromium local se reutiliza **solo si es la revision exacta** que
  pide el Playwright del paquete. Una distinta produce un paquete que
  arranca y falla al abrir el navegador -- el peor momento para
  enterarse. Si no se puede descargar (proxy corporativo), el paquete
  se arma igual y lo dice.
- [`INSTALACION.md`](INSTALACION.md) reescrita: para el equipo, para
  quien arma el paquete, y para quien desarrolla.

### Interfaz

- **Los tags de DV Pinnacle aceptan varios archivos.** Una campana puede
  tener mas de un partner y DV entrega un archivo por cada uno; el
  uploader aceptaba uno solo. En la solicitud de BlackRock eran dos
  --Bloomberg (18 placements) y The New York Times (6)-- y subiendo solo
  el primero los 6 del segundo salian FAIL "requires DV but has no row
  in the DV Pinnacle file". Seis hallazgos falsos sobre trabajo bien
  hecho. Ahora se leen todos como uno, y cada fila recuerda de que
  archivo vino.
- **Se quito el sello del build de la barra lateral.** Al equipo no le
  dice nada. La version sigue yendo a `qa_run.log`, que es donde hace
  falta cuando alguien reporta un problema.
- **Guia de instalacion** paso a paso ([`INSTALACION.md`](INSTALACION.md)):
  descarga, arranque, conexion con Innovid y que hacer si algo falla.

### Dos casos que se leian bien y no se validaban

Los dos encontrados probando solicitudes nuevas dias antes del
lanzamiento. Los dos con la misma forma: QA2 leia la Traffic Sheet
correctamente y despues no comparaba nada.

- **Swap de creativos de video sobre un decision set existente.** Los
  tres creativos que Innovid si tenia asignados salian como "extra
  creative": sin comparacion, sin fechas, sin rotacion y sin poder
  confirmar que el placeholder que habia que desasignar se hubiera ido.
  La causa: la columna "Dims or Duration" trae, para video, la duracion
  ("15s"), y el filtro por dimension la comparaba contra 1920x1080. No
  hacia match, y se llevaba por delante el grupo entero. Ese filtro
  ahora solo opina cuando los dos lados son de verdad un ancho por alto.
  En la TS del caso, 78 de 225 filas de rotacion declaran duracion.

- **Swap de solo landing page con la pestana de rotaciones oculta.** La
  cadena de BlackRock es placement → creative rotation → landing page →
  URL, y el placement no nombra su landing page: dice "See Creative
  Rotation Tab". Cuando esas filas estan ocultas -- las 67 lo estaban --
  el eslabon del medio desaparecia y los 56 placements salian
  NOT_WORKED pese a 33 pares rojo/verde en Landing Pages. Ahora de una
  fila oculta se toma unicamente a que landing page apunta cada grupo,
  que es estructura de la campana y no una solicitud. El color se sigue
  leyendo solo de lo visible: una fila oculta no cuenta como verde, ni
  como rojo, ni como blanco.
  **Cambio de comportamiento:** un swap de solo URL en esa forma pasa de
  no revisar nada a marcar sus placements como URL_SWAP.

### Validaciones nuevas

- **`TAG-014` — la landing page dentro del click tag de 1x1.** Idea del
  equipo: en el static clicktag de 1x1 siempre viene la landing page de
  la TS. Es la única regla que mira el destino dentro del archivo que el
  sitio realmente recibe, sin pasar por Innovid. 30 de 30 en la
  solicitud de Ahold, 2 de 2 en la de Adobe.
  Habla solo donde hay evidencia, así que los casos de Adobe que no
  mandan el static no generan ruido: 93 filas con `ftrack 1x1 click`
  sin `url=`, ni un hallazgo falso.
- **Análisis de tags.** Panel con el conteo de todos los tags, si cada
  tipo de placement trae las columnas que le corresponden, y la tabla
  completa tal cual se importarían. DV Pinnacle en su propia pestaña.
- **`ROT-001` — cambios de rotación.** Antes una solicitud de 355
  cambios de rotación cerraba en verde sin haber comparado ni uno: el
  porcentaje vive dentro del decision set y el export solo dice
  `"Decision Tree"`. Ahora sale `NOT_VERIFIED` cuando no se pudo
  comparar.
- **`EXT-000` — una TS que no se pudo leer bloquea la corrida.** Llegó
  una TS de BlackRock con el encabezado borrado: el parser leyó cero de
  384 rotaciones y el motor daba PASSED sobre 144 comprobaciones que
  nunca tocaron un creativo.

### Correcciones

- **Adobe 1x1 / Direct Assignment** no validaba URL ni CGEN. En 1x1 los
  creativos van directo al placement, así que no había creativo que
  aportara la URL y el bloque nunca corría. Ahora se calcula a nivel de
  placement: de 0 a 4 de 4 en Acrobat, de 32 a 127 en Students.
  **Cambio de comportamiento:** aparecen hallazgos de URL y atribución
  en placements de Adobe donde antes no salía nada.
- **Adobe 3p con Decision Tree** mostraba todo como creativos extra:
  de 0 a 710 rotaciones comparadas, de 1152 extras a 0.
- **DISQO se evalúa según el tipo de placement.** En 3p la evidencia es
  `Third_Party_Impression` de Innovid, no los tags. En 1x1 sí es la
  columna en los tags. Antes se buscaba en el lugar equivocado.
- **Los grises de BlackRock.** Cuando el mismo placement aparece en gris
  (pedido viejo) y en blanco (el actual), manda el que está en alcance.
  Antes el pedido viejo pisaba al actual: 3 swaps que no se comparaban
  ahora sí, y las remociones se ven en rojo.
- **`P3JPFSN` reportado como CGEN.** Era el `Third_Party_ID` del
  Placement View, que no es un CGEN. Se quitó como respaldo; producía
  falsos FAIL de atribución.
- **`TAG-006` retirada.** El Third Party ID no se valida en los archivos
  de tags; ahí solo se valida que estén los placements correctos.
  **Cambio de comportamiento:** desaparecen esos hallazgos.
- **`DV-001` ya no exige tags en swaps ni desasignaciones.** Los tags se
  descargan cuando los placements se crean.
- **Un creativo faltante es un hallazgo, no 127.**
- **Las filas ocultas ya no confunden la lectura de la TS.** La
  detección de perfil recorre toda la grilla; antes una TS con las
  primeras filas ocultas se leía como si no tuviera rotaciones.
- **El aviso de los 60 decision sets:** de 60 consultas a 6.

### Firma y desempeño

Firmar no funcionaba y tuvo tres causas distintas, encontradas una por
una con el log de corrida:

1. Un `st.rerun()` encima de los botones se comía el clic.
2. `st.tabs` ejecuta el cuerpo de todas las pestañas, y la reconstrucción
   del PDF y del Excel en cada interacción hacía la pasada tan larga que
   el clic siguiente se perdía.
3. El navegador no alcanzaba a pintar 44 placements desplegados.

Qué se hizo:

- El panel de firma está en el cuerpo, arriba, y aparece apenas termina
  la corrida.
- Solo se dibuja la sección elegida, no las seis.
- El PDF y el Excel se memorizan y se reconstruyen solo si cambió el
  resultado.
- La lista de placements se dibuja entera —72 filas en 15 ms— pero solo
  se despliega el cuerpo del que está abierto.
- Las descargas quedaron arriba, como antes.

### Reportes

- Excel con hoja de tags y hoja de evidencia.
- PDF con marca de WPP Media.
- El identificador de cada hallazgo es determinista, así que una firma
  sobrevive a volver a correr el QA.

---

## Plantilla para la próxima versión

```markdown
## X.Y.Z — AAAA-MM-DD

### Validaciones nuevas
- **`REGLA-00N` — qué comprueba.** Por qué hacía falta.

### Correcciones
- **Qué estaba mal.** Qué se ve distinto ahora.
  **Cambio de comportamiento:** si algo que antes pasaba ahora falla.

### Interfaz
- Qué se ve distinto.
```

Numeración: `MAYOR.MENOR.PARCHE`.
**Parche** = correcciones. **Menor** = validaciones o funciones nuevas.
**Mayor** = algo que obliga al equipo a cambiar cómo trabaja.

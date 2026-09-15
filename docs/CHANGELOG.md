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

# Portafolio interactivo en Google Apps Script

Versión web del portafolio de **María Alejandra Gómez** (el mismo de Canva del video):
mismas secciones, mismos textos y misma paleta, pero con interacción real —
el recibo se imprime, el extracto bancario se despliega, las cartas se voltean,
los objetos del bolso se abren y hay un formulario de contacto que escribe en la hoja.

El contenido **no vive en el código**: vive en una hoja de cálculo. Ella edita el
Sheets y la web cambia sola.

```
portfolio-appscript/
├── apps-script/        ← lo que se copia y pega en el editor de Apps Script
│   ├── Code.gs           backend: lee la hoja, guarda mensajes, instala todo
│   ├── Seed.gs           contenido inicial (generado, no editar a mano)
│   ├── Index.html        estructura de las 7 secciones
│   ├── Styles.html       diseño (paleta, tipografías, animaciones)
│   ├── Script.html       interacción (todo se dibuja desde los datos)
│   └── appsscript.json   permisos y configuración del proyecto
├── data/seed.json      ← única fuente del contenido inicial
├── scripts/build.py    ← genera Seed.gs y la vista previa
└── dist/preview.html   ← ábrelo en el navegador para verlo sin publicar nada
```

---

## 1. Publicarlo (15 minutos, sin instalar nada)

1. Crea una hoja de cálculo nueva en Google Drive. Llámala `Portafolio – María Alejandra`.
2. En la hoja: **Extensiones → Apps Script**.
3. Borra el `Code.gs` de ejemplo y crea **exactamente estos archivos** con el contenido
   de la carpeta `apps-script/` (el botón `+` de la izquierda; los `.html` se crean
   con “HTML”, los `.gs` con “Secuencia de comandos”):

   | Archivo en el editor | Archivo de este repo |
   |---|---|
   | `Code.gs`    | `apps-script/Code.gs` |
   | `Seed.gs`    | `apps-script/Seed.gs` |
   | `Index.html` | `apps-script/Index.html` |
   | `Styles.html`| `apps-script/Styles.html` |
   | `Script.html`| `apps-script/Script.html` |

   (Opcional: ⚙️ *Configuración del proyecto → Mostrar `appsscript.json`* y pega el del repo.)
4. Arriba, elige la función **`instalarPortafolio`** y dale **Ejecutar**.
   Google pedirá permisos una vez → *Revisar permisos → Configuración avanzada →
   Ir al proyecto → Permitir*. Esto crea las 11 hojas con todo el contenido.
5. **Implementar → Nueva implementación → Aplicación web**
   - *Ejecutar como:* **Yo**
   - *Quién tiene acceso:* **Cualquier persona**
6. Copia la URL que termina en `/exec`. Esa es la web. Ya está.

> Cada vez que cambies el **código**, hay que volver a *Implementar → Editar la
> implementación → Versión nueva*. Si solo cambias la **hoja**, no hay que hacer nada.

---

## 2. Estructura del Sheets

`instalarPortafolio()` crea todo esto solo. Esta tabla es para saber qué toca dónde.

### `CONFIG` — datos generales (clave / valor)

| clave | para qué sirve |
|---|---|
| `saludo`, `nombre`, `rol` | portada |
| `foto_url` | su foto recortada (si está vacío, sale la silueta) |
| `email`, `linkedin`, `linkedin_label`, `telefono`, `telefono_link`, `ubicacion` | bloque de contacto |
| `cv_url` | si lo llenas, aparece un enlace “Descargar CV” |
| `cierre_titulo`, `cierre_sub`, `contacto_titulo`, `form_titulo`, `form_nota` | textos del cierre |
| `notificar_email` | `TRUE` = le llega un correo con cada mensaje del formulario |
| `registrar_visitas` | `TRUE` = guarda en `VISITAS` qué secciones se ven |
| `color_vino`, `color_carmin`, `color_rosa`, `color_nude`, `color_durazno`, `color_papel` | la paleta completa, editable desde la hoja |

### `RESUMEN` — encabezado del extracto (clave / valor)
`titulo`, `subtitulo`, `periodo`, `cuenta`, `estado`, `total_experiencia`, `enfoque`,
`skills`, `metodo_pago`, `frecuencia`, `moneda`.

### Hojas de tabla (encabezados en la fila 1, una fila por elemento)

| Hoja | Columnas |
|---|---|
| `RECIBO` | `num` · `item` · `check` |
| `RECIBO_TOTAL` | `campo` · `valor` |
| `REWARDS` | `concepto` · `valor` |
| `EXPERIENCIA` | `fecha` · `empresa` · `rol` · `categoria` · `detalle` · `destacado` · `activo` |
| `SKILLS` | `carta` · `palo` · `titulo` · `herramientas` · `descripcion` · `nivel` · `activo` |
| `BAG` | `objeto` · `icono` · `etiqueta` · `keywords` · `frase` · `imagen_url` · `x` · `y` · `activo` |
| `PROYECTOS` | `titulo` · `categoria` · `descripcion` · `imagen_url` · `link` · `fecha` · `tags` · `activo` |
| `MENSAJES` | se llena sola con el formulario: `fecha` · `nombre` · `email` · `mensaje` · `origen` |
| `VISITAS` | se llena sola: `fecha` · `seccion` |

Detalles útiles:

- **`activo`**: escribe `FALSE` en cualquier fila para ocultarla sin borrarla.
- **`categoria`** de `EXPERIENCIA` genera sola los filtros del extracto.
- **`carta`** (`A`, `J`, `Q`, `K`, `JOKER`) y **`palo`** (`hearts`, `spades`, `diamonds`,
  `clubs`, `joker`) dibujan la carta; **`nivel`** (0–100) es la barra del reverso.
- **`x` / `y`** de `BAG` son el porcentaje donde se pone cada objeto sobre el bolso.
- Agregar una fila = agregar una tarjeta, una carta o un movimiento. No hay que tocar código.

### Imágenes

Sube la foto o los proyectos a Drive → clic derecho → **Compartir → Cualquier persona
con el enlace** → *Copiar vínculo* → pega el enlace tal cual en `foto_url` o `imagen_url`.
El código lo convierte solo al formato que entiende el navegador.

---

## 3. El día a día

- **Cambiar un texto:** se edita la celda. La web se actualiza sola (hay un caché de
  5 minutos). Para verlo ya: menú **🎀 Portafolio → Actualizar la web ahora**.
- **Ver quién escribió:** hoja `MENSAJES` (y el correo, si `notificar_email` está en `TRUE`).
- **Ver qué secciones miran:** hoja `VISITAS` → una tabla dinámica y listo.
- **Menú 🎀 Portafolio:** aparece al abrir la hoja. Si no sale, recarga la pestaña.

---

## 4. Vista previa sin publicar

```bash
python3 scripts/build.py        # regenera Seed.gs y dist/preview.html
open dist/preview.html          # (o doble clic en el archivo)
```

`dist/preview.html` es el portafolio completo con el contenido de `data/seed.json`
metido dentro: sirve para mostrárselo a alguien antes de publicar. El formulario
ahí no guarda nada (lo dice al enviar); en la web publicada sí escribe en la hoja.

---

## 5. Detalles que conviene saber

- Cada visita usa 1 lectura de la hoja como máximo cada 5 minutos (`CacheService`),
  así que aguanta tráfico normal sin ponerse lenta.
- `MailApp` tiene cuota diaria (100 correos en cuentas gratuitas). Si se acaba, el
  mensaje igual queda guardado en `MENSAJES`.
- La URL es de `script.google.com`. Se puede poner detrás de un dominio propio con
  un redirect o un iframe (el `setXFrameOptionsMode(ALLOWALL)` ya lo permite).
- Diseño responsive: en móvil las cartas se vuelven carrusel y el bolso, una lista.
- Respeta `prefers-reduced-motion` y funciona con teclado (↑ ↓ entre secciones, `Esc`
  cierra la galería).

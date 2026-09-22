/**
 * Portafolio interactivo — María Alejandra Gómez
 * -----------------------------------------------------------------------------
 * Web App de Google Apps Script que lee TODO su contenido desde una hoja de
 * cálculo de Google Sheets (el "CMS") y lo devuelve al front en un solo JSON.
 *
 * Para publicarlo:
 *   1. Ejecutar la función  instalarPortafolio()  una sola vez (crea las hojas
 *      y las llena con el contenido inicial).
 *   2. Implementar → Nueva implementación → Aplicación web
 *        · Ejecutar como: Yo
 *        · Quién tiene acceso: Cualquier persona
 *   3. Copiar la URL /exec y compartirla.
 *
 * Después de eso, para cambiar el portafolio SOLO se edita la hoja.
 */

/** Nombre de las hojas. Cambiarlos aquí los cambia en todo el proyecto. */
var HOJAS = {
  CONFIG: 'CONFIG',
  RESUMEN: 'RESUMEN',
  RECIBO: 'RECIBO',
  RECIBO_TOTAL: 'RECIBO_TOTAL',
  REWARDS: 'REWARDS',
  EXPERIENCIA: 'EXPERIENCIA',
  SKILLS: 'SKILLS',
  BAG: 'BAG',
  PROYECTOS: 'PROYECTOS',
  MENSAJES: 'MENSAJES',
  VISITAS: 'VISITAS'
};

var CACHE_KEY = 'portafolio_v1';
var CACHE_SEGUNDOS = 300; // 5 minutos

// -----------------------------------------------------------------------------
// Web App
// -----------------------------------------------------------------------------

function doGet(e) {
  var datos = getPortfolioData();
  var plantilla = HtmlService.createTemplateFromFile('Index');
  // Se escapa '<' para que ningún texto de la hoja pueda romper el <script>.
  plantilla.datosIniciales = JSON.stringify(datos).replace(/</g, '\\u003c');
  return plantilla
    .evaluate()
    .setTitle(datos.config.nombre || 'Portafolio')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .setFaviconUrl('https://ssl.gstatic.com/docs/script/images/favicon.ico');
}

/** Permite partir el HTML en varios archivos: <?!= include('Styles') ?> */
function include(nombre) {
  return HtmlService.createHtmlOutputFromFile(nombre).getContent();
}

// -----------------------------------------------------------------------------
// Lectura de datos
// -----------------------------------------------------------------------------

/**
 * Devuelve todo el contenido del portafolio.
 * Usa CacheService para no leer la hoja en cada visita (la hoja es lenta).
 */
function getPortfolioData(forzar) {
  var cache = CacheService.getScriptCache();
  if (!forzar) {
    var guardado = cache.get(CACHE_KEY);
    if (guardado) {
      try { return JSON.parse(guardado); } catch (err) { /* cache corrupto */ }
    }
  }

  var ss = SpreadsheetApp.getActive();
  var datos = {
    config: leerClaveValor_(ss, HOJAS.CONFIG),
    resumen: leerClaveValor_(ss, HOJAS.RESUMEN),
    recibo: leerTabla_(ss, HOJAS.RECIBO),
    recibo_total: leerTabla_(ss, HOJAS.RECIBO_TOTAL),
    rewards: leerTabla_(ss, HOJAS.REWARDS),
    experiencia: leerTabla_(ss, HOJAS.EXPERIENCIA),
    skills: leerTabla_(ss, HOJAS.SKILLS),
    bag: leerTabla_(ss, HOJAS.BAG),
    proyectos: leerTabla_(ss, HOJAS.PROYECTOS)
  };

  // Las imágenes de Drive se sirven con un link que <img> sí entiende.
  ['bag', 'proyectos'].forEach(function (clave) {
    datos[clave].forEach(function (fila) {
      fila.imagen_url = normalizarImagen_(fila.imagen_url);
    });
  });
  datos.config.foto_url = normalizarImagen_(datos.config.foto_url);

  try {
    cache.put(CACHE_KEY, JSON.stringify(datos), CACHE_SEGUNDOS);
  } catch (err) { /* >100KB: se sirve sin cache */ }

  return datos;
}

/** Hoja de dos columnas -> objeto { clave: valor }. */
function leerClaveValor_(ss, nombreHoja) {
  var hoja = ss.getSheetByName(nombreHoja);
  if (!hoja || hoja.getLastRow() < 2) return {};
  var filas = hoja.getRange(2, 1, hoja.getLastRow() - 1, 2).getDisplayValues();
  var salida = {};
  filas.forEach(function (fila) {
    var clave = String(fila[0] || '').trim();
    if (clave) salida[clave] = String(fila[1] == null ? '' : fila[1]).trim();
  });
  return salida;
}

/** Hoja con encabezados en la fila 1 -> [{ encabezado: valor }]. */
function leerTabla_(ss, nombreHoja) {
  var hoja = ss.getSheetByName(nombreHoja);
  if (!hoja || hoja.getLastRow() < 2) return [];
  var ancho = hoja.getLastColumn();
  var valores = hoja.getRange(1, 1, hoja.getLastRow(), ancho).getDisplayValues();
  var encabezados = valores.shift().map(function (h) {
    return String(h || '').trim().toLowerCase().replace(/\s+/g, '_');
  });
  return valores
    .filter(function (fila) {
      return fila.join('').trim() !== ''; // ignora filas vacías
    })
    .map(function (fila) {
      var obj = {};
      encabezados.forEach(function (h, i) {
        if (h) obj[h] = String(fila[i] == null ? '' : fila[i]).trim();
      });
      return obj;
    })
    .filter(function (obj) {
      // Columna "activo": si existe y dice FALSE/NO, la fila no se publica.
      if (!('activo' in obj) || obj.activo === '') return true;
      return !/^(false|no|0)$/i.test(obj.activo);
    });
}

/**
 * Acepta un link normal de Drive y lo convierte en uno que se puede usar
 * dentro de una etiqueta <img>. Cualquier otra URL se deja igual.
 */
function normalizarImagen_(url) {
  url = String(url || '').trim();
  if (!url) return '';
  var id = url.match(/\/file\/d\/([\w-]{20,})/) || url.match(/[?&]id=([\w-]{20,})/);
  if (id) return 'https://lh3.googleusercontent.com/d/' + id[1];
  return url;
}

// -----------------------------------------------------------------------------
// Interacción desde la web (escritura)
// -----------------------------------------------------------------------------

/**
 * Guarda un mensaje del formulario de contacto en la hoja MENSAJES
 * y (opcional) avisa por correo.
 */
function enviarMensaje(payload) {
  payload = payload || {};
  var nombre = limpiar_(payload.nombre, 120);
  var email = limpiar_(payload.email, 160);
  var mensaje = limpiar_(payload.mensaje, 3000);

  if (!nombre || !email || !mensaje) {
    return { ok: false, error: 'Faltan datos. Completa nombre, correo y mensaje.' };
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return { ok: false, error: 'Ese correo no parece válido.' };
  }
  if (payload.website) { // honeypot anti-bots: los humanos no lo ven
    return { ok: true, mensaje: '¡Gracias! Te escribo pronto.' };
  }

  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(10000);
    var ss = SpreadsheetApp.getActive();
    var hoja = ss.getSheetByName(HOJAS.MENSAJES) || ss.insertSheet(HOJAS.MENSAJES);
    if (hoja.getLastRow() === 0) {
      hoja.appendRow(['fecha', 'nombre', 'email', 'mensaje', 'origen']);
    }
    hoja.appendRow([new Date(), nombre, email, mensaje, limpiar_(payload.origen, 80)]);
  } catch (err) {
    return { ok: false, error: 'No pude guardar el mensaje. Intenta de nuevo.' };
  } finally {
    try { lock.releaseLock(); } catch (err2) {}
  }

  var config = leerClaveValor_(SpreadsheetApp.getActive(), HOJAS.CONFIG);
  if (/^true$/i.test(config.notificar_email || '') && config.email) {
    try {
      MailApp.sendEmail({
        to: config.email,
        subject: 'Nuevo mensaje desde tu portafolio — ' + nombre,
        replyTo: email,
        body: nombre + ' (' + email + ') escribió:\n\n' + mensaje
      });
    } catch (err) { /* sin cuota de correo: el mensaje ya quedó en la hoja */ }
  }

  return { ok: true, mensaje: '¡Listo! Tu mensaje ya me llegó.' };
}

/** Registra una visita/sección vista para tener estadísticas propias. */
function registrarVisita(seccion) {
  var config = leerClaveValor_(SpreadsheetApp.getActive(), HOJAS.CONFIG);
  if (!/^true$/i.test(config.registrar_visitas || '')) return false;
  try {
    var ss = SpreadsheetApp.getActive();
    var hoja = ss.getSheetByName(HOJAS.VISITAS) || ss.insertSheet(HOJAS.VISITAS);
    if (hoja.getLastRow() === 0) hoja.appendRow(['fecha', 'seccion']);
    hoja.appendRow([new Date(), limpiar_(seccion, 60)]);
    return true;
  } catch (err) {
    return false;
  }
}

function limpiar_(texto, max) {
  return String(texto == null ? '' : texto)
    .replace(/[<>]/g, '')
    .trim()
    .slice(0, max || 200);
}

// -----------------------------------------------------------------------------
// Instalación y mantenimiento (se ejecutan desde el editor o el menú)
// -----------------------------------------------------------------------------

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🎀 Portafolio')
    .addItem('Instalar / reparar hojas', 'instalarPortafolio')
    .addItem('Actualizar la web ahora', 'limpiarCache')
    .addSeparator()
    .addItem('Ver datos que lee la web', 'verDatos')
    .addToUi();
}

/** Borra el cache para que los cambios de la hoja se vean de inmediato. */
function limpiarCache() {
  CacheService.getScriptCache().remove(CACHE_KEY);
  try {
    SpreadsheetApp.getUi().alert('Listo. Recarga el portafolio y verás los cambios.');
  } catch (err) { /* ejecutado desde el editor */ }
}

/** Cambio manual en la hoja -> cache fuera. Se conecta como activador onEdit. */
function onEdit(e) {
  CacheService.getScriptCache().remove(CACHE_KEY);
}

function verDatos() {
  var json = JSON.stringify(getPortfolioData(true), null, 2);
  var html = HtmlService.createHtmlOutput('<pre style="font:12px/1.5 monospace">' +
    json.replace(/[<>&]/g, function (c) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c];
    }) + '</pre>').setWidth(800).setHeight(600);
  SpreadsheetApp.getUi().showModalDialog(html, 'Datos del portafolio');
}

/**
 * Crea (o repara) todas las hojas con sus encabezados y el contenido inicial.
 * Es seguro ejecutarla varias veces: no borra filas que ya existan.
 */
function instalarPortafolio() {
  var ss = SpreadsheetApp.getActive();
  var seed = SEED; // definido en Seed.gs

  escribirKV_(ss, HOJAS.CONFIG, seed.config);
  escribirKV_(ss, HOJAS.RESUMEN, seed.resumen);
  escribirTabla_(ss, HOJAS.RECIBO, ['num', 'item', 'check'], seed.recibo);
  escribirTabla_(ss, HOJAS.RECIBO_TOTAL, ['campo', 'valor'], seed.recibo_total);
  escribirTabla_(ss, HOJAS.REWARDS, ['concepto', 'valor'], seed.rewards);
  escribirTabla_(ss, HOJAS.EXPERIENCIA,
    ['fecha', 'empresa', 'rol', 'categoria', 'detalle', 'destacado', 'activo'], seed.experiencia);
  escribirTabla_(ss, HOJAS.SKILLS,
    ['carta', 'palo', 'titulo', 'herramientas', 'descripcion', 'nivel', 'activo'], seed.skills);
  escribirTabla_(ss, HOJAS.BAG,
    ['objeto', 'icono', 'etiqueta', 'keywords', 'frase', 'imagen_url', 'x', 'y', 'activo'], seed.bag);
  escribirTabla_(ss, HOJAS.PROYECTOS,
    ['titulo', 'categoria', 'descripcion', 'imagen_url', 'link', 'fecha', 'tags', 'activo'], seed.proyectos);
  escribirTabla_(ss, HOJAS.MENSAJES, ['fecha', 'nombre', 'email', 'mensaje', 'origen'], []);
  escribirTabla_(ss, HOJAS.VISITAS, ['fecha', 'seccion'], []);

  limpiarCache();
  try {
    SpreadsheetApp.getUi().alert('Hojas listas ✨\n\nAhora: Implementar → Nueva implementación → Aplicación web.');
  } catch (err) { /* sin UI */ }
}

function escribirKV_(ss, nombre, objeto) {
  var hoja = prepararHoja_(ss, nombre, ['clave', 'valor']);
  if (hoja.getLastRow() > 1) return; // ya tiene contenido: no lo pisamos
  var filas = Object.keys(objeto).map(function (k) { return [k, objeto[k]]; });
  if (filas.length) hoja.getRange(2, 1, filas.length, 2).setValues(filas);
  hoja.setColumnWidth(1, 180);
  hoja.setColumnWidth(2, 520);
}

function escribirTabla_(ss, nombre, encabezados, filas) {
  var hoja = prepararHoja_(ss, nombre, encabezados);
  if (hoja.getLastRow() > 1 || !filas.length) return;
  var matriz = filas.map(function (fila) {
    return encabezados.map(function (h) {
      return fila[h] === undefined ? '' : fila[h];
    });
  });
  hoja.getRange(2, 1, matriz.length, encabezados.length).setValues(matriz);
  hoja.autoResizeColumns(1, Math.min(encabezados.length, 6));
}

function prepararHoja_(ss, nombre, encabezados) {
  var hoja = ss.getSheetByName(nombre) || ss.insertSheet(nombre);
  hoja.getRange(1, 1, 1, encabezados.length)
    .setValues([encabezados])
    .setFontWeight('bold')
    .setBackground('#5A0B2D')
    .setFontColor('#FFFFFF');
  hoja.setFrozenRows(1);
  return hoja;
}

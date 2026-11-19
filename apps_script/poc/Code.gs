/*
 * QA2 phase 1 test, Google side.
 *
 * Reads one .xlsx / .xlsm from Drive the way QA2 reads a Traffic Sheet,
 * and leaves two things next to this spreadsheet:
 *   - a tab "Test · <file>" with how long each step took and what it read
 *   - a JSON file with every cell it read, to compare with Python's reading
 *
 * It only reads. The temporary Google Sheets copy it makes to read the
 * file goes to the trash at the end; the original is never changed.
 *
 * Needs the advanced services Drive (v3) and Sheets (v4): see LEEME.md.
 */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('QA2 test')
    .addItem('Read a file from Drive…', 'readFileFromDrive')
    .addToUi();
}

function readFileFromDrive() {
  var ui = SpreadsheetApp.getUi();
  var answer = ui.prompt('QA2 test',
    'Paste the Drive link (or ID) of the .xlsx or .xlsm to read: a Traffic Sheet or the extension\'s Excel.',
    ui.ButtonSet.OK_CANCEL);
  if (answer.getSelectedButton() !== ui.Button.OK) return;
  var id = fileIdFrom(answer.getResponseText());
  if (!id) {
    ui.alert('That doesn\'t look like a Drive link or a file ID.');
    return;
  }

  var snap = snapshotDriveFile(id);
  var here = SpreadsheetApp.getActiveSpreadsheet();
  var jsonName = 'QA2_test_' + snap.file.replace(/\.[^.]+$/, '') + '.json';
  var json = DriveApp.createFile(jsonName, JSON.stringify(snap), 'application/json');
  var parents = DriveApp.getFileById(here.getId()).getParents();
  if (parents.hasNext()) json.moveTo(parents.next());
  writeSummaryTab(here, snap, json);
  ui.alert('Done in ' + snap.totalSecs.toFixed(1) + ' s',
    'The tab "' + tabName(snap.file) + '" has the times. The file "' + jsonName +
    '" is in the same Drive folder as this spreadsheet: download it and send it over.',
    ui.ButtonSet.OK);
}

function fileIdFrom(text) {
  var m = String(text || '').match(/[-\w]{25,}/);
  return m ? m[0] : '';
}

function snapshotDriveFile(id) {
  var started = Date.now(), timings = [];
  var lap = function (label, since) { timings.push([label, (Date.now() - since) / 1000]); };

  var source = DriveApp.getFileById(id);
  var t = Date.now();
  var copy = Drive.Files.copy(
    {name: '[QA2 test, temporary] ' + source.getName(), mimeType: MimeType.GOOGLE_SHEETS},
    id, {supportsAllDrives: true});
  lap('Convert to Google Sheets', t);

  var out = {file: source.getName(), reader: 'apps-script', sheets: [], timings: timings};
  try {
    t = Date.now();
    var meta = Sheets.Spreadsheets.get(copy.id, {
      includeGridData: true,
      fields: 'properties.timeZone,sheets(properties(title,hidden),merges,data(startRow,rowMetadata(hiddenByUser)))'
    });
    lap('Hidden rows and merged cells', t);
    var tz = meta.properties.timeZone;
    var formatDate = function (d) { return Utilities.formatDate(d, tz, 'yyyy-MM-dd HH:mm:ss'); };
    var book = SpreadsheetApp.openById(copy.id);

    meta.sheets.forEach(function (s) {
      t = Date.now();
      var name = s.properties.title;
      var range = book.getSheetByName(name).getDataRange();
      var raw = {
        values: range.getValues(),
        backgrounds: range.getBackgrounds(),
        fontColors: range.getFontColors(),
        links: range.getRichTextValues().map(function (row) { return row.map(linkOf); }),
        hiddenRows: hiddenRowsOf(s),
        merges: (s.merges || []).map(function (m) {
          return {r1: (m.startRowIndex || 0) + 1, r2: m.endRowIndex,
                  c1: (m.startColumnIndex || 0) + 1, c2: m.endColumnIndex};
        })
      };
      var sheet = Snapshot.buildSheet(raw, formatDate);
      sheet.name = name;
      sheet.hidden = !!s.properties.hidden;
      out.sheets.push(sheet);
      lap('Read "' + name + '"', t);
    });
  } finally {
    DriveApp.getFileById(copy.id).setTrashed(true);
  }
  out.totalSecs = (Date.now() - started) / 1000;
  return out;
}

/* The link of a cell: the whole cell's, or else the first one inside it. */
function linkOf(rt) {
  if (!rt) return '';
  var url = rt.getLinkUrl();
  if (url) return url;
  var runs = rt.getRuns();
  for (var i = 0; i < runs.length; i++) {
    if (runs[i].getLinkUrl()) return runs[i].getLinkUrl();
  }
  return '';
}

function hiddenRowsOf(s) {
  var out = [];
  (s.data || []).forEach(function (d) {
    var start = d.startRow || 0;
    (d.rowMetadata || []).forEach(function (m, i) {
      if (m && m.hiddenByUser) out.push(start + i + 1);
    });
  });
  return out;
}

function tabName(file) {
  return ('Test · ' + file).slice(0, 90);
}

function writeSummaryTab(book, snap, json) {
  var name = tabName(snap.file);
  var old = book.getSheetByName(name);
  if (old) book.deleteSheet(old);
  var tab = book.insertSheet(name);
  var rows = [['Item', 'Value', '', '', '', ''],
    ['File', snap.file, '', '', '', ''],
    ['Read on', Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm'), '', '', '', ''],
    ['Total time (s)', snap.totalSecs, '', '', '', ''],
    ['JSON for the comparison', json.getName(), '', '', '', ''],
    ['', '', '', '', '', ''],
    ['Step', 'Seconds', '', '', '', '']];
  snap.timings.forEach(function (t) { rows.push([t[0], t[1], '', '', '', '']); });
  rows.push(['', '', '', '', '', '']);
  rows.push(['Sheet', 'Hidden sheet', 'Last row', 'Hidden rows', 'Merged ranges', 'Cells read']);
  snap.sheets.forEach(function (s) {
    rows.push([s.name, s.hidden ? 'Yes' : '', s.maxRow, s.hiddenRows.length, s.merges, s.cells.length]);
  });
  rows.push(['', '', '', '', '', '']);
  rows.push(['Colour of the cells read', 'GREEN', 'RED', 'YELLOW', 'GREY', 'Other']);
  snap.sheets.forEach(function (s) {
    var n = {GREEN: 0, RED: 0, YELLOW: 0, GREY: 0, other: 0};
    s.cells.forEach(function (c) {
      if (!c[3]) return;
      if (n[c[4]] !== undefined) n[c[4]] += 1; else n.other += 1;
    });
    rows.push([s.name, n.GREEN, n.RED, n.YELLOW, n.GREY, n.other]);
  });
  tab.getRange(1, 1, rows.length, 6).setValues(rows);
  tab.getRange(1, 1, 1, 6).setFontWeight('bold');
  tab.autoResizeColumns(1, 6);
}

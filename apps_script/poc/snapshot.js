/*
 * QA2 phase 1 test: reads a sheet the way QA2's Python reads a Traffic
 * Sheet (core/extraction.py read_sheet + core/colors.py classify).
 *
 * Pure functions, no Google services: the same file runs in Apps Script
 * (as Snapshot.gs) and under Node for the tests. Code.gs hands it what
 * Google returns for one sheet; it hands back the cells QA2 would see.
 */
/* eslint-disable no-var */
var Snapshot = (function () {
  var GREEN = "GREEN", RED = "RED", YELLOW = "YELLOW", GREY = "GREY", WHITE = "WHITE", UNKNOWN = "UNKNOWN";

  /* Python's colorsys.rgb_to_hsv. */
  function hsv(r, g, b) {
    var max = Math.max(r, g, b), min = Math.min(r, g, b), v = max;
    if (max === min) return [0, 0, v];
    var s = (max - min) / max;
    var rc = (max - r) / (max - min), gc = (max - g) / (max - min), bc = (max - b) / (max - min);
    var h;
    if (r === max) h = bc - gc;
    else if (g === max) h = 2.0 + rc - bc;
    else h = 4.0 + gc - rc;
    h = (h / 6.0) % 1.0;
    if (h < 0) h += 1.0;
    return [h, s, v];
  }

  /*
   * The color family of a fill, as core/colors.py classify() decides it.
   * Returns [family, confidence].
   */
  function classify(rgb) {
    if (!rgb || !/^[0-9A-Fa-f]{6}$/.test(rgb)) return [UNKNOWN, "NONE"];
    var x = hsv(parseInt(rgb.slice(0, 2), 16) / 255, parseInt(rgb.slice(2, 4), 16) / 255,
      parseInt(rgb.slice(4, 6), 16) / 255);
    var hue = x[0] * 360, s = x[1], v = x[2];
    if (s <= 0.04) return v >= 0.93 ? [WHITE, "HIGH"] : [GREY, "HIGH"];
    var conf = s >= 0.25 ? "HIGH" : "MEDIUM";
    if (hue <= 14 || hue >= 346) return [RED, conf];
    if (hue >= 15 && hue <= 44) return [YELLOW, "LOW"];
    if (hue >= 45 && hue <= 72) return [YELLOW, conf];
    if (hue >= 73 && hue <= 175) return [GREEN, conf];
    return [UNKNOWN, "NONE"];
  }

  /* core/normalize.py norm_text: trim, collapse spaces, Excel's _x000D_. */
  function normText(value) {
    return String(value).replace(/\u00a0/g, " ").replace(/_x000[dDaA]_/g, " ").replace(/\s+/g, " ").trim();
  }

  /*
   * A value as Python's str() writes what openpyxl reads, so both sides
   * compare as text. `formatDate(d)` -> "yyyy-MM-dd HH:mm:ss" in the
   * spreadsheet's own time zone (Apps Script's Utilities.formatDate).
   */
  function valueText(v, formatDate) {
    if (v === null || v === undefined || v === "") return null;
    if (v instanceof Date || Object.prototype.toString.call(v) === "[object Date]") return formatDate(v);
    if (v === true) return "True";
    if (v === false) return "False";
    return normText(v);
  }

  /* "#ffffff" (or nothing) is no fill; anything else, "RRGGBB". */
  function hex(color) {
    var c = String(color || "").replace("#", "").toUpperCase();
    return /^[0-9A-F]{6}$/.test(c) && c !== "FFFFFF" ? c : null;
  }

  /*
   * One sheet, as read_sheet() sees it:
   *   - hidden rows are skipped (a hidden row is not part of the request)
   *   - a cell counts when it has a value or a fill
   *   - the last row is the last row with a value, not with formatting
   *   - a merged range copies its first cell into the rest (fill-down)
   *   - the letter color is kept only when there is no fill
   *
   * raw: {values, backgrounds, fontColors, links} (2D, from A1),
   *      hiddenRows: [row, ...] (1-based),
   *      merges: [{r1, c1, r2, c2}] (1-based, inclusive)
   * Cells come back as [row, col, text, rgb, family, fontRgb, link, inheritedFromRow].
   */
  function buildSheet(raw, formatDate) {
    var hidden = {};
    (raw.hiddenRows || []).forEach(function (r) { hidden[r] = true; });
    var grid = {}, maxRow = 0, cells = [];
    var values = raw.values || [];
    for (var i = 0; i < values.length; i++) {
      var r = i + 1;
      if (hidden[r]) continue;
      var rowHasContent = false;
      for (var j = 0; j < values[i].length; j++) {
        var text = valueText(values[i][j], formatDate);
        var rgb = hex(((raw.backgrounds || [])[i] || [])[j]);
        if (text === null && rgb === null) continue;
        if (text !== null) rowHasContent = true;
        var font = null;
        if (rgb === null && text !== null) {
          var f = String((((raw.fontColors || [])[i] || [])[j]) || "").replace("#", "").toUpperCase();
          if (/^[0-9A-F]{6}$/.test(f) && f !== "000000") font = f;
        }
        var link = ((raw.links || [])[i] || [])[j] || null;
        (grid[r] = grid[r] || {})[j + 1] = [r, j + 1, text === null ? "" : text, rgb,
          rgb ? classify(rgb)[0] : WHITE, font, link, 0];
      }
      if (rowHasContent) maxRow = r;
    }

    var mergedApplied = 0;
    (raw.merges || []).forEach(function (m) {
      if (m.r1 > maxRow) return;
      var anchor = (grid[m.r1] || {})[m.c1];
      if (!anchor || anchor[2] === "") return;
      for (var rr = m.r1; rr <= Math.min(m.r2, maxRow); rr++) {
        for (var cc = m.c1; cc <= m.c2; cc++) {
          if (rr === m.r1 && cc === m.c1) continue;
          (grid[rr] = grid[rr] || {})[cc] = [rr, cc, anchor[2], anchor[3], anchor[4], null, anchor[6], m.r1];
          mergedApplied += 1;
        }
      }
    });

    Object.keys(grid).map(Number).sort(function (a, b) { return a - b; }).forEach(function (r) {
      Object.keys(grid[r]).map(Number).sort(function (a, b) { return a - b; }).forEach(function (c) {
        cells.push(grid[r][c]);
      });
    });
    return {
      maxRow: maxRow,
      hiddenRows: (raw.hiddenRows || []).slice().sort(function (a, b) { return a - b; }),
      merges: (raw.merges || []).length,
      mergedApplied: mergedApplied,
      cells: cells
    };
  }

  return {classify: classify, normText: normText, valueText: valueText, buildSheet: buildSheet};
})();

if (typeof module !== "undefined") module.exports = Snapshot;

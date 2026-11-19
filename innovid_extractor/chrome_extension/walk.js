/*
 * The Innovid walk-through, ported from extractor.py.
 *
 * Pure functions: they take a `call(url, method, body)` that returns
 * parsed JSON, so the same code runs in the extension and in the tests.
 * No network, no Chrome APIs here.
 */
/* eslint-disable no-var */
var Walk = (function () {
  var APP_ORIGIN = "https://campaign-manager.flashtalking.net";
  var API = "https://api.flashtalking.net";
  var CM_BASE = API + "/cm/v1/ui";
  var DT_BASE = API + "/dt/v1/ui";
  var TAG_BASE = API + "/tag/v1/ui";
  var CM_V1 = API + "/cm/v1";

  var SUMMARY_FIELDS = [
    "status", "siteName", "placementId", "placementName", "placementType",
    "dimensions", "clickTag1", "startDate", "endDate", "creativeDescription",
    "creativeId", "fileName", "thirdPartySurvey1", "thirdPartyImpression1",
    "thirdPartyImpression2", "verificationPartner", "verificationStatus",
    "bookedUnits", "id", "name", "level", "rotationWeight",
    "placementModernDtreeId", "modernDtreeId", "modernDtreeName",
    "placementDecisionSetId", "decisionSetId", "decisionSetName"
  ];
  var SUMMARY_PAGE_SIZE = 500;
  var MAX_SUMMARY_PAGES = 40;
  var GIVE_UP_AFTER_FAILED_LOOKUPS = 3;
  var MAX_SITES = 40;
  var PARALLEL = 4;

  function tokens(textIn) {
    var out = [];
    String(textIn || "").split(/[\n\r,;\t]+/).forEach(function (t) {
      t = t.trim();
      if (t && out.indexOf(t) < 0) out.push(t);
    });
    return out;
  }

  /*
   * "Only these placements" (Placement ID or the P code the name starts
   * with) and "Only these decision sets" (id or name). Both empty: null,
   * everything. Both filled: their union. What matched nothing is noted.
   */
  function applyFilters(ex, opts) {
    var pl = tokens(opts.placements), ds = tokens(opts.dsets);
    if (!pl.length && !ds.length) return null;
    var scope = {placements: {}, dsets: null};
    var unmatched = [];
    var placementRows = ex.rows.filter(function (r) { return !r.isCreative || r.isDecisionSet; });

    pl.forEach(function (t) {
      var up = t.toUpperCase(), hit = false;
      placementRows.forEach(function (r) {
        var name = r.placementName.toUpperCase();
        if (r.placementId === t || name === up || name.indexOf(up + "_") === 0) {
          scope.placements[r.placementId] = true;
          hit = true;
        }
      });
      if (!hit) unmatched.push(t);
    });

    if (ds.length) {
      scope.dsets = {};
      ds.forEach(function (t) {
        var low = t.toLowerCase(), hit = false;
        ex.rows.forEach(function (r) {
          [[r.dtreeId, r.dtreeName], [r.dsetId, r.dsetName], [r.dsetLinkId, r.dsetName]].forEach(function (p) {
            if (p[0] && (p[0] === t || (p[1] && p[1].toLowerCase() === low))) {
              scope.dsets[p[0]] = true;
              scope.placements[r.placementId] = true;
              hit = true;
            }
          });
        });
        if (!hit) unmatched.push(t);
      });
      // Placements asked for by ID keep all their decision sets.
      ex.rows.forEach(function (r) {
        if (scope.placements[r.placementId] && pl.length && placementMatches(r, pl)) {
          [r.dtreeId, r.dsetId, r.dsetLinkId].forEach(function (k) { if (k) scope.dsets[k] = true; });
        }
      });
    }
    ex.scope = Object.keys(scope.placements);
    ex.filters = {placements: pl, dsets: ds, unmatched: unmatched};
    return scope;
  }

  function placementMatches(r, pl) {
    var name = r.placementName.toUpperCase();
    return pl.some(function (t) {
      var up = t.toUpperCase();
      return r.placementId === t || name === up || name.indexOf(up + "_") === 0;
    });
  }

  function text(v) {
    if (v === null || v === undefined) return "";
    if (typeof v === "object") v = v.name || v.value || "";
    return String(v).trim();
  }

  function SessionProblem(message) {
    this.name = "SessionProblem";
    this.message = message;
  }
  SessionProblem.prototype = Object.create(Error.prototype);

  function parseSummary(payload) {
    var items = payload && Array.isArray(payload.items) ? payload.items : [];
    var rows = [];
    items.forEach(function (it) {
      if (!it || typeof it !== "object" || !text(it.placementId)) return;
      var g = function (k) { return text(it[k]); };
      var row = {
        level: g("level"), placementId: g("placementId"), placementName: g("placementName"),
        site: g("siteName"), dimensions: g("dimensions"), status: g("status"),
        start: g("startDate"), end: g("endDate"), creativeId: g("creativeId"),
        fileName: g("fileName"), clickUrl: g("clickTag1"), surveyPixel: g("thirdPartySurvey1"),
        impressionPixel1: g("thirdPartyImpression1"), impressionPixel2: g("thirdPartyImpression2"),
        verificationPartner: g("verificationPartner"), verificationStatus: g("verificationStatus"),
        rotationWeight: g("rotationWeight"),
        dtreeId: g("placementModernDtreeId") || g("modernDtreeId"), dtreeName: g("modernDtreeName"),
        dsetId: g("decisionSetId"), dsetName: g("decisionSetName"), dsetLinkId: g("placementDecisionSetId"),
        // Everything Innovid sent for this row: the export-style sheets
        // read their columns from it.
        raw: it
      };
      row.isCreative = row.level.toUpperCase() === "PLACEMENT-CREATIVE";
      // Innovid lists a placement's decision set as one more line under
      // it, at creative level but with no creative id.
      row.isDecisionSet = row.isCreative && !row.creativeId && !!(row.dtreeId || row.dsetId || row.dsetLinkId);
      rows.push(row);
    });
    return rows;
  }

  function parseDset(payload, askedFor) {
    if (!payload || !Array.isArray(payload.nodes)) return [];
    var def = payload.defaultServing && typeof payload.defaultServing === "object" ? payload.defaultServing : {};
    return payload.nodes.filter(function (n) { return n && typeof n === "object"; }).map(function (n) {
      var s = n.serving, isDefault = !!n.isDefault, cid, cname;
      if (s && typeof s === "object") { cid = text(s.id); cname = text(s.name || s.fileName); }
      else { cid = text(s); cname = ""; }
      if (isDefault && !cid) { cid = text(def.id); cname = text(def.name); }
      return {
        dsetId: askedFor, dsetName: text(payload.name), servingMethod: text(payload.servingMethod),
        creativeId: cid, creativeName: cname, start: text(n.startTimestamp), end: text(n.endTimestamp),
        weight: text(n.weight), isDefault: isDefault
      };
    });
  }

  function dsetMismatch(payload, askedFor, expectedName) {
    if (!payload || typeof payload !== "object") return "came back in an unexpected shape";
    var got = text(payload.id);
    if (got && got !== askedFor) return "asked for " + askedFor + ", Innovid returned " + got + "; ignored";
    var name = text(payload.name);
    if (expectedName && name && name !== expectedName) {
      return "named '" + name + "' here but '" + expectedName + "' in the summary; ignored";
    }
    return "";
  }

  function mediaFilterOf(detail) {
    var g = (((detail || {}).videoConfig || {}).optionGroups || {}).ctvOttGroup || {};
    var v = g.mediaFilter;
    return v === null || v === undefined || v === "" ? "Default" : String(v);
  }

  function now() { return (typeof performance !== "undefined" ? performance.now() : Date.now()) / 1000; }

  /*
   * Reads one campaign. `say(text)` reports progress. Never throws for a
   * partial failure; throws SessionProblem when only signing in fixes it.
   */
  async function extract(campaignId, call, say, opts) {
    say = say || function () {};
    var ex = {
      campaignId: String(campaignId), rows: [], nodes: [], mediaFilters: [], errors: [],
      timings: [], dsetsAsked: 0, dsetsRead: 0, summaryPages: 0
    };

    var t0 = now(), page = 1;
    say("Reading placements…");
    for (;;) {
      var payload = await call(CM_BASE + "/campaigns/" + campaignId + "/summary?fields=" + SUMMARY_FIELDS.join(","),
        "POST", {rpp: SUMMARY_PAGE_SIZE, page: page, searchTerm: null, sortBy: "name", sortOrder: "ASC"});
      Array.prototype.push.apply(ex.rows, parseSummary(payload));
      ex.summaryPages = page;
      var total = payload && payload.totalPages;
      if (typeof total !== "number" || page >= total) break;
      if (page >= MAX_SUMMARY_PAGES) {
        ex.errors.push("Stopped after " + MAX_SUMMARY_PAGES + " summary pages: the placement list is incomplete.");
        break;
      }
      page += 1;
    }
    ex.timings.push(["Campaign summary (placements)", now() - t0]);

    t0 = now();
    var scope = applyFilters(ex, opts || {});
    var groups = [["modern decision tree", {}], ["decisionSetId", {}], ["placementDecisionSetId", {}]];
    ex.rows.forEach(function (r) {
      if (scope && !scope.placements[r.placementId]) return;
      if (r.dtreeId && !(r.dtreeId in groups[0][1])) groups[0][1][r.dtreeId] = r.dtreeName;
      if (r.dsetId) { if (!(r.dsetId in groups[1][1])) groups[1][1][r.dsetId] = r.dsetName; }
      else if (r.dsetLinkId && !r.dtreeId && !(r.dsetLinkId in groups[2][1])) groups[2][1][r.dsetLinkId] = r.dsetName;
    });
    var seen = {};
    groups.forEach(function (g) {
      Object.keys(g[1]).forEach(function (k) {
        if (seen[k] || (scope && scope.dsets && !scope.dsets[k])) delete g[1][k];
        seen[k] = true;
      });
    });
    groups.forEach(function (g) { ex.dsetsAsked += Object.keys(g[1]).length; });

    var done = 0;
    for (var gi = 0; gi < groups.length; gi++) {
      var source = groups[gi][0], ids = groups[gi][1], keys = Object.keys(ids).sort();
      var failures = 0, shapes = {};
      // A few at a time: much faster than one by one, gentle enough for
      // an API that slows down when it gets many requests at once.
      for (var ki = 0; ki < keys.length; ki += PARALLEL) {
        if (failures >= GIVE_UP_AFTER_FAILED_LOOKUPS && Object.keys(shapes).length === 1) {
          ex.errors.push("Stopped asking for " + (keys.length - ki) + " more " + source +
            " id(s): the first " + failures + " failed the same way.");
          break;
        }
        var batch = keys.slice(ki, ki + PARALLEL);
        var answers = await Promise.all(batch.map(function (id) {
          return call(DT_BASE + "/dset/" + id, "GET", null).then(
            function (dset) { return {id: id, dset: dset, problem: dsetMismatch(dset, id, ids[id])}; },
            function (e) {
              if (e instanceof SessionProblem) throw e;
              return {id: id, dset: null, problem: String(e && e.message || e)};
            });
        }));
        answers.forEach(function (a) {
          if (a.problem) {
            failures += 1;
            shapes[a.problem.split(a.id).join("{id}")] = true;
            ex.errors.push("Decision set " + a.id + " (" + source + "): " + a.problem);
            return;
          }
          Array.prototype.push.apply(ex.nodes, parseDset(a.dset, a.id));
          ex.dsetsRead += 1;
        });
        done += batch.length;
        say("Reading decision sets " + done + " / " + ex.dsetsAsked + "…");
      }
    }
    ex.timings.push(["Decision sets (creatives)", now() - t0]);

    t0 = now();
    say("Reading Media Filters…");
    try {
      var sites = await call(CM_V1 + "/campaigns/" + campaignId + "/campaign-sites?rpp=543", "GET", null);
      var items = sites && !Array.isArray(sites) ? (sites.items || []) : (sites || []);
      for (var si = 0; si < Math.min(items.length, MAX_SITES); si++) {
        var it = items[si];
        if (!it || !it.id) continue;
        var site = it.site && typeof it.site === "object" ? it.site : {};
        var detail = await call(TAG_BASE + "/campaign-sites/" + it.id, "GET", null);
        ex.mediaFilters.push([text(site.id || it.siteId), text(site.name), mediaFilterOf(detail)]);
      }
    } catch (e) {
      if (e instanceof SessionProblem) throw e;
      ex.errors.push("Couldn't read the sites' Media Filters: " + (e && e.message || e));
    }
    ex.timings.push(["Media Filters (sites)", now() - t0]);
    return ex;
  }

  /*
   * The columns of Innovid's own exports (placement_v2 and
   * placement-creative_v2), in their order and with their names, so the
   * extension's file reads like the exports it replaces.
   */
  var PL_COLUMNS = [
    "Site_ID", "Placement_ID", "Site", "Placement", "Dimensions", "Start_Date", "End_Date",
    "Placement_Type", "Status", "Hidden", "Stopped", "Booked_Units", "Booked_Cost", "Media_Cost_Type",
    "Media_Cost_Rate", "Cost_Cap_Period", "Package_ID", "Package_Name", "Flashtalking_Cost_Type",
    "Flashtalking_Cost", "Third_Party_ID", "Content_Category", "Strategy"
  ].concat(numbered("Clicktag_", 20), numbered("Third_Party_Impression_", 10), [
    "Third_Party_Survey", "Third_Party_Survey_2", "Third_Party_Survey_3", "Ad_Gap_ID",
    "Placement_Target", "Delivered_Impressions", "Percent_Delivered", "Event_Tag_Count",
    "Custom_Data_1", "Custom_Data_2", "Custom_Data_3"
  ]);
  var PC_COLUMNS = [
    "Enabled", "Site_ID", "Placement_ID", "Creative_ID", "Site", "Placement", "Dimensions",
    "Legacy_Decision_Tree", "Decision_Tree_Name", "Decision_Tree_ID", "Filename", "Placement_Type",
    "Placement_Creative_ID", "Start_Date", "End_Date", "Third_Party_ID", "Creative_Name", "ClickTags", "Rotation"
  ].concat(numbered("Clicktag_", 20), numbered("Third_Party_Impression_", 10), [
    "Third_Party_Survey", "Third_Party_Survey_2", "Third_Party_Survey_3", "Creative_Group_1",
    "Creative_Group_2", "Status", "Stopped", "Ad_Type", "Creative_Type", "Expand_Dimensions",
    "Backup_Image_ID", "Backup_Image_Name", "Base_File_Size (KB)", "Total_File_Size (KB)", "Video",
    "Rich", "Instant", "Linked", "Event_Tag_Count", "Custom_Data_1", "Custom_Data_2", "Custom_Data_3"
  ]);

  function numbered(prefix, n) {
    var out = [];
    for (var i = 1; i <= n; i++) out.push(prefix + i);
    return out;
  }

  /*
   * Where a column's name and Innovid's field name differ by more than
   * case and underscores. Everything else is found by the column's own
   * name (Clicktag_1 -> clickTag1, Site_ID -> siteId, Hidden -> isHidden).
   */
  var FIELD_ALIASES = {
    "Site": ["siteName"],
    "Placement": ["placementName"],
    "Third_Party_Survey": ["thirdPartySurvey1", "thirdPartySurvey"],
    "Creative_Name": ["creativeName", "creativeDescription"],
    "ClickTags": ["numClickTags", "clickTags", "clickTagCount"],
    "Media_Cost_Type": ["costTypeMedia"],
    "Media_Cost_Rate": ["costRateMedia"],
    "Flashtalking_Cost_Type": ["costTypeFt"],
    "Flashtalking_Cost": ["costRateFt"],
    "Delivered_Impressions": ["impressionsDelivered"],
    "Legacy_Decision_Tree": ["legacyDecisionTree", "isLegacyDecisionTree", "isLegacyDtree", "legacyDtree"],
    "Decision_Tree_Name": ["decisionTreeName", "legacyDtreeName", "dtreeName"],
    "Decision_Tree_ID": ["decisionTreeId", "legacyDtreeId", "dtreeId"],
    "Base_File_Size (KB)": ["baseFileSize", "baseFileSizeKb"],
    "Total_File_Size (KB)": ["totalFileSize", "totalFileSizeKb"]
  };

  /* Columns Innovid doesn't send but the export works out the same way. */
  var DERIVED = {"Stopped": true, "Rotation": true};

  /* How the export writes some numbers (checked against campaign 330328). */
  function decimals(d) {
    return function (v) { var n = Number(v); return v !== "" && isFinite(n) ? n.toFixed(d) : v; };
  }
  function kilobytes(v) {
    var n = Number(v);
    return isFinite(n) ? (Math.ceil(n * 100 / 1024 - 1e-9) / 100).toFixed(2) : v;
  }
  var FORMATS = {
    "Booked_Cost": decimals(2), "Media_Cost_Rate": decimals(4), "Flashtalking_Cost": decimals(4),
    "Percent_Delivered": decimals(2),
    // Innovid sends bytes; the export writes KB with two decimals,
    // rounded up (1995.291 KB is 1995.30 there).
    "Base_File_Size (KB)": kilobytes,
    "Total_File_Size (KB)": kilobytes
  };

  function squash(name) { return String(name).replace(/[^A-Za-z0-9]/g, "").toLowerCase(); }

  function candidates(column) {
    var base = squash(column.replace(/\s*\(.*?\)\s*/g, ""));
    return (FIELD_ALIASES[column] || []).map(squash).concat([base, "is" + base]);
  }

  /* A value as the export writes it: Yes/No for flags, lists joined. */
  function cell(v) {
    if (v === null || v === undefined) return "";
    if (v === true) return "Yes";
    if (v === false) return "No";
    if (Array.isArray(v)) return v.map(cell).filter(function (x) { return x !== ""; }).join(", ");
    if (typeof v === "object") return cell(v.name !== undefined ? v.name : v.value !== undefined ? v.value : v.id);
    return String(v).trim();
  }

  /*
   * Fills the export columns of one sheet from the rows' raw fields.
   * Returns the rows plus, per column, which Innovid field it came from
   * ("" when no row carried any field by that name).
   */
  /*
   * Costs and rates: commercial data the QA never uses. The columns stay,
   * so the sheet keeps the export's layout, but their values are not
   * written, and Innovid fields shows no example of them.
   */
  var WITHHELD = ["Booked_Cost", "Media_Cost_Type", "Media_Cost_Rate", "Cost_Cap_Period",
    "Flashtalking_Cost_Type", "Flashtalking_Cost"];
  var WITHHELD_FIELD = /cost/i;

  var CLASSIFICATION = "Internal · Confidential. WPP Media campaign data: do not share outside the company.";

  function exportColumns(rows, columns) {
    var source = {};
    columns.forEach(function (c) { source[c] = ""; });
    var out = rows.map(function (r) {
      var index = {};
      Object.keys(r.raw || {}).forEach(function (k) { index[k.toLowerCase()] = k; });
      return columns.map(function (c) {
        var cands = candidates(c);
        for (var i = 0; i < cands.length; i++) {
          var key = index[cands[i]];
          if (key !== undefined) {
            if (!source[c]) source[c] = key;
            if (WITHHELD.indexOf(c) >= 0) return "";
            var v = cell(r.raw[key]);
            return v !== "" && FORMATS[c] ? FORMATS[c](v) : v;
          }
        }
        return "";
      });
    });
    return {rows: out, source: source};
  }

  /* Every field Innovid sent, how often it had a value, and where it went. */
  function fieldsSheet(rows, usedBy) {
    var info = {};
    rows.forEach(function (r) {
      var lvl = r.isCreative ? "Placement-Creative" : "Placement";
      Object.keys(r.raw || {}).forEach(function (k) {
        var f = info[k] = info[k] || {levels: {}, filled: 0, example: ""};
        f.levels[lvl] = true;
        var v = cell(r.raw[k]);
        if (v !== "") {
          f.filled += 1;
          if (!f.example) {
            f.example = WITHHELD_FIELD.test(k) ? "(not extracted)" : v.length > 120 ? v.slice(0, 117) + "…" : v;
          }
        }
      });
    });
    var out = [["Innovid field", "Levels", "Rows with a value", "Example", "Used for column"]];
    Object.keys(info).sort(function (a, b) { return a.toLowerCase() < b.toLowerCase() ? -1 : 1; }).forEach(function (k) {
      var f = info[k];
      out.push([k, Object.keys(f.levels).join(", "), f.filled, f.example, (usedBy[k] || []).join(", ")]);
    });
    return out;
  }

  /* The sheets of the workbook, as arrays of rows (first row = headers). */
  function sheets(ex, extraTimings) {
    var inScope = {};
    (ex.scope || []).forEach(function (id) { inScope[id] = true; });
    var rows = ex.scope ? ex.rows.filter(function (r) { return inScope[r.placementId]; }) : ex.rows;
    var placements = rows.filter(function (r) { return !r.isCreative; });
    var creatives = rows.filter(function (r) { return r.isCreative && !r.isDecisionSet; });
    var dsRows = rows.filter(function (r) { return r.isDecisionSet; });
    var timings = (extraTimings || []).concat(ex.timings);
    var totalSecs = timings.reduce(function (a, t) { return a + t[1]; }, 0);
    var placementIds = {};
    rows.forEach(function (r) { placementIds[r.placementId] = true; });

    var dsOf = {};
    placements.concat(dsRows).forEach(function (r) {
      if ((r.dtreeId || r.dsetId || r.dsetLinkId) && !dsOf[r.placementId]) dsOf[r.placementId] = r;
    });
    var parentOf = {};
    placements.forEach(function (r) { parentOf[r.placementId] = r; });
    var byDset = {};
    ex.nodes.forEach(function (n) { (byDset[n.dsetId] = byDset[n.dsetId] || []).push(n); });

    var summary = [["Item", "Value"],
      ["Classification", CLASSIFICATION],
      ["Campaign ID", ex.campaignId],
      ["Extracted", new Date().toISOString().slice(0, 16).replace("T", " ")],
      ["Read with", "Chrome extension"],
      ["Placements", Object.keys(placementIds).length],
      ["Placements with a decision set", Object.keys(dsOf).length],
      ["Creative rows", creatives.length],
      ["Decision sets read", ex.dsetsRead + " of " + ex.dsetsAsked],
      ["Creatives inside decision sets", ex.nodes.length],
      ["Sites (Media Filters)", ex.mediaFilters.length]];
    if (ex.filters) {
      summary.push(["Filter · only these placements", ex.filters.placements.join(", ") || "(all)"],
        ["Filter · only these decision sets", ex.filters.dsets.join(", ") || "(all)"]);
      if (ex.filters.unmatched.length) {
        summary.push(["Filter · not found in this campaign", ex.filters.unmatched.join(", ")]);
      }
    } else {
      summary.push(["Filter", "None: the whole campaign"]);
    }
    summary.push(["", ""]);
    timings.forEach(function (t) { summary.push(["Time · " + t[0], t[1].toFixed(1) + " s"]); });
    summary.push(["Time · total", totalSecs.toFixed(1) + " s"], ["", ""]);
    if (ex.errors.length) ex.errors.forEach(function (e) { summary.push(["Could not read", e]); });
    else summary.push(["Could not read", "Nothing: everything was read."]);

    var dsCols = function (d) {
      return d ? [d.dtreeId || d.dsetId || d.dsetLinkId, d.dtreeName || d.dsetName || d.fileName] : ["", ""];
    };

    // Placement level: Innovid's placement export, then what no export has.
    var plx = exportColumns(placements, PL_COLUMNS);
    var pl = [PL_COLUMNS.concat(["Verification_Partner", "Verification_Status", "Prisma_Placement_ID",
      "Decision_Set_ID", "Decision_Set_Name"])];
    var plCol = function (name) { return PL_COLUMNS.indexOf(name); };
    var stoppedOf = {};
    placements.forEach(function (r, i) {
      var line = plx.rows[i];
      // The export's own conventions, checked against campaign 330328:
      // the site carries its id, and Stopped is Yes when the status is.
      if (r.site && line[plCol("Site_ID")]) line[plCol("Site")] = r.site + " (" + line[plCol("Site_ID")] + ")";
      if (!plx.source.Stopped) line[plCol("Stopped")] = /^stopped$/i.test(r.status) ? "Yes" : "No";
      stoppedOf[r.placementId] = line[plCol("Stopped")];
      pl.push(line.concat([r.verificationPartner, r.verificationStatus,
        cell((r.raw || {}).prismaPlacementId)], dsCols(dsOf[r.placementId])));
    });

    // Placement-creative level: every line the export has, the decision
    // set's own line included, then the creative's flight inside it.
    var pcRows = rows.filter(function (r) { return r.isCreative; });
    var pcx = exportColumns(pcRows, PC_COLUMNS);
    var col = function (name) { return PC_COLUMNS.indexOf(name); };
    var cr = [PC_COLUMNS.concat(["Decision_Set_ID", "Decision_Set_Name", "Rotation_Weight",
      "DS_Start_Date", "DS_End_Date", "DS_Weight", "DS_Default"])];
    pcRows.forEach(function (r, i) {
      var line = pcx.rows[i], parent = parentOf[r.placementId];
      if (parent) {
        if (!line[col("Placement")]) line[col("Placement")] = parent.placementName;
        if (!line[col("Site")]) line[col("Site")] = parent.site;
      }
      // As the export writes them: the placement and the file carry their
      // id, a creative of a stopped placement is stopped, and a line in a
      // decision set rotates by "Decision Tree" instead of a weight.
      if (line[col("Placement")]) line[col("Placement")] += " (" + r.placementId + ")";
      var ownId = r.isDecisionSet ? (r.dtreeId || r.dsetId || r.dsetLinkId) : r.creativeId;
      if (line[col("Filename")] && ownId) line[col("Filename")] += " (" + ownId + ")";
      if (!pcx.source.Stopped && stoppedOf[r.placementId]) line[col("Stopped")] = stoppedOf[r.placementId];
      if (!pcx.source.Rotation) {
        line[col("Rotation")] = (r.isDecisionSet || dsOf[r.placementId]) ? "Decision Tree"
          : (r.rotationWeight ? Number(r.rotationWeight).toFixed(2) : "");
      }
      if (r.isDecisionSet) {
        cr.push(line.concat(dsCols(r), [r.rotationWeight, "", "", "", ""]));
        return;
      }
      var holder = dsOf[r.placementId] || {};
      var keys = (r.dtreeId || r.dsetId) ? [r.dtreeId, r.dsetId, r.dsetLinkId]
        : [holder.dtreeId, holder.dsetId, holder.dsetLinkId];
      var nodes = [];
      keys.forEach(function (k) {
        (byDset[k] || []).forEach(function (n) {
          var sameId = r.creativeId && n.creativeId === r.creativeId;
          var sameName = r.fileName && n.creativeName.toLowerCase() === r.fileName.toLowerCase();
          if ((sameId || sameName) && nodes.indexOf(n) < 0) nodes.push(n);
        });
      });
      // The default node's timestamp is when it was made default, not a flight.
      var flights = nodes.filter(function (n) { return !n.isDefault; });
      var join = function (attr) {
        return flights.map(function (n) { return n[attr] || (attr === "end" ? "Ongoing" : ""); }).join(" | ");
      };
      cr.push(line.concat(dsCols(r.dtreeId || r.dsetId ? r : dsOf[r.placementId]), [r.rotationWeight,
        join("start"), join("end"), join("weight"),
        nodes.some(function (n) { return n.isDefault; }) ? "Yes" : (nodes.length ? "" : "Not found in its decision set")]));
    });

    // Which export columns Innovid's data filled, and which it doesn't carry.
    var usedBy = {};
    summary.push(["", ""]);
    [["Placement", plx.source], ["Placement-Creative", pcx.source]].forEach(function (s) {
      var missing = [], found = 0;
      Object.keys(s[1]).forEach(function (c) {
        var k = s[1][c];
        if (!k && DERIVED[c]) { found += 1; return; }
        if (!k) { missing.push(c); return; }
        found += 1;
        (usedBy[k] = usedBy[k] || []).push(s[0] + " · " + c);
      });
      summary.push(["Export columns · " + s[0], found + " of " + (found + missing.length) + " found in Innovid's data"]);
      if (missing.length) summary.push(["Not in Innovid's data · " + s[0], missing.join(", ")]);
      if (s[0] === "Placement") {
        summary.push(["Left empty on purpose", WITHHELD.join(", ") + ": costs and rates aren't needed for the QA"]);
      }
    });
    var fields = fieldsSheet(rows, usedBy);
    var ds = [["Decision set ID", "Decision set", "Serving method", "Creative ID", "Creative",
      "Start", "End", "Weight", "Default"]];
    ex.nodes.forEach(function (n) {
      ds.push([n.dsetId, n.dsetName, n.servingMethod, n.creativeId, n.creativeName,
        n.start, n.end || "Ongoing", n.weight, n.isDefault ? "Yes" : ""]);
    });

    var mf = [["Site ID", "Site", "Media Filters (Remove VPAID)"]].concat(ex.mediaFilters);
    return [["Summary", summary], ["Placement", pl], ["Placement-Creative", cr], ["Decision sets", ds],
      ["Media Filters", mf], ["Innovid fields", fields]];
  }

  /*
   * The only requests the extension may make: three reads and the
   * summary, which Innovid serves as a POST but only reads. Anything
   * else is refused before it leaves the browser.
   */
  var ALLOWED = [
    ["POST", /^https:\/\/api\.flashtalking\.net\/cm\/v1\/ui\/campaigns\/\d+\/summary\?fields=[\w,]+$/],
    ["GET", /^https:\/\/api\.flashtalking\.net\/dt\/v1\/ui\/dset\/\d+$/],
    ["GET", /^https:\/\/api\.flashtalking\.net\/cm\/v1\/campaigns\/\d+\/campaign-sites\?rpp=543$/],
    ["GET", /^https:\/\/api\.flashtalking\.net\/tag\/v1\/ui\/campaign-sites\/\d+$/]
  ];

  function isAllowedCall(method, url) {
    return ALLOWED.some(function (a) { return a[0] === method && a[1].test(url); });
  }

  function campaignIds(textIn) {
    var out = [];
    (String(textIn || "").match(/\d{3,}/g) || []).forEach(function (id) { if (out.indexOf(id) < 0) out.push(id); });
    return out;
  }

  function campaignFromUrl(url) {
    if (!url || url.indexOf(APP_ORIGIN) !== 0) return "";
    var m = url.slice(APP_ORIGIN.length).match(/^\/(?:campaign\/)?(\d{3,})(?:\/|$)/);
    return m ? m[1] : "";
  }

  return {
    APP_ORIGIN: APP_ORIGIN, extract: extract, sheets: sheets, parseSummary: parseSummary,
    parseDset: parseDset, dsetMismatch: dsetMismatch, mediaFilterOf: mediaFilterOf,
    PL_COLUMNS: PL_COLUMNS, PC_COLUMNS: PC_COLUMNS, WITHHELD: WITHHELD,
    campaignIds: campaignIds, tokens: tokens, campaignFromUrl: campaignFromUrl, isAllowedCall: isAllowedCall, SessionProblem: SessionProblem
  };
})();

if (typeof module !== "undefined") module.exports = Walk;

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
        dsetId: g("decisionSetId"), dsetName: g("decisionSetName"), dsetLinkId: g("placementDecisionSetId")
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
  async function extract(campaignId, call, say) {
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
    var groups = [["modern decision tree", {}], ["decisionSetId", {}], ["placementDecisionSetId", {}]];
    ex.rows.forEach(function (r) {
      if (r.dtreeId && !(r.dtreeId in groups[0][1])) groups[0][1][r.dtreeId] = r.dtreeName;
      if (r.dsetId) { if (!(r.dsetId in groups[1][1])) groups[1][1][r.dsetId] = r.dsetName; }
      else if (r.dsetLinkId && !r.dtreeId && !(r.dsetLinkId in groups[2][1])) groups[2][1][r.dsetLinkId] = r.dsetName;
    });
    var seen = {};
    groups.forEach(function (g) {
      Object.keys(g[1]).forEach(function (k) { if (seen[k]) delete g[1][k]; seen[k] = true; });
    });
    groups.forEach(function (g) { ex.dsetsAsked += Object.keys(g[1]).length; });

    var done = 0;
    for (var gi = 0; gi < groups.length; gi++) {
      var source = groups[gi][0], ids = groups[gi][1], keys = Object.keys(ids).sort();
      var failures = 0, shapes = {};
      for (var ki = 0; ki < keys.length; ki++) {
        var id = keys[ki];
        if (failures >= GIVE_UP_AFTER_FAILED_LOOKUPS && Object.keys(shapes).length === 1) {
          ex.errors.push("Stopped asking for " + (keys.length - failures) + " more " + source +
            " id(s): the first " + failures + " failed the same way.");
          break;
        }
        done += 1;
        say("Reading decision sets " + done + " / " + ex.dsetsAsked + "…");
        var problem = "", dset = null;
        try {
          dset = await call(DT_BASE + "/dset/" + id, "GET", null);
          problem = dsetMismatch(dset, id, ids[id]);
        } catch (e) {
          if (e instanceof SessionProblem) throw e;
          problem = String(e && e.message || e);
        }
        if (problem) {
          failures += 1;
          shapes[problem.split(id).join("{id}")] = true;
          ex.errors.push("Decision set " + id + " (" + source + "): " + problem);
          continue;
        }
        Array.prototype.push.apply(ex.nodes, parseDset(dset, id));
        ex.dsetsRead += 1;
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

  /* The sheets of the workbook, as arrays of rows (first row = headers). */
  function sheets(ex, extraTimings) {
    var placements = ex.rows.filter(function (r) { return !r.isCreative; });
    var creatives = ex.rows.filter(function (r) { return r.isCreative && !r.isDecisionSet; });
    var dsRows = ex.rows.filter(function (r) { return r.isDecisionSet; });
    var timings = (extraTimings || []).concat(ex.timings);
    var totalSecs = timings.reduce(function (a, t) { return a + t[1]; }, 0);
    var placementIds = {};
    ex.rows.forEach(function (r) { placementIds[r.placementId] = true; });

    var dsOf = {};
    placements.concat(dsRows).forEach(function (r) {
      if ((r.dtreeId || r.dsetId || r.dsetLinkId) && !dsOf[r.placementId]) dsOf[r.placementId] = r;
    });
    var parentOf = {};
    placements.forEach(function (r) { parentOf[r.placementId] = r; });
    var byDset = {};
    ex.nodes.forEach(function (n) { (byDset[n.dsetId] = byDset[n.dsetId] || []).push(n); });

    var summary = [["Item", "Value"],
      ["Campaign ID", ex.campaignId],
      ["Extracted", new Date().toISOString().slice(0, 16).replace("T", " ")],
      ["Read with", "Chrome extension"],
      ["Placements", Object.keys(placementIds).length],
      ["Placements with a decision set", Object.keys(dsOf).length],
      ["Creative rows", creatives.length],
      ["Decision sets read", ex.dsetsRead + " of " + ex.dsetsAsked],
      ["Creatives inside decision sets", ex.nodes.length],
      ["Sites (Media Filters)", ex.mediaFilters.length],
      ["", ""]];
    timings.forEach(function (t) { summary.push(["Time · " + t[0], t[1].toFixed(1) + " s"]); });
    summary.push(["Time · total", totalSecs.toFixed(1) + " s"], ["", ""]);
    if (ex.errors.length) ex.errors.forEach(function (e) { summary.push(["Could not read", e]); });
    else summary.push(["Could not read", "Nothing: everything was read."]);

    var pl = [["Placement ID", "Placement", "Site", "Size", "Status", "Start", "End",
      "Verification Partner", "Verification Status", "Decision set", "Decision set ID"]];
    placements.forEach(function (r) {
      var d = dsOf[r.placementId];
      pl.push([r.placementId, r.placementName, r.site, r.dimensions, r.status, r.start, r.end,
        r.verificationPartner, r.verificationStatus,
        d ? (d.dtreeName || d.dsetName || d.fileName) : "", d ? (d.dtreeId || d.dsetId || d.dsetLinkId) : ""]);
    });

    var cr = [["Placement ID", "Placement", "Creative ID", "File name", "Status", "Click URL",
      "Impression pixel 1", "Impression pixel 2", "Survey pixel", "DS start", "DS end", "DS weight", "Default"]];
    creatives.forEach(function (r) {
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
      var parent = parentOf[r.placementId];
      cr.push([r.placementId, r.placementName || (parent ? parent.placementName : ""), r.creativeId, r.fileName,
        r.status, r.clickUrl, r.impressionPixel1, r.impressionPixel2, r.surveyPixel,
        join("start"), join("end"), join("weight"),
        nodes.some(function (n) { return n.isDefault; }) ? "Yes" : (nodes.length ? "" : "Not found in its decision set")]);
    });

    var ds = [["Decision set ID", "Decision set", "Serving method", "Creative ID", "Creative",
      "Start", "End", "Weight", "Default"]];
    ex.nodes.forEach(function (n) {
      ds.push([n.dsetId, n.dsetName, n.servingMethod, n.creativeId, n.creativeName,
        n.start, n.end || "Ongoing", n.weight, n.isDefault ? "Yes" : ""]);
    });

    var mf = [["Site ID", "Site", "Media Filters (Remove VPAID)"]].concat(ex.mediaFilters);
    return [["Summary", summary], ["Placements", pl], ["Creatives", cr], ["Decision sets", ds], ["Media Filters", mf]];
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
    campaignIds: campaignIds, campaignFromUrl: campaignFromUrl, isAllowedCall: isAllowedCall, SessionProblem: SessionProblem
  };
})();

if (typeof module !== "undefined") module.exports = Walk;

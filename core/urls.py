"""
URL and attribution engine.

URL comparison by component, NEVER by raw string equality:
  scheme+host lowercase, normalized path, query params as a SET
  (order is irrelevant), fragment discarded.

Attribution triangle (Adobe):
    TS.CGENS  ==  Export.Third_Party_ID  ==  sdid in the URL
When all three match -> PASS with certainty.
When one differs -> the finding points out WHICH one is off.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, unquote, urlsplit

# Params that identify the CGEN inside the URL, in priority order
CGEN_URL_PARAMS = ["sdid", "s_did"]

# Derived attribution params that Adobe uses
ATTR_PARAMS = ["as_campaign", "as_source", "as_content", "as_camptype",
               "as_channel", "as_campclass", "mv", "mv2"]

# Params ignored when comparing (cache busters, timestamps)
IGNORE_PARAMS = {"ord", "random", "cachebuster", "cb", "ts", "_"}

# Unreplaced macros or tokens
_MACRO = re.compile(r"(%%|\[[A-Za-z_]+\]|%[A-Za-z_]+!|\{\{|\$\{|%e[a-z]+!)")

@dataclass
class ParsedURL:
    raw: str = ""
    ok: bool = False
    scheme: str = ""
    host: str = ""
    path: str = ""
    params: dict[str, str] = field(default_factory=dict)
    unresolved_macros: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def base(self) -> str:
        return f"{self.scheme}://{self.host}{self.path}"

    @property
    def cgen(self) -> str:
        for p in CGEN_URL_PARAMS:
            if self.params.get(p):
                return self.params[p]
        return ""

def parse_url(value: object) -> ParsedURL:
    raw = str(value or "").strip()
    out = ParsedURL(raw=raw)
    if not raw:
        out.error = "empty"
        return out

    out.unresolved_macros = sorted(set(_MACRO.findall(raw)))

    try:
        s = urlsplit(raw)
    except Exception as exc:
        out.error = f"not parseable: {exc}"
        return out

    if not s.scheme or not s.netloc:
        out.error = "no scheme or host"
        return out

    out.scheme = s.scheme.lower()
    out.host = s.netloc.lower().removeprefix("www.")
    path = unquote(s.path or "/")
    out.path = path.rstrip("/") or "/"

    for k, v in parse_qsl(s.query, keep_blank_values=True):
        kl = k.strip().lower()
        if kl in IGNORE_PARAMS:
            continue
        out.params[kl] = v.strip()

    out.ok = True
    return out

# ------------------------------------------------------------------ comparison

URL_MATCH = "MATCH"
URL_PARAMS_DIFF = "PARAMS_DIFF"
URL_BASE_DIFF = "BASE_DIFF"
URL_MISSING_ACTUAL = "MISSING_ACTUAL"
URL_MISSING_EXPECTED = "MISSING_EXPECTED"
URL_BOTH_MISSING = "BOTH_MISSING"
URL_MALFORMED = "MALFORMED"

@dataclass
class URLComparison:
    result: str = URL_BOTH_MISSING
    expected: ParsedURL = field(default_factory=ParsedURL)
    actual: ParsedURL = field(default_factory=ParsedURL)
    params_only_expected: dict[str, str] = field(default_factory=dict)
    params_only_actual: dict[str, str] = field(default_factory=dict)
    params_diff_value: dict[str, tuple[str, str]] = field(default_factory=dict)
    note: str = ""

    @property
    def is_ok(self) -> bool:
        return self.result == URL_MATCH

def compare_urls(expected: object, actual: object) -> URLComparison:
    e, a = parse_url(expected), parse_url(actual)
    c = URLComparison(expected=e, actual=a)

    if not e.raw and not a.raw:
        c.result = URL_BOTH_MISSING
        c.note = "no URL declared"
        return c
    if not e.raw:
        c.result = URL_MISSING_EXPECTED
        c.note = "the TS doesn't declare a URL for this creative"
        return c
    if not a.raw:
        c.result = URL_MISSING_ACTUAL
        c.note = "the creative has no ClickTag in Innovid"
        return c
    if not e.ok or not a.ok:
        c.result = URL_MALFORMED
        c.note = f"expected: {e.error or 'ok'} · actual: {a.error or 'ok'}"
        return c

    if e.base != a.base:
        c.result = URL_BASE_DIFF
        c.note = f"different destination: '{e.base}' vs '{a.base}'"
        return c

    ek, ak = set(e.params), set(a.params)
    for k in sorted(ek - ak):
        c.params_only_expected[k] = e.params[k]
    for k in sorted(ak - ek):
        c.params_only_actual[k] = a.params[k]
    for k in sorted(ek & ak):
        if e.params[k] != a.params[k]:
            c.params_diff_value[k] = (e.params[k], a.params[k])

    if c.params_only_expected or c.params_only_actual or c.params_diff_value:
        c.result = URL_PARAMS_DIFF
        bits = []
        if c.params_diff_value:
            bits.append(", ".join(f"{k}: {v[0]} -> {v[1]}"
                                  for k, v in list(c.params_diff_value.items())[:3]))
        if c.params_only_expected:
            bits.append(f"missing: {', '.join(list(c.params_only_expected)[:3])}")
        if c.params_only_actual:
            bits.append(f"extra: {', '.join(list(c.params_only_actual)[:3])}")
        c.note = " · ".join(bits)
        return c

    c.result = URL_MATCH
    c.note = "destination and params match"
    return c

# ------------------------------------------------------------------ triangle

TRI_OK = "OK"
TRI_URL_MISMATCH = "URL_MISMATCH"
TRI_EXPORT_MISMATCH = "EXPORT_MISMATCH"
TRI_TS_MISMATCH = "TS_MISMATCH"
TRI_ALL_DIFFERENT = "ALL_DIFFERENT"
TRI_INCOMPLETE = "INCOMPLETE"

@dataclass
class AttributionTriangle:
    """
    Three vertices that must match:
      ts       = CGENS declared in the Traffic Sheet
      export   = Third_Party_ID of the row in Innovid
      url      = sdid param extracted from the ClickTag
    """
    ts: str = ""
    export: str = ""
    url: str = ""
    result: str = TRI_INCOMPLETE
    deviant: str = ""
    consensus: str = ""
    note: str = ""
    missing: list[str] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return self.result == TRI_OK

def check_triangle(ts_cgen: object, export_tpid: object,
                   url_value: object) -> AttributionTriangle:
    t = AttributionTriangle(
        ts=str(ts_cgen or "").strip(),
        export=str(export_tpid or "").strip(),
        url=parse_url(url_value).cgen,
    )

    present = {k: v for k, v in
               (("TS", t.ts), ("Innovid", t.export), ("URL", t.url)) if v}
    t.missing = [k for k in ("TS", "Innovid", "URL")
                 if k not in present]

    if len(present) < 2:
        t.result = TRI_INCOMPLETE
        t.note = ("not verifiable: only "
                  f"{', '.join(present) or 'no vertex'} present")
        return t

    vals = list(present.values())
    if len(set(vals)) == 1:
        t.consensus = vals[0]
        if len(present) == 3:
            t.result = TRI_OK
            t.note = f"all three vertices match on {t.consensus}"
        else:
            t.result = TRI_INCOMPLETE
            t.note = (f"{' and '.join(present)} match on {t.consensus}, "
                      f"missing {', '.join(t.missing)}")
        return t

    if len(present) == 2:
        a, b = list(present.items())
        t.result = TRI_ALL_DIFFERENT
        t.note = f"{a[0]}={a[1]} vs {b[0]}={b[1]} (missing {', '.join(t.missing)})"
        return t

    # three vertices disagree: find the majority
    counts: dict[str, list[str]] = {}
    for src, val in present.items():
        counts.setdefault(val, []).append(src)

    majority = max(counts.items(), key=lambda kv: len(kv[1]))
    if len(majority[1]) == 2:
        t.consensus = majority[0]
        odd_src = next(s for s in present if s not in majority[1])
        t.deviant = odd_src
        t.result = {"URL": TRI_URL_MISMATCH,
                    "Innovid": TRI_EXPORT_MISMATCH,
                    "TS": TRI_TS_MISMATCH}[odd_src]
        t.note = (f"{' and '.join(majority[1])} match on {t.consensus}, "
                  f"but {odd_src}={present[odd_src]}")
        return t

    t.result = TRI_ALL_DIFFERENT
    t.note = f"TS={t.ts} · Innovid={t.export} · URL={t.url}"
    return t

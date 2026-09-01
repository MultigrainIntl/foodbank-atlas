#!/usr/bin/env python3
"""
Food Bank Atlas — one config-driven pipeline. For a food bank (name + county FIPS),
pull ACS tract data + tract geometry from Census Reporter (keyless), score food need,
attach a place name to every tract, flag group-quarters, and render one consistent
shaded-polygon map. Same code for every food bank == guaranteed consistency.

Runs on GitHub Actions (open internet reaches Census Reporter + the Census geocoder).
Usage:  python build_atlas.py config/<foodbank>.json  ->  site/<slug>.html
"""
import json, sys, time, urllib.request, urllib.parse
from pathlib import Path

CR = "https://api.censusreporter.org/1.0"
GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
TABLES = "B01003,B17001,C17002,B22003,B19013,B26001,B02001"
HEAT = ['#3F8F74', '#8DA65E', '#E4B24A', '#DE7C3B', '#C0442E']

STATE_FIPS = {
    "01": ("Alabama", "AL"), "02": ("Alaska", "AK"), "04": ("Arizona", "AZ"),
    "05": ("Arkansas", "AR"), "06": ("California", "CA"), "08": ("Colorado", "CO"),
    "09": ("Connecticut", "CT"), "10": ("Delaware", "DE"), "11": ("District of Columbia", "DC"),
    "12": ("Florida", "FL"), "13": ("Georgia", "GA"), "15": ("Hawaii", "HI"),
    "16": ("Idaho", "ID"), "17": ("Illinois", "IL"), "18": ("Indiana", "IN"),
    "19": ("Iowa", "IA"), "20": ("Kansas", "KS"), "21": ("Kentucky", "KY"),
    "22": ("Louisiana", "LA"), "23": ("Maine", "ME"), "24": ("Maryland", "MD"),
    "25": ("Massachusetts", "MA"), "26": ("Michigan", "MI"), "27": ("Minnesota", "MN"),
    "28": ("Mississippi", "MS"), "29": ("Missouri", "MO"), "30": ("Montana", "MT"),
    "31": ("Nebraska", "NE"), "32": ("Nevada", "NV"), "33": ("New Hampshire", "NH"),
    "34": ("New Jersey", "NJ"), "35": ("New Mexico", "NM"), "36": ("New York", "NY"),
    "37": ("North Carolina", "NC"), "38": ("North Dakota", "ND"), "39": ("Ohio", "OH"),
    "40": ("Oklahoma", "OK"), "41": ("Oregon", "OR"), "42": ("Pennsylvania", "PA"),
    "44": ("Rhode Island", "RI"), "45": ("South Carolina", "SC"), "46": ("South Dakota", "SD"),
    "47": ("Tennessee", "TN"), "48": ("Texas", "TX"), "49": ("Utah", "UT"),
    "50": ("Vermont", "VT"), "51": ("Virginia", "VA"), "53": ("Washington", "WA"),
    "54": ("West Virginia", "WV"), "55": ("Wisconsin", "WI"), "56": ("Wyoming", "WY"),
    "72": ("Puerto Rico", "PR"),
}


def load_foodbanks():
    """Cross-page switcher / search: every food bank with a built summary (US + Canada)."""
    out = []
    for p in sorted((Path(__file__).parent / "docs" / "data").glob("*.json")):
        try:
            s = json.loads(p.read_text())
        except Exception:
            continue
        if s.get("slug"):
            out.append({"name": s["name"], "slug": s["slug"],
                        "region_label": s.get("region_label", s["name"]),
                        "state": s.get("state", "")})
    return sorted(out, key=lambda x: x["name"])


def summarize(cfg, fc):
    """Compact per-food-bank summary that the home page reads (stats + map pin)."""
    feats = fc["features"]
    cents = [centroid(f["geometry"]) for f in feats]
    lat = round(sum(c[0] for c in cents) / len(cents), 4) if cents else None
    lon = round(sum(c[1] for c in cents) / len(cents), 4) if cents else None
    scored = [f for f in feats if f["properties"].get("score") is not None]
    top = max(scored, key=lambda f: f["properties"]["score"]) if scored else None
    fips2 = (cfg["county_fips"][0] or "")[:2]
    state, abbr = STATE_FIPS.get(fips2, ("", ""))
    return {
        "name": cfg["name"], "slug": cfg["slug"],
        "region_label": cfg.get("region_label", cfg["name"]),
        "state": state, "state_abbr": abbr,
        "ntracts": len(feats),
        "ngq": sum(1 for f in feats if f["properties"].get("gq")),
        "center": [lat, lon],
        "top_place": (top["properties"].get("place") or "") if top else "",
        "top_score": top["properties"]["score"] if top else None,
    }


def _get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "food-bank-atlas/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def num(v):
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def fetch_county(fips):
    """Return (data dict keyed by geoid, geojson features) for one county's tracts."""
    data = _get(f"{CR}/data/show/latest?table_ids={TABLES}&geo_ids=140|05000US{fips}")["data"]
    geo = _get(f"{CR}/geo/show/tiger2023?geo_ids=140|05000US{fips}")["features"]
    return data, geo


def derive(e):
    est = lambda t, c: num(e[t]["estimate"][c])
    pop = est("B01003", "B01003001")
    povU, povB = est("B17001", "B17001001"), est("B17001", "B17001002")
    c1 = est("C17002", "C17002001")
    u200 = sum(est("C17002", k) or 0 for k in
               ["C17002002", "C17002003", "C17002004", "C17002005", "C17002006", "C17002007"])
    snU, snB = est("B22003", "B22003001"), est("B22003", "B22003002")  # total hh, SNAP hh
    inc = est("B19013", "B19013001")
    gqpop = est("B26001", "B26001001")
    # SNAP gap: people income-eligible (~under 130% of poverty; C17002 bands <1.25) who are
    # not reached by SNAP. "Served" estimated as SNAP households x avg household size.
    u130 = sum(est("C17002", k) or 0 for k in ["C17002002", "C17002003", "C17002004"])
    hhsize = (pop / snU) if (pop and snU) else None
    served = (snB * hhsize) if (snB is not None and hhsize) else None
    gap = max(0.0, u130 - served) if (served is not None and u130) else None
    aian = est("B02001", "B02001004")  # American Indian / Alaska Native alone
    return {
        "pop": int(pop) if pop is not None else None,
        "pov": round(100 * povB / povU, 1) if povU else None,
        "fpl200": round(100 * u200 / c1, 1) if c1 else None,
        "snap": round(100 * snB / snU, 1) if snU else None,
        "inc": int(inc) if inc is not None else None,
        "gq": bool((pop is not None and pop < 1200) or (pop and (gqpop or 0) / pop >= 0.5)),
        "elig130": int(u130) if u130 else None,
        "sgap": int(round(gap)) if gap is not None else None,
        "gapr": round(100 * gap / pop, 1) if (gap is not None and pop) else None,
        "aian": int(aian) if aian is not None else None,
        "aianr": round(100 * aian / pop, 1) if (aian is not None and pop) else None,
    }


def score(rows):
    """rows: list of derived dicts -> add 'score' (0-100), normalized on residential tracts."""
    IND = [("pov", False), ("fpl200", False), ("snap", False), ("inc", True)]
    base = [r for r in rows if not r["gq"] and r["pop"]]
    mm = {}
    for k, _ in IND:
        v = [r[k] for r in base if r[k] is not None]
        mm[k] = (min(v), max(v)) if v else (0, 1)
    for r in rows:
        parts = []
        for k, inv in IND:
            x = r[k]
            if x is None:
                continue
            lo, hi = mm[k]
            n = (x - lo) / ((hi - lo) or 1)
            if inv:
                n = 1 - n
            parts.append(max(0.0, min(1.0, n)))
        r["score"] = round(100 * sum(parts) / len(parts), 1) if parts else None


def centroid(geom):
    if geom["type"] == "Polygon":
        ring = geom["coordinates"][0]
    else:  # MultiPolygon -> largest ring
        ring = max((p[0] for p in geom["coordinates"]), key=len)
    sx = sum(c[0] for c in ring); sy = sum(c[1] for c in ring)
    return sy / len(ring), sx / len(ring)  # lat, lon


def place_of(lat, lon):
    """Census geocoder: incorporated place, else county subdivision. Keyless."""
    q = urllib.parse.urlencode({
        "x": lon, "y": lat, "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "Incorporated Places,County Subdivisions", "format": "json"})
    try:
        g = _get(f"{GEOCODER}?{q}")["result"]["geographies"]
        for key in ("Incorporated Places", "County Subdivisions"):
            arr = g.get(key) or []
            if arr:
                import re as _re
                return _re.sub(r"\s+(city|town|CDP|CCD|borough|village|\(balance\))$", "", arr[0]["NAME"]).strip()
    except Exception:
        pass
    return None


def tract_no(geoid):
    return f"{int(geoid[-6:]) / 100:.2f}".rstrip("0").rstrip(".")


def build(cfg):
    feats = []
    rows_by_gid = {}
    for fips in cfg["county_fips"]:
        data, geo = fetch_county(fips)
        for gid, e in data.items():
            rows_by_gid[gid] = derive(e)
        for f in geo:
            gid = "14000US" + f["properties"]["geoid"][-11:] if not f["properties"]["geoid"].startswith("14000US") else f["properties"]["geoid"]
            gid = f["properties"]["geoid"]
            if gid in rows_by_gid:
                feats.append((gid, f))
    rows = list(rows_by_gid.values())
    score(rows)
    # attach place names by centroid (geocoder)
    out_feats = []
    for gid, f in feats:
        r = rows_by_gid[gid]
        if r.get("score") is None or not r.get("pop"):
            continue
        lat, lon = centroid(f["geometry"])
        r["place"] = place_of(lat, lon) or ""
        r["tract"] = tract_no(gid)
        f["properties"] = {"GEOID": gid, **r}
        out_feats.append(f)
    return {"type": "FeatureCollection", "features": out_feats}


def html(cfg, fc):
    scores = [f["properties"]["score"] for f in fc["features"] if f["properties"]["score"] is not None]
    ngq = sum(1 for f in fc["features"] if f["properties"]["gq"])
    geo = json.dumps(fc, separators=(",", ":"))
    funding, grants, state_foundations, state_name = _funding_data(cfg)
    T = Path(__file__).parent / "template.html"
    tpl = T.read_text()
    foodbanks = load_foodbanks()
    return (tpl.replace("__TITLE__", cfg["name"])
               .replace("__REGION__", cfg.get("region_label", cfg["name"]))
               .replace("__NTRACTS__", str(len(fc["features"])))
               .replace("__NGQ__", str(ngq))
               .replace("__SLUG__", json.dumps(cfg["slug"]))
               .replace("__BRIEF__", "/" + cfg["slug"] + "-brief")
               .replace("__STATE__", json.dumps(state_name))
               .replace("__FOODBANKS__", json.dumps(foodbanks, separators=(",", ":")))
               .replace("__GRANTS__", json.dumps(grants, separators=(",", ":")))
               .replace("__FOUNDATIONS__", json.dumps(state_foundations, separators=(",", ":")))
               .replace("__FUNDING__", json.dumps(funding, separators=(",", ":")))
               .replace("__DATA__", geo))


def _funding_data(cfg):
    """(funding.json, grants.json, this state's foundations, state name) — shared by map + brief."""
    cdir = Path(__file__).parent / "config"
    def _load(name):
        p = cdir / name
        try:
            return json.loads(p.read_text()) if p.exists() else {}
        except Exception:
            return {}
    fips2 = (cfg["county_fips"][0] or "")[:2]
    name, abbr = STATE_FIPS.get(fips2, ("", ""))
    fbs = _load("foundations_by_state.json")
    return _load("funding.json"), _load("grants.json"), (fbs.get("states") or {}).get(abbr, []), name


def brief_html(cfg, fc):
    """A print-ready need + funding brief a food bank can paste into a grant app or board deck."""
    feats = fc["features"]
    res = [f["properties"] for f in feats if not f["properties"].get("gq") and f["properties"].get("pop")]
    tot = sum(p["pop"] for p in res) or 1
    def wavg(k):
        vals = [(p[k], p["pop"]) for p in res if p.get(k) is not None]
        return round(sum(v * w for v, w in vals) / (sum(w for _, w in vals) or 1), 1) if vals else None
    high = [p for p in (f["properties"] for f in feats) if (p.get("score") or 0) >= 60]
    high_pop = sum(p.get("pop") or 0 for p in high)
    snap_gap = sum((f["properties"].get("sgap") or 0) for f in feats)
    top = sorted((f["properties"] for f in feats), key=lambda p: -(p.get("score") or 0))[:12]
    funding, grants, foundations, state_name = _funding_data(cfg)
    ops = (grants or {}).get("opportunities", [])[:6]

    def esc(s):
        return (str(s if s is not None else "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    rows = "".join(
        f'<tr><td>{esc(p.get("place"))}</td><td class="mono">{esc(p.get("tract"))}</td>'
        f'<td class="num"><b>{p.get("score")}</b></td><td class="num">{p.get("pov")}%</td>'
        f'<td class="num">{p.get("fpl200")}%</td><td class="num">{p.get("snap")}%</td>'
        f'<td class="num">{(p.get("pop") or 0):,}</td></tr>' for p in top)
    grant_rows = "".join(
        f'<li><a href="{o.get("url")}">{esc(o.get("title"))}</a> — {esc(o.get("agency"))} · closes {esc(o.get("close"))}</li>'
        for o in ops) or '<li>No open federal opportunities matched right now — check Grants.gov and state programs.</li>'
    fA = lambda m: "" if m is None else ("$%.1fB" % (m / 1000) if m >= 1000 else "$%dM" % m)
    fdn_rows = "".join(
        f'<li><a href="{f.get("gm_url")}">{esc(f.get("name"))}</a> <span class="mono">{fA(f.get("assets_musd"))}</span>'
        f'{" · " + esc(f.get("city")) if f.get("city") else ""}</li>' for f in foundations[:8]) \
        or '<li>See grantmakers.io for local private foundations.</li>'
    region = cfg.get("region_label", cfg["name"])
    tpl = (Path(__file__).parent / "brief.html").read_text()
    return (tpl.replace("__NAME__", esc(cfg["name"]))
               .replace("__REGION__", esc(region))
               .replace("__MAPHREF__", "/" + cfg["slug"])
               .replace("__DATE__", time.strftime("%B %-d, %Y"))
               .replace("__NTRACTS__", f"{len(feats):,}")
               .replace("__NHIGH__", f"{len(high):,}")
               .replace("__HIGHPOP__", f"{high_pop:,}")
               .replace("__SNAPGAP__", f"{snap_gap:,}")
               .replace("__POV__", str(wavg("pov")))
               .replace("__FPL__", str(wavg("fpl200")))
               .replace("__SNAP__", str(wavg("snap")))
               .replace("__TOTPOP__", f"{tot:,}")
               .replace("__ROWS__", rows)
               .replace("__GRANTS__", grant_rows)
               .replace("__FOUNDATIONS__", fdn_rows)
               .replace("__STATE__", esc(state_name)))


def main():
    cfg = json.loads(Path(sys.argv[1]).read_text())
    if "county_fips" not in cfg or "slug" not in cfg:
        print(f"skip {sys.argv[1]}: not a food-bank config (no county_fips/slug)")
        return
    fc = build(cfg)
    out = Path("docs") / (cfg["slug"] + ".html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html(cfg, fc))
    data_dir = Path("docs") / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / (cfg["slug"] + ".json")).write_text(
        json.dumps(summarize(cfg, fc), separators=(",", ":")))
    (Path("docs") / (cfg["slug"] + "-brief.html")).write_text(brief_html(cfg, fc))
    print(f"wrote {out} : {len(fc['features'])} tracts (+ brief)")


if __name__ == "__main__":
    main()

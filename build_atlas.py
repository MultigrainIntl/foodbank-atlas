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
TABLES = "B01003,B17001,C17002,B22003,B19013,B26001"
HEAT = ['#3F8F74', '#8DA65E', '#E4B24A', '#DE7C3B', '#C0442E']


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
    snU, snB = est("B22003", "B22003001"), est("B22003", "B22003002")
    inc = est("B19013", "B19013001")
    gqpop = est("B26001", "B26001001")
    return {
        "pop": int(pop) if pop is not None else None,
        "pov": round(100 * povB / povU, 1) if povU else None,
        "fpl200": round(100 * u200 / c1, 1) if c1 else None,
        "snap": round(100 * snB / snU, 1) if snU else None,
        "inc": int(inc) if inc is not None else None,
        "gq": bool((pop is not None and pop < 1200) or (pop and (gqpop or 0) / pop >= 0.5)),
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
    fpath = Path(__file__).parent / "config" / "funding.json"
    funding = json.loads(fpath.read_text()) if fpath.exists() else {}
    T = Path(__file__).parent / "template.html"
    tpl = T.read_text()
    return (tpl.replace("__TITLE__", cfg["name"])
               .replace("__REGION__", cfg.get("region_label", cfg["name"]))
               .replace("__NTRACTS__", str(len(fc["features"])))
               .replace("__NGQ__", str(ngq))
               .replace("__FUNDING__", json.dumps(funding, separators=(",", ":")))
               .replace("__DATA__", geo))


def main():
    cfg = json.loads(Path(sys.argv[1]).read_text())
    fc = build(cfg)
    out = Path("docs") / (cfg["slug"] + ".html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html(cfg, fc))
    print(f"wrote {out} : {len(fc['features'])} tracts")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Canadian Food-Need Atlas — dissemination-area maps, keyless.

The Canadian twin of build_atlas.py. Same idea (split a food bank's service area
into small neighbourhoods, score food need, match funding, render one consistent
shaded-polygon map), but on 2021 Census data via Statistics Canada's *keyless*
Census Profile SDMX API and StatCan's open boundary files.

Why a separate script: Canada has no SNAP/TEFAP and no U.S. Census tracts. Need is
measured with the Low-income measure after tax (LIM-AT), government-transfer
reliance and income; neighbourhoods are dissemination areas (~400–700 people,
finer than U.S. tracts); Indigenous identity is a first-class layer.

Runs on GitHub Actions (open internet reaches StatCan). It cannot run in the
Cowork container, whose egress does not include Statistics Canada.

Usage:  python build_ca.py config/ca/<slug>.json  ->  docs/<slug>.html
"""
import json, sys, time, zipfile, tempfile, urllib.request, urllib.parse
from pathlib import Path

# ---- Statistics Canada endpoints (all keyless) -----------------------------
SDMX = "https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/data/STC_CP,DF_DA/"
BND  = "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/"
DA_ZIP  = "lda_000b21a_e.zip"   # dissemination areas — cartographic (land-clipped)
CMA_ZIP = "lcma000a21a_e.zip"   # CMAs/CAs — digital (small); used to select the metro
CSD_ZIP = "lcsd000a21a_e.zip"   # census subdivisions — digital; gives municipality names

# 2021 Census Profile characteristic codes (verified live against CL_CHARACTERISTIC)
CH = {"pop": 1, "pph": 89, "inc": 229, "lim": 331, "govt": 144, "indb": 1388, "indn": 1389}
CHARS = "+".join(str(CH[k]) for k in ["pop", "pph", "inc", "lim", "govt", "indb", "indn"])
DA_PREFIX = "2021S0512"         # DA geography codes are this prefix + the 8-digit DAUID

HEAT = ['#3F8F74', '#8DA65E', '#E4B24A', '#DE7C3B', '#C0442E']


# ---------------------------------------------------------------- helpers ----
def log(*a):
    print(*a, flush=True)


def _download(name, dest_dir):
    """Download a StatCan boundary zip and extract it; return the .shp path.
    Each zip extracts into its OWN subdirectory so the .shp lookup can't pick up
    a different layer's shapefile."""
    url = BND + name
    sub = Path(dest_dir) / name.replace(".zip", "")
    sub.mkdir(parents=True, exist_ok=True)
    zp = sub / name
    log(f"  downloading {name} …")
    req = urllib.request.Request(url, headers={"User-Agent": "food-bank-atlas/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(zp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    with zipfile.ZipFile(zp) as z:
        z.extractall(sub)
    shp = next(Path(sub).rglob("*.shp"))
    log(f"  extracted {shp.name} ({zp.stat().st_size/1e6:.0f} MB zip)")
    return str(shp)


def num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _get_bytes(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "food-bank-atlas/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


# ---------------------------------------------------------------- geography --
def load_saskatoon_das(cfg, workdir):
    """Return a GeoDataFrame of the dissemination areas in the target CMA,
    reprojected to WGS84, simplified for the web, with a municipality name."""
    import geopandas as gpd

    cma_uid = str(cfg["cma_uid"])
    pr = str(cfg["pruid"])

    da_shp  = _download(DA_ZIP,  workdir)
    cma_shp = _download(CMA_ZIP, workdir)
    csd_shp = _download(CSD_ZIP, workdir)

    # Metro polygon (one CMA) --------------------------------------------------
    cma = gpd.read_file(cma_shp, where=f"CMAUID = '{cma_uid}'", engine="pyogrio")
    if cma.empty:
        raise SystemExit(f"CMA {cma_uid} not found in {CMA_ZIP}")
    cma = cma.to_crs(4326)
    metro = cma.geometry.union_all() if hasattr(cma.geometry, "union_all") else cma.geometry.unary_union

    # Dissemination areas in the province, then clipped to the metro ----------
    da = gpd.read_file(da_shp, where=f"PRUID = '{pr}'", engine="pyogrio").to_crs(4326)
    da["DAUID"] = da["DAUID"].astype(str)
    reps = da.geometry.representative_point()
    da = da[reps.within(metro)].copy()
    log(f"  {len(da)} dissemination areas fall inside CMA {cma_uid}")

    # Attach municipality (census subdivision) name via a point-in-polygon join
    csd = gpd.read_file(csd_shp, where=f"PRUID = '{pr}'", engine="pyogrio").to_crs(4326)
    name_col = "CSDNAME" if "CSDNAME" in csd.columns else \
               next((c for c in csd.columns if c.upper().startswith("CSDNAME")), None)
    pts = da.copy()
    pts["geometry"] = da.geometry.representative_point()
    joined = gpd.sjoin(pts, csd[[name_col, "geometry"]], predicate="within", how="left")
    joined = joined[~joined.index.duplicated(keep="first")]
    da["csd"] = joined[name_col].fillna("").astype(str).values

    # Simplify polygons so the baked-in map stays small
    da["geometry"] = da.geometry.simplify(0.00025, preserve_topology=True)
    return da


# ---------------------------------------------------------------- census -----
def fetch_profile(dauids):
    """Query the StatCan SDMX API in batches; return {dauid: {char: value}}."""
    out = {}
    geos = [DA_PREFIX + d for d in dauids]
    BATCH = 40
    for i in range(0, len(geos), BATCH):
        chunk = geos[i:i + BATCH]
        key = "A5." + "+".join(chunk) + ".1." + CHARS + ".1"
        url = SDMX + urllib.parse.quote(key, safe="+.") + "?format=csv"
        raw = _get_bytes(url).decode("utf-8", "replace")
        lines = raw.splitlines()
        if not lines:
            continue
        hdr = lines[0].split(",")
        ri, ci, vi = hdr.index("REF_AREA"), hdr.index("CHARACTERISTIC"), hdr.index("OBS_VALUE")
        for ln in lines[1:]:
            p = ln.split(",")
            if len(p) <= vi:
                continue
            dau = p[ri][len(DA_PREFIX):]
            out.setdefault(dau, {})[p[ci]] = p[vi]
        log(f"  fetched census for {min(i+BATCH,len(geos))}/{len(geos)} DAs")
        time.sleep(0.3)
    return out


def derive(rec):
    """One DA's raw characteristic dict -> tidy need metrics."""
    g = lambda code: num(rec.get(str(code)))
    pop = g(CH["pop"])
    lim = g(CH["lim"])            # LIM-AT prevalence (%)
    govt = g(CH["govt"])          # government transfers, share of income (%)
    inc = g(CH["inc"])            # median total household income ($)
    indb = g(CH["indb"])          # Indigenous-identity base (pop in private households)
    indn = g(CH["indn"])          # Indigenous-identity count
    return {
        "pop": int(pop) if pop is not None else None,
        "lim": lim,
        "govt": govt,
        "inc": int(inc) if inc is not None else None,
        "indn": int(indn) if indn is not None else None,
        "indig": round(100 * indn / indb, 1) if (indn is not None and indb) else None,
        # a DA with income & low-income suppressed can't be scored on need
        "sup": (lim is None and inc is None),
    }


def score(rows):
    """Add a 0–100 'score': min-max composite of LIM-AT %, government-transfer %,
    and inverse median income, normalized across scorable DAs (mirrors the U.S. tool)."""
    IND = [("lim", False), ("govt", False), ("inc", True)]
    base = [r for r in rows if r["pop"] and not r["sup"]]
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


# ---------------------------------------------------------------- assemble ---
def build(cfg):
    workdir = tempfile.mkdtemp(prefix="ca_atlas_")
    da = load_saskatoon_das(cfg, workdir)
    dauids = list(da["DAUID"])
    prof = fetch_profile(dauids)

    feats = []
    rows = []
    for _, row in da.iterrows():
        dau = row["DAUID"]
        r = derive(prof.get(dau, {}))
        r["dauid"] = dau
        r["csd"] = row.get("csd", "") or ""
        rows.append(r)
    score(rows)

    for (_, row), r in zip(da.iterrows(), rows):
        geom = row["geometry"].__geo_interface__
        feats.append({"type": "Feature",
                      "properties": {k: r[k] for k in
                                     ["dauid", "csd", "score", "pop", "lim", "govt",
                                      "inc", "indn", "indig", "sup"]},
                      "geometry": geom})
    return {"type": "FeatureCollection", "features": feats}


def _poly_centroid_latlon(fc):
    xs, ys, n = 0.0, 0.0, 0
    for f in fc["features"]:
        g = f["geometry"]
        ring = g["coordinates"][0] if g["type"] == "Polygon" else \
               max((p[0] for p in g["coordinates"]), key=len)
        cx = sum(c[0] for c in ring) / len(ring)
        cy = sum(c[1] for c in ring) / len(ring)
        xs += cx; ys += cy; n += 1
    return (round(ys / n, 4), round(xs / n, 4)) if n else (None, None)


def summarize(cfg, fc):
    feats = fc["features"]
    lat, lon = _poly_centroid_latlon(fc)
    scored = [f for f in feats if f["properties"].get("score") is not None]
    top = max(scored, key=lambda f: f["properties"]["score"]) if scored else None
    return {
        "name": cfg["name"], "slug": cfg["slug"],
        "region_label": cfg.get("region_label", cfg["name"]),
        "state": cfg.get("country", "Canada"),          # groups under a "Canada" heading
        "state_abbr": "CA",
        "ntracts": len(feats),
        "ngq": sum(1 for f in feats if f["properties"].get("sup")),
        "center": [lat, lon],
        "top_place": (top["properties"].get("csd") or "") if top else "",
        "top_score": top["properties"]["score"] if top else None,
    }


PRUID_ABBR = {
    "10": "NL", "11": "PE", "12": "NS", "13": "NB", "24": "QC", "35": "ON",
    "46": "MB", "47": "SK", "48": "AB", "59": "BC", "60": "YT", "61": "NT", "62": "NU",
}


def _funding(cfg=None):
    """Funding panel for one food bank page. federal_channels/foundation_finder/order
    are shared across all Canada pages; provincial and local_foundations are keyed by
    the food bank's province (pruid) and slug respectively, so e.g. Saskatoon's
    curated local foundations don't leak onto Regina's page (same province, different
    city), and Saskatchewan's provincial info doesn't leak onto Toronto/Calgary/etc."""
    p = Path(__file__).parent / "config" / "ca_funding.json"
    try:
        raw = json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}
    out = {
        "note": raw.get("note", ""),
        "federal_channels": raw.get("federal_channels", []),
        "foundation_finder": raw.get("foundation_finder"),
        "order": raw.get("order"),
        "provincial": [],
        "local_foundations": [],
    }
    if cfg:
        pr = PRUID_ABBR.get(str(cfg.get("pruid", "")), "")
        out["provincial"] = raw.get("provincial_by_province", {}).get(pr, [])
        out["local_foundations"] = raw.get("local_foundations_by_slug", {}).get(cfg.get("slug", ""), [])
    return out


def load_foodbanks():
    """Cross-page switcher: every food bank that has a built summary (US + Canada)."""
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


def html(cfg, fc):
    geo = json.dumps(fc, separators=(",", ":"))
    tpl = (Path(__file__).parent / "template_ca.html").read_text()
    scored = [f["properties"]["score"] for f in fc["features"] if f["properties"]["score"] is not None]
    return (tpl.replace("__TITLE__", cfg["name"])
               .replace("__REGION__", cfg.get("region_label", cfg["name"]))
               .replace("__NTRACTS__", str(len(fc["features"])))
               .replace("__SLUG__", json.dumps(cfg["slug"]))
               .replace("__BRIEF__", "/" + cfg["slug"] + "-brief")
               .replace("__FOODBANKS__", json.dumps(load_foodbanks(), separators=(",", ":")))
               .replace("__FUNDING__", json.dumps(_funding(cfg), separators=(",", ":")))
               .replace("__DATA__", geo))


def esc(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def brief_html(cfg, fc):
    feats = fc["features"]
    res = [f["properties"] for f in feats if f["properties"].get("pop") and not f["properties"].get("sup")]
    tot = sum(p["pop"] for p in res) or 1

    def wavg(k):
        vals = [(p[k], p["pop"]) for p in res if p.get(k) is not None]
        return round(sum(v * w for v, w in vals) / (sum(w for _, w in vals) or 1), 1) if vals else None

    high = [f["properties"] for f in feats if (f["properties"].get("score") or 0) >= 60]
    high_pop = sum(p.get("pop") or 0 for p in high)
    indig_tot = sum((f["properties"].get("indn") or 0) for f in feats)
    top = sorted((f["properties"] for f in feats), key=lambda p: -(p.get("score") or 0))[:12]
    fund = _funding(cfg)
    chans = fund.get("federal_channels", [])[:7]

    rows = "".join(
        f'<tr><td>{esc(p.get("csd"))}</td><td class="mono">{esc(p.get("dauid"))}</td>'
        f'<td class="num"><b>{p.get("score")}</b></td><td class="num">{p.get("lim")}%</td>'
        f'<td class="num">{p.get("govt")}%</td><td class="num">${(p.get("inc") or 0):,}</td>'
        f'<td class="num">{(p.get("pop") or 0):,}</td></tr>' for p in top)
    chan_rows = "".join(
        f'<li><a href="{c.get("url")}">{esc(c.get("name"))}</a> — {esc(c.get("what"))}</li>'
        for c in chans) or "<li>See the funding panel on the map.</li>"

    tpl = BRIEF_TPL
    return (tpl.replace("__NAME__", esc(cfg["name"]))
               .replace("__REGION__", esc(cfg.get("region_label", cfg["name"])))
               .replace("__MAPHREF__", "/" + cfg["slug"])
               .replace("__DATE__", time.strftime("%B %-d, %Y"))
               .replace("__NTRACTS__", f"{len(feats):,}")
               .replace("__NHIGH__", f"{len(high):,}")
               .replace("__HIGHPOP__", f"{high_pop:,}")
               .replace("__INDIG__", f"{indig_tot:,}")
               .replace("__LIM__", str(wavg("lim")))
               .replace("__GOVT__", str(wavg("govt")))
               .replace("__TOTPOP__", f"{tot:,}")
               .replace("__ROWS__", rows)
               .replace("__CHANNELS__", chan_rows))


def main():
    data = json.loads(Path(sys.argv[1]).read_text())
    items = data if isinstance(data, list) else [data]
    Path("docs").mkdir(exist_ok=True)
    ddir = Path("docs") / "data"; ddir.mkdir(parents=True, exist_ok=True)
    for cfg in items:
        if "cma_uid" not in cfg or "slug" not in cfg:
            log(f"skip {sys.argv[1]} ({cfg.get('slug','?')}): needs cma_uid/slug/pruid")
            continue
        fc = build(cfg)
        (Path("docs") / (cfg["slug"] + ".html")).write_text(html(cfg, fc))
        (ddir / (cfg["slug"] + ".json")).write_text(json.dumps(summarize(cfg, fc), separators=(",", ":")))
        (Path("docs") / (cfg["slug"] + "-brief.html")).write_text(brief_html(cfg, fc))
        log(f"wrote docs/{cfg['slug']}.html : {len(fc['features'])} dissemination areas (+ brief)")


# ---- print-ready brief template (kept inline to minimise repo files) --------
BRIEF_TPL = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__NAME__ — Food Need & Funding Brief</title>
<style>
 @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Mono:wght@400;500&family=Public+Sans:wght@400;500;600;700&display=swap');
 :root{--ground:#EDF1EE;--paper:#FBFCFB;--ink:#16211D;--ink-soft:#4F615A;--ink-faint:#7B8C84;--line:#D8E1DC;--primary:#1E6B57;}
 @media (prefers-color-scheme:dark){:root{--ground:#0C1411;--paper:#14201C;--ink:#E6EEE9;--ink-soft:#9EB0A8;--ink-faint:#71827A;--line:#253431;--primary:#53BF9F;}}
 *{box-sizing:border-box} body{margin:0;background:var(--ground);color:var(--ink);font-family:"Public Sans",system-ui,sans-serif;font-size:14.5px;line-height:1.55}
 .bar{background:var(--paper);border-bottom:1px solid var(--line);padding:9px 18px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
 .bar a{color:var(--ink-soft);text-decoration:none;font-size:13px} .bar a:hover{color:var(--primary)}
 .btn{background:var(--primary);color:#fff;border:none;border-radius:8px;padding:8px 14px;font:inherit;font-weight:700;font-size:13px;cursor:pointer}
 .sheet{max-width:820px;margin:22px auto;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:34px 40px;box-shadow:0 8px 26px rgba(20,40,34,.07)}
 .kick{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--primary);margin:0 0 6px}
 h1{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.7rem;letter-spacing:-.02em;margin:0}
 .meta{color:var(--ink-faint);font-size:12.5px;margin:5px 0 0;font-family:"IBM Plex Mono",monospace}
 h2{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.12rem;margin:26px 0 8px;border-bottom:1px solid var(--line);padding-bottom:5px}
 p{color:var(--ink-soft);margin:9px 0} b{color:var(--ink)}
 .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
 .stat{background:var(--ground);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
 .stat .n{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.35rem;line-height:1.1}
 .stat .l{color:var(--ink-faint);font-size:11px;margin-top:3px}
 table{width:100%;border-collapse:collapse;margin:8px 0;font-size:12.5px}
 th{text-align:left;color:var(--ink-faint);font-weight:600;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--line);padding:6px 8px}
 td{padding:6px 8px;border-bottom:1px solid var(--line)} td.num{text-align:right;font-variant-numeric:tabular-nums} td.mono{font-family:"IBM Plex Mono",monospace;color:var(--ink-faint)}
 ul{margin:8px 0;padding-left:20px} li{margin:6px 0;font-size:13px;color:var(--ink-soft)} li a{color:var(--primary)}
 .ask{background:var(--ground);border:1px dashed var(--primary);border-radius:10px;padding:14px 16px;color:var(--ink-soft);font-size:13.5px}
 .foot{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink-faint);margin-top:22px;border-top:1px solid var(--line);padding-top:12px}
 @media print{.bar{display:none} body{background:#fff} .sheet{box-shadow:none;border:none;border-radius:0;margin:0;max-width:none;padding:0 8px} h2{break-after:avoid} table,ul{break-inside:avoid} a{color:#1E6B57;text-decoration:none}}
</style></head><body>
<div class="bar">
 <a href="__MAPHREF__">← Back to the map</a>
 <button class="btn" onclick="window.print()">Print / Save as PDF</button>
</div>
<div class="sheet">
 <p class="kick">Food Aid Project · Food-Need Atlas · Evidence Brief</p>
 <h1>__NAME__ — Food Need &amp; Funding Brief</h1>
 <p class="meta">__REGION__ · generated __DATE__</p>
 <p>Across __REGION__, the Food-Need Atlas scores every one of <b>__NTRACTS__ dissemination areas</b> (neighbourhoods of ~400–700 people) on the low-income measure (LIM-AT), reliance on government transfers, and income. <b>__NHIGH__ neighbourhoods — about __HIGHPOP__ people — register high food need</b>, and are where distribution, mobile pantries and the right product mix return the most.</p>
 <p><b>Indigenous food insecurity:</b> about <b>__INDIG__ residents</b> across __REGION__ report Indigenous identity. Standard neighbourhood maps under-represent Indigenous need — some reserves are incompletely enumerated — so treat this as a floor and route support through Indigenous-led programs and food-sovereignty initiatives.</p>
 <div class="stats">
  <div class="stat"><div class="n">__NHIGH__</div><div class="l">high-need neighbourhoods</div></div>
  <div class="stat"><div class="n">__LIM__%</div><div class="l">low income, LIM-AT (avg)</div></div>
  <div class="stat"><div class="n">__GOVT__%</div><div class="l">income from gov. transfers (avg)</div></div>
  <div class="stat"><div class="n">__TOTPOP__</div><div class="l">people in scored areas</div></div>
 </div>
 <h2>Highest-need neighbourhoods</h2>
 <table>
  <thead><tr><th>Municipality</th><th>DA</th><th class="num">Score</th><th class="num">LIM-AT</th><th class="num">Gov. transfers</th><th class="num">Median income</th><th class="num">Population</th></tr></thead>
  <tbody>__ROWS__</tbody>
 </table>
 <h2>Funding to pursue</h2>
 <p><b>Federal &amp; national programs</b> (confirm current eligibility before applying):</p>
 <ul>__CHANNELS__</ul>
 <p>Food Aid Project can also source and ship a <a href="https://foodbank-atlas.web.app/order">mixed truckload</a> of shelf-stable staples into these neighbourhoods.</p>
 <h2>The ask (template)</h2>
 <div class="ask">__NAME__ serves __REGION__, where __NHIGH__ neighbourhoods — approximately __HIGHPOP__ residents — face high food insecurity, with the low-income rate (LIM-AT) averaging __LIM__%. We are seeking <b>$______</b> to <b>[expand mobile distribution / purchase and move food / launch a new pantry site]</b> in the highest-need neighbourhoods identified above, reaching an estimated <b>______ people</b> in the first year.</div>
 <div class="foot">Statistics Canada 2021 Census of Population (dissemination area) via the Census Profile SDMX web service · food-need score = min-max composite of LIM-AT prevalence, government-transfer share of income, and inverse median household income across scorable dissemination areas · Illustrative planning brief. Verify all figures and eligibility before use.</div>
</div>
</body></html>'''


if __name__ == "__main__":
    main()

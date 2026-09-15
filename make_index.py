#!/usr/bin/env python3
"""Build the Food-Need Atlas home page from the per-food-bank summaries that
build_atlas.py writes to docs/data/*.json: a US overview map with a pin per
food bank, a search box, and stat cards grouped by state."""
import json, glob
from datetime import date
from pathlib import Path

BUILT = date.today().strftime('%-d %B %Y')   # stamped into the pages at build time

sums = []
for p in sorted(glob.glob("docs/data/*.json")):
    try:
        s = json.loads(Path(p).read_text())
    except Exception:
        continue
    if s.get("slug") and Path(f"docs/{s['slug']}.html").exists():
        sums.append(s)

# only food banks whose map actually built; sort by name
sums.sort(key=lambda s: s["name"])

# group by state (fall back to region_label)
groups = {}
for s in sums:
    key = s.get("state") or s.get("region_label") or "Other"
    groups.setdefault(key, []).append(s)


def card(s):
    top = ""
    if s.get("top_place") and s.get("top_score") is not None:
        top = (f'<div class="stat"><span class="k">Highest need</span>'
               f'<span class="v">{s["top_place"]} <span class="pill">{s["top_score"]}</span></span></div>')
    ntr = s.get("ntracts") or 0
    search = f'{s["name"]} {s.get("region_label","")} {s.get("state","")}'.lower()
    return (f'<a class="fbcard" href="/{s["slug"]}" data-s="{search}">'
            f'<div class="fbname">{s["name"]}</div>'
            f'<div class="fbregion">{s.get("region_label","")}</div>'
            f'<div class="stat"><span class="k">Neighborhoods mapped</span>'
            f'<span class="v">{ntr:,}</span></div>{top}'
            f'<div class="go">Open map →</div></a>')


sections = []
for state in sorted(groups):
    cards = "".join(card(s) for s in groups[state])
    sections.append(f'<section class="grp" data-grp="{state.lower()}">'
                    f'<h2 class="grph">{state}</h2><div class="fbgrid">{cards}</div></section>')

# pins for the US map (skip any without a center)
pins = [{"name": s["name"], "slug": s["slug"], "region": s.get("region_label", ""),
         "lat": s["center"][0], "lon": s["center"][1], "n": s.get("ntracts", 0)}
        for s in sums if s.get("center") and s["center"][0] is not None]

# mixed-truckload ordering tool (from funding.json)
order = {}
try:
    order = json.loads(Path("config/funding.json").read_text()).get("order", {})
except Exception:
    pass
_order_ext = order.get("url", "").startswith("http")
_order_tgt = ' target="_blank" rel="noopener"' if _order_ext else ""
order_nav = (f'<a class="ordlink" href="{order["url"]}"{_order_tgt}>Order a truckload →</a>'
             if order.get("url") else "")
fbs_json = json.dumps([{"slug": s["slug"], "name": s["name"], "region_label": s.get("region_label", ""), "state": s.get("state", "")}
                       for s in sums], separators=(",", ":"))
FBSEARCH_NAV = ('<div class="fbsearch"><input class="fbsearch-in" id="fbsearch" type="search" '
                'placeholder="\U0001f50d Find a food bank…" autocomplete="off" aria-label="Find a food bank">'
                '<div class="fbsearch-menu" id="fbsearchMenu"></div></div>')
FBSEARCH_JS = '<script>\nvar FBS=' + fbs_json + ';\n' + r'''(function(){
  var inp=document.getElementById("fbsearch"),menu=document.getElementById("fbsearchMenu");if(!inp||!menu)return;
  function esc(s){return String(s==null?"":s).replace(/[<>&]/g,function(c){return {"<":"&lt;",">":"&gt;","&":"&amp;"}[c];});}
  function norm(s){return String(s==null?"":s).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();}
  function render(){var t=norm(inp.value.trim());
    var list=FBS.filter(function(f){return !t||norm(f.name+" "+(f.region_label||"")+" "+(f.state||"")).indexOf(t)>=0;});
    menu.innerHTML=list.length?list.map(function(f){return '<a href="/'+f.slug+'">'+esc(f.name)+'<small>'+esc(f.region_label||"")+'</small></a>';}).join(""):'<div class="fbsearch-empty">No food banks match.</div>';}
  function openM(){render();menu.classList.add("open");}function closeM(){menu.classList.remove("open");}
  inp.addEventListener("focus",openM);inp.addEventListener("input",openM);
  inp.addEventListener("keydown",function(e){if(e.key==="Enter"){var a=menu.querySelector("a");if(a){e.preventDefault();location.href=a.getAttribute("href");}}else if(e.key==="Escape"){closeM();inp.blur();}});
  document.addEventListener("click",function(e){if(!menu.contains(e.target)&&e.target!==inp)closeM();});
})();
</script>
<!-- Cloudflare Web Analytics --><script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{"token": "8d77e1ce7e0c4dadb342f5b3324fdd4e"}'></script><!-- End Cloudflare Web Analytics -->'''
order_banner = (
    f'<a class="order-cta" href="{order["url"]}"{_order_tgt}>'
    f'<div class="order-txt"><div class="order-kick">Food Aid Project · fill the trucks</div>'
    f'<div class="order-h">{order.get("label","Build a mixed truckload")} →</div>'
    f'<div class="order-help">{order.get("help","")}</div></div>'
    f'<span class="order-btn">{order.get("label","Build a mixed truckload")} →</span></a>'
) if order.get("url") else ""

Path("docs").mkdir(exist_ok=True)
Path("docs/index.html").write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Food-Need Atlas — Food Aid Project</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
 @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Mono:wght@400;500&family=Public+Sans:wght@400;500;600;700&display=swap');
 :root{{--ground:#EDF1EE;--paper:#FBFCFB;--ink:#16211D;--ink-soft:#4F615A;--ink-faint:#7B8C84;--line:#D8E1DC;--primary:#1E6B57;}}
 @media (prefers-color-scheme:dark){{:root{{--ground:#0C1411;--paper:#14201C;--ink:#E6EEE9;--ink-soft:#9EB0A8;--ink-faint:#71827A;--line:#253431;--primary:#53BF9F;}}}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--ground);color:var(--ink);font-family:"Public Sans",system-ui,sans-serif;font-size:15px;line-height:1.55}}
 .nav{{position:sticky;top:0;z-index:1000;background:var(--paper);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 18px;flex-wrap:wrap}}
 .brand{{font-family:"IBM Plex Mono",monospace;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--primary);text-decoration:none}}
 .brand b{{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;letter-spacing:-.01em;text-transform:none;font-size:14px}}
 .count{{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink-faint)}}
 .wrap{{max-width:1020px;margin:0 auto;padding:26px 18px 64px}}
 h1{{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.9rem;letter-spacing:-.02em;margin:0}}
 .lead{{color:var(--ink-soft);max-width:80ch;margin:12px 0 18px}}
 #usmap{{height:400px;border-radius:14px;border:1px solid var(--line);box-shadow:0 8px 26px rgba(20,40,34,.08)}}
 .search{{margin:22px 0 6px}}
 .search input{{width:100%;font:inherit;font-size:15px;padding:11px 14px;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink)}}
 .search input:focus{{outline:none;border-color:var(--primary)}}
 .grph{{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--primary);margin:26px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}}
 .fbgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}}
 .fbcard{{display:block;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px 18px;text-decoration:none;color:var(--ink);box-shadow:0 4px 14px rgba(20,40,34,.05);transition:border-color .12s,transform .12s}}
 .fbcard:hover{{border-color:var(--primary);transform:translateY(-2px)}}
 .fbname{{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.08rem;letter-spacing:-.01em}}
 .fbregion{{color:var(--ink-soft);font-size:13px;margin:2px 0 12px}}
 .stat{{display:flex;justify-content:space-between;align-items:baseline;gap:10px;font-size:13px;padding:5px 0;border-top:1px dashed var(--line)}}
 .stat .k{{color:var(--ink-faint)}} .stat .v{{font-weight:600;text-align:right}}
 .pill{{display:inline-block;background:var(--primary);color:#fff;border-radius:20px;padding:0 8px;font-weight:700;font-size:12px}}
 .go{{margin-top:12px;color:var(--primary);font-weight:700;font-size:13px}}
 .empty{{color:var(--ink-faint);font-size:14px;padding:20px 0;display:none}}
 .foot{{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink-faint);margin-top:30px;border-top:1px solid var(--line);padding-top:14px}}
 a.brand:hover{{opacity:.85}}
 .ordlink{{color:var(--primary);text-decoration:none;font-weight:700;font-size:13px}} .ordlink:hover{{text-decoration:underline}}
 .tlink{{color:var(--ink-soft);text-decoration:none;font-size:13px}} .tlink:hover{{color:var(--primary)}}
 .navlinks{{display:flex;align-items:center;gap:16px}}
 .fbsearch{{position:relative}}
 .fbsearch-in{{font:inherit;font-size:13px;font-weight:500;color:var(--ink);background:var(--ground);border:1px solid var(--line);border-radius:8px;padding:7px 12px;width:210px;max-width:46vw;transition:width .12s}}
 .fbsearch-in:focus{{outline:none;border-color:var(--primary);background:var(--paper);width:240px}}
 .fbsearch-menu{{position:absolute;right:0;top:calc(100% + 6px);background:var(--paper);border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 30px rgba(20,40,34,.16);padding:6px;min-width:260px;max-width:min(360px,92vw);max-height:62vh;overflow:auto;display:none;z-index:1100}}
 .fbsearch-menu.open{{display:block}}
 .fbsearch-menu a{{display:block;padding:8px 10px;border-radius:7px;text-decoration:none;color:var(--ink);font-size:13.5px;font-weight:600}}
 .fbsearch-menu a small{{display:block;color:var(--ink-faint);font-size:11.5px;font-weight:400;margin-top:1px}}
 .fbsearch-menu a:hover,.fbsearch-menu a.sel{{background:var(--ground)}}
 .fbsearch-menu a.here{{background:var(--primary);color:#fff}} .fbsearch-menu a.here small{{color:rgba(255,255,255,.82)}}
 .fbsearch-empty{{padding:8px 10px;color:var(--ink-faint);font-size:12.5px}}
 .order-cta{{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:20px 0 0;background:linear-gradient(100deg,rgba(30,107,87,.10),rgba(30,107,87,.03));border:1px solid var(--primary);border-radius:14px;padding:18px 22px;text-decoration:none;color:var(--ink);flex-wrap:wrap}}
 .order-cta:hover{{background:linear-gradient(100deg,rgba(30,107,87,.16),rgba(30,107,87,.06))}}
 .order-txt{{flex:1 1 340px}}
 .order-kick{{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--primary)}}
 .order-h{{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.12rem;letter-spacing:-.01em;margin:3px 0 4px}}
 .order-help{{font-size:13px;color:var(--ink-soft);max-width:74ch}}
 .order-btn{{flex:0 0 auto;background:var(--primary);color:#fff;font-weight:700;font-size:14px;border-radius:10px;padding:11px 18px;white-space:nowrap}}
</style></head><body>
<header class="nav">
 <a class="brand" href="/">Food Aid Project · <b>Food-Need Atlas</b></a>
 <div class="navlinks"><a class="tlink" href="/about">About</a>{order_nav}{FBSEARCH_NAV}<span class="count">{len(sums)} food bank{"s" if len(sums)!=1 else ""}</span></div>
</header>
<div class="wrap">
 <h1>Food-Need Atlas</h1>
 <p class="lead">Neighborhood-level food-need maps, one per food bank. In the United States every census tract in a service area is scored on poverty, share under 200% of the poverty line, SNAP receipt and low income. In Canada every dissemination area is scored on the low-income measure, government transfers and income. Each map is matched to funding that food bank can pursue. Every map is generated by the same pipeline, so every map is built and read the same way. Scores rank neighbourhoods within one service area and are not comparable between food banks. Pick a food bank on the map or below.</p>
 <div id="usmap"></div>
 {order_banner}
 <div class="search"><input id="q" type="search" placeholder="Search food banks by name, state, or region…" autocomplete="off"></div>
 <div id="sections">{"".join(sections)}</div>
 <div class="empty" id="empty">No food banks match that search.</div>
 <div class="foot">U.S. Census ACS 5-year (tract) via Census Reporter · place names via the U.S. Census geocoder · Illustrative — not a Feeding America product.</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
 const PINS={json.dumps(pins, separators=(",", ":"))};
 (function(){{
   const map=L.map('usmap',{{scrollWheelZoom:false}});
   L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{attribution:'© OpenStreetMap',maxZoom:12,subdomains:'abc'}}).addTo(map);
   const pts=[];
   PINS.forEach(p=>{{
     const m=L.circleMarker([p.lat,p.lon],{{radius:9,color:'#fff',weight:2,fillColor:'#1E6B57',fillOpacity:.95}}).addTo(map);
     m.bindPopup('<b>'+p.name+'</b><br>'+p.region+'<br>'+p.n.toLocaleString()+' neighborhoods<br><a href="/'+p.slug+'">Open map →</a>');
     m.on('mouseover',()=>m.openPopup());
     m.on('click',()=>{{location.href='/'+p.slug;}});
     pts.push([p.lat,p.lon]);
   }});
   if(pts.length) map.fitBounds(pts,{{padding:[40,40],maxZoom:9}}); else map.setView([39.5,-98.35],4);
 }})();
 // search filter
 const q=document.getElementById('q'), empty=document.getElementById('empty');
 q.addEventListener('input',()=>{{
   const nrm=s=>String(s==null?'':s).normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();
   const t=nrm(q.value.trim()); let any=false;
   document.querySelectorAll('.grp').forEach(g=>{{
     let shown=0;
     g.querySelectorAll('.fbcard').forEach(c=>{{
       const hit=!t||nrm(c.dataset.s).includes(t); c.style.display=hit?'':'none'; if(hit)shown++;
     }});
     g.style.display=shown?'':'none'; if(shown)any=true;
   }});
   empty.style.display=any?'none':'block';
 }});
</script>{FBSEARCH_JS}</body></html>''')
print("wrote docs/index.html with", len(sums), "food banks,", len(pins), "map pins")

# ---------------------------------------------------------------- About page
ABOUT = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>About — Food-Need Atlas</title>
<style>
 @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Mono:wght@400;500&family=Public+Sans:wght@400;500;600;700&display=swap');
 :root{--ground:#EDF1EE;--paper:#FBFCFB;--ink:#16211D;--ink-soft:#4F615A;--ink-faint:#7B8C84;--line:#D8E1DC;--primary:#1E6B57;}
 @media (prefers-color-scheme:dark){:root{--ground:#0C1411;--paper:#14201C;--ink:#E6EEE9;--ink-soft:#9EB0A8;--ink-faint:#71827A;--line:#253431;--primary:#53BF9F;}}
 *{box-sizing:border-box} body{margin:0;background:var(--ground);color:var(--ink);font-family:"Public Sans",system-ui,sans-serif;font-size:15px;line-height:1.6}
 .nav{position:sticky;top:0;z-index:1000;background:var(--paper);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 18px;flex-wrap:wrap}
 .brand{font-family:"IBM Plex Mono",monospace;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--primary);text-decoration:none}
 .brand b{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;letter-spacing:-.01em;text-transform:none;font-size:14px}
 .navlinks{display:flex;align-items:center;gap:16px}
 .tlink{color:var(--ink-soft);text-decoration:none;font-size:13px} .tlink:hover{color:var(--primary)}
 .ordlink{color:var(--primary);text-decoration:none;font-weight:700;font-size:13px} .ordlink:hover{text-decoration:underline}
 .fbsearch{position:relative}
 .fbsearch-in{font:inherit;font-size:13px;font-weight:500;color:var(--ink);background:var(--ground);border:1px solid var(--line);border-radius:8px;padding:7px 12px;width:210px;max-width:46vw;transition:width .12s}
 .fbsearch-in:focus{outline:none;border-color:var(--primary);background:var(--paper);width:240px}
 .fbsearch-menu{position:absolute;right:0;top:calc(100% + 6px);background:var(--paper);border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 30px rgba(20,40,34,.16);padding:6px;min-width:260px;max-width:min(360px,92vw);max-height:62vh;overflow:auto;display:none;z-index:1100}
 .fbsearch-menu.open{display:block}
 .fbsearch-menu a{display:block;padding:8px 10px;border-radius:7px;text-decoration:none;color:var(--ink);font-size:13.5px;font-weight:600}
 .fbsearch-menu a small{display:block;color:var(--ink-faint);font-size:11.5px;font-weight:400;margin-top:1px}
 .fbsearch-menu a:hover,.fbsearch-menu a.sel{background:var(--ground)}
 .fbsearch-menu a.here{background:var(--primary);color:#fff} .fbsearch-menu a.here small{color:rgba(255,255,255,.82)}
 .fbsearch-empty{padding:8px 10px;color:var(--ink-faint);font-size:12.5px}
 .wrap{max-width:760px;margin:0 auto;padding:30px 18px 70px}
 .kick{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--primary);margin:0 0 6px}
 h1{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:2rem;letter-spacing:-.02em;margin:0 0 6px}
 h2{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.18rem;letter-spacing:-.01em;margin:30px 0 8px}
 p{color:var(--ink-soft);margin:11px 0} b{color:var(--ink)} a{color:var(--primary)}
 .lead{font-size:17px;color:var(--ink);max-width:64ch}
 .src{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:14px 18px;font-size:13.5px;color:var(--ink-soft);margin:14px 0}
 .src b{color:var(--ink)}
 .cta{display:inline-block;background:var(--primary);color:#fff;font-weight:700;text-decoration:none;border-radius:10px;padding:11px 18px;margin-top:6px}
 .foot{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink-faint);margin-top:34px;border-top:1px solid var(--line);padding-top:14px}
</style></head><body>
<header class="nav">
 <a class="brand" href="/">Food Aid Project · <b>Food-Need Atlas</b></a>
 <div class="navlinks"><a class="tlink" href="/">Atlas</a><a class="tlink" href="/methodology">Methodology</a>__ORDER_NAV____FBSEARCH_NAV__</div>
</header>
<div class="wrap">
 <p class="kick">About</p>
 <h1>Need you can aim at — and the money to meet it</h1>
 <p class="lead">The Food-Need Atlas is a free, neighborhood-level map of food need, and the funding to fill it, built for food banks by <a href="https://www.foodaidproject.org" target="_blank" rel="noopener">Food Aid Project</a>. It exists because "food insecurity" usually arrives as one county number — and a county is far too big to aim a distribution, a mobile pantry, or a truckload at.</p>

 <h2>From a county number to a neighborhood</h2>
 <p>National sources report food insecurity by county, but a single county can span a million people and every income bracket at once. The Atlas splits each food bank's service area into <b>census tracts</b> — about 4,000 people each — and scores every one, so you can see where need actually concentrates and put food, mobile pantries, and the right product mix where they matter most.</p>

 <h2>How the food-need score works</h2>
 <p>Each tract gets a 0–100 score: a min-max composite of four U.S. Census ACS 5-year measures — the poverty rate, the share of people under 200% of the federal poverty line, SNAP receipt, and (inverted) median household income. Scores are normalized across the residential tracts in <em>your</em> service area, so the darkest neighborhoods are the highest-need ones relative to your region. It's a relative index for ranking and targeting — not an official headcount, and not a substitute for Map the Meal Gap's dollar estimates. The exact formula, the weights, the missing-data rule, the comparability limits and the validation status are set out in full on the <a href="/methodology">methodology page</a>.</p>

 <h2>Students, seniors, and group quarters — kept in</h2>
 <p>Many need maps quietly drop "group-quarters" tracts: college dorms, military housing, senior facilities, shelters. Hunger there is real — student and senior food insecurity are both well documented — so the Atlas keeps those tracts in and flags them with a dashed purple outline instead of hiding them.</p>

 <h2>Funding to fill the gap</h2>
 <p>Seeing need is half the job; paying for the food is the other half. Every map carries a funding panel, refreshed weekly: <b>open federal grant opportunities</b> pulled from Grants.gov and filtered to food work; the largest <b>private foundations in your own state</b> (from IRS 990-PF data, each linked to its grantmakers.io giving history and 990); the standing federal programs (TEFAP, CSFP, and more); and a direct line to <b>order a mixed truckload</b> of staples from Food Aid Project.</p>

 <h2>Consistent everywhere</h2>
 <p>Every food bank's map is generated by the same pipeline from the same Census data — same method, same look, same scoring — so every map is built and read the same way, and adding a new food bank means one configuration file. The <em>scores</em> are a different matter: each map's scale is stretched to its own service area, so a score ranks neighbourhoods within one food bank's region and is not comparable with a score on another food bank's map.</p>

 <h2>Canada, on the same idea</h2>
 <p>North of the border the Atlas works the same way on Canadian data. Neighbourhoods are Statistics Canada <b>dissemination areas</b> — about 400–700 people, even finer than U.S. tracts — and each is scored 0–100 from the <b>2021 Census</b>: the Low-income measure, after tax (LIM-AT), reliance on government transfers, and (inverted) median income. <b>Indigenous identity is a first-class layer</b>, with the honest caveat that some reserves are incompletely enumerated, so those counts are a floor — route support through Indigenous-led and food-sovereignty programs. Canadian maps carry their own funding guidance rather than the U.S. federal programs.</p>

 <h2>Where the data comes from</h2>
 <div class="src"><b>Need:</b> U.S. Census ACS 5-year estimates at tract level, via Census Reporter. <b>Place names:</b> the U.S. Census geocoder. <b>Grants:</b> the Grants.gov Search2 API. <b>Foundations:</b> IRS Form 990-PF filings via ProPublica Nonprofit Explorer and grantmakers.io. <b>In Canada:</b> 2021 Census Profile via Statistics Canada's keyless SDMX API, with dissemination-area boundaries from StatCan's open boundary files.</div>

 <h2>Who builds it</h2>
 <p>Food Aid Project is a nonprofit that does two things food banks rarely find in one place: it builds technology like this Atlas, and it <b>sources and ships actual food</b> — truckloads and co-packed pouches of shelf-stable staples — to food banks across the U.S. and Canada. The Atlas is the free, neutral intelligence layer; the food is how the gap actually gets filled.</p>

 <h2>Honest caveats</h2>
 <p>This is an illustrative planning tool, not a Feeding America product. The score ranks <em>relative</em> need, and it is not an official food-insecurity count. <b>The data is not current.</b> U.S. figures come from the ACS 5-year estimates, which average five years and sit roughly three years behind the present. Canadian figures come from the 2021 Census, whose income measures refer to the 2020 tax year, so they are five to six years old and predate the rise in food prices since 2022. Use the Atlas to see where need concentrates, not how much need exists today. Full detail on the <a href="/methodology">methodology page</a>. Grant eligibility and foundation guidelines change constantly, so always verify on the source before applying, and treat the foundation list as prospects to research on grantmakers.io, not a guarantee of fit.</p>

 <h2>Get your food bank on the map</h2>
 <p>Adding a food bank takes minutes — send us your service area and it's mapped, scored, and matched to funding.</p>
 <a class="cta" href="https://www.foodaidproject.org/food-banks.html" target="_blank" rel="noopener">Talk to Food Aid Project →</a>

 <div class="foot">Food Aid Project · Food-Need Atlas · illustrative, not a Feeding America product</div>
</div>
__FBSEARCH_JS__</body></html>'''
ABOUT = ABOUT.replace("__ORDER_NAV__", order_nav).replace("__FBSEARCH_NAV__", FBSEARCH_NAV).replace("__FBSEARCH_JS__", FBSEARCH_JS)
Path("docs/about.html").write_text(ABOUT)
print("wrote docs/about.html")

METHOD = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Methodology: Food-Need Atlas</title>
<style>
 @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Mono:wght@400;500&family=Public+Sans:wght@400;500;600;700&display=swap');
 :root{--ground:#EDF1EE;--paper:#FBFCFB;--ink:#16211D;--ink-soft:#4F615A;--ink-faint:#7B8C84;--line:#D8E1DC;--primary:#1E6B57;}
 @media (prefers-color-scheme:dark){:root{--ground:#0C1411;--paper:#14201C;--ink:#E6EEE9;--ink-soft:#9EB0A8;--ink-faint:#71827A;--line:#253431;--primary:#53BF9F;}}
 *{box-sizing:border-box} body{margin:0;background:var(--ground);color:var(--ink);font-family:"Public Sans",system-ui,sans-serif;font-size:15px;line-height:1.6}
 .nav{position:sticky;top:0;z-index:1000;background:var(--paper);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 18px;flex-wrap:wrap}
 .brand{font-family:"IBM Plex Mono",monospace;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--primary);text-decoration:none}
 .brand b{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;letter-spacing:-.01em;text-transform:none;font-size:14px}
 .navlinks{display:flex;align-items:center;gap:16px}
 .tlink{color:var(--ink-soft);text-decoration:none;font-size:13px} .tlink:hover{color:var(--primary)}
 .ordlink{color:var(--primary);text-decoration:none;font-weight:700;font-size:13px} .ordlink:hover{text-decoration:underline}
 .fbsearch{position:relative}
 .fbsearch-in{font:inherit;font-size:13px;font-weight:500;color:var(--ink);background:var(--ground);border:1px solid var(--line);border-radius:8px;padding:7px 12px;width:210px;max-width:46vw;transition:width .12s}
 .fbsearch-in:focus{outline:none;border-color:var(--primary);background:var(--paper);width:240px}
 .fbsearch-menu{position:absolute;right:0;top:calc(100% + 6px);background:var(--paper);border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 30px rgba(20,40,34,.16);padding:6px;min-width:260px;max-width:min(360px,92vw);max-height:62vh;overflow:auto;display:none;z-index:1100}
 .fbsearch-menu.open{display:block}
 .fbsearch-menu a{display:block;padding:8px 10px;border-radius:7px;text-decoration:none;color:var(--ink);font-size:13.5px;font-weight:600}
 .fbsearch-menu a small{display:block;color:var(--ink-faint);font-size:11.5px;font-weight:400;margin-top:1px}
 .fbsearch-menu a:hover,.fbsearch-menu a.sel{background:var(--ground)}
 .fbsearch-menu a.here{background:var(--primary);color:#fff} .fbsearch-menu a.here small{color:rgba(255,255,255,.82)}
 .fbsearch-empty{padding:8px 10px;color:var(--ink-faint);font-size:12.5px}
 .wrap{max-width:760px;margin:0 auto;padding:30px 18px 70px}
 .kick{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--primary);margin:0 0 6px}
 h1{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:2rem;letter-spacing:-.02em;margin:0 0 6px}
 h2{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.18rem;letter-spacing:-.01em;margin:30px 0 8px}
 p{color:var(--ink-soft);margin:11px 0} b{color:var(--ink)} a{color:var(--primary)}
 .lead{font-size:17px;color:var(--ink);max-width:64ch}
 .src{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:14px 18px;font-size:13.5px;color:var(--ink-soft);margin:14px 0}
 .src b{color:var(--ink)}
 .cta{display:inline-block;background:var(--primary);color:#fff;font-weight:700;text-decoration:none;border-radius:10px;padding:11px 18px;margin-top:6px}
 .tldr{background:var(--paper);border:1px solid var(--line);border-left:3px solid var(--primary);border-radius:12px;padding:6px 20px 16px;margin:22px 0 6px}
 .tldr-h{font-size:1rem;margin:14px 0 6px}
 .tldr ul{margin:0;padding-left:18px} .tldr li{color:var(--ink-soft);margin:7px 0;font-size:14.5px}
 h3{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1rem;margin:22px 0 6px;color:var(--ink)}
 .eq{background:var(--paper);border:1px solid var(--line);border-left:3px solid var(--primary);border-radius:8px;padding:12px 16px;margin:12px 0;font-family:"IBM Plex Mono",monospace;font-size:13.5px;color:var(--ink);overflow-x:auto}
 .mono{font-family:"IBM Plex Mono",monospace;font-size:12.5px;background:var(--paper);border:1px solid var(--line);border-radius:5px;padding:1px 5px}
 .foot{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink-faint);margin-top:34px;border-top:1px solid var(--line);padding-top:14px}
</style></head><body>
<header class="nav">
 <a class="brand" href="/">Food Aid Project · <b>Food-Need Atlas</b></a>
 <div class="navlinks"><a class="tlink" href="/">Atlas</a><a class="tlink" href="/about">About</a>__ORDER_NAV____FBSEARCH_NAV__</div>
</header>
<div class="wrap">
 <p class="kick">Methodology · Version 1.4 · 15 September 2026</p>
 <h1>How the food-need score is built</h1>
 <p class="lead">This page states the exact formula, the weights, the missing-data rule, what the score can and cannot be compared against, how old the data is, and what has and has not been validated. It exists so a food bank can evaluate the Atlas before citing it in a grant application or a board report.</p>

 <div class="src"><b>Version 1.4</b> · published 15 September 2026 · applies to all 41 maps. <b>This site was last built __BUILT__.</b> Changes to the formula, the indicators, or the weights will appear in the changelog at the foot of this page with a new version number.</div>

 <div class="tldr">
  <h2 class="tldr-h">The short version</h2>
  <ul>
   <li><b>What the score is.</b> A 0–100 ranking of neighbourhoods by measured food need, built from official census statistics.</li>
   <li><b>How it is built.</b> Three indicators in Canada (low income, government transfers, median income), four in the United States. Each is put on the same scale, then averaged. <b>Equal weight</b>: one-third each in Canada, one-quarter each in the US.</li>
   <li><b>What you may compare.</b> Neighbourhoods <em>within one food bank's map</em>. <b>Never between food banks, cities or countries</b>. Each map is scaled to its own service area.</li>
   <li><b>How old the data is.</b> Canada: the 2021 Census, with income figures referring to 2020. United States: the latest ACS 5-year estimates. Neither reflects conditions today.</li>
   <li><b>Where data is missing.</b> Suppressed neighbourhoods are either left unscored or scored on the indicators that remain. Nothing is invented to fill a gap.</li>
   <li><b>What has not been tested.</b> Whether the score predicts where people actually go hungry. It has not been checked against food bank demand or food-insecurity surveys. Cite it as a measure of disadvantage, not a count of hunger.</li>
  </ul>
 </div>

 <h2>1. The formula</h2>
 <p>Every neighbourhood gets one score from 0 to 100. The calculation runs in three steps, in this order.</p>
 <p><b>Step one: put each indicator on the same 0-to-1 scale.</b> For each indicator, take the lowest and highest values found across the reference set of neighbourhoods in that food bank's service area (defined in section 3), then rescale:</p>
 <div class="eq">n = ( x − min ) / ( max − min )</div>
 <p>For median household income the direction is flipped, because <em>less</em> income means <em>more</em> need:</p>
 <div class="eq">n = 1 − ( x − min ) / ( max − min )</div>
 <p>The result is clamped to the range 0 to 1, so a neighbourhood outside the reference set cannot push past either end.</p>
 <p><b>Step two: average the rescaled indicators.</b> Add them up and divide by how many there are.</p>
 <p><b>Step three: express it out of 100</b> and round to one decimal place.</p>
 <div class="eq">score = 100 × ( n<sub>1</sub> + n<sub>2</sub> + … + n<sub>k</sub> ) ÷ k</div>
 <p>There is no second rescaling after the average. That is why the highest-scoring neighbourhood on a map is usually not exactly 100 (Saskatoon's peak is 95.3, Regina's 95.7), and why no neighbourhood ever scores 0 unless it sits at the bottom of every indicator at once.</p>

 <h2>2. The indicators and their weights</h2>
 <p><b>The weights are equal.</b> No indicator is given more influence than another. In Canada each of the three indicators carries one-third of the score; in the United States each of the four carries one-quarter. This was a deliberate choice: there is no published evidence base that would justify a particular unequal weighting, and an arbitrary one would be harder to defend than an equal one.</p>
 <div class="src"><b>Canada: three indicators, one-third each.</b> Statistics Canada 2021 Census Profile, dissemination-area level, characteristic codes in brackets.<br>
 · <b>Low-income measure, after tax (LIM-AT)</b>: prevalence, % of population [331]<br>
 · <b>Government transfers</b>: share of total household income, % [144]<br>
 · <b>Median total household income</b>: dollars, <b>inverted</b> [229]</div>
 <div class="src"><b>United States: four indicators, one-quarter each.</b> U.S. Census American Community Survey 5-year estimates, tract level, via Census Reporter; ACS table in brackets.<br>
 · <b>Poverty rate</b>: % below the federal poverty line [B17001]<br>
 · <b>Share under 200% of the federal poverty line</b>: % [C17002]<br>
 · <b>SNAP receipt</b>: % of households [B22003]<br>
 · <b>Median household income</b>: dollars, <b>inverted</b> [B19013]</div>
 <p>The two countries are scored on different indicators because the two statistical systems publish different things. There is no Canadian equivalent of SNAP receipt, and no U.S. equivalent of LIM-AT at this geography.</p>

 <h2>3. What the scale is measured against</h2>
 <p>The minimum and maximum in step one are not national. They are taken from the <b>reference set</b>: the neighbourhoods inside that one food bank's service area that are eligible to set the scale.</p>
 <p><b>In Canada</b>, the reference set is every dissemination area with a population above zero whose low-income and income figures are not both suppressed.</p>
 <p><b>In the United States</b>, the reference set is every tract with a population above zero that is not flagged as group quarters. A tract is flagged as group quarters if its population is under 1,200 <em>or</em> at least half its residents live in group quarters: dormitories, military housing, senior facilities, shelters, correctional facilities. That flag is a rule applied by the Atlas, not a label published by the Census Bureau.</p>
 <p>Neighbourhoods outside the reference set are still scored and still drawn on the map, and are marked with a dashed purple outline rather than hidden, but they do not set the ends of the scale, and their scores are clamped to the 0–100 range.</p>

 <h2>4. Missing and suppressed data</h2>
 <p>Statistics Canada suppresses figures for small or sparsely populated areas to protect privacy, and ACS estimates are sometimes absent. The rule is the same in both countries: <b>a missing indicator is dropped, and the remaining indicators are averaged among themselves.</b> The divisor <em>k</em> in the formula is the number of indicators actually available for that neighbourhood, not the full three or four. Missing values are never imputed, never filled with a national average, and never treated as zero.</p>
 <p>This means a neighbourhood can be scored on fewer indicators than its neighbours. <b>That is a real limitation and it should be read as one.</b> The numbers, verified against the live maps on 15 September 2026:</p>
 <div class="src"><b>Canada</b>: 24,420 dissemination areas across 9 maps. <b>23,836</b> are scored. <b>584</b> have both low-income and income suppressed and are left unscored entirely, carrying no score at all rather than a partial one. Of those scored, <b>444</b> (1.9%) rest on one or two indicators instead of three.<br><br>
 <b>United States</b>: 26,882 tracts across 32 maps. All are scored. Of those, <b>186</b> (0.7%) rest on fewer than four indicators. <b>555</b> are flagged as group quarters.</div>
 <p>A neighbourhood scored on one indicator is a weaker estimate than one scored on three. Click any neighbourhood on a map to see which indicators it actually has; a suppressed figure is shown as blank, not as a number.</p>

 <h2>5. What the score can be compared against, and what it cannot</h2>
 <p>Because the scale is built from the highest and lowest values <em>inside each service area</em>, the score is a <b>local ranking</b>. This is the single most important limitation on the page.</p>
 <p><b>Valid:</b> comparing neighbourhoods within one food bank's map. A neighbourhood scoring 90 has substantially higher measured need than one scoring 40 in the same service area. That is what the score is for, and what it does well.</p>
 <p><b>Not valid:</b> comparing scores between food banks, between cities, between provinces, or between countries. Saskatoon's highest-need neighbourhood scores 95.3 and Toronto's scores 99.9. This does <b>not</b> mean need in Toronto is greater. Each map's scale is stretched to its own range, so almost every map has a top neighbourhood somewhere in the 80s or 90s regardless of the absolute conditions there. Two neighbourhoods in different cities with identical poverty and income can receive very different scores.</p>
 <p><b>Not valid across the border under any circumstances:</b> the Canadian and U.S. scores are built from different indicators drawn from different statistical systems with different definitions. They share a 0–100 presentation and nothing else.</p>
 <p>If you need figures that are comparable between regions, use the underlying indicators themselves. The LIM-AT rate, the poverty rate and the median income are shown for every neighbourhood and are comparable, rather than the composite score.</p>

 <h2>6. How old the data is</h2>
 <p><b>Canada: the 2021 Census of Population.</b> It was collected in May 2021, and its income and low-income measures refer to the <b>2020 tax year</b>. As of September 2026 that makes the income figures roughly six years old. This matters: they describe conditions before the sharp food-price inflation of 2022–23, and Canadian food-bank visits have risen substantially since. The Atlas is useful here for showing <em>where</em> need concentrates, and unreliable for showing <em>how much</em> need there is now. The next Canadian refresh depends on Statistics Canada. The 2026 Census was collected in May 2026, and dissemination-area profile data is expected in 2027–28.</p>
 <p><b>United States: the American Community Survey 5-year estimates.</b> The builder requests the latest 5-year release available at the time each map is built; the release current as of September 2026 is the <b>2024 5-year</b> file, covering 2020–2024. A 5-year estimate is an average across five years, so its midpoint is about three years behind the present even when the file is brand new. Tract boundaries come from the 2023 TIGER release.</p>
 <p><b>When the maps were last built.</b> This site was last built <b>__BUILT__</b>. Rebuilding does not make the underlying data newer: new figures exist only when the statistical agencies publish them. The Census Bureau releases a new ACS 5-year file each December, and Statistics Canada releases dissemination-area Census Profile data after each census. The build history for every page is public at <a href="https://github.com/MultigrainIntl/foodbank-atlas/commits/main" target="_blank" rel="noopener">github.com/MultigrainIntl/foodbank-atlas</a>.</p>
 <p><b>A known gap in version 1.0:</b> the specific ACS release used for each individual map is not currently recorded on that map's page, and the build caches census responses, so a rebuild does not by itself guarantee freshly pulled data. Until each map carries its own data stamp, treat the rebuild dates in the version box above as the build date, not as proof of the data vintage.</p>

 <h2>7. Validation: what has and has not been tested</h2>
 <p>This section is deliberately blunt, because a food bank citing the Atlas in a funding application needs to know exactly how much weight it will bear. It separates what has been tested from what has not.</p>

 <h3>Tested: does the index reproduce, and does the weighting hold up?</h3>
 <p>Two things have been tested across <b>all 41 maps and 49,634 neighbourhoods</b> with complete indicator data.</p>
 <p><b>Reproducibility: passed exactly.</b> Every published score was recomputed from the formula in section 1 using only the indicator values shown on the maps. All 50,718 scored neighbourhoods matched to the decimal place. The tool computes what this page says it computes.</p>
 <p><b>Weighting sensitivity: the equal weighting is supported by the data.</b> The obvious objection is that one-third each is an arbitrary choice. So the data was allowed to pick the weights instead, using a standard statistical method that reads the weights out of how the indicators move together. It picked weights almost exactly equal, and ranked the neighbourhoods in the same order:</p>
 <div class="src"><b>Weights the data chooses, against the equal weights actually used</b><br>
 · <b>Canada</b>. Equal: 0.333 / 0.333 / 0.333. Data-derived: <b>0.333 / 0.327 / 0.340</b> (LIM-AT / transfers / income).<br>
 · <b>United States</b>. Equal: 0.250 each. Data-derived: <b>0.250 / 0.267 / 0.241 / 0.242</b> (poverty / under-200% / SNAP / income).<br>
 · Rank correlation between the equal-weighted and data-weighted scores: <b>1.000</b> in both countries.<br>
 · The indicators overlap heavily. About <b>78% (Canada) and 80% (United States)</b> of the variation between neighbourhoods is one common pattern, which is what makes combining them into a single score reasonable.</div>
 <p>In plain terms: the three (or four) indicators largely measure one underlying thing, and the equal weighting is not a shortcut that distorts the result. It is what the data itself points to.</p>
 <p><b>Missing-data rule: holds.</b> Dropping any single indicator and rescoring changes the neighbourhood ranking very little: rank correlation with the full score stays between 0.90 and 0.98 in Canada and 0.96 and 0.99 in the United States. This is direct evidence that the neighbourhoods scored on fewer indicators (section 4) are not badly misplaced.</p>
 <p><b>The composite does more than any one indicator.</b> No single indicator reproduces it. The worst-matching single indicator correlates 0.66 (Canada) and 0.74 (United States) with the composite.</p>
 <p><b>One limit this testing found.</b> We tried 500 different ways of weighting the indicators to see whether the same neighbourhoods kept coming out in the top 10%. About three quarters of them did. In the worst cases, only about half. <b>So treat the highest-need neighbourhoods as a group, not a ranking.</b> Whether a neighbourhood comes 6th or 16th is not meaningful. Whether it is in the top 10% rather than the bottom half is.</p>

 <h3>Not tested: does the score predict actual food need?</h3>
 <p><b>The index has not been validated against any observed outcome.</b> It has not been compared with food-bank visit counts, client registrations, or distribution volumes. It has not been compared with Canadian Income Survey or Household Food Security Survey Module food-insecurity estimates, with Statistics Canada's Canadian Index of Multiple Deprivation, or with Feeding America's Map the Meal Gap. No external statistical or academic review has been carried out. No confidence intervals are reported, and ACS margins of error are not propagated into the score.</p>
 <p>Everything in the tested section above is <b>internal</b>: it shows the index is arithmetically sound, stable, and not an artefact of an arbitrary weighting choice. None of it shows that the composite predicts where people actually go hungry. That is a different question and it remains open.</p>
 <p><b>What this means for citation.</b> The Atlas is defensible as a transparent, reproducible, weighting-robust index of measured socioeconomic disadvantage at neighbourhood level, built from official statistics. It is not a validated measure of food insecurity and should not be cited as one. The honest framing in a grant application is that the Atlas identifies where recognised drivers of food need concentrate within a service area, not that it counts food-insecure people.</p>
 <p>If your food bank holds aggregate service data and wants the score tested against real demand in your own area, get in touch and we will look at it with you.</p>

 <h2>8. Related and complementary sources</h2>
 <p>In Canada, <a href="https://foodbankscanada.ca/" target="_blank" rel="noopener">Food Banks Canada</a>'s Poverty Vulnerability Map covers Federal Electoral Districts and Census Metropolitan Areas with a broader set of vulnerability indicators and an established methodology. It is the better instrument for national research and advocacy. The Atlas works at a far finer geography, dissemination areas of 400 to 700 people, for operational planning inside a single service area. The two are complementary, and where they disagree the national research resource should be treated as authoritative.</p>
 <p>In the United States, Feeding America's Map the Meal Gap provides county-level food-insecurity rates and meal-cost estimates. The Atlas does not replace it and does not produce dollar or meal estimates.</p>

 <h2>9. How to cite the Atlas</h2>
 <div class="src">Food Aid Project. <em>Food-Need Atlas</em>, [food bank name] service area. Methodology version 1.4, 15 September 2026. Retrieved [date] from https://foodbank-atlas.web.app<br><br>
 When citing a score, state the geography and the limitation, for example: "Dissemination area 47110567 scores 95.3 on the Food-Need Atlas composite index, the highest relative score within the Saskatoon service area. The index ranks neighbourhoods within a service area and is not comparable between regions."</div>

 <h2>10. Reproducing the calculation</h2>
 <p>The score for every neighbourhood can be recomputed from the values shown on the map itself, using the formula in section 1. The build code is open: <a href="https://github.com/MultigrainIntl/foodbank-atlas" target="_blank" rel="noopener">github.com/MultigrainIntl/foodbank-atlas</a>. The scoring function is <span class="mono">score()</span> in <span class="mono">build_ca.py</span> for Canada and <span class="mono">build_atlas.py</span> for the United States. If your recomputation disagrees with a published score by more than rounding, that is a defect and we want to hear about it.</p>

 <h2>Changelog</h2>
 <div class="src"><b>Version 1.4, 15 September 2026.</b> Build date now generated automatically instead of hard-coded, so it cannot go stale.<br><b>Version 1.3, 15 September 2026.</b> Added a plain-language summary at the top of the page.<br><b>Version 1.2, 15 September 2026.</b> Plain-language rewrite of the weighting-test explanation in section 7. No change to the method or the results.<br><b>Version 1.1, 15 September 2026.</b> Added tested validation results: reproducibility check on all 50,718 scores, data-derived weighting comparison, leave-one-out stability, and a weighting stress test of the top decile.<br><b>Version 1.0, 15 September 2026.</b> First published methodology. States the formula, equal weighting, reference population, missing-data rule, comparability limits, and data vintages.</div>

 <h2>Questions about the method</h2>
 <p>If something on this page is unclear, insufficient, or wrong, say so. Corrections and challenges to the method are welcome.</p>
 <a class="cta" href="https://www.foodaidproject.org/food-banks.html" target="_blank" rel="noopener">Talk to Food Aid Project →</a>

 <div class="foot">Food Aid Project · Food-Need Atlas · methodology v1.4 · illustrative, not a Feeding America product</div>
</div>
__FBSEARCH_JS__</body></html>'''
METHOD = METHOD.replace("__BUILT__", BUILT).replace("__ORDER_NAV__", order_nav).replace("__FBSEARCH_NAV__", FBSEARCH_NAV).replace("__FBSEARCH_JS__", FBSEARCH_JS)
Path("docs/methodology.html").write_text(METHOD)
print("wrote docs/methodology.html")

# ---------------------------------------------------------------- Order page (embedded truckload tool)
if order.get("embed_url"):
    ORDER = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Order a truckload — Food-Need Atlas</title>
<style>
 @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Mono:wght@400;500&family=Public+Sans:wght@400;500;600;700&display=swap');
 :root{--ground:#EDF1EE;--paper:#FBFCFB;--ink:#16211D;--ink-soft:#4F615A;--ink-faint:#7B8C84;--line:#D8E1DC;--primary:#1E6B57;}
 @media (prefers-color-scheme:dark){:root{--ground:#0C1411;--paper:#14201C;--ink:#E6EEE9;--ink-soft:#9EB0A8;--ink-faint:#71827A;--line:#253431;--primary:#53BF9F;}}
 *{box-sizing:border-box} body{margin:0;background:var(--ground);color:var(--ink);font-family:"Public Sans",system-ui,sans-serif;font-size:15px;line-height:1.6}
 .nav{position:sticky;top:0;z-index:1000;background:var(--paper);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 18px;flex-wrap:wrap}
 .brand{font-family:"IBM Plex Mono",monospace;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--primary);text-decoration:none}
 .brand b{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;letter-spacing:-.01em;text-transform:none;font-size:14px}
 a.brand:hover{opacity:.85}
 .navlinks{display:flex;align-items:center;gap:16px}
 .tlink{color:var(--ink-soft);text-decoration:none;font-size:13px} .tlink:hover{color:var(--primary)}
 .fbsearch{position:relative}
 .fbsearch-in{font:inherit;font-size:13px;font-weight:500;color:var(--ink);background:var(--ground);border:1px solid var(--line);border-radius:8px;padding:7px 12px;width:210px;max-width:46vw;transition:width .12s}
 .fbsearch-in:focus{outline:none;border-color:var(--primary);background:var(--paper);width:240px}
 .fbsearch-menu{position:absolute;right:0;top:calc(100% + 6px);background:var(--paper);border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 30px rgba(20,40,34,.16);padding:6px;min-width:260px;max-width:min(360px,92vw);max-height:62vh;overflow:auto;display:none;z-index:1100}
 .fbsearch-menu.open{display:block}
 .fbsearch-menu a{display:block;padding:8px 10px;border-radius:7px;text-decoration:none;color:var(--ink);font-size:13.5px;font-weight:600}
 .fbsearch-menu a small{display:block;color:var(--ink-faint);font-size:11.5px;font-weight:400;margin-top:1px}
 .fbsearch-menu a:hover,.fbsearch-menu a.sel{background:var(--ground)}
 .fbsearch-menu a.here{background:var(--primary);color:#fff} .fbsearch-menu a.here small{color:rgba(255,255,255,.82)}
 .fbsearch-empty{padding:8px 10px;color:var(--ink-faint);font-size:12.5px}
 .wrap{max-width:960px;margin:0 auto;padding:26px 18px 56px}
 .kick{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--primary);margin:0 0 6px}
 h1{font-family:"Bricolage Grotesque",sans-serif;font-weight:800;font-size:1.9rem;letter-spacing:-.02em;margin:0 0 8px}
 .lead{color:var(--ink-soft);max-width:74ch;margin:10px 0 8px}
 .openfull{font-size:12.5px;color:var(--ink-faint);margin:2px 0 14px}
 .openfull a{color:var(--primary)}
 .embed-wrap{background:var(--paper);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 8px 26px rgba(20,40,34,.08)}
 .embed-frame{display:block;width:100%;height:calc(100vh - 150px);min-height:760px;border:0;background:#fff}
 .foot{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink-faint);margin-top:22px;border-top:1px solid var(--line);padding-top:14px}
</style></head><body>
<header class="nav">
 <a class="brand" href="/">Food Aid Project · <b>Food-Need Atlas</b></a>
 <div class="navlinks"><a class="tlink" href="/">Atlas</a><a class="tlink" href="/about">About</a>__FBSEARCH_NAV__</div>
</header>
<div class="wrap">
 <p class="kick">Food Aid Project · fill the trucks</p>
 <h1>Order a mixed truckload</h1>
 <p class="lead">Mix and match beans, lentils, chickpeas, oats, rice and grains to fill a 53-ft dry van — watch the load build to 26 pallets / 42,000 lb — then start a conversation with Food Aid Project. Free planning tool, not a binding order.</p>
 <p class="openfull">Trouble loading below? <a href="__EMBED_URL__" target="_blank" rel="noopener">Open the full tool in a new tab →</a></p>
 <div class="embed-wrap"><iframe class="embed-frame" src="__EMBED_URL__" title="Build a mixed truckload" loading="lazy"></iframe></div>
 <div class="foot">Food Aid Project · Food-Need Atlas · illustrative, not a Feeding America product</div>
</div>
__FBSEARCH_JS__</body></html>'''
    ORDER = ORDER.replace("__FBSEARCH_NAV__", FBSEARCH_NAV).replace("__FBSEARCH_JS__", FBSEARCH_JS).replace("__EMBED_URL__", order["embed_url"])
    Path("docs/order.html").write_text(ORDER)
    print("wrote docs/order.html")

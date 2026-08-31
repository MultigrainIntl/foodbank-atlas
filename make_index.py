#!/usr/bin/env python3
"""Build the Food-Need Atlas home page from the per-food-bank summaries that
build_atlas.py writes to docs/data/*.json: a US overview map with a pin per
food bank, a search box, and stat cards grouped by state."""
import json, glob
from pathlib import Path

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
order_nav = (f'<a class="ordlink" href="{order["url"]}" target="_blank" rel="noopener">Order a truckload →</a>'
             if order.get("url") else "")
switch_items = "".join(
    f'<a href="/{s["slug"]}">{s["name"]}<small>{s.get("region_label","")}</small></a>' for s in sums)
order_banner = (
    f'<a class="order-cta" href="{order["url"]}" target="_blank" rel="noopener">'
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
 .navlinks{{display:flex;align-items:center;gap:16px}}
 .switch{{position:relative}}
 .switch-btn{{font:inherit;font-size:13px;font-weight:600;color:var(--ink);background:var(--ground);border:1px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer}}
 .switch-btn:hover{{border-color:var(--primary)}}
 .switch-menu{{position:absolute;right:0;top:calc(100% + 6px);background:var(--paper);border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 30px rgba(20,40,34,.16);padding:6px;min-width:270px;max-height:62vh;overflow:auto;display:none;z-index:1100}}
 .switch-menu.open{{display:block}}
 .switch-menu a{{display:block;padding:8px 10px;border-radius:7px;text-decoration:none;color:var(--ink);font-size:13.5px;font-weight:600}}
 .switch-menu a small{{display:block;color:var(--ink-faint);font-size:11.5px;font-weight:400;margin-top:1px}}
 .switch-menu a:hover{{background:var(--ground)}}
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
 <div class="navlinks">{order_nav}<div class="switch"><button class="switch-btn" id="switchBtn" aria-haspopup="true">Switch food bank ▾</button><div class="switch-menu" id="switchMenu">{switch_items}</div></div><span class="count">{len(sums)} food bank{"s" if len(sums)!=1 else ""}</span></div>
</header>
<div class="wrap">
 <h1>Food-Need Atlas</h1>
 <p class="lead">Neighborhood-level food-need maps, one per food bank — every U.S. census tract in a food bank's service area scored on poverty, share under 200% of the poverty line, SNAP receipt, and low income, and matched to funding it can pursue. Every map is generated by the same pipeline, so any two are directly comparable. Pick a food bank on the map or below.</p>
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
   const t=q.value.trim().toLowerCase(); let any=false;
   document.querySelectorAll('.grp').forEach(g=>{{
     let shown=0;
     g.querySelectorAll('.fbcard').forEach(c=>{{
       const hit=!t||c.dataset.s.includes(t); c.style.display=hit?'':'none'; if(hit)shown++;
     }});
     g.style.display=shown?'':'none'; if(shown)any=true;
   }});
   empty.style.display=any?'none':'block';
 }});
 (function(){{
   const menu=document.getElementById('switchMenu'), btn=document.getElementById('switchBtn');
   if(menu&&btn){{
     btn.addEventListener('click',function(e){{e.stopPropagation();menu.classList.toggle('open');}});
     document.addEventListener('click',function(e){{if(!menu.contains(e.target)&&e.target!==btn)menu.classList.remove('open');}});
   }}
 }})();
</script></body></html>''')
print("wrote docs/index.html with", len(sums), "food banks,", len(pins), "map pins")

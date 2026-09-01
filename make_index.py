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
_order_ext = order.get("url", "").startswith("http")
_order_tgt = ' target="_blank" rel="noopener"' if _order_ext else ""
order_nav = (f'<a class="ordlink" href="{order["url"]}"{_order_tgt}>Order a truckload →</a>'
             if order.get("url") else "")
fbs_json = json.dumps([{"slug": s["slug"], "name": s["name"], "region_label": s.get("region_label", "")}
                       for s in sums], separators=(",", ":"))
FBSEARCH_NAV = ('<div class="fbsearch"><input class="fbsearch-in" id="fbsearch" type="search" '
                'placeholder="\U0001f50d Find a food bank…" autocomplete="off" aria-label="Find a food bank">'
                '<div class="fbsearch-menu" id="fbsearchMenu"></div></div>')
FBSEARCH_JS = '<script>\nvar FBS=' + fbs_json + ';\n' + r'''(function(){
  var inp=document.getElementById("fbsearch"),menu=document.getElementById("fbsearchMenu");if(!inp||!menu)return;
  function esc(s){return String(s==null?"":s).replace(/[<>&]/g,function(c){return {"<":"&lt;",">":"&gt;","&":"&amp;"}[c];});}
  function render(){var t=inp.value.trim().toLowerCase();
    var list=FBS.filter(function(f){return !t||(f.name+" "+(f.region_label||"")).toLowerCase().indexOf(t)>=0;});
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
 <div class="navlinks"><a class="tlink" href="/">Atlas</a>__ORDER_NAV____FBSEARCH_NAV__</div>
</header>
<div class="wrap">
 <p class="kick">About</p>
 <h1>Need you can aim at — and the money to meet it</h1>
 <p class="lead">The Food-Need Atlas is a free, neighborhood-level map of food need, and the funding to fill it, built for food banks by <a href="https://www.foodaidproject.org" target="_blank" rel="noopener">Food Aid Project</a>. It exists because "food insecurity" usually arrives as one county number — and a county is far too big to aim a distribution, a mobile pantry, or a truckload at.</p>

 <h2>From a county number to a neighborhood</h2>
 <p>National sources report food insecurity by county, but a single county can span a million people and every income bracket at once. The Atlas splits each food bank's service area into <b>census tracts</b> — about 4,000 people each — and scores every one, so you can see where need actually concentrates and put food, mobile pantries, and the right product mix where they matter most.</p>

 <h2>How the food-need score works</h2>
 <p>Each tract gets a 0–100 score: a min-max composite of four U.S. Census ACS 5-year measures — the poverty rate, the share of people under 200% of the federal poverty line, SNAP receipt, and (inverted) median household income. Scores are normalized across the residential tracts in <em>your</em> service area, so the darkest neighborhoods are the highest-need ones relative to your region. It's a relative index for ranking and targeting — not an official headcount, and not a substitute for Map the Meal Gap's dollar estimates.</p>

 <h2>Students, seniors, and group quarters — kept in</h2>
 <p>Many need maps quietly drop "group-quarters" tracts: college dorms, military housing, senior facilities, shelters. Hunger there is real — student and senior food insecurity are both well documented — so the Atlas keeps those tracts in and flags them with a dashed purple outline instead of hiding them.</p>

 <h2>Funding to fill the gap</h2>
 <p>Seeing need is half the job; paying for the food is the other half. Every map carries a live funding panel: <b>open federal grant opportunities</b> pulled from Grants.gov and filtered to food work; the largest <b>private foundations in your own state</b> (from IRS 990-PF data, each linked to its grantmakers.io giving history and 990); the standing federal programs (TEFAP, CSFP, and more); and a direct line to <b>order a mixed truckload</b> of staples from Food Aid Project.</p>

 <h2>Consistent everywhere</h2>
 <p>Every food bank's map is generated by the same pipeline from the same Census data — same method, same look, same scoring — so any two are directly comparable, and adding a new food bank is a one-line change.</p>

 <h2>Where the data comes from</h2>
 <div class="src"><b>Need:</b> U.S. Census ACS 5-year estimates at tract level, via Census Reporter. <b>Place names:</b> the U.S. Census geocoder. <b>Grants:</b> the Grants.gov Search2 API. <b>Foundations:</b> IRS Form 990-PF filings via ProPublica Nonprofit Explorer and grantmakers.io.</div>

 <h2>Who builds it</h2>
 <p>Food Aid Project is a nonprofit that does two things food banks rarely find in one place: it builds technology like this Atlas, and it <b>sources and ships actual food</b> — truckloads and co-packed pouches of shelf-stable staples — to food banks across the U.S. and Canada. The Atlas is the free, neutral intelligence layer; the food is how the gap actually gets filled.</p>

 <h2>Honest caveats</h2>
 <p>This is an illustrative planning tool, not a Feeding America product. The score ranks <em>relative</em> need — it is not an official food-insecurity count. Census figures lag one to two years. Grant eligibility and foundation guidelines change constantly, so always verify on the source before applying, and treat the foundation list as prospects to research on grantmakers.io, not a guarantee of fit.</p>

 <h2>Get your food bank on the map</h2>
 <p>Adding a food bank takes minutes — send us your service area and it's mapped, scored, and matched to funding.</p>
 <a class="cta" href="https://www.foodaidproject.org/food-banks.html" target="_blank" rel="noopener">Talk to Food Aid Project →</a>

 <div class="foot">Food Aid Project · Food-Need Atlas · illustrative, not a Feeding America product</div>
</div>
__FBSEARCH_JS__</body></html>'''
ABOUT = ABOUT.replace("__ORDER_NAV__", order_nav).replace("__FBSEARCH_NAV__", FBSEARCH_NAV).replace("__FBSEARCH_JS__", FBSEARCH_JS)
Path("docs/about.html").write_text(ABOUT)
print("wrote docs/about.html")

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

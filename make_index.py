import json, glob
from pathlib import Path
cards=[]
for c in sorted(glob.glob("config/*.json")):
    cfg=json.loads(Path(c).read_text())
    if "slug" not in cfg or "county_fips" not in cfg:
        continue  # skip funding.json and other non-food-bank configs
    if not Path(f"docs/{cfg['slug']}.html").exists():
        continue  # only list food banks whose map actually built
    cards.append(f'<li><a href="{cfg["slug"]}.html">{cfg["name"]}</a> <span>{cfg.get("region_label","")}</span></li>')
Path("docs").mkdir(exist_ok=True)
Path("docs/index.html").write_text(f'''<!doctype html><meta charset=utf-8><title>Food-Need Atlas</title>
<style>body{{font-family:"Public Sans",system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 18px;color:#16211D}}
h1{{font-weight:800}} li{{margin:8px 0}} span{{color:#7B8C84;font-size:13px}} a{{color:#1E6B57;font-weight:600}}</style>
<h1>Food-Need Atlas</h1><p>Neighborhood-level food-need maps, one per food bank — generated from U.S. Census data by a single pipeline.</p>
<ul>{"".join(cards)}</ul>''')
print("wrote docs/index.html with", len(cards), "food banks")

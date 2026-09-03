#!/usr/bin/env python3
"""
pull_funding.py — refresh the live funding data the Food-Need Atlas shows, from
two public sources. Runs on GitHub Actions (which can reach these APIs; the
Cowork container is firewalled from them). Stdlib only. Never fatal: on any
failure it leaves the existing committed file in place so the site still builds.

    python pull_funding.py grants        -> config/grants.json
    python pull_funding.py foundations   -> config/foundations_by_state.json

grants:       open, food-relevant federal opportunities from the Grants.gov
              Search2 API (themed + de-noised, same engine as the Zufall tool).
foundations:  for every state any configured food bank sits in, the largest
              private grantmaking foundations (IRS 990-PF) from ProPublica's
              Nonprofit Explorer — real local funders to check on grantmakers.io.
"""
import json, sys, re, time, glob, urllib.request, urllib.parse, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = {"User-Agent": "foodbank-atlas/1.0"}

STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY", "72": "PR",
}
STATE_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}


def get_json(url, data=None, headers=None, tries=3, timeout=60):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


# ------------------------------------------------------------------ GRANTS.GOV
GRANTS_API = "https://api.grants.gov/v1/api/search2"
GRANT_KEYWORDS = [
    "food bank", "food insecurity", "food security", "nutrition assistance", "hunger",
    "emergency food", "food access", "healthy food financing", "local food purchase",
    "farm to food bank", "commodity supplemental food", "produce", "SNAP outreach",
    "senior nutrition", "child nutrition", "food distribution", "food supply chain",
]
GRANT_THEMES = [
    ("food-supply", ("food bank", "commodity", "food distribution", "supply chain", "purchase", "tefap", "csfp", "bulk")),
    ("nutrition", ("nutrition", "healthy", "produce", "fruit", "vegetable", "meal", "dietary", "wic")),
    ("hunger", ("hunger", "food insecurity", "food security", "emergency food", "feeding")),
    ("access", ("access", "desert", "financing", "local food", "farm to", "farmers market", "snap", "outreach")),
    ("child-senior", ("child nutrition", "school", "summer", "senior", "older adult", "elderly")),
    ("capacity", ("capacity", "technical assistance", "infrastructure", "cold storage", "equipment")),
]
BAD_AGENCY = ("national institutes", "national institute of", "defense", "army", "navy", "naval",
              "air force", "national science", "geological", "fish and wildlife", "foreign agricultural",
              "energy", "maritime", "oceanic", "endowment", "bureau of land", "u.s. mission",
              "telecommunications", "international labor")
BAD_TITLE = ("clinical trial", "(r0", "(r2", "(r3", "(k0", "(u0", "(p0", "sbir", "sttr", "fellowship",
             "dissertation", "research center", "global", "international", "overseas", "foreign",
             "pepfar", "malaria", "surveillance", "wildlife", "watershed", "aquaculture",
             "specialty crop block", "livestock", "genome", "vaccine", "seafood", "wireless",
             "supply chain innovation", "water infrastructure", "critical mineral", "pro-american",
             "forced labor", "healthy homes", "housing preservation")
# An opportunity is kept only if its title carries a genuine food / nutrition / hunger term —
# this is what keeps generic "supply chain" / "workforce" / "healthy" grants out.
FOOD_CORE = ("food", "nutrition", "hunger", "meal", "produce", "grocery", "snap", "wic", "tefap",
             "csfp", "feeding", "pantry", "farm to", "fruit", "vegetable", "dietary", "commodity food",
             "emergency food", "food security", "food access", "food assistance", "food bank")


def theme_tag(title):
    s = title.lower()
    return [k for k, kws in GRANT_THEMES if any(w in s for w in kws)] or ["general"]


def iso(d):
    try:
        return datetime.datetime.strptime(d, "%m/%d/%Y").date().isoformat()
    except (ValueError, TypeError):
        return None


def grants_search(keyword):
    body = json.dumps({"rows": 25, "oppStatuses": "posted", "keyword": keyword}).encode()
    return (get_json(GRANTS_API, data=body, headers={"Content-Type": "application/json"})
            .get("data") or {}).get("oppHits") or []


def pull_grants():
    merged = {}
    for kw in GRANT_KEYWORDS:
        try:
            for o in grants_search(kw):
                merged.setdefault(o["number"], o)
        except Exception as e:
            print(f"  WARN grants '{kw}': {e}", file=sys.stderr)
    if not merged:
        print("No Grants.gov results — leaving existing config/grants.json untouched.", file=sys.stderr)
        sys.exit(1)
    cutoff = datetime.date.today() + datetime.timedelta(days=5)
    kept = []
    for o in merged.values():
        ag = (o.get("agency") or "").lower()
        ti = (o.get("title") or "").replace("&amp;", "&")
        if any(b in ag for b in BAD_AGENCY) or any(b in ti.lower() for b in BAD_TITLE):
            continue
        close = iso(o.get("closeDate"))
        if not close or datetime.date.fromisoformat(close) < cutoff:
            continue
        til = ti.lower()
        if not any(w in til for w in FOOD_CORE):   # must be genuinely food-related
            continue
        th = theme_tag(ti)
        if th == ["general"]:
            th = ["food"]
        kept.append({"number": o.get("number"), "title": ti, "agency": o.get("agency"),
                     "close": close, "cfda": (o.get("cfdaList") or [""])[0], "themes": th,
                     "url": "https://www.grants.gov/search-results-detail/" + str(o.get("id"))})
    kept.sort(key=lambda x: x["close"])
    kept = kept[:24]
    out = {"source": "Grants.gov Search2 API — open federal opportunities",
           "source_url": "https://www.grants.gov", "pulled": datetime.date.today().isoformat(),
           "note": "Open federal opportunities matched to food-bank work by keyword and theme. "
                   "Federal NOFOs a food bank can pursue directly are limited at any moment — verify "
                   "eligibility and full details on grants.gov before applying.",
           "opportunities": kept}
    (ROOT / "config" / "grants.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Wrote config/grants.json — {len(kept)} open opportunities ({len(merged)} raw hits).")


# ------------------------------------------------------------------ FOUNDATIONS (ProPublica 990-PF)
PP_SEARCH = "https://projects.propublica.org/nonprofits/api/v2/search.json"
PP_ORG = "https://projects.propublica.org/nonprofits/api/v2/organizations/{}.json"


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s


def latest_assets(ein):
    """Latest total end-of-year assets (USD) from ProPublica filings, else None."""
    try:
        d = get_json(PP_ORG.format(ein), timeout=45)
    except Exception:
        return None
    fils = (d.get("filings_with_data") or [])
    for f in fils:  # newest first
        for k in ("totassetsend", "totassetsendofyear", "totalassetsendofyearamt"):
            v = f.get(k)
            if v:
                return int(v)
    return None


def foundations_for_state(abbr):
    """Largest private grantmaking foundations (NTEE T) in a state."""
    cands = {}
    for page in (0, 1, 2):
        try:
            q = urllib.parse.urlencode({"q": "foundation", "state[id]": abbr,
                                        "ntee[id]": 7, "page": page})
            res = get_json(f"{PP_SEARCH}?{q}", timeout=45)
        except Exception as e:
            print(f"  WARN pp search {abbr} p{page}: {e}", file=sys.stderr)
            break
        orgs = res.get("organizations") or []
        if not orgs:
            break
        for o in orgs:
            ntee = (o.get("ntee_code") or "").upper()
            if not ntee.startswith("T"):          # T = Philanthropy / grantmaking
                continue
            if str(o.get("subseccd")) not in ("3", "92"):  # 501(c)(3)
                continue
            cands.setdefault(str(o.get("ein")), o)
    # rank candidates by assets (detail call each), keep the biggest few
    ranked = []
    for ein, o in list(cands.items())[:40]:
        a = latest_assets(ein)
        if a and a >= 2_000_000:                  # skip tiny shells
            ranked.append((a, ein, o))
        time.sleep(0.2)
    ranked.sort(reverse=True)
    cards = []
    for a, ein, o in ranked[:8]:
        name = (o.get("name") or "").title()
        cards.append({
            "name": name, "ein": ein, "city": (o.get("city") or "").title(),
            "assets_musd": round(a / 1_000_000),
            "focus": "Private grantmaking foundation (IRS 990-PF)",
            "gm_url": f"https://www.grantmakers.io/profiles/v1/{ein}-{slugify(name)}",
            "pp_url": f"https://projects.propublica.org/nonprofits/organizations/{ein}",
        })
    return cards


def config_states():
    states = {}
    for p in sorted(glob.glob(str(ROOT / "config" / "*.json"))):
        try:
            c = json.loads(Path(p).read_text())
        except Exception:
            continue
        if isinstance(c, list):
            c = c[0] if c else {}
        for fips in c.get("county_fips", []):
            ab = STATE_FIPS.get((fips or "")[:2])
            if ab:
                states[ab] = STATE_NAME.get(ab, ab)
    return states


def pull_foundations():
    out_path = ROOT / "config" / "foundations_by_state.json"
    existing = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text()).get("states", {})
        except Exception:
            existing = {}
    states = config_states()
    data = dict(existing)
    for ab in sorted(states):
        try:
            cards = foundations_for_state(ab)
        except Exception as e:
            print(f"  WARN foundations {ab}: {e}", file=sys.stderr)
            cards = []
        if cards:
            data[ab] = cards
            print(f"  {ab}: {len(cards)} foundations")
        elif ab in existing:
            print(f"  {ab}: kept {len(existing[ab])} existing (pull empty)")
    if not data:
        print("No foundations pulled and none existing — leaving file untouched.", file=sys.stderr)
        sys.exit(1)
    out = {"source": "IRS Form 990-PF via ProPublica Nonprofit Explorer",
           "source_url": "https://projects.propublica.org/nonprofits/",
           "compiled": datetime.date.today().isoformat(),
           "method": "Largest private grantmaking foundations (NTEE T, 501(c)(3)) headquartered in each "
                     "food bank's state, ranked by total assets from the latest public 990-PF. Assets shown "
                     "because a private foundation must pay out ~5% of assets in grants a year. Open each on "
                     "grantmakers.io to see its actual giving history and judge food-relief fit before applying.",
           "states": data}
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Wrote config/foundations_by_state.json — {len(data)} states.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if mode == "grants":
            pull_grants()
        elif mode == "foundations":
            pull_foundations()
        else:
            raise SystemExit("usage: pull_funding.py grants|foundations")
    except SystemExit:
        raise
    except Exception as e:
        print(f"{mode} pull failed ({e}); keeping existing file.", file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env python3
"""CI link guard for the Food-Need Atlas.

Fails the build if any generated page sends the "mixed truckload" / order-builder
link anywhere other than the on-site /order page. This is the class of bug that
shipped twice: a truckload link pointing at foodaidproject.org instead of /order.

It checks BOTH ways the order URL reaches a page:
  1. Static <a> anchors whose visible text mentions "truckload" (briefs, home
     order CTA, nav) — their href must be the on-site order page.
  2. The embedded funding JSON on map pages: "order":{"url":"..."} — that url is
     what the map's "Build a truckload" button is built from at runtime, so it
     must be the on-site order page too.

Legitimate Food Aid Project links that are NOT the truckload builder (e.g. the
About page's "Talk to Food Aid Project" contact CTA) are left alone: they are
only flagged if their text mentions a truckload.

An "on-site order page" is "/order" or "https://foodbank-atlas.web.app/order".
"""
import glob
import re
import sys

DOCS = sys.argv[1] if len(sys.argv) > 1 else "docs"

# Accept the relative on-site path or the absolute on-site URL.
OK_URL = re.compile(r'^(/order(?:[/?#]|$)|https://foodbank-atlas\.web\.app/order(?:[/?#]|$))')

anchor = re.compile(r'<a\b[^>]*?href="([^"]*)"[^>]*>(.*?)</a>', re.I | re.S)
order_blob = re.compile(r'"order"\s*:\s*\{\s*"url"\s*:\s*"([^"]*)"')

bad = []

for path in sorted(glob.glob(f"{DOCS}/*.html")):
    html = open(path, encoding="utf-8").read()

    # 1) static truckload anchors. Skip JS template placeholders like
    #    href="${ORDERURL}" — those are filled at runtime from the embedded
    #    funding JSON, which is validated separately in check (2) below.
    for m in anchor.finditer(html):
        href, text = m.group(1).strip(), re.sub(r"<[^>]+>", "", m.group(2))
        if "${" in href:
            continue
        if re.search(r"truckload", text, re.I) and not OK_URL.match(href):
            bad.append((path, "anchor", text.strip()[:50], href))

    # 2) embedded funding order.url (map pages)
    for m in order_blob.finditer(html):
        url = m.group(1)
        if not OK_URL.match(url.strip()):
            bad.append((path, "funding.order.url", "(embedded)", url))

if bad:
    print("LINK GUARD FAILED — truckload/order link(s) not pointing to the on-site /order page:")
    for path, kind, text, url in bad:
        print(f"  {path} [{kind}] {text!r} -> {url}")
    sys.exit(1)

print("link guard OK — every truckload/order link points to the on-site /order page")

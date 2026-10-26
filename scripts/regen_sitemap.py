#!/usr/bin/env python3
"""MCH pSEO — rigenera apps/seo-farm/public/sitemap.xml dalla cartella content/ corrente.
URL: root + /oss/{slug} + /settore/{slug} + /confronto/{slug}. lastmod = oggi.
Uso: python3 scripts/regen_sitemap.py
"""
import os, datetime, glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(BASE, "apps", "seo-farm", "content")
OUT = os.path.join(BASE, "apps", "seo-farm", "public", "sitemap.xml")
DOMAIN = "https://mch-one.vercel.app"
TODAY = datetime.date.today().isoformat()

urls = [(DOMAIN, TODAY)]
for typ in ("oss", "settore", "confronto"):
    d = os.path.join(CONTENT, typ)
    if not os.path.isdir(d):
        continue
    for f in sorted(glob.glob(os.path.join(d, "*.md"))):
        slug = os.path.splitext(os.path.basename(f))[0]
        urls.append((f"{DOMAIN}/{typ}/{slug}", TODAY))

lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for loc, lm in urls:
    lines.append("  <url>")
    lines.append(f"    <loc>{loc}</loc>")
    lines.append(f"    <lastmod>{lm}</lastmod>")
    lines.append("  </url>")
lines.append("</urlset>")
with open(OUT, "w") as fh:
    fh.write("\n".join(lines) + "\n")
print(f"sitemap rigenerata: {len(urls)} URL → {OUT} (lastmod {TODAY})")

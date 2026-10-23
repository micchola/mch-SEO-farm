#!/usr/bin/env python3
"""MCH pSEO — generatore batch settoriale "solo nuovi" (giorno, qwen2.5:3b).
Genera 5 articoli settoriali i cui slug NON esistono ancora in content/settore/,
poi li copia in apps/seo-farm/content/settore/. Commit finale a cura dello script shell.
Uso: python3 scripts/make_new_sector_batch.py
"""
import os, sys, time, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_batch as gb

# Tutte le 15 coppie (ordine canonico del batch), filtrate su quelle non ancora generate
SECTORS = ["ristoranti", "palestre", "studi-medici", "parrucchieri", "ecommerce"]
CATEGORIES = ["crm", "pos", "gestionale", "email-marketing", "booking"]
pairs = [(c, s) for c in CATEGORIES for s in SECTORS[:3]]

out_dir = os.path.abspath(gb.OUT_DIR) + "/settore"
os.makedirs(out_dir, exist_ok=True)
existing = set(f.replace('.md', '') for f in os.listdir(out_dir) if f.endswith('.md'))
todo = [(c, s) for (c, s) in pairs if f"{c}-{s}" not in existing]
todo = todo[:5]

print(f"Settore batch: {len(todo)} nuovi da generare (skip {len(existing)} esistenti)")
results = []
for category, sector in todo:
    slug = f"{category}-{sector}"
    print(f"  → {slug}")
    prompt = gb.PROMPT_SECTOR_V2.format(category=category, sector=sector)
    t0 = time.time()
    content = gb.ollama(prompt, 1000)
    elapsed = time.time() - t0
    path = os.path.join(out_dir, f"{slug}.md")
    with open(path, 'w') as f:
        f.write(content)
    results.append(slug)
    print(f"    OK {elapsed:.0f}s")
    time.sleep(1)

# Copia in cartella Astro
import shutil
dest = os.path.join(os.path.dirname(os.path.abspath(gb.OUT_DIR)), "apps", "seo-farm", "content", "settore")
os.makedirs(dest, exist_ok=True)
for slug in results:
    shutil.copy2(os.path.join(out_dir, f"{slug}.md"), os.path.join(dest, f"{slug}.md"))
    print(f"  copied → apps/seo-farm/content/settore/{slug}.md")

print(f"DONE: {len(results)} new sector articles: {', '.join(results)}")

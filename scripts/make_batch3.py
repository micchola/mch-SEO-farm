#!/usr/bin/env python3
"""MCH pSEO — Batch 3 (23/10): 5 articoli settoriali NUOVI (combinazioni non ancora generate).
Estende il coverage a settori nuovi (agenzie-immobiliari, parrucchieri, studi-commerciali).
qwen2.5:3b. Poi: copia in apps/, sitemap, build, commit, attempt push (a cura dello step shell).
Uso: python3 scripts/make_batch3.py
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_batch as gb

# 5 combo NUOVI (non in content/settore/ — verifica fatta al run)
TARGETS = [
    ("gestionale", "agenzie-immobiliari"),   # settore nuovo: immobiliari
    ("crm", "parrucchieri"),                 # parrucchieri, crm
    ("booking", "agenzie-immobiliari"),      # agenzie, booking
    ("email-marketing", "parrucchieri"),     # parrucchieri, email
    ("gestionale", "studi-commerciali"),     # settore nuovo: studi commerciali
]

out_dir = os.path.abspath(gb.OUT_DIR) + "/settore"
os.makedirs(out_dir, exist_ok=True)
existing = set(f.replace('.md', '') for f in os.listdir(out_dir) if f.endswith('.md'))

todo = [(c, s) for (c, s) in TARGETS if f"{c}-{s}" not in existing]
print(f"Batch 3: {len(todo)} nuovi da generare (skip {len(existing)} esistenti)", flush=True)
if not todo:
    print("WARN: nessun nuovo combo — tutti i TARGETS già esistono", flush=True)

results = []
for category, sector in todo:
    slug = f"{category}-{sector}"
    print(f"  → {slug}", flush=True)
    prompt = gb.PROMPT_SECTOR_V2.format(category=category, sector=sector)
    t0 = time.time()
    content = gb.ollama(prompt, 1000)
    elapsed = time.time() - t0
    path = os.path.join(out_dir, f"{slug}.md")
    with open(path, 'w') as f:
        f.write(content)
    results.append(slug)
    print(f"    OK {elapsed:.0f}s ({len(content.split())} parole)", flush=True)
    time.sleep(1)

import shutil
dest = os.path.join(os.path.dirname(os.path.abspath(gb.OUT_DIR)), "apps", "seo-farm", "content", "settore")
os.makedirs(dest, exist_ok=True)
for slug in results:
    shutil.copy2(os.path.join(out_dir, f"{slug}.md"), os.path.join(dest, f"{slug}.md"))
    print(f"  copied → apps/seo-farm/content/settore/{slug}.md", flush=True)

json.dump(results, open(os.path.join(out_dir, "..", "batch3_new.json"), "w"))
print(f"DONE: {len(results)} nuovi: {', '.join(results)}", flush=True)

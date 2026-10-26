#!/usr/bin/env python3
"""MCH pSEO — Batch 4 (26/10): 5 articoli settoriali NUOVI (combinazioni non generate).
Estende il coverage a crm-estetisti, crm-studi-commerciali, booking-studi-dentistici,
booking-pizzerie, fidelizzazione-estetisti. qwen2.5:3b (daytime).
Poi: QC (placeholders/sezioni), copia in apps/, sitemap, build, commit, attempt push.
Uso: python3 scripts/make_batch4_pseo.py
"""
import os, sys, time, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_batch as gb

# 5 combo NUOVI (verifica: nessuno esiste in content/settore/)
TARGETS = [
    ("crm", "estetisti"),                 # crm-estetisti (outreach: estetisti)
    ("crm", "studi-commerciali"),         # crm-studi-commerciali (outreach: commercialisti)
    ("booking", "studi-dentistici"),      # booking-studi-dentistici
    ("booking", "pizzerie"),             # booking-pizzerie
    ("fidelizzazione", "estetisti"),      # fidelizzazione-estetisti
]

REQUIRED_SECTIONS = ["Tabella confronto", "FAQ", "Come scegliere", "consiglio"]
PLACEHOLDER_RE = re.compile(r"\[Tool\]|\[tool\]|\[LINK AFFILIATE\]|\[\w+\]", re.IGNORECASE)

out_dir = os.path.abspath(gb.OUT_DIR) + "/settore"
os.makedirs(out_dir, exist_ok=True)
existing = set(f.replace('.md', '') for f in os.listdir(out_dir) if f.endswith('.md'))

todo = [(c, s) for (c, s) in TARGETS if f"{c}-{s}" not in existing]
print(f"Batch 4: {len(todo)} nuovi da generare (skip {len(existing)} esistenti)", flush=True)
if not todo:
    print("WARN: nessun nuovo combo — tutti i TARGETS già esistono", flush=True)
    sys.exit(0)

results, qc = [], []
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
    words = len(content.split())
    ph = PLACEHOLDER_RE.findall(content)
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    status = "ok"
    if words < 300 or ph:
        status = "low-quality"
    qc.append({"slug": slug, "words": words, "placeholders": ph, "missing_sections": missing,
               "seconds": round(elapsed), "status": status})
    results.append(slug)
    print(f"    OK {elapsed:.0f}s ({words} parole, placeholders={len(ph)}, miss_sect={missing})", flush=True)
    time.sleep(1)

# QC gate: rigenera gli articoli di qualità bassa (1 retry)
for item in qc:
    if item["status"] != "ok":
        print(f"  RETRY {item['slug']} (low-quality) ...", flush=True)
        c, s = item["slug"].split("-", 1)
        prompt = gb.PROMPT_SECTOR_V2.format(category=c, sector=s)
        t0 = time.time()
        content = gb.ollama(prompt, 1000)
        path = os.path.join(out_dir, f"{item['slug']}.md")
        with open(path, 'w') as f:
            f.write(content)
        words = len(content.split())
        ph = PLACEHOLDER_RE.findall(content)
        item["words"] = words
        item["placeholders"] = ph
        item["status"] = "ok" if words >= 300 and not ph else "still-low"
        item["retried"] = True
        print(f"    RETRY {item['slug']}: {words} parole, placeholders={len(ph)} → {item['status']}", flush=True)

# Copia in cartella Astro
import shutil
dest = os.path.join(os.path.dirname(os.path.abspath(gb.OUT_DIR)), "apps", "seo-farm", "content", "settore")
os.makedirs(dest, exist_ok=True)
for slug in results:
    shutil.copy2(os.path.join(out_dir, f"{slug}.md"), os.path.join(dest, f"{slug}.md"))
    print(f"  copied → apps/seo-farm/content/settore/{slug}.md", flush=True)

json.dump(results, open(os.path.join(out_dir, "..", "batch4_new.json"), "w"))
json.dump(qc, open(os.path.join(out_dir, "..", "batch4_qc.json"), "w"))
ok = sum(1 for q in qc if q["status"] == "ok")
print(f"DONE: {len(results)} nuovi: {', '.join(results)} | QC ok {ok}/{len(qc)}", flush=True)

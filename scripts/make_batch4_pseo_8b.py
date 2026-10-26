#!/usr/bin/env python3
"""MCH pSEO — Batch 4 regeneration con qwen3:8b (think-off) quando il 3B daytime lascia
placeholder / liste incomplete. Stessi 5 slugs di make_batch4_pseo.py ma col modello 8B:
struttura completa (10 tool + tabella + FAQ, 0 placeholder). Overwrites i file 3B.
Uso: OLLAMA_URL=http://127.0.0.1:11434 python3 scripts/make_batch4_pseo_8b.py
"""
import os, sys, time, json, re, urllib.request, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_batch as gb

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:8b-q4_K_M')
# Difetti REALI: [Tool]/[tool] (nome vuoto) e €X (prezzo non compilato).
# [LINK AFFILIATE] è TOLLERATO (baseline di tutto il content base, tag in attesa approvazione).
BADPH_RE = re.compile(r"\[Tool\]|\[tool\]|€X", re.IGNORECASE)

TARGETS = [
    ("crm", "estetisti"),
    ("crm", "studi-commerciali"),
    ("booking", "studi-dentistici"),
    ("booking", "pizzerie"),
    ("fidelizzazione", "estetisti"),
]

def ollama8b(prompt, num_predict=2400):
    payload = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False, "think": False,
        "options": {"num_ctx": 8192, "num_predict": num_predict, "temperature": 0.6}
    })
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=payload.encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1500) as resp:
        return json.load(resp).get('response', '')

out_dir = os.path.abspath(gb.OUT_DIR) + "/settore"
os.makedirs(out_dir, exist_ok=True)

results, qc = [], []
def is_good(content):
    words = len(content.split())
    tools = len(re.findall(r"^###\s*[0-9]", content, re.MULTILINE)) or \
            len(re.findall(r"^\d+\.\s+\*\*", content, re.MULTILINE))
    has_table = "Tabella confronto" in content or bool(re.search(r"^\|.*\|.*\|", content, re.MULTILINE))
    has_faq = "FAQ" in content
    badph = len(BADPH_RE.findall(content))
    good = words >= 400 and tools >= 8 and has_table and has_faq and badph == 0
    return good, words, tools, badph

for category, sector in TARGETS:
    slug = f"{category}-{sector}"
    path = os.path.join(out_dir, f"{slug}.md")
    # Skip-if-good: se il file esiste e passa QC (8B precedente o 3B già buono), non rigenerare.
    if os.path.exists(path) and os.path.getsize(path) > 500:
        good, w, t, b = is_good(open(path).read())
        if good:
            print(f"  skip [8B] {slug} — già buono ({w}w, {t} tool)", flush=True)
            qc.append({"slug": slug, "words": w, "tools": t, "badph": b,
                      "seconds": 0, "status": "skipped-good"})
            results.append(slug)
            continue
    print(f"  → [8B] {slug}", flush=True)
    prompt = gb.PROMPT_SECTOR_V2.format(category=category, sector=sector)
    t0 = time.time()
    content = ollama8b(prompt, 2400)
    elapsed = time.time() - t0
    with open(path, 'w') as f:
        f.write(content)
    good, words, tools, badph = is_good(content)
    qc.append({"slug": slug, "words": words, "tools": tools, "badph": badph,
               "seconds": round(elapsed), "status": "ok" if good else "low"})
    print(f"    {elapsed:.0f}s — {words}w, {tools} tool, badph={badph} → {qc[-1]['status']}", flush=True)
    results.append(slug)
    time.sleep(1)

# QC gate: retry SOLO i difetti reali (€X / [Tool] / struttura incompleta), num_predict più alto
for item in qc:
    if item["status"] != "low":
        continue
    c, s = item["slug"].split("-", 1)
    print(f"  RETRY [8B] {item['slug']} ...", flush=True)
    content = ollama8b(gb.PROMPT_SECTOR_V2.format(category=c, sector=s), 3000)
    with open(os.path.join(out_dir, f"{item['slug']}.md"), 'w') as f:
        f.write(content)
    good, words, tools, badph = is_good(content)
    item["words"] = words; item["tools"] = tools; item["badph"] = badph; item["retried"] = True
    item["status"] = "ok" if good else "still-low"
    print(f"    RETRY {item['slug']}: {words}w, {tools} tool, badph={badph} → {item['status']}", flush=True)

# Copia in cartella Astro
dest = os.path.join(os.path.dirname(os.path.abspath(gb.OUT_DIR)), "apps", "seo-farm", "content", "settore")
os.makedirs(dest, exist_ok=True)
for slug in results:
    shutil.copy2(os.path.join(out_dir, f"{slug}.md"), os.path.join(dest, f"{slug}.md"))
    print(f"  copied → apps/seo-farm/content/settore/{slug}.md", flush=True)

json.dump(qc, open(os.path.join(out_dir, "..", "batch4_qc_8b.json"), "w"))
ok = sum(1 for q in qc if q["status"] == "ok")
print(f"DONE [8B]: {len(results)} rigenerati | QC ok {ok}/{len(qc)}", flush=True)

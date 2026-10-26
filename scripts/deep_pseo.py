#!/usr/bin/env python3
"""
MCH pSEO Deep — 5 articoli su keyword a volume (keyword gap vs contenuti esistenti).
Ollama qwen2.5:3b. Output: content/settore/*.md
Uso: python3 deep_pseo.py [NUM]
"""
import json, os, sys, time, urllib.request

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b')
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'content', 'settore')

# (slug, keyword volume-alta, categoria, settore) — evitano i 13 già in content/settore
TOPICS = [
    ("booking-palestre", "software booking online palestre", "booking", "palestre"),
    ("booking-studi-medici", "software prenotazioni studi medici", "booking", "studi medici"),
    ("gestionale-parrucchieri", "software gestionale parrucchieri", "gestionale", "parrucchieri"),
    ("crm-agenzie-immobiliari", "crm agenzia immobiliare", "crm", "agenzie immobiliari"),
    ("crm-ecommerce", "crm per e-commerce", "crm", "e-commerce"),
    # Batch deep-research 2026-10-23: keyword a volume, allineate ai settori outreach (fabbri/estetisti/parrucchieri/e-commerce)
    ("booking-parrucchieri", "software prenotazioni online parrucchieri", "booking", "parrucchieri"),
    ("booking-estetisti", "software booking estetisti e saloni", "booking", "estetisti"),
    ("gestionale-artigiani", "software gestione preventivi artigiani", "gestionale", "artigiani (fabbri, idraulici, elettricisti)"),
    ("ecommerce-pmi", "piattaforme e-commerce per pmi italiane", "e-commerce", "e-commerce"),
    ("marketing-automation-pmi", "software marketing automation per pmi", "marketing", "pmi"),
    # Batch deep-research 2026-10-24: keyword a volume, settori nuovi (dentisti, pizzerie, b&b, fedeltà, agenzie)
    ("gestionale-studi-dentistici", "software gestionale studi dentistici", "gestionale", "studi dentistici"),
    ("gestionale-pizzerie", "software gestionale pizzerie e forni", "gestionale", "pizzerie"),
    ("email-marketing-agenzie-immobiliari", "software email marketing agenzie immobiliari", "email marketing", "agenzie immobiliari"),
    ("software-bnb", "software gestione b&b e affittacamere", "gestionale", "b&b e affittacamere"),
    ("fidelizzazione-pmi", "software fedelta e fidelizzazione clienti per pmi", "marketing", "pmi"),
    # Batch deep-research 2026-10-25: settori nuovi outreach (idraulici, fabbri) + keyword generiche a volume
    ("software-idraulici", "software gestione preventivi idraulici", "gestionale", "idraulici"),
    ("gestionale-fabbri", "software gestionale per fabbri e serramenti", "gestionale", "fabbri"),
    ("crm-pmi", "software crm per pmi italiane", "crm", "pmi"),
    ("software-preventivi-pmi", "programmi per preventivi per pmi", "gestionale", "pmi"),
    ("gestionale-estetisti", "software gestionale estetisti e saloni di bellezza", "gestionale", "estetisti"),
]

PROMPT = """Sei un redattore SEO italiano. Scrivi UN articolo COMPLETO in italiano di minimo 550 parole,
keyword target: "{kw}" (settore: {sector}).

Struttura obbligatoria (tutte le sezioni, in quest'ordine):
# I 10 migliori software {category} per {sector} in Italia (2026)
Intro (2-3 frasi)
## Come scegliere
3 criteri pratici
## I 10 tool
### 1. [Tool]  (fino a ### 10., ognuna 3-4 righe con Prezzo, Pro, Contro)
## Tabella confronto
| Tool | Prezzo | Pro | Contro |
## Il nostro consiglio
- Per chi sta partendo: [tool entry]
- Per chi scala: [tool pro]
## FAQ
3 domande con risposta breve

Regole ferree:
- NON ripetere sezioni già scritte
- Completa TUTTI E 10 I tool (mai fermarti a metà lista)
- Prezzi in EUR, realistici
- Tono pratico, SEO, niente esagerazioni
- H1 con la keyword "{kw}"
- Termina sempre con la sezione FAQ"""

def ollama(prompt, max_tokens=1400):
    payload = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False, "think": False,
        "options": {"num_ctx": 4096, "num_predict": 2400, "temperature": 0.7}
    })
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=payload.encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1500) as resp:
        return json.load(resp).get('response', '')

def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    os.makedirs(OUT_DIR, exist_ok=True)
    results = []
    for slug, kw, cat, sector in TOPICS[:count]:
        path = os.path.abspath(os.path.join(OUT_DIR, f"{slug}.md"))
        if os.path.exists(path) and os.path.getsize(path) > 500:
            print(f"  skip (esiste): {slug}")
            results.append({'slug': slug, 'path': path, 'status': 'exists'})
            continue
        t0 = time.time()
        content = ollama(PROMPT.format(kw=kw, sector=sector, category=cat))
        if len(content) < 300:
            print(f"  FALLITO ({len(content)} char): {slug}")
            results.append({'slug': slug, 'path': path, 'status': 'failed', 'len': len(content)})
            continue
        with open(path, 'w') as f:
            f.write(content)
        el = time.time() - t0
        print(f"  ok {slug} → {path} ({el:.0f}s, {len(content)} char)")
        results.append({'slug': slug, 'path': path, 'status': 'ok', 'seconds': el})
        time.sleep(1)
    print(json.dumps(results, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()

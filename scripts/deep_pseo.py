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
]

PROMPT = """Sei un redattore SEO italiano. Scrivi un articolo in italiano, 600-900 parole,
keyword target: "{kw}" (settore: {sector}).

Struttura:
# I 10 migliori software {category} per {sector} in Italia (2026)

## Come scegliere
3 criteri pratici

## I 10 tool
### 1. [Tool]
- Prezzo: da €X/mese
- Pro / Contro (2-3 ciascuno)

## Tabella confronto
| Tool | Prezzo | Pro | Contro |

## Il nostro consiglio
- Per chi sta partendo: [tool entry]
- Per chi scala: [tool pro]

## FAQ
3 domande

---
*Articolo generato con AI. Aggiornato Ottobre 2026.*

Regole:
- Prezzi in EUR, realistici
- Tono pratico, SEO, niente esagerazioni
- H1 con la keyword "{kw}"
"""

def ollama(prompt, max_tokens=1100):
    payload = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"num_ctx": 4096, "num_predict": max_tokens, "temperature": 0.7}
    })
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=payload.encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=420) as resp:
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

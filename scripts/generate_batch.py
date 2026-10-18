#!/usr/bin/env python3
"""
MCH pSEO — Batch generator v2
Genera un batch di articoli con CTA affiliate per il primo cash flow.
Uso: python3 scripts/generate_batch.py [--count N] [--type oss|sector|comparison|all]
"""
import json, os, sqlite3, sys, time, urllib.request, argparse

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'packages', 'data', 'data.db')
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'content')

# Affiliate programs (da aggiornare quando Michele ha i tag)
AFFILIATE = {
    'hubspot': {
        'name': 'HubSpot',
        'url': 'https://hubspot.com/start-free-trial? affiliate=mch0b4-21',  # TODO: sostituire
        'commission': '20% ricorrente',
    },
    'clickup': {
        'name': 'ClickUp',
        'url': 'https://clickup.com?ref=YOUR_TAG',
        'commission': '15% ricorrente',
    },
    'shopify': {
        'name': 'Shopify',
        'url': 'https://shopify.com/affiliates',
        'commission': '100-200€/signup',
    },
    'notion': {
        'name': 'Notion',
        'url': 'https://notion.so',
        'commission': 'N/A (no affiliate)',
    },
}

# Prompt arricchito con CTA affiliate
PROMPT_OSS_V2 = """Sei un redattore SEO italiano. Scrivi un articolo in italiano, 500-800 parole,
argomento: "Alternative open source a {tool_name}".

Struttura:
# Alternative open source a {tool_name}: le migliori del 2026

## Che cos'è {tool_name}
Breve descrizione (2-3 righe)

## Perché cercare alternative open source
2-3 motivi concreti

## Le migliori alternative open source
### 1. [Repo 1]
- Descrizione, licenza, pro/contro
### 2. [Repo 2]
(ditto)

## Confronto rapido
Tabella markdown

## La scelta giusta per te
- Se vuoi zero costi e privacy: [repo migliore]
- Se preferisci un tool commerciale: {tool_name} → [CTA LINK]

## FAQ
3 domande brevi con risposta

---
*Articolo generato con AI. Fonte: GitHub API. Aggiornato Ottobre 2026.*

Regole:
- Includi 1-2 link ad affiliate program (HubSpot, Shopify) dove pertinenti
- Tono pratico, SEO, niente esagerazioni
- Ogni assert deve avere una fonte (link al repo GitHub)
"""

PROMPT_SECTOR_V2 = """Sei un redattore SEO italiano. Scrivi un articolo in italiano, 600-1000 parole,
argomento: "I 10 migliori software {category} per {sector} in Italia (2026)".

Struttura:
# I 10 migliori software {category} per {sector} in Italia nel 2026

## Come scegliere
3 criteri pratici

## I 10 tool
### 1. [Tool]
- Prezzo: da €X/mese
- Pro / Contro (2-3 ciascuno)
- [LINK AFFILIATE SE PRESENTE]

## Tabella confronto
| Tool | Prezzo | Pro | Contro |

## Il nostro consiglio
- Per chi sta partendo: [tool entry]
- Per chi scala: [tool pro]

## FAQ
3 domande

---
*Articolo generato con AI. Aggiornato Ottobre 2026. [DISCLAIMER AFFILIATE]*

Regole:
- Prezzi in EUR, realistici
- CTA affiliate su 2-3 tool (HubSpot, ClickUp, Shopify)
- SEO: H1 con "miglior software {category} per {sector}"
"""

PROMPT_COMPARISON_V2 = """Sei un redattore SEO italiano. Scrivi un articolo in italiano, 600-900 parole,
argomento: "{tool_a} vs {tool_b}: quale scegliere nel 2026".

Struttura:
# {tool_a} vs {tool_b}: quale scegliere nel 2026

## Differenza chiave
1 riga

## {tool_a}
Punti di forza + [LINK AFFILIATE]

## {tool_b}
Punti di forza + [LINK AFFILIATE]

## Tabella confronto
| Aspetto | {tool_a} | {tool_b} |
Prezzo, Feature, Facilità, Supporto, Integrazioni

## Quale scegliere?
### Scegli {tool_a} se:
### Scegli {tool_b} se:

## Verdetto
2 righe

---
*Articolo generato con AI. Aggiornato Ottobre 2026. [DISCLAIMER AFFILIATE]*
"""


def ollama(prompt, max_tokens=800):
    """Generate with Ollama (3B model, ~90s per call)."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 2048, "num_predict": max_tokens, "temperature": 0.7}
    })
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload.encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.load(resp)
    return result.get('response', '')


def generate_batch(type_, count, conn):
    """Generate a batch of articles."""
    base_out = os.path.abspath(OUT_DIR)
    results = []

    if type_ in ('oss', 'all'):
        out_dir = os.path.join(base_out, 'oss')
        os.makedirs(out_dir, exist_ok=True)
        cur = conn.cursor()
        # Get tools that don't have articles yet
        existing = set(f.replace('.md','') for f in os.listdir(out_dir) if f.endswith('.md')) if os.path.exists(out_dir) else set()
        if existing:
            placeholders = ','.join(['?']*len(existing))
            tools = cur.execute(
                f"SELECT slug, name FROM tools WHERE slug NOT IN ({placeholders}) LIMIT ?",
                list(existing) + [count]
            ).fetchall()
        else:
            tools = cur.execute("SELECT slug, name FROM tools LIMIT ?", (count,)).fetchall()

        for slug, name in tools:
            print(f"  → OSS: {name} ({slug})")
            prompt = PROMPT_OSS_V2.format(tool_name=name)
            t0 = time.time()
            content = ollama(prompt, 1000)
            elapsed = time.time() - t0
            path = os.path.join(out_dir, f"{slug}.md")
            with open(path, 'w') as f:
                f.write(content)
            results.append({'type': 'oss', 'slug': slug, 'path': path, 'time': elapsed})
            print(f"    ✅ {elapsed:.0f}s")
            time.sleep(1)

    if type_ in ('sector', 'all'):
        out_dir = os.path.join(base_out, 'settore')
        os.makedirs(out_dir, exist_ok=True)
        sectors = ["ristoranti", "palestre", "studi-medici", "parrucchieri", "ecommerce"]
        categories = ["crm", "pos", "gestionale", "email-marketing", "booking"]
        pairs = [(c, s) for c in categories for s in sectors[:3]]
        for category, sector in pairs[:count]:
            slug = f"{category}-{sector}"
            print(f"  → Settorale: {category} × {sector}")
            prompt = PROMPT_SECTOR_V2.format(category=category, sector=sector)
            t0 = time.time()
            content = ollama(prompt, 1000)
            elapsed = time.time() - t0
            path = os.path.join(out_dir, f"{slug}.md")
            with open(path, 'w') as f:
                f.write(content)
            results.append({'type': 'settore', 'slug': slug, 'path': path, 'time': elapsed})
            print(f"    ✅ {elapsed:.0f}s")
            time.sleep(1)

    if type_ in ('comparison', 'all'):
        out_dir = os.path.join(base_out, 'confronto')
        os.makedirs(out_dir, exist_ok=True)
        cur = conn.cursor()
        rows = cur.execute("""
            SELECT c.slug, a.name, b.name
            FROM comparisons c
            JOIN tools a ON c.tool_a_id = a.id
            JOIN tools b ON c.tool_b_id = b.id
            LIMIT ?
        """, (count,)).fetchall()
        for slug, tool_a, tool_b in rows:
            print(f"  → Confronto: {tool_a} vs {tool_b}")
            prompt = PROMPT_COMPARISON_V2.format(tool_a=tool_a, tool_b=tool_b)
            t0 = time.time()
            content = ollama(prompt, 1000)
            elapsed = time.time() - t0
            path = os.path.join(out_dir, f"{slug}.md")
            with open(path, 'w') as f:
                f.write(content)
            results.append({'type': 'confronto', 'slug': slug, 'path': path, 'time': elapsed})
            print(f"    ✅ {elapsed:.0f}s")
            time.sleep(1)

    return results


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--count', type=int, default=3, help='Articoli per nicchia')
    ap.add_argument('--type', choices=['oss', 'sector', 'comparison', 'all'], default='all')
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    print(f"🚀 Batch generation — {args.type} × {args.count} — modello: {OLLAMA_MODEL}")
    print(f"   Stima tempo: ~{args.count * 3 * 90}s (90s per articolo)\n")

    results = generate_batch(args.type, args.count, conn)
    conn.close()

    total_time = sum(r['time'] for r in results)
    print(f"\n✅ Batch completato: {len(results)} articoli in {total_time:.0f}s")
    for r in results:
        print(f"   {r['type']:10s} {r['slug']}  ({r['time']:.0f}s)")

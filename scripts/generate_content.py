#!/usr/bin/env python3
"""
MCH pSEO — Content Generator
Genera articoli markdown usando Ollama (Qwen 3 8B locale).
Output: content/oss-alternatives/{slug}.md
        content/sector-software/{category}-{sector}.md
        content/tool-comparisons/{slug}.md
"""
import json, os, re, sqlite3, sys, time, urllib.request

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'packages', 'data', 'data.db')
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'content')

# ─── Prompt template per NICCHIA 1: OSS alternatives ───────────────────────
PROMPT_OSS = """Sei un redattore SEO italiano. Scrivi un articolo in italiano, 500-800 parole,
sugli argomenti: "Alternative open source a {tool_name}".

Struttura:
# Alternative open source a {tool_name}: le migliori del 2026

## Che cos'è {tool_name}
Breve descrizione (2-3 righe)

## Perché cercare alternative open source
2-3 motivi concreti

## Le migliori alternative open source
### 1. {repo_1}
- Descrizione: {desc_1}
- Licenza: {license_1}
- Pro: ...
- Contro: ...

### 2. {repo_2}
(ditto)

### 3. {repo_3}
(ditto)

## Confronto rapido
Tabella markdown: Tool | Licenza | Lingua | Stars | Ultima release

## Conclusione
2 righe

---
*Articolo generato con AI. Fonte dati: GitHub API. Licenza: CC BY-SA 4.0.*

Regole:
- Tono professionale ma accessibile
- SEO: H1 con keyword, H2 con varianti
- Nessuna esagerazione, nessuna bugia sui dati
- Includi link ai repo GitHub
"""

# ─── Prompt template per NICCHIA 2: Software per settore ────────────────────
PROMPT_SECTOR = """Sei un redattore SEO italiano. Scrivi un articolo in italiano, 600-1000 parole,
sugli argomenti: "I 10 migliori software {category} per {sector} in Italia (2026)".

Struttura:
# I 10 migliori software {category} per {sector} in Italia nel 2026

## Come scegliere il software giusto
3 criteri pratici

## I 10 migliori [tool per settore]
### 1. [Tool Name]
- Prezzo: da €X/mese
- Pro: ...
- Contro: ...
- Ideale per: ...

(rileva fino a 10 tool noti nel settore {sector} per categoria {category})

## Tabella di confronto
Tabella markdown: Tool | Prezzo | Pro principale | Contro principale

## Cose da considerare
3-4 avvisi pratici

## Conclusione
2 righe

---
*Articolo generato con AI. Aggiornato {month_year}.*

Regole:
- Tono professionale, orientato alla pratica
- Prezzi realistici in EUR
- SEO: H1 con keyword "miglior software {category} per {sector}"
- Ogni tool con 2-3 pro e 1-2 contro concreti
"""

# ─── Prompt template per NICCHIA 3: Comparazioni ─────────────────────────────
PROMPT_COMPARISON = """Sei un redattore SEO italiano. Scrivi un articolo in italiano, 600-900 parole,
sugli argomenti: "{tool_a} vs {tool_b}: quale scegliere nel 2026".

Struttura:
# {tool_a} vs {tool_b}: quale scegliere nel 2026

## Differenza fondamentale
1 riga: la differenza chiave tra i due

## {tool_a}: punti di forza
3-4 punti con dettagli

## {tool_b}: punti di forza
3-4 punti con dettagli

## Confronto diretto
Tabella markdown: | Caratteristica | {tool_a} | {tool_b} |
(Riga per: Prezzo, Funzionalità chiave, Facilità d'uso, Supporto, Integrazioni)

## Quale scegliere?
### Scegli {tool_a} se:
3 bullet
### Scegli {tool_b} se:
3 bullet

## Conclusione
2 righe

---
*Articolo generato con AI. Aggiornato {month_year}.*

Regole:
- Tono oggettivo, nessuna forzatura
- SEO: H1 con "X vs Y"
- Dati realistici (prezzi, feature note)
- Utile per chi è indeciso
"""


def ollama_generate(prompt, max_tokens=1500):
    """Chiamata Ollama per generare il contenuto."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 4096, "num_predict": max_tokens, "temperature": 0.7}
    })
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload.encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        result = json.load(resp)
    return result.get('response', '')


def generate_oss(conn, out_dir, limit=5):
    """Genera articoli per le alternative OSS."""
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT t.slug, t.name, oa.repo_name, oa.stars, oa.license, oa.description
        FROM tools t
        JOIN oss_alternatives oa ON t.id = oa.saas_tool_id
        GROUP BY t.id
        ORDER BY t.name
        LIMIT ?
    """, (limit,)).fetchall()

    os.makedirs(out_dir, exist_ok=True)
    for slug, name, repo, stars, license, desc in rows:
        prompt = PROMPT_OSS.format(
            tool_name=name,
            repo_1=repo, desc_1=desc, license_1=license
        )
        print(f"  → Generando: {slug} (tool: {name})")
        content = ollama_generate(prompt)
        path = os.path.join(out_dir, f"{slug}.md")
        with open(path, 'w') as f:
            f.write(content)
        print(f"  ✅ {path}")
        time.sleep(1)


def generate_sectors(conn, out_dir, limit=5):
    """Genera articoli per categoria × settore."""
    sectors = ["ristoranti", "palestre", "studi-medici", "parrucchieri"]
    categories = ["crm", "pos", "erp", "email-marketing", "booking"]

    pairs = [(c, s) for s in sectors for c in categories[:limit]]
    os.makedirs(out_dir, exist_ok=True)

    for category, sector in pairs[:limit]:
        prompt = PROMPT_SECTOR.format(
            category=category, sector=sector,
            month_year="Ottobre 2026"
        )
        slug = f"{category}-{sector}"
        print(f"  → Generando: {slug}")
        content = ollama_generate(prompt)
        path = os.path.join(out_dir, f"{slug}.md")
        with open(path, 'w') as f:
            f.write(content)
        print(f"  ✅ {path}")
        time.sleep(1)


def generate_comparisons(conn, out_dir, limit=5):
    """Genera articoli di confronto."""
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT c.slug, a.name, b.name
        FROM comparisons c
        JOIN tools a ON c.tool_a_id = a.id
        JOIN tools b ON c.tool_b_id = b.id
        LIMIT ?
    """, (limit,)).fetchall()

    os.makedirs(out_dir, exist_ok=True)
    for slug, tool_a, tool_b in rows:
        prompt = PROMPT_COMPARISON.format(
            tool_a=tool_a, tool_b=tool_b, month_year="Ottobre 2026"
        )
        print(f"  → Generando: {tool_a} vs {tool_b}")
        content = ollama_generate(prompt)
        path = os.path.join(out_dir, f"{slug}.md")
        with open(path, 'w') as f:
            f.write(content)
        print(f"  ✅ {path}")
        time.sleep(1)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--type', choices=['oss', 'sector', 'comparison', 'all'], default='all')
    ap.add_argument('--limit', type=int, default=3)
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    base_out = os.path.abspath(OUT_DIR)

    print(f"🖊️  Generazione contenuti — modello: {OLLAMA_MODEL}")
    print(f"   Ollama: {OLLAMA_URL}")

    if args.type in ('oss', 'all'):
        print("\n📦 Nicchia OSS...")
        generate_oss(conn, os.path.join(base_out, 'oss-alternatives'), args.limit)

    if args.type in ('sector', 'all'):
        print("\n🏢 Nicchia Settori...")
        generate_sectors(conn, os.path.join(base_out, 'sector-software'), args.limit)

    if args.type in ('comparison', 'all'):
        print("\n⚔️  Nicchia Confronti...")
        generate_comparisons(conn, os.path.join(base_out, 'tool-comparisons'), args.limit)

    conn.close()
    print("\n✅ Generazione completata")

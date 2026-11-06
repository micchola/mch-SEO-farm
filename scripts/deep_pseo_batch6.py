#!/usr/bin/env python3
"""MCH pSEO — Deep Research notturno (one-shot).
Genera 5 nuovi articoli pSEO settoriali su keyword a volume NON ancora presenti in
content/settore, con Ollama qwen3:8b (think off, num_ctx 4096 / 3000 tokens / timeout 1500s — tuning 01/11 anti-timeout CPU N95).
Riutilizza PROMPT_SECTOR_V2 di generate_batch.py.
Nessuna modifica agli script esistenti: è un runner standalone.
Uso: cd /home/impact/mch/seo-farm && OLLAMA_MODEL=qwen3:8b-q4_K_M python3 scripts/deep_pseo_batch6.py
"""
import json, os, sys, time, urllib.request, shutil
import generate_batch as gb

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:8b-q4_K_M')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))

SETTORE = os.path.join(REPO, 'content', 'settore')
APPS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'apps', 'seo-farm', 'content', 'settore'))
os.makedirs(SETTORE, exist_ok=True)

# Candidati (categoria, settore) su keyword a volume. Filtra quelli già esistenti
# in content/settore e prende i primi 5 nuovi.
CANDIDATI = [
    ('crm', 'veterinari'),
    ('gestionale', 'fisioterapisti'),
    ('booking', 'barbieri'),
    ('crm', 'concessionari-auto'),
    ('fidelizzazione', 'bar'),
    ('email-marketing', 'farmacie'),
    ('gestionale', 'veterinari'),
    ('fidelizzazione', 'pasticcerie'),
    ('booking', 'farmacie'),
]
N_CERCATI = 5

def ollama_call(prompt, max_tokens=3000, retries=3):
    last = ''
    for attempt in range(retries):
        try:
            payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt,
                                  "stream": False, "think": False,
                                  "options": {"num_ctx": 4096, "num_predict": max_tokens,
                                              "temperature": 0.7}})
            req = urllib.request.Request(f"{OLLAMA_URL}/api/generate",
                data=payload.encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=1500) as r:
                result = json.load(r)
            last = result.get('response', '')
            if len(last) >= 300:
                return last
            print(f'  ⚠️ output corto ({len(last)} chars) — retry {attempt+1}/{retries}', file=sys.stderr)
            time.sleep(5)
        except Exception as e:
            print(f'  ❌ Ollama: {e} — retry {attempt+1}/{retries}', file=sys.stderr)
            time.sleep(30)
    return last

def qc_fatal(text):
    """Controlli STRUTTURALI: se falliscono l'articolo è incompleto → NON viene scritto."""
    issues = []
    words = len(text.split())
    if words < 400:
        issues.append(f'word_count={words}')
    n_h2 = text.count('\n## ')
    if n_h2 < 3:
        issues.append(f'h2={n_h2}')
    if '|' not in text:
        issues.append('no_table')
    if 'FAQ' not in text and 'Domande' not in text:
        issues.append('no_faq')
    return issues

def qc_warn(text):
    """Controlli COSMETICI (placeholder, terminologia): solo warning, NON bloccanti.
    L'articolo viene scritto comunque; i placeholder residui si puliscono in post-processing."""
    warns = []
    for p in ('TOOL_X', 'TOOL_1', 'TOOL_2', '[link]', '[LINK', '[Tool]', '[tool]', '[tool entry]', '[tool pro]', '[DISCLAIMER', '[X]'):
        if p in text:
            warns.append(f'placeholder {p}')
    if 'software' not in text.lower():
        warns.append('missing software')
    return warns

def main():
    existing = {f[:-3] for f in os.listdir(SETTORE) if f.endswith('.md')}
    targets = [(c, s) for (c, s) in CANDIDATI if f'{c}-{s}' not in existing][:N_CERCATI]
    print(f'🚀 Deep pSEO — {OLLAMA_MODEL} — {len(targets)} nuovi target (di {len(CANDIDATI)} candidati)')
    for c, s in targets:
        print(f'   → {c}-{s}')
    if len(targets) < N_CERCATI:
        print(f'⚠️ meno di {N_CERCATI} nuovi candidati', file=sys.stderr)

    ok, fail, overwrote = 0, 0, 0
    for i, (category, sector) in enumerate(targets, 1):
        slug = f'{category}-{sector}'
        path = os.path.join(SETTORE, f'{slug}.md')
        prompt = gb.PROMPT_SECTOR_V2.format(category=category, sector=sector)
        t0 = time.time()
        content = ollama_call(prompt, 3000, retries=3)
        elapsed = time.time() - t0
        fatal = qc_fatal(content)
        warns = qc_warn(content)
        if fatal:
            fail += 1
            print(f'  [{i}/{len(targets)}] {slug} ⚠️ QC-fatal: {fatal} ({elapsed:.0f}s) — NON scritto', file=sys.stderr)
            continue
        existed = os.path.exists(path)
        with open(path, 'w') as f:
            f.write(content)
        ok += 1
        if warns:
            print(f'  [{i}/{len(targets)}] {slug} ℹ️ QC-warn: {warns} — scritto comunque', file=sys.stderr)
        if os.path.isdir(APPS):
            app_path = os.path.join(APPS, f'{slug}.md')
            existed_app = os.path.exists(app_path)
            shutil.copy2(path, app_path)
            if existed_app:
                overwrote += 1
                print(f'  ({slug}: overwrite su apps)', file=sys.stderr)
            print(f'  [{i}/{len(targets)}] {slug} ✅ ({elapsed:.0f}s, {len(content.split())} parole, {len(content):,} chars)')
        else:
            print(f'  [{i}/{len(targets)}] {slug} ✅ (solo content/, apps/ assente)')
    print(f'\n📊 Deep pSEO batch6: {ok} OK, {fail} QC-fail, {overwrote} overwrote (target {N_CERCATI})')
    print(f'   → {SETTORE} (+ copy su {APPS})')

if __name__ == '__main__':
    main()

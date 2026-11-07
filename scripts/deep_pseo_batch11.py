#!/usr/bin/env python3
"""MCH pSEO — Deep Research batch11 (deep night 22:00, 06/11).
Genera 5 nuovi articoli pSEO settoriali su keyword a volume NON ancora presenti in
content/settore (88 slug al momento), con Ollama qwen3:8b-q4_K_M (think off,
num_ctx 4096 / 3000 tokens / timeout 1500s — tuning anti-timeout CPU N95).
QC gate (parole>=400, h2>=3, tabella, FAQ, placeholder) + QC-warn.
Sincronizza content/settore -> apps/seo-farm/content/settore.
Uso: cd /home/impact/mch/seo-farm && OLLAMA_MODEL=qwen3:8b-q4_K_M python3 scripts/deep_pseo_batch11.py
"""
import json, os, sys, time, urllib.request, shutil
import generate_batch as gb

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:8b-q4_K_M')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))

SETTORE = os.path.join(REPO, 'content', 'settore')
APPS = os.path.join(REPO, 'apps', 'seo-farm', 'content', 'settore')
os.makedirs(SETTORE, exist_ok=True)
os.makedirs(APPS, exist_ok=True)

# Candidati batch11 (deep night 2026-11-06): 5 keyword a volume (categoria x settore)
# NON gia' presenti tra gli 88 slug di content/settore. Backup in coda (10 slot).
CANDIDATI = [
    # 5 primari
    ('crm', 'pizzerie'),
    ('fidelizzazione', 'studi-dentistici'),
    ('email-marketing', 'barbieri'),
    ('pos', 'bar'),
    ('fidelizzazione', 'barbieri'),
    # backup (usati solo se uno dei 5 primari risulta gia' esistente)
    ('crm', 'fabbri'),
    ('email-marketing', 'concessionari-auto'),
    ('gestionale', 'pmi'),
    ('pos', 'parrucchieri'),
    ('booking', 'fisioterapisti'),
]
N_CERCATI = 5
QC_JSON = os.path.join(REPO, 'logs', 'pseo_batch11_qc.json')


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
    warns = []
    for p in ('TOOL_X', 'TOOL_1', 'TOOL_2', '[link]', '[LINK', '[Tool]', '[tool]', '[tool entry]', '[tool pro]', '[DISCLAIMER', '[X]'):
        if p in text:
            warns.append(f'placeholder {p}')
    if 'software' not in text.lower():
        warns.append('missing software')
    return warns


def main():
    existing = {f[:-3] for f in os.listdir(SETTORE) if f.endswith('.md')}
    targets = []
    seen = set()
    for c, s in CANDIDATI:
        slug = f'{c}-{s}'
        if slug in existing or slug in seen:
            continue
        targets.append((c, s))
        seen.add(slug)
    if not targets:
        print('  ❌ nessun nuovo candidato disponibile', file=sys.stderr); return
    print(f'🚀 Deep pSEO batch11 — {OLLAMA_MODEL} — {len(targets)} candidati, genero finché non ne ho {N_CERCATI} OK', file=sys.stderr)
    for c, s in targets:
        print(f'   → {c}-{s}', file=sys.stderr)

    ok, fail, overwrote = 0, 0, 0
    report = []
    for i, (category, sector) in enumerate(targets, 1):
        if ok >= N_CERCATI:
            break
        slug = f'{category}-{sector}'
        path = os.path.join(SETTORE, f'{slug}.md')
        prompt = gb.PROMPT_SECTOR_V2.format(category=category, sector=sector)
        t0 = time.time()
        content = ollama_call(prompt, 3000, retries=3)
        elapsed = time.time() - t0
        fatal = qc_fatal(content)
        warns = qc_warn(content)
        entry = {'slug': slug, 'status': None, 'seconds': round(elapsed, 1),
                 'words': len(content.split()), 'chars': len(content), 'fatal': fatal, 'warns': warns}
        if fatal:
            fail += 1
            entry['status'] = 'qc_fatal'
            report.append(entry)
            print(f'  [{i}/{len(targets)}] {slug} ⚠️ QC-fatal: {fatal} ({elapsed:.0f}s) — NON scritto', file=sys.stderr)
            continue
        with open(path, 'w') as f:
            f.write(content)
        ok += 1
        app_path = os.path.join(APPS, f'{slug}.md')
        existed_app = os.path.exists(app_path)
        shutil.copy2(path, app_path)
        if existed_app:
            overwrote += 1
        entry['status'] = 'ok'
        report.append(entry)
        w = f' ℹ️ QC-warn: {warns}' if warns else ''
        print(f'  [{i}/{len(targets)}] {slug} ✅ ({elapsed:.0f}s, {entry["words"]} parole, {len(content):,} chars){w} — sync su apps/', file=sys.stderr)
        time.sleep(1)

    os.makedirs(os.path.dirname(QC_JSON), exist_ok=True)
    with open(QC_JSON, 'w') as f:
        json.dump({'model': OLLAMA_MODEL, 'generated': time.strftime('%Y-%m-%d %H:%M'),
                   'ok': ok, 'fail': fail, 'overwrote': overwrote, 'articles': report}, f, ensure_ascii=False, indent=2)
    print(f'\n📊 Deep pSEO batch11: {ok} OK, {fail} QC-fail, {overwrote} overwrote (target {N_CERCATI})', file=sys.stderr)
    print(f'   → {SETTORE} (+ sync su {APPS})', file=sys.stderr)
    print(f'   → QC report: {QC_JSON}', file=sys.stderr)


if __name__ == '__main__':
    main()

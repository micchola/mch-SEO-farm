#!/usr/bin/env python3
"""MCH Deep Research STEP 1 — Scoring lead con Ollama qwen3:8b (think off).

Legge la pool grezza (scrape_leads.py brescia), seleziona un subset di lead con
contatto concreto, li punta con Ollama qwen3:8b-q4_K_M (think:false — tuning CPU N95),
aggiunge il flag di attendibilita' ("fonte primaria" / "da verificare" se fonte non
primaria = directory/sito da verificare), salva su leads.db + JSON + run_log.

NON usa Gemini. Uso:
  cd /home/impact/mch/seo-farm/scripts
  OLLAMA_MODEL=qwen3:8b-q4_K_M OLLAMA_NUM_PREDICT=384 N_SCORE=24 \
      python3 score_leads_8b.py /home/impact/progetti/mch/output/raw_leads_brescia_pmi_deep_20261106.json
"""
import json, os, sys, time, urllib.request, hashlib
from datetime import datetime, timezone
from collections import Counter

import lead_research as lr  # riutilizza get_db + SCORE_PROMPT + DB_PATH + OUTPUT_DIR

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:8b-q4_K_M')
N_PREDICT = int(os.environ.get('OLLAMA_NUM_PREDICT', '384'))
N_SCORE = int(os.environ.get('N_SCORE', '24'))

# Directory / fonti NON primarie (fonte secondaria -> lead "da verificare")
NON_PRIMARY = {'paginegialle.it', 'yelp.it', 'tripadvisor.it', 'trustpilot.com',
               'facebook.com', 'instagram.com', 'openstreetmap.org', 'g.page'}


def is_primary(lead):
    """Fonte primaria = il sito e' il dominio proprio dell'azienda, non una directory."""
    site = (lead.get('website') or '').strip()
    if not site or site == 'da verificare':
        return False
    try:
        from urllib.parse import urlparse
        host = urlparse(site if '://' in site else f'http://{site}').netloc.lower().replace('www.', '')
    except Exception:
        return False
    if not host:
        return False
    if any(host == d or host.endswith('.' + d) for d in NON_PRIMARY):
        return False
    return host.count('.') >= 1 and not host.startswith('http')


def ollama_json(prompt, retries=3):
    last = ''
    for attempt in range(retries):
        try:
            payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt,
                                  "stream": False, "think": False,
                                  "options": {"num_ctx": 4096, "num_predict": N_PREDICT,
                                              "temperature": 0.3}})
            req = urllib.request.Request(f"{OLLAMA_URL}/api/generate",
                data=payload.encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                last = json.load(r).get('response', '')
            text = last.strip()
            s, e = text.find('{'), text.rfind('}')
            if s != -1 and e > s:
                return json.loads(text[s:e + 1])
        except Exception as e:
            print(f'    ❌ Ollama: {e} — retry {attempt+1}/{retries}', file=sys.stderr)
            time.sleep(10)
        time.sleep(0.5)
    return None


def select(pool, n):
    """Punta ~n lead con contatto concreto, bilanciati per settore (PagineGialle prima)."""
    concrete = [l for l in pool if (l.get('contatto', '').strip() not in ('', 'da verificare'))]
    by_sector = {}
    for l in concrete:
        by_sector.setdefault(l.get('settore', '?'), []).append(l)
    for sec in by_sector:
        by_sector[sec].sort(key=lambda x: 0 if x.get('fonte') == 'paginegialle' else 1)
    picked, secs = [], list(by_sector.keys())
    i = 0
    while len(picked) < n and any(by_sector.values()):
        sec = secs[i % len(secs)]
        if by_sector.get(sec):
            picked.append(by_sector[sec].pop(0))
        i += 1
    return picked[:n]


def main():
    if len(sys.argv) < 2:
        print('uso: score_leads_8b.py <pool_grezza.json> [N]', file=sys.stderr); sys.exit(2)
    pool_path = sys.argv[1]
    if len(sys.argv) >= 3:
        global N_SCORE; N_SCORE = int(sys.argv[2])
    pool = json.load(open(pool_path))
    target = select(pool, N_SCORE)
    print(f'🎯 scello {len(target)} lead da {len(pool)} pool (con contatto concreto)', file=sys.stderr)

    conn = lr.get_db()
    now = datetime.now(timezone.utc).isoformat()
    project = pool[0].get('project', 'MCH Deep Research — Brescia') if pool else 'MCH Deep'
    now_ts = datetime.now().strftime('%Y%m%d')
    out_file = lr.OUTPUT_DIR / f"leads_{project.replace(' ', '_').replace('—', '')}_{now_ts}_deep.json"

    scored = []
    n_prim = 0
    for i, lead in enumerate(target, 1):
        d = ollama_json(lr.SCORE_PROMPT.format(
            name=lead.get('company_name', ''),
            settore=lead.get('settore', ''),
            website=lead.get('website', ''),
            fonte=lead.get('fonte_url', lead.get('fonte', '')),
        ))
        prim = is_primary(lead)
        lead['attendibilita'] = 'fonte primaria' if prim else 'da verificare'
        if prim:
            n_prim += 1
        dom = (lead.get('website', '').split('/')[2].lower().replace('www.', '')
               if '/' in (lead.get('website') or '') else '')
        lead['id'] = hashlib.md5(f"{dom}|{lead.get('company_name','').lower()}|{lead.get('citta','').lower()}".encode()).hexdigest()[:12]
        lead['project'] = project
        if d:
            lead['punteggio'] = int(d.get('punteggio', 0) or 0)
            lead['classifica'] = d.get('classifica', 'D')
            lead['motivo_qualifica'] = d.get('motivo', '')
            lead['segnali_dolore'] = d.get('dolore', 'da verificare')
            # conserva il telefono concreto dello scrape se il campo contatto LLM non e' un telefono reale
            llm_contact = (d.get('contatto') or '').strip()
            digits = sum(c.isdigit() for c in llm_contact)
            lead['contatto'] = llm_contact if digits >= 6 else lead.get('contatto', 'da verificare')
            lead['motivo_qualifica'] = (lead['motivo_qualifica'] + f" | fonte: {lead['attendibilita']}").strip()
        else:
            lead['punteggio'] = 0
            lead['classifica'] = 'D'
            lead['motivo_qualifica'] = 'score fallito (Ollama) | fonte: ' + lead['attendibilita']
        scored.append(lead)
        # persistenza incremental per lead (crash-safe): DB idempotente + JSON riscritto
        conn.execute("""
        INSERT OR REPLACE INTO leads (
            id,project,company_name,website,settore,citta,dimensione,servizi,
            segnali_dolore,contatto,fonte_url,punteggio,classifica,
            motivo_qualifica,automazione_consigliata,beneficio,
            primo_messaggio,prossima_azione,escluso,creato_in,aggiornato_in
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            lead["id"], project, lead.get('company_name',''), lead.get('website',''),
            lead.get('settore',''), lead.get('citta',''), lead.get('dimensione','da verificare'),
            lead.get('servizi','da verificare'), lead.get('segnali_dolore',''),
            lead.get('contatto',''), lead.get('fonte_url', lead.get('fonte','')),
            lead.get('punteggio',0), lead.get('classifica',''),
            lead.get('motivo_qualifica',''), lead.get('automazione_consigliata',''),
            lead.get('beneficio',''), lead.get('primo_messaggio',''),
            lead.get('prossima_azione',''), lead.get('escluso',0), now, now
        ))
        conn.commit()
        out_file.write_text(json.dumps(scored, ensure_ascii=False, indent=2))
        print(f"  [{i}/{len(target)}] {lead.get('company_name','?'):<28} {lead.get('settore','?'):<14} "
              f"pun={lead['punteggio']:<3} {lead['classifica']}  {lead['attendibilita']}", file=sys.stderr)
        time.sleep(0.5)

    a = sum(1 for l in scored if l.get('classifica') == 'A')
    b = sum(1 for l in scored if l.get('classifica') == 'B')
    conn.execute("INSERT OR REPLACE INTO run_log (run_id,project,started_at,finished_at,leads_found,leads_a,leads_b,errors) VALUES (?,?,?,?,?,?,?,?)",
        (datetime.now().strftime('%Y%m%d_%H%M%S') + '_deep8b', project, now, now, len(scored), a, b, ''))
    conn.commit()

    top = sorted([l for l in scored if l['classifica'] in ('A', 'B')], key=lambda x: -x.get('punteggio', 0))[:8]
    print(f'\n✅ {len(scored)} lead puntati ({a} A, {b} B) | {n_prim} fonte primaria, {len(scored)-n_prim} da verificare', file=sys.stderr)
    print(f'   JSON: {out_file}', file=sys.stderr)
    print(f'   DB: {lr.DB_PATH}', file=sys.stderr)
    print(f'\nTOP LEAD PER OUTREACH:')
    for l in top:
        print(f'  [{l["classifica"]}] {l.get("company_name","?")} ({l.get("settore","?")}) — {l.get("contatto","?")} — {l.get("motivo_qualifica","")[:70]}')



if __name__ == '__main__':
    main()

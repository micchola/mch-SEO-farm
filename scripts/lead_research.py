#!/usr/bin/env python3
"""
MCH Lead Research — data layer
Chiamato dal cron Hermes per: scoring Ollama, salvataggio SQLite, report vocale.
Uso:
  python3 lead_research.py score <json_file>  → score leads e salva in DB
  python3 lead_research.py report <project>   → genera report testuale
  python3 lead_research.py list A             → elenca lead A
"""
import json, sqlite3, os, sys, time, hashlib
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path("/home/impact/progetti/mch")
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = OUTPUT_DIR / "leads.db"
OLLM_URL = "http://127.0.0.1:11434/api/generate"

def ollama(prompt: str, model: str = None, system: str = "", timeout: int = 300) -> str:
    import urllib.request
    if model is None:
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    # cap num_predict: evita generazioni "fuori controllo" su CPU (lead che scappano 10+ min)
    num_predict = int(os.environ.get("OLLAMA_NUM_PREDICT", "512"))
    temperature = float(os.environ.get("OLLAMA_TEMPERATURE", "0.3"))
    payload = json.dumps({"model": model, "prompt": prompt, "system": system, "stream": False,
                          "options": {"num_predict": num_predict, "temperature": temperature}})
    req = urllib.request.Request(OLLM_URL, data=payload.encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()).get("response", "").strip()
    except Exception as e:
        return f"[Ollama error: {e}]"

def get_db() -> sqlite3.Connection:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS leads (
        id TEXT PRIMARY KEY, project TEXT, company_name TEXT, website TEXT,
        settore TEXT, citta TEXT, dimensione TEXT, servizi TEXT,
        segnali_dolore TEXT, contatto TEXT, fonte_url TEXT,
        punteggio INTEGER, classifica TEXT, motivo_qualifica TEXT,
        automazione_consigliata TEXT, beneficio TEXT, primo_messaggio TEXT,
        prossima_azione TEXT, escluso INTEGER DEFAULT 0,
        creato_in TEXT, aggiornato_in TEXT
    );
    CREATE TABLE IF NOT EXISTS run_log (
        run_id TEXT PRIMARY KEY, project TEXT, started_at TEXT,
        finished_at TEXT, leads_found INTEGER, leads_a INTEGER,
        leads_b INTEGER, errors TEXT
    );
    """)
    conn.commit()
    return conn

SCORE_PROMPT = """Sei un analista MCH. Punteggio 0-100 per questo lead:
+25 ICP match (5-50 dip., processi manuali)
+20 processo manuale evidente
+15 urgenza (assunzioni, crescita, recensioni neg.)
+15 contatto decisionale pubblico
+15 offerta MCH applicabile
+10 sito ok ma zero automazione
-20 troppo grande / concorrente / inaccessibile

Lead: {name} | {settore} | {website} | Fonte: {fonte}

Rispondi SOLO JSON: {{"punteggio":N,"classifica":"X","motivo":"2 frasi","dolore":"1 frase","contatto":"...|da verificare"}}"""

def cmd_score(json_path: str):
    """Score a list of raw leads (JSON) and save to DB."""
    with open(json_path) as f:
        raw_leads = json.load(f)
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    project = raw_leads[0].get("project", "unknown") if raw_leads else "unknown"

    scored = []
    for lead in raw_leads:
        # Dedupe
        dom = lead.get("website", "").split("/")[2].lower().replace("www.", "") if "/" in lead.get("website", "") else ""
        cid = hashlib.md5(f"{dom}|{lead.get('company_name','').lower()}|{lead.get('citta','').lower()}".encode()).hexdigest()[:12]
        lead["id"] = cid
        lead["project"] = project

        # Score via Ollama
        result = ollama(SCORE_PROMPT.format(
            name=lead.get("company_name", ""),
            settore=lead.get("settore", ""),
            website=lead.get("website", ""),
            fonte=lead.get("fonte_url", ""),
        ))
        try:
            d = json.loads(result)
            lead["punteggio"] = int(d.get("punteggio", 0))
            lead["classifica"] = d.get("classifica", "D")
            lead["motivo_qualifica"] = d.get("motivo", "")
            lead["segnali_dolore"] = d.get("dolore", "da verificare")
            lead["contatto"] = d.get("contatto", "da verificare")
        except (json.JSONDecodeError, ValueError):
            lead["punteggio"] = 0
            lead["classifica"] = "D"
            lead["motivo_qualifica"] = "score fallito"

        scored.append(lead)
        time.sleep(0.5)  # rate limit

    # Save
    for lead in scored:
        conn.execute("""
        INSERT OR REPLACE INTO leads (
            id,project,company_name,website,settore,citta,dimensione,servizi,
            segnali_dolore,contatto,fonte_url,punteggio,classifica,
            motivo_qualifica,automazione_consigliata,beneficio,
            primo_messaggio,prossima_azione,escluso,creato_in,aggiornato_in
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            lead["id"], project, lead.get("company_name",""), lead.get("website",""),
            lead.get("settore",""), lead.get("citta",""), lead.get("dimensione","da verificare"),
            lead.get("servizi","da verificare"), lead.get("segnali_dolore",""),
            lead.get("contatto",""), lead.get("fonte_url",""),
            lead.get("punteggio",0), lead.get("classifica",""),
            lead.get("motivo_qualifica",""), lead.get("automazione_consigliata",""),
            lead.get("beneficio",""), lead.get("primo_messaggio",""),
            lead.get("prossima_azione",""), lead.get("escluso",0), now, now
        ))

    conn.commit()
    a = sum(1 for l in scored if l.get("classifica") == "A")
    b = sum(1 for l in scored if l.get("classifica") == "B")
    conn.execute("""
        INSERT OR REPLACE INTO run_log
        (run_id, project, started_at, finished_at, leads_found, leads_a, leads_b, errors)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        datetime.now().strftime("%Y%m%d_%H%M%S"), project,
        now, now, len(scored), a, b, ""
    ))
    conn.commit()

    # Save JSON output
    out_file = OUTPUT_DIR / f"leads_{project.replace(' ','_').replace('—','')}_{datetime.now().strftime('%Y%m%d')}.json"
    out_file.write_text(json.dumps(scored, ensure_ascii=False, indent=2))
    print(f"Scored {len(scored)} leads ({a} A, {b} B) → {out_file}")
    print(f"DB: {DB_PATH}")

MSG_PROMPT = """Sei MCH. Scrivi messaggio WhatsApp (max 90 parole) per:
Nome: {name} ({settore})
Sito: {website}
Dolore: {dolore}
Offerta: {offerta}

Regole: personalizzato, concreto, CTA chiara, niente "la nostra azienda", firma MCH.
Rispondi SOLO con il messaggio."""

def cmd_report(project: str):
    """Generate voice report text for a project."""
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d")

    rows = conn.execute("""
        SELECT company_name, settore, punteggio, motivo_qualifica,
               automazione_consigliata, primo_messaggio, classifica
        FROM leads WHERE project=? AND escluso=0
        ORDER BY punteggio DESC LIMIT 10
    """, (project,)).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM leads WHERE project=? AND escluso=0", (project,)).fetchone()[0]
    a_count = conn.execute("SELECT COUNT(*) FROM leads WHERE project=? AND esclusiva='A'", (project,)).fetchone()[0] if False else \
              conn.execute("SELECT COUNT(*) FROM leads WHERE project=? AND classifica='A' AND escluso=0", (project,)).fetchone()[0]
    b_count = conn.execute("SELECT COUNT(*) FROM leads WHERE project=? AND classifica='B' AND escluso=0", (project,)).fetchone()[0]

    lines = [f"Report MCH Lead Research, {now}.", f"Aziende in pipeline: {total}. Lead A: {a_count}. Lead B: {b_count}."]
    if rows:
        lines.append("Top opportunità:")
        for i, r in enumerate(rows[:5], 1):
            lines.append(f"{i}. {r[0]} — {r[1]}, punteggio {r[2]}.")
            if r[3]: lines.append(f"   {r[3]}")
            if r[4]: lines.append(f"   Offerta: {r[4]}")
    else:
        lines.append("Nessun lead in pipeline ancora.")
    lines.append("Azioni da approvare: invio messaggi lead A e B.")
    lines.append("Fine report.")

    report = "\n".join(lines)
    out = OUTPUT_DIR / f"report_vocale_{project.replace(' ','_').replace('—','')}_{now}.txt"
    out.write_text(report)
    print(report)
    print(f"\n[Salvato: {out}]")

def cmd_list(classifica: str):
    conn = get_db()
    rows = conn.execute("SELECT company_name, punteggio, motivo_qualifica FROM leads WHERE classifica=? AND escluso=0 ORDER BY punteggio DESC", (classifica,)).fetchall()
    for r in rows:
        print(f"[{r[1]}] {r[0]} — {r[2]}")
    print(f"Totale: {len(rows)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "score" and len(sys.argv) > 2:
        cmd_score(sys.argv[2])
    elif cmd == "report" and len(sys.argv) > 2:
        cmd_report(sys.argv[2])
    elif cmd == "list" and len(sys.argv) > 2:
        cmd_list(sys.argv[2])
    else:
        print(__doc__)

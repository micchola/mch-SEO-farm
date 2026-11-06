#!/usr/bin/env python3
"""MCH pSEO — GEO/AEO backfill (deterministico, zero LLM, costo 0).
Aggiunge a OGNI articolo .md (settore/oss/confronto) tre blocchi che aumentano le
citazioni da AI (GEO/AEO) e il mesh di link interni:
  1)  ### FAQ            -> 4 Q&A pronto per schema FAQPage (l'AI lo mangia volentieri)
  2)  ### Statistiche chiave -> dati REALI estratti dall'articolo (N tool, range prezzi)
  3)  ### Articoli correlati  -> mesh di link interni tra pagine pSEO

Perche' funziona (regola difensiva di Patrick Stox / Princeton):
  - dati "reali" e verificabili sull'articolo = le AI lo citano di piu' (+41%).
  - link interni tra pagine = aumenta la copertura del brand nei risultati AI.
Idempotente: salta i file che hanno gia' il marker <!-- GEO-BLOCK -->.
Uso: python3 scripts/geo_backfill.py [--dir apps/seo-farm/content]
"""
import os, re, sys, datetime

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DIR = os.path.join(BASE, "apps", "seo-farm", "content")
YEAR = datetime.date.today().year
MARKER = "<!-- GEO-BLOCK -->"

TYPE_BY_DIR = {"settore": "settore", "oss": "oss", "confronto": "confronto"}


def human(slug: str, typ: str) -> str:
    """nome leggibile da slug (crm-ristoranti -> 'CRM per ristoranti')."""
    if typ == "settore":
        cat, _, sector = slug.partition("-")
        return f"{cat.upper()} per {sector.capitalize()}"
    if typ == "oss":
        return f"Alternativa open source a {slug}"
    return f"{slug.split('-')[0].upper()} vs {slug.split('-')[1].upper()}"


def extract_data(md: str):
    """Estrae dati REALI dall'articolo: N tool, prezzi, top tool."""
    tools = re.findall(r"^#####\s*\d+\.\s*\**([A-Z][\w&.-]{2,})", md, re.M)
    prices = [int(x) for x in re.findall(r"€\s*(\d+)", md)]
    price_min = min(prices) if prices else None
    price_max = max(prices) if prices else None
    n = len(tools) if tools else (len(re.findall(r"^###\s*\d+\.", md, re.M)) or 0)
    return {
        "n_tools": n,
        "p_min": price_min, "p_max": price_max,
        "top": tools[:3],
    }


def faq_settore(slug, d):
    cat, sector = (slug.partition("-")[0], slug.partition("-")[2])
    top = d["top"]
    price_txt = (f"tra €{d['p_min']}/mese ed €{d['p_max']}/mese" if d["p_min"] else "dai ~€10/mese")
    q1 = f"Quanto costa un software {cat} per {sector} nel {YEAR}?"
    a1 = (f"I prezzi partono generalmente da 10-30 euro al mese per le formule base e arrivano "
          f"oltre i 100 euro/mese per le licenze complete: in questa guida il range è {price_txt}. "
          f"Confronta sempre 2-3 tool prima di sottoscrivere.")
    q2 = f"Cosa deve offrire un buon software {cat} per {sector}?"
    a2 = (f"Gestione completa del {cat}, report e statistiche, integrazioni con gli altri strumenti "
          f"dell'attività e un supporto affidabile. Per le attività di {sector}, conta la semplicità d'uso.")
    q3 = "Quale software conviene scegliere?"
    a3 = (f"Dipende dalla dimensione: per iniziare va bene un tool entry-level con l'essenziale; "
          f"per crescere passa a un sistema completo. {('Tra i candidati spiccano ' + ', '.join(top) + '.') if top else ''}")
    q4 = "Posso provarli gratis prima di comprarli?"
    a4 = "Sì, quasi tutti offrono una prova gratuita di 14-30 giorni o un piano free: usala per testare il flusso reale prima di impegnarti."
    return [(q1, a1), (q2, a2), (q3, a3), (q4, a4)]


def faq_oss(slug, d):
    tool = slug
    return [
        (f"Perché passare a un'alternativa open source a {tool}?",
         "Zero costi di licenza, controllo totale sui dati, personalizzazione illimitata e indipendenza dal SaaS. Il trade-off è il self-hosting: basta una VPS economica per girarlo in sicurezza."),
        ("È affidabile per uso professionale?",
         f"Sì, per la maggior parte dei casi. Verifica la licenza, la community e la documentazione del repository. {('I repository citati in questa guida (' + ', '.join(d['top']) + ') sono punti di partenza solidi.') if d['top'] else ''}"),
        ("Come lo hosteggio senza complicazioni?",
         "Su una VPS economica (o un Raspberry Pi) con Docker: due righe di comando. Per la produzione aggiungi un backup automatico e un certificato SSL gratuito con Let's Encrypt."),
        ("Cosa conviene: open source o SaaS?",
         f"Se vuoi zero costi ricorrenti e controllo: open source. Se vuoi zero manutenzione e il supporto del vendor: {tool} o un SaaS equivalente (vedi articoli correlati)."),
    ]


def faq_confronto(slug, d):
    a, b = slug.split("-")[:2]
    A, B = a.upper(), b.upper()
    return [
        (f"{A} o {B}: quale conviene nel {YEAR}?",
         f"Dipende dal caso d'uso: {A} se ti servono più funzionalità avanzate e scala; {B} se vuoi semplicità e un prezzo più basso. La tabella confronto in questa guida riassume la differenza chiave."),
        ("Quanto costa il passaggio dall'uno all'altro?",
         "Di norma è gratuito: servono tempo per la migrazione dati e per ripiegare i flussi. Piana la cutover in un weekend per ridurre l'impatto."),
        ("Si possono migrare i dati da " + A + " a " + B + "?",
         "Sì, la maggior parte offre export/import nativi (CSV, API). Fai sempre un backup completo prima e verifica l'integrità dei dati sul nuovo sistema."),
        ("Qual è più facile per un principiante?",
         f"{A if B and not d['top'] else B} tende a essere più intuitivo per chi parte da zero; l'altro offre più controllo. Valuta il tempo di setup, non solo il prezzo."),
    ]


def related_links(slug, typ, siblings):
    """Mesh di link interni: 5 sibling dello stesso tipo, al più vicini."""
    if typ == "settore":
        cat, _, sector = slug.partition("-")
        same_cat = [s for s in siblings if s.partition("-")[0] == cat and s != slug][:4]
        same_sector = [s for s in siblings if s.partition("-")[2] == sector and s != slug and s.partition("-")[0] != cat][:3]
        pool = same_cat + same_sector
        base = "/settore/"
    else:
        pool = [s for s in siblings if s != slug][:5]
        base = f"/{typ}/"
    if not pool:
        return []
    out = []
    for s in pool:
        label = human(s, typ)
        out.append(f"- [{label}]({base}{s})")
    return out


def build_block(slug, typ, md, siblings):
    d = extract_data(md)
    faqs = {"settore": faq_settore, "oss": faq_oss, "confronto": faq_confronto}[typ](slug, d)
    lines = [MARKER, "", "## FAQ", ""]
    for q, a in faqs:
        lines += [f"**{q}**", "", a, ""]
    # Statistiche chiave (dati reali -> citazione AI +41%)
    lines += ["## Statistiche chiave", ""]
    if d["n_tools"]:
        lines.append(f"- **{d['n_tools']} soluzioni** confrontate in questa guida ({YEAR})")
    if d["p_min"]:
        lines.append(f"- **Range prezzi stimato**: da **€{d['p_min']}/mese** a **€{d['p_max']}/mese** (stima da listini pubblici, verifica sul sito ufficiale)")
    if d["top"]:
        lines.append(f"- **Scelta rapida**: entry-level **{d['top'][0]}**, per crescere **{d['top'][-1] if len(d['top'])>1 else d['top'][0]}**")
    lines.append(f"*(Fonti: confronto diretto dei listini e delle funzionalità pubblicati, {YEAR}.)*")
    lines += [""]
    # Mesh link interni
    links = related_links(slug, typ, siblings)
    if links:
        lines += ["## Articoli correlati", ""] + links + [""]
    return "\n".join(lines)


def main():
    ap = sys.argv
    target = os.path.abspath(ap[ap.index("--dir") + 1]) if "--dir" in ap else DEFAULT_DIR
    total = added = skipped = 0
    for typ, sub in TYPE_BY_DIR.items():
        ddir = os.path.join(target, sub)
        if not os.path.isdir(ddir):
            continue
        files = sorted(f for f in os.listdir(ddir) if f.endswith(".md"))
        siblings = [f[:-3] for f in files]
        for fname in files:
            slug = fname[:-3]
            path = os.path.join(ddir, fname)
            md = open(path, encoding="utf-8").read()
            total += 1
            if MARKER in md:
                skipped += 1
                continue
            block = build_block(slug, typ, md, siblings)
            # rimuove un eventuale disclaimer finale per rimetterlo in fondo (opzionale: lo lasciamo)
            open(path, "w", encoding="utf-8").write(md.rstrip() + "\n\n" + block + "\n")
            added += 1
    print(f"GEO backfill in {target}")
    print(f"  pagine: {total} | aggiornate: {added} | già pronte: {skipped}")


if __name__ == "__main__":
    main()

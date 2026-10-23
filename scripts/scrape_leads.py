#!/usr/bin/env python3
"""
MCH Lead Research — Improved Scraping (Hybrid: Nominatim + web_search + firecrawl)
Fonti:
  1. Nominatim OSM → nomi aziende (gratis, rate limit 1 req/s)
  2. PagineGialle / TheFork / directory → contatto (via firecrawl o web_search)
  3. web_search → email/telefono sito
Uso:
  python3 scrape_leads.py <config_json> <output_json> [--limit 50]
"""
import json, sys, os, time, re, hashlib, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path("/home/impact/progetti/mch")

# Nominatim query patterns per categoria
NOMINATIM_QUERIES = {
    "ristorante": [
        "restaurant in Brescia, Italy",
        "pizzeria in Brescia, Italy",
        "bar in Brescia, Italy",
        "ristorante in Franciacorta, Italy",
    ],
    "palestra": [
        "fitness centre in Brescia, Italy",
        "gym in Brescia, Italy",
        "sports centre in Brescia, Italy",
    ],
    "studio medico": [
        "medical clinic in Brescia, Italy",
        "doctor in Brescia, Italy",
        "dental in Brescia, Italy",
    ],
    "commercialista": [
        "accountant in Brescia, Italy",
        "tax consultant in Brescia, Italy",
    ],
    "agenzia": [
        "real estate agency in Brescia, Italy",
        "insurance in Brescia, Italy",
    ],
    "estetista": [
        "beauty salon in Brescia, Italy",
        "hairdresser in Brescia, Italy",
        "spa in Brescia, Italy",
    ],
    "idraulico": [
        "plumber in Brescia, Italy",
        "heating engineer in Brescia, Italy",
    ],
    "fabbro": [
        "locksmith in Brescia, Italy",
        "metal workshop in Brescia, Italy",
    ],
}

def nominatim_search(query, limit=10):
    """Search Nominatim for businesses."""
    url = f"https://nominatim.openstreetmap.org/search?{urllib.parse.urlencode({
        'q': query, 'format': 'json', 'limit': limit, 'extratags': 1
    })}"
    req = urllib.request.Request(url, headers={'User-Agent': 'MCH-LeadResearch/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Nominatim error: {e}")
        return []

def parse_nominatim(results, settore):
    """Convert Nominatim results to lead format."""
    leads = []
    for r in results:
        name = r.get("name") or r.get("display_name", "").split(",")[0].strip()
        if not name or "Brescia" in name.upper() and len(name) < 5:
            continue
        tags = r.get("extratags") or {}
        website = tags.get("website", "")
        phone = tags.get("phone", "")
        email = tags.get("email", "") or tags.get("contact:email", "")
        
        leads.append({
            "company_name": name,
            "website": website or "da verificare",
            "settore": settore,
            "citta": "Brescia",
            "dimensione": "da verificare",
            "servizi": "da verificare",
            "segnali_dolore": "",
            "contatto": email or phone or "da verificare",
            "fonte": "openstreetmap",
            "fonte_url": r.get("osm_type", "") and f"osm:{r.get('osm_id')}" or "nominatim",
            "id": hashlib.md5(f"{name.lower()}|{website}".encode()).hexdigest()[:12],
            "escluso": 0
        })
    return leads

def enrich_with_websearch(lead, limit_chars=300):
    """Enrich a lead with contact info via web_search hint."""
    # This is a marker for the cron agent to follow up with web_search
    lead["needs_websearch"] = True
    lead["search_query"] = f'"{lead["company_name"]}" {lead["citta"]} email contatto'
    return lead

def firecrawl_scrape(url):
    """Scrape a URL using Firecrawl API."""
    key_path = "/home/impact/.hermes/secrets/firecrawl_api_key.txt"
    try:
        key = open(key_path).read().strip()
    except FileNotFoundError:
        print(f"  Firecrawl key not found at {key_path}, skipping")
        return ""
    try:
        payload = json.dumps({"url": url, "formats": ["markdown"], "onlyMainContent": True}).encode()
        req = urllib.request.Request("https://api.firecrawl.dev/v1/scrape", data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data.get("data", {}).get("markdown", "")
    except Exception as e:
        print(f"  Firecrawl error: {e}")
        return ""

def scrape_paginegialle(category, city="brescia"):
    """Scrape PagineGialle for a category, extract phone numbers + names."""
    pg_url = f"https://www.paginegialle.it/lombardia/{city}/{category}.html"
    md = firecrawl_scrape(pg_url)
    if not md:
        return []
    lines = md.split('\n')
    results = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.search(r'030\s+\d{6,7}\s*$', stripped)
        if not m or 'http' in stripped:
            continue
        phone = m.group()
        name = None
        for j in range(max(0, i-8), i):
            l = lines[j].strip().strip('*').strip()
            if re.match(r'^[A-ZÀ-Ú][^ ]{3,40}$', l) and l not in ('Telefono','Chiudi'):
                name = l
                break
        results.append({
            "phone": phone,
            "name": name,
            "category": category,
            "city": city,
            "source": "paginegialle"
        })
    return results

def deduplicate(leads):
    """Deduplicate by website domain or name."""
    seen = set()
    unique = []
    for lead in leads:
        dom = ""
        w = lead.get("website", "")
        if w and w != "da verificare":
            dom = w.split("/")[2].lower().replace("www.", "") if "/" in w else ""
        
        key = dom or f"{lead.get('company_name','').lower()}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(lead)
    return unique

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    config_path = sys.argv[1]
    output_path = sys.argv[2]
    limit = 50
    for arg in sys.argv[3:]:
        if arg.startswith("--limit"):
            limit = int(arg.split("=")[1]) if "=" in arg else int(sys.argv[sys.argv.index(arg)+1])
    
    with open(config_path) as f:
        config = json.load(f)
    
    project = config.get("project", "unknown")
    city = config.get("city", "Brescia")
    keywords = config.get("keywords", config.get("parole_chiave", []))
    # Strip city name from keywords if present
    city_only = city
    keywords = [k.replace(f" {city}", "").replace(f" {city.lower()}", "").strip() or city for k in keywords]
    excluded = config.get("exclusions", [])
    
    print(f"=== MCH Scrape: {project} → {city} (limit {limit}) ===")
    
    all_leads = []
    
    # 1. Nominatim for business names
    print("\n[1/2] Nominatim OSM...")
    for kw in keywords:
        queries = NOMINATIM_QUERIES.get(kw, [f"{kw} in {city}, Italy"])
        for q in queries:
            results = nominatim_search(q, limit=15)
            leads = parse_nominatim(results, kw)
            all_leads.extend(leads)
            print(f"  {kw}: {len(leads)} found")
            time.sleep(1.1)  # Nominatim rate limit
    
    # 2. PagineGialle via Firecrawl
    print("\n[2/2] PagineGialle via Firecrawl...")
    PG_CATEGORIES = {
        "ristorante": "ristoranti", "palestra": "palestre",
        "studio medico": "studi_medici", "commercialista": "commercialisti",
        "agenzia": "agenzie_immobiliari", "estetista": "estetisti",
        "idraulico": "idraulici", "fabbro": "fabbri"
    }
    for kw in keywords:
        pg_cat = PG_CATEGORIES.get(kw, kw.lower().replace(' ', '_'))
        try:
            pg_leads = scrape_paginegialle(pg_cat, city)
            for pl in pg_leads:
                all_leads.append({
                    "company_name": pl.get("name") or f"[PG: {pl.get('category')} Brescia]",
                    "website": "da verificare",
                    "settore": kw,
                    "citta": city,
                    "dimensione": "PMI",
                    "servizi": f"PagineGialle: {pl.get('category')}",
                    "segnali_dolore": "",
                    "contatto": pl.get("phone", "da verificare"),
                    "fonte": "paginegialle",
                    "fonte_url": f"https://www.paginegialle.it/lombardia/{city}/{pg_cat}.html",
                    "id": hashlib.md5(f"pg_{pl.get('phone','x')}".encode()).hexdigest()[:12],
                    "escluso": 0
                })
            print(f"  {kw}: {len(pg_leads)} PagineGialle leads")
        except Exception as e:
            print(f"  {kw}: Firecrawl error: {e}")
        time.sleep(1)
    
    # Filter exclusions
    all_leads = [l for l in all_leads if not any(ex.lower() in l.get("company_name", "").lower() for ex in excluded)]
    
    # Deduplicate
    all_leads = deduplicate(all_leads)
    
    # Limit
    all_leads = all_leads[:limit]
    
    # Assign project
    for l in all_leads:
        l["project"] = project
        l["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    
    # Save
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(all_leads, f, ensure_ascii=False, indent=2)
    
    # Stats
    with_web = [l for l in all_leads if l.get("website") and l["website"] != "da verificare"]
    pg = [l for l in all_leads if l.get("needs_firecrawl")]
    print(f"\n=== Total: {len(all_leads)} leads → {output_path} ===")
    print(f"With website: {len(with_web)} | PagineGialle pending: {len(pg)}")
    print(f"\nTop candidates:")
    for l in all_leads[:5]:
        print(f"  - {l['company_name']} ({l['settore']}) → {l['website']}")
    
    # Save enrichment hints for the cron agent
    hints_path = output_path.replace(".json", "_hints.json")
    needs_search = [l for l in all_leads if l.get("needs_websearch") or l.get("needs_firecrawl")]
    with open(hints_path, "w") as f:
        json.dump(needs_search, f, ensure_ascii=False, indent=2)
    print(f"\nEnrichment hints: {len(needs_search)} → {hints_path}")

if __name__ == "__main__":
    main()

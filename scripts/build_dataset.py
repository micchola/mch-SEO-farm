#!/usr/bin/env python3
"""
MCH pSEO — Dataset Builder
Costruisce il dataset iniziale per le 3 nicchie in SQLite.
Uso: python3 scripts/build_dataset.py [--type oss|sector|comparison|all]
"""
import json, sqlite3, time, urllib.request, urllib.error, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'packages', 'data', 'data.db')

# ─── NICHIA 1: SaaS popolari → da mappare a OSS alternatives ───────────────
SaaS_TOOLS = [
    # (name, slug, category, pricing_model, price_from, price_to, sector, affiliate_prog)
    ("Notion",      "notion",       "notes",    "freemium", 0, 10,   "produttivita",       "direct"),
    ("Slack",       "slack",        "chat",     "paid",     7,  125,  "team-work",          "impact"),
    ("Figma",       "figma",        "design",   "freemium", 0,  15,   "design-ux",         "direct"),
    ("Salesforce",  "salesforce",   "crm",      "paid",     25, 250,  "vendite",            "direct"),
    ("HubSpot",     "hubspot",      "crm",      "freemium", 0,  320,  "vendite-marketing", "impact"),
    ("Zendesk",     "zendesk",      "support",  "paid",     5,  111,  "customer-service",   "impact"),
    ("Shopify",     "shopify",      "ecommerce","paid",     0,  289,  "ecommerce",          "shareasale"),
    ("Mailchimp",   "mailchimp",    "email",    "freemium", 0,  299,  "marketing-email",    "impact"),
    ("Jira",        "jira",         "pm",       "freemium", 0,  11,   "sviluppo-software","direct"),
    ("Trello",      "trello",       "pm",       "freemium", 0,  12,   "produttivita",       "direct"),
    ("Airtable",    "airtable",     "db",       "freemium", 0,  24,   "produttivita",       "direct"),
    ("GitHub",      "github",       "dev",      "freemium", 0,  30,   "sviluppo-software",  "direct"),
    ("Discord",     "discord",      "chat",     "free",     0,  0,    "gaming-comunicazione", "direct"),
    ("Zoom",        "zoom",         "video",    "freemium", 0,  20,   "riunioni-videocall","direct"),
    ("Canva",       "canva",        "design",   "freemium", 0,  12,   "marketing-grafica",  "direct"),
    ("Asana",       "asana",        "pm",       "freemium", 0,  25,   "produttivita",       "direct"),
    ("Monday.com",  "monday",       "pm",       "paid",     9,  289,  "produttivita",       "impact"),
    ("ClickUp",     "clickup",      "pm",       "freemium", 0,  25,   "produttivita",       "direct"),
    ("Webflow",     "webflow",      "web",      "freemium", 0,  39,   "web-design",         "direct"),
    ("WordPress",   "wordpress",    "cms",      "free",     0,  0,    "web-content",        "direct"),
    # aggiungi altri tool qui...
]

# ─── NICHIA 2: Settori IT × Categorie Software ──────────────────────────────
SECTORS = [
    "ristoranti", "palestre", "studi-medici", "parrucchieri",
    "ecommerce", "immobiliare", "agenzie-marketing", "sviluppo-software",
    "logistica", "istruzioni-formazione", "salute-benessere", "artigianato",
    "turismo-alberghiero", "farmacie", "officine-auto",
]

CATEGORIES = [
    "crm", "pos", "erp", "gestionale", "ecommerce", "email-marketing",
    "social-media", "videoconferenze", "accounting", "inventory",
    "booking", "customer-support",
]

# ─── NICHIA 3: Pair per comparazioni ────────────────────────────────────────
TOOL_PAIRS = [
    ("notion",       "airtable"),
    ("slack",        "discord"),
    ("jira",         "clickup"),
    ("trello",       "asana"),
    ("hubspot",      "salesforce"),
    ("zendesk",      "intercom"),
    ("shopify",      "woocommerce"),
    ("mailchimp",    "brevo"),
    ("figma",        "framer"),
    ("canva",        "adobe-photoshop"),
    ("monday",       "asana"),
    ("zoom",         "google-meet"),
    ("webflow",      "wordpress"),
    ("clickup",      "trello"),
    ("hubspot",      "brevo"),
]


def init_db(db_path=DB_PATH):
    schema = open(os.path.join(os.path.dirname(__file__), '..', 'packages', 'data', 'schema.sql')).read()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    return conn


def seed_tools(conn):
    """Inserisce i SaaS tool nel DB (idempotente)."""
    cur = conn.cursor()
    for row in SaaS_TOOLS:
        name, slug, cat, pm, pmin, pmax, sector, aff = row
        cur.execute("""
            INSERT OR IGNORE INTO tools
            (name, slug, category, saas_url, pricing_model, price_from, price_to, target_sectors, affiliate_program)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (name, slug, cat, f"https://{slug}.com", pm, pmin, pmax, json.dumps([sector]), aff))
    conn.commit()
    print(f"  → {len(SaaS_TOOLS)} tool seedati")


def fetch_oss_alternatives(conn, limit=30):
    """Cerca su GitHub API le OSS alternatives per i tool seedati."""
    cur = conn.cursor()
    tools = cur.execute("SELECT id, name, slug FROM tools LIMIT ?", (limit,)).fetchall()
    for tid, name, slug in tools:
        # Cerca su GitHub "open source alternative to {name}"
        query = f"open source alternative to {name}"
        api_url = (
            "https://api.github.com/search/repositories?"
            f"q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page=5"
        )
        try:
            req = urllib.request.Request(api_url, headers={"User-Agent": "mch-pseo/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
            for repo in data.get('items', []):
                cur.execute("""
                    INSERT OR IGNORE INTO oss_alternatives
                    (saas_tool_id, repo_name, repo_url, stars, license, description, last_push)
                    VALUES (?,?,?,?,?,?,?)
                """, (
                    tid,
                    f"{repo['owner']['login']}/{repo['name']}",
                    repo['html_url'],
                    repo['stargazers_count'],
                    (repo.get('license') or {}).get('spdx_id', 'N/A'),
                    repo.get('description', '')[:200],
                    repo.get('pushed_at', ''),
                ))
            conn.commit()
            print(f"  → {name}: {len(data.get('items', []))} alternative trovate")
        except Exception as e:
            print(f"  ⚠ {name}: {e}")
        time.sleep(2)  # rate limit GitHub


def seed_comparisons(conn):
    """Crea i pair di comparazione nel DB."""
    cur = conn.cursor()
    for slug_a, slug_b in TOOL_PAIRS:
        ta = cur.execute("SELECT id FROM tools WHERE slug=?", (slug_a,)).fetchone()
        tb = cur.execute("SELECT id FROM tools WHERE slug=?", (slug_b,)).fetchone()
        if ta and tb:
            pair_slug = f"{slug_a}-vs-{slug_b}"
            cur.execute("""
                INSERT OR IGNORE INTO comparisons (tool_a_id, tool_b_id, slug)
                VALUES (?,?,?)
            """, (ta[0], tb[0], pair_slug))
    conn.commit()
    print(f"  → {len(TOOL_PAIRS)} pair di comparazioni seedati")


import urllib.parse

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--type', choices=['oss', 'sector', 'comparison', 'all'], default='all')
    args = ap.parse_args()

    print("🔧 Build dataset pSEO MCH...")
    conn = init_db()

    seed_tools(conn)

    if args.type in ('oss', 'all'):
        print("\n📡 Fetch OSS alternatives da GitHub...")
        fetch_oss_alternatives(conn)

    if args.type in ('comparison', 'all'):
        print("\n⚔️ Seed comparazioni...")
        seed_comparisons(conn)

    print("\n✅ Dataset ready →", os.path.abspath(DB_PATH))
    conn.close()

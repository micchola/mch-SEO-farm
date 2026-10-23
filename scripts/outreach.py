#!/usr/bin/env python3
"""
MCH Outreach — Email list builder + sender
Compila database contatti pubblici e invia outreach personalizzato via Gmail.
Solo firma MCH, zero riferimenti personali.
"""
import sqlite3, os, csv, time, smtplib, ssl, argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), '..', 'packages', 'data', 'outreach.db')
SENDER = 'michfromholland@gmail.com'
FROM_NAME = 'MCH'
APP_PASSWORD_FILE = os.path.join(os.path.dirname(__file__), '..', 'packages', 'data', 'gmail_app_password.txt')

SITE_URL = 'https://mch-one.vercel.app'

# ── Email Templates (solo MCH, zero riferimenti personali) ─────────────────────

TEMPLATES = {
    'ristoranti': {
        'subject': 'MCH Directory: la tua attività inclusa nella guida italiana',
        'body': """Buongiorno {{nome}},

MCH sta costruendo una directory italiana dei software per il settore ristorazione: confronto prezzi, feature e tool consigliati per ogni dimensione di locale.

Se la tua attività usa un software specifico (gestionale, POS, CRM, prenotazioni), possiamo includerlo gratuitamente nella directory — con un link diretto al tuo sito.

Per essere inclusi, rispondi a questa email con:
- Nome software o servizio
- Link al sito
- Cosa fa (1 riga)

La directory è gratuita per chi viene incluso.

MCH
{site}

Per cancellarti: rispondi con "ESCI" in oggetto.
""",
    },
    'palestre': {
        'subject': 'MCH Directory: la tua attività inclusa nella guida italiana',
        'body': """Buongiorno {{nome}},

MCH sta costruendo una directory italiana dei software per palestre e centri fitness: booking, membership, gestione clienti, fatturazione.

Se la tua attività usa un software specifico, possiamo includerlo gratuitamente nella directory — con un link diretto al tuo sito.

Per essere inclusi, rispondi a questa email con:
- Nome software o servizio
- Link al sito
- Cosa fa (1 riga)

La directory è gratuita per chi viene incluso.

MCH
{site}

Per cancellarti: rispondi con "ESCI" in oggetto.
""",
    },
    'studi_medici': {
        'subject': 'MCH Directory: la tua attività inclusa nella guida italiana',
        'body': """Buongiorno {{nome}},

MCH sta costruendo una directory italiana dei software per studi medici e odontoiatrici: gestionali, booking, fatturazione, conformità GDPR.

Se la tua attività usa un software specifico, possiamo includerlo gratuitamente nella directory — con un link diretto al tuo sito.

Per essere inclusi, rispondi a questa email con:
- Nome software o servizio
- Link al sito
- Cosa fa (1 riga)

La directory è gratuita per chi viene incluso.

MCH
{site}

Per cancellarti: rispondi con "ESCI" in oggetto.
""",
    },
}


def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY,
        nome TEXT,
        email TEXT UNIQUE,
        settore TEXT,
        citta TEXT,
        nome_azi TEXT,
        fonte TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS sent (
        id INTEGER PRIMARY KEY,
        contact_id INTEGER,
        sent_at TEXT,
        status TEXT,
        FOREIGN KEY(contact_id) REFERENCES contacts(id)
    );
    """)
    conn.commit()
    return conn


def add_contacts_from_csv(csv_path, settore=''):
    conn = init_db()
    count = 0
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO contacts (nome, email, settore, citta, nome_azi, fonte) VALUES (?,?,?,?,?,?)",
                    (row.get('nome',''), row.get('email',''), row.get('settore','') or settore,
                     row.get('citta',''), row.get('nome_azi',''), row.get('fonte','csv'))
                )
                count += 1
            except sqlite3.IntegrityError:
                pass
    conn.commit()
    conn.close()
    print(f"✅ {count} contatti aggiunti da {csv_path}")


def get_pending(conn, settore, limit=20):
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT c.id, c.nome, c.email, c.nome_azi, c.citta
        FROM contacts c
        WHERE c.email NOT IN (SELECT c2.email FROM sent s JOIN contacts c2 ON s.contact_id=c2.id
                              WHERE s.status='sent')
          AND (c.settore = ? OR (? = 'any'))
        LIMIT ?
    """, (settore, settore, limit)).fetchall()
    return rows


def send_outreach(conn, settore, limit=5, dry_run=True):
    with open(APP_PASSWORD_FILE) as f:
        app_password = f.read().strip()

    template = TEMPLATES.get(settore, TEMPLATES['ristoranti'])
    pending = get_pending(conn, settore, limit)

    if not pending:
        print(f"No pending contacts for {settore}")
        return 0

    sent = 0
    for cid, nome, email, nome_azi, citta in pending:
        if not email:
            continue

        first_name = nome_azi or (nome.split()[0] if nome else '')
        body = template['body'].format(site=SITE_URL, nome=first_name)
        subject = template['subject']

        if dry_run:
            print(f"  [DRY] {email} | {first_name} | {subject[:50]}")
            continue

        try:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx, timeout=20)
            server.login(SENDER, app_password)

            msg = MIMEMultipart('alternative')
            msg['From'] = f'{FROM_NAME} <{SENDER}>'
            msg['To'] = email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # HTML version — approved layout: benefits box + numbered CTA + dark button
            template_html = {
                'ristoranti': """<div style="font-family:Arial,sans-serif;max-width:540px;margin:0 auto">
  <p style="font-size:14px;line-height:1.6;color:#222;margin:0 0 14px;">
    MCH sta costruendo la directory italiana dei software per il settore <strong>ristorazione</strong>:
    confronto prezzi, feature e tool consigliati per ogni dimensione di locale.
  </p>
  <p style="font-size:14px;line-height:1.6;color:#444;margin:0 0 20px;">
    Se la tua attività usa un software specifico (gestionale, POS, CRM, prenotazioni),
    puoi farlo <strong>includere gratuitamente</strong> nella directory.
  </p>
  <table style="background:#f0f7ff;border-radius:8px;padding:16px 18px;margin:0 0 20px;width:100%;border-collapse:collapse;">
    <tr><td>
      <div style="font-size:13px;font-weight:600;color:#1a56db;margin-bottom:8px;">Cosa ottieni</div>
      <div style="font-size:13px;color:#333;line-height:1.8;">
        <div style="margin-bottom:6px;">✓ <strong>Visibilità</strong> su una piattaforma che riceve traffico da chi cerca tool per il tuo settore</div>
        <div style="margin-bottom:6px;">✓ <strong>Link diretto</strong> al tuo sito (backlink, gratis)</div>
        <div>✓ <strong>Nessuna spesa</strong>, nessun impegno</div>
      </div>
    </td></tr>
  </table>
  <p style="font-size:14px;color:#333;margin:0 0 10px;line-height:1.5;">Per essere inclusi, <strong>rispondi a questa email</strong> con:</p>
  <ol style="font-size:13px;color:#444;padding-left:20px;margin:0 0 24px;line-height:1.8;">
    <li>Nome software / servizio</li>
    <li>Link al sito</li>
    <li>Cosa fa (1 riga)</li>
  </ol>
  <a href="{site}" style="display:inline-block;background:#1a56db;color:#fff;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px;text-decoration:none;">
    Vai alla directory →
  </a>
</div>""",
                'palestre': """<div style="font-family:Arial,sans-serif;max-width:540px;margin:0 auto">
  <p style="font-size:14px;line-height:1.6;color:#222;margin:0 0 14px;">
    MCH sta costruendo la directory italiana dei software per <strong>palestre e centri fitness</strong>:
    booking, membership, gestione clienti, fatturazione.
  </p>
  <p style="font-size:14px;line-height:1.6;color:#444;margin:0 0 20px;">
    Se la tua attività usa un software specifico,
    puoi farlo <strong>includere gratuitamente</strong> nella directory.
  </p>
  <table style="background:#f0f7ff;border-radius:8px;padding:16px 18px;margin:0 0 20px;width:100%;border-collapse:collapse;">
    <tr><td>
      <div style="font-size:13px;font-weight:600;color:#1a56db;margin-bottom:8px;">Cosa ottieni</div>
      <div style="font-size:13px;color:#333;line-height:1.8;">
        <div style="margin-bottom:6px;">✓ <strong>Visibilità</strong> su una piattaforma che riceve traffico da chi cerca tool per il tuo settore</div>
        <div style="margin-bottom:6px;">✓ <strong>Link diretto</strong> al tuo sito (backlink, gratis)</div>
        <div>✓ <strong>Nessuna spesa</strong>, nessun impegno</div>
      </div>
    </td></tr>
  </table>
  <p style="font-size:14px;color:#333;margin:0 0 10px;line-height:1.5;">Per essere inclusi, <strong>rispondi a questa email</strong> con:</p>
  <ol style="font-size:13px;color:#444;padding-left:20px;margin:0 0 24px;line-height:1.8;">
    <li>Nome software / servizio</li>
    <li>Link al sito</li>
    <li>Cosa fa (1 riga)</li>
  </ol>
  <a href="{site}" style="display:inline-block;background:#1a56db;color:#fff;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px;text-decoration:none;">
    Vai alla directory →
  </a>
</div>""",
                'studi_medici': """<div style="font-family:Arial,sans-serif;max-width:540px;margin:0 auto">
  <p style="font-size:14px;line-height:1.6;color:#222;margin:0 0 14px;">
    MCH sta costruendo la directory italiana dei software per <strong>studi medici e odontoiatrici</strong>:
    gestionali, booking, fatturazione, conformità GDPR.
  </p>
  <p style="font-size:14px;line-height:1.6;color:#444;margin:0 0 20px;">
    Se la tua attività usa un software specifico,
    puoi farlo <strong>includere gratuitamente</strong> nella directory.
  </p>
  <table style="background:#f0f7ff;border-radius:8px;padding:16px 18px;margin:0 0 20px;width:100%;border-collapse:collapse;">
    <tr><td>
      <div style="font-size:13px;font-weight:600;color:#1a56db;margin-bottom:8px;">Cosa ottieni</div>
      <div style="font-size:13px;color:#333;line-height:1.8;">
        <div style="margin-bottom:6px;">✓ <strong>Visibilità</strong> su una piattaforma che riceve traffico da chi cerca tool per il tuo settore</div>
        <div style="margin-bottom:6px;">✓ <strong>Link diretto</strong> al tuo sito (backlink, gratis)</div>
        <div>✓ <strong>Nessuna spesa</strong>, nessun impegno</div>
      </div>
    </td></tr>
  </table>
  <p style="font-size:14px;color:#333;margin:0 0 10px;line-height:1.5;">Per essere inclusi, <strong>rispondi a questa email</strong> con:</p>
  <ol style="font-size:13px;color:#444;padding-left:20px;margin:0 0 24px;line-height:1.8;">
    <li>Nome software / servizio</li>
    <li>Link al sito</li>
    <li>Cosa fa (1 riga)</li>
  </ol>
  <a href="{site}" style="display:inline-block;background:#1a56db;color:#fff;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px;text-decoration:none;">
    Vai alla directory →
  </a>
</div>""",
            }
            html_body = template_html.get(settore, template_html['ristoranti']).format(site=SITE_URL)
            # Footer with opt-out
            html_body += f'<div style="font-family:Arial,sans-serif;max-width:540px;margin:8px auto 0;padding:12px 0;font-size:11px;color:#999;">Non vuoi più ricevere email? Rispondi <strong>"ESCI"</strong> in oggetto. — MCH, {SITE_URL}</div>'
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            server.sendmail(SENDER, [email], msg.as_string())
            server.quit()

            conn.execute("INSERT INTO sent (contact_id, sent_at, status) VALUES (?, ?, 'sent')",
                        (cid, datetime.now().isoformat()))
            conn.commit()
            print(f"  ✅ inviato → {email} ({nome_azi or nome})")
            sent += 1
            time.sleep(2)
        except Exception as e:
            print(f"  ❌ {email}: {e}")
            continue

    if dry_run:
        print(f"\n[DRY RUN] {len(pending)} pending per {settore}")
    else:
        print(f"\n✅ {sent} email inviate ({settore})")
    return sent


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--import', dest='csv_file', help='Import CSV contacts')
    ap.add_argument('--settore', default='ristoranti')
    ap.add_argument('--limit', type=int, default=5)
    ap.add_argument('--send', action='store_true', help='Actually send (default: dry run)')
    args = ap.parse_args()

    if args.csv_file:
        add_contacts_from_csv(args.csv_file, args.settore)
    else:
        conn = init_db()
        send_outreach(conn, args.settore, args.limit, dry_run=not args.send)

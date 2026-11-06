#!/usr/bin/env python3
"""MCH — X Seeding: genera post X (<=280) per le pagine pSEO nuove (social proof/citazioni).

DRY-RUN di default: stampa + salva in jsonl, NON pubblica. Pubblica solo con --post
e solo se c'è uno script di posting (xurl) — altrimenti si ferma e avvisa.
Uso: python3 x_seed.py [--limit N] [--post]
     legge gli slug nuovi da output/new_slugs.json (generato da regen/make_new_sector_batch)
     e produce packages/data/x_posts.jsonl
"""
import os, sys, json, argparse, datetime, subprocess

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mch", "seo-farm"))
DOMAIN = "https://mch-seo-farm.vercel.app"

HOOKS = [
    "In Italia quasi nessuno lo chiede, ma esiste. I 10 software {cat} per {sec} del {y} (prezzi reali e pro/contro) -> {url}",
    "Quale {cat} conviene per i {sec} in Italia? Ho fatto un confronto di 10 tool con prezzi 2026 -> {url}",
    "Guide pratiche e gratuite: i {cat} per {sec} (confronto, prezzi, alternative open source) -> {url}",
]


def posts_for(slug: str, hooks=None) -> list:
    hooks = hooks or HOOKS
    cat, sec = (slug.partition("-")[0], slug.partition("-")[2]) if "-" in slug else ("software", slug)
    url = f"{DOMAIN}/settore/{slug}"
    out = []
    for h in hooks:
        p = h.format(cat=cat, sec=sec, y=datetime.date.today().year, url=url)
        p = p[:243] + "…" if len(p) > 280 else p
        out.append({"slug": slug, "text": p, "url": url, "ts": datetime.date.today().isoformat()})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()

    new = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "output", "new_slugs.json")
    slugs = json.load(open(new)) if os.path.exists(new) else [
        "pos-palestre", "crm-ristoranti", "gestionale-estetisti", "email-marketing-studi-medici", "booking-hotel"
    ][: a.limit]

    all_posts = []
    for s in slugs[: a.limit]:
        all_posts.extend(posts_for(s))
    out_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "packages", "data", "x_posts.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "a") as f:
        for p in all_posts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"[x_seed] {len(all_posts)} post pronti (dry-run, {len(slugs)} pagine) -> {out_path}")
    for p in all_posts[:3]:
        print(f"  • {p['text']}")
    if a.post:
        if not os.path.exists("xurl") and shutil_which("xurl") is None:
            print("  ! --post ma 'xurl' non disponibile: non pubblicato (resta dry-run). Installa xurl per abilitare.")
        else:
            print("  (posting via xurl: non implementato in dry-run — MCH deve abilitare esplicitamente)")
    else:
        print("  [dry-run] per pubblicare: xurl post --text \"...\" (abbiato da MCH)")


def shutil_which(name):
    import shutil
    return shutil.which(name)


if __name__ == "__main__":
    main()

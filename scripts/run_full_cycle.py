#!/usr/bin/env python3
"""MCH — Ciclo completo pSEO in un comando (pipeline sicura).

Default (zero costo, no API): GEO backfill -> build Astro -> sitemap -> X seeding dry-run.
Con --generate aggiunge prima la generazione contenuti (serve Groq/Gemini key + tempo).
Uso:  python3 run_full_cycle.py                # ciclo GEO+build+sitemap+x (dry-run)
      python3 run_full_cycle.py --generate     # + generazione nuovi articoli (API)
"""
import os, sys, subprocess, argparse, shutil

FARM = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))   # root repo /home/impact/mch/seo-farm
ASTRO = os.path.join(FARM, "apps", "seo-farm")                         # progetto Astro (build + content + dist)
SCRIPTS = os.path.join(FARM, "scripts")
NODE = shutil.which("node") or "/usr/bin/node"


def run(name, cmd, cwd=FARM, api=False):
    print(f"\n== {name} ==")
    if not api and not shutil.which(cmd[0]) and not os.path.exists(cmd[0]):
        print(f"   skip: '{cmd[0]}' non trovato")
        return
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or [""])[-1][:160]
    print(f"   [{'ok' if r.returncode == 0 else 'FALLITA'}] {name}: {tail}")
    if r.returncode and r.stderr:
        print("   " + (r.stderr.strip().splitlines() or [""])[-1][:160])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate", action="store_true", help="genera nuovi articoli (richiede key API)")
    a = ap.parse_args()

    if a.generate:
        run("Generazione contenuti (API)", ["python3", os.path.join(SCRIPTS, "generate_batch.py")], api=True)

    run("GEO backfill (FAQ+stats+link mesh)", ["python3", os.path.join(SCRIPTS, "geo_backfill.py")])
    run("Build Astro", ["npx", "astro", "build"], cwd=ASTRO)
    run("Rigenera sitemap", ["python3", os.path.join(SCRIPTS, "regen_sitemap.py")])
    run("X seeding (dry-run)", ["python3", os.path.join(SCRIPTS, "x_seed.py")])

    print("\nDONE. Verifica: (1) dist/ ha i JSON-LD; (2) sitemap aggiornato; (3) x_posts.jsonl in dry-run.")
    print("Pubblicazione: deploy Vercel DOPO OK di MCH (gate rigido).")


if __name__ == "__main__":
    main()

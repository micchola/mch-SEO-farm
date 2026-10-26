#!/bin/bash
# MCH pSEO — step di spedizione post-generazione (batch4 26/10):
# sitemap rigenerata → astro build → commit locale → tentativo push (atteso 401 token).
set -e
BASE="/home/impact/mch/seo-farm"
cd "$BASE"
echo "=== [1/4] sitemap ==="
python3 scripts/regen_sitemap.py
echo "=== [2/4] astro build ==="
cd apps/seo-farm
npm run build > /tmp/mch_build.log 2>&1 || { echo "BUILD FAIL"; tail -20 /tmp/mch_build.log; exit 1; }
echo "build ok: $(grep -c 'index.html' /tmp/mch_build.log 2>/dev/null || echo n/a) pagine"
tail -3 /tmp/mch_build.log
cd "$BASE"
echo "=== [3/4] commit locale ==="
git add -A
if git diff --cached --quiet; then
  echo "nothing to commit"
else
  git commit -m "pSEO batch4 (26/10): 5 nuovi articoli setter 8B (crm-estetisti, crm-studi-commerciali, booking-studi-dentistici, booking-pizzerie, fidelizzazione-estetisti) + sitemap aggiornata"
fi
echo "=== [4/4] tentativo push ==="
if git push origin main 2>&1; then
  echo "PUSH OK"
else
  echo "PUSH FALLITO (token 401 atteso) — restano in coda:"
  git rev-list --count origin/main..main
fi

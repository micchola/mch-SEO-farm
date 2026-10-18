#!/bin/bash
# MCH pSEO — Cron notturno
set -e
BASE="/home/impact/mch/seo-farm"
mkdir -p "$BASE/logs"
if ! curl -s http://127.0.0.1:11434/api/version | grep -q version; then
  ~/.local/bin/ollama serve &
  sleep 5
fi
cd "$BASE"
python3 scripts/build_dataset.py --type oss 2>&1
python3 scripts/generate_content.py --type oss --limit 10 2>&1
python3 scripts/generate_content.py --type sector --limit 5 2>&1
python3 scripts/generate_content.py --type comparison --limit 5 2>&1
cp -r content/oss/* apps/seo-farm/content/oss/ 2>/dev/null || true
cp -r content/settore/* apps/seo-farm/content/settore/ 2>/dev/null || true
cp -r content/confronto/* apps/seo-farm/content/confronto/ 2>/dev/null || true
cd "$BASE/apps/seo-farm" && npm run build 2>&1
cd "$BASE"
git add content/ apps/seo-farm/content/ apps/seo-farm/dist/
git diff --cached --quiet || { git commit -m "pSEO: content refresh $(date +'%Y-%m-%d %H:%M')" && git push origin main; }

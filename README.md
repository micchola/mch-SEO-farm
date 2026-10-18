## MCH pSEO

Monorepo per il pipeline pSEO MCH.

### Struttura
- apps/seo-farm — Astro (3 route: /oss/, /settore/, /confronto/)
- scripts/ — dataset builder + content generator (Ollama)
- packages/data/ — SQLite DB + schema
- .github/workflows/ — cron notturno

### Deploy
Auto-deploy su Vercel: mch-one.vercel.app

# Production validation — 2026-10-12 (commit 02fa6dd, branch conflict_051026_2250)
- Backend https://interview-ai-engine.onrender.com · Frontend https://interview-ai-engine.pages.dev
- Auth + Atlas + Career Score: 17/17 (prod_auth.py)
- Pack/IPS/Decision Report/isolation: 24/24 (pack_iso.py) — pack done in 88 s, IPS 64 B, CO-2026-000001
- UI prod: login → dashboard → dossier OK; exports PDF/DOCX CV + lettre OK (code in filename + footer/stamp, accents OK)
- Findings: (1) AI decision_summary cites its own IPS numbers (~48→~68) ≠ formula IPS 64; (2) admin login DEBUG display still active
- Test accounts created in prod: validation+prod1791765…@careeros.dev, validation+iso…, validation+bf… (password ProdCheck2026!)

# Validation production — Radar V2 (2026-10-13 02:55 UTC)

API : https://interview-ai-engine.onrender.com/api

**43/43 contrôles réussis**

Run 1 : {"fetched": 90, "new": 90, "known": 0, "analyzed": 50, "skipped_limit": 40} · par source : {"jooble": {"fetched": 54, "analyzed": 50}, "workday": {"fetched": 28, "analyzed": 0}, "boards": {"fetched": 8, "analyzed": 0}, "adzuna": {"fetched": 0, "analyzed": 0}}

- ✅ settings without token -> 401
- ✅ portal detect without token -> 401
- ✅ cron without secret -> 401
- ✅ Career Memory saved
- ✅ Jooble configured on server
- ✅ Workday + sites carrières available
- ✅ daily limit = 50
- ✅ no hardcoded companies for a new member
- ✅ Adzuna dropped when not configured
- ✅ companies saved, duplicate removed
- ✅ portals parsed (workday / amazon / jooble only)
- ✅ disabled company kept disabled
- ✅ portal detect Desjardins -> ok=True
- ✅ portal detect Amazon -> ok=True
- ✅ portal detect Hydro-Québec -> ok=False
- ✅ run started
- ✅ concurrent run -> 409
- ✅ run 1 done
- ✅ Jooble returns offers
- ✅ Workday returns offers
- ✅ amazon.jobs / sites carrières return offers
- ✅ no Jooble error
- ✅ analyzed <= 50 and analyzed_today <= 50
- ✅ sources_status shown
- ✅ offers analyzed with official IPS
- ✅ IPS 0-100 + priority A/B/C
- ✅ Decision Report starts with IPS Radar
- ✅ radar calibration: 8 criteria, stage radar
- ✅ A/B/C consistent with official thresholds
- ✅ Jooble offers flagged as excerpt
- ✅ no pack generated automatically
- ✅ run 2: already-known offers deduplicated
- ✅ run 2: analyzed offers not re-analyzed
- ✅ run 2: daily limit still respected
- ✅ pack on demand created
- ✅ application code CO-YYYY-NNNNNN + origin radar
- ✅ pack idempotent
- ✅ email = draft requiring member validation
- ✅ .ics valid with CO code
- ✅ member B cannot ignore A's offer
- ✅ member B cannot pack A's offer
- ✅ member B cannot read A's .ics
- ✅ member B dashboard empty

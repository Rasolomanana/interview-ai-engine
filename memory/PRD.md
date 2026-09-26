# PRD — Copilote Entretien IA

## Deux livrables
1. **App web** (React + FastAPI + MongoDB) — version serveur, dans /app/backend + /app/frontend.
2. **Extension Chrome autonome GRATUITE** — version 100% navigateur, sans serveur :
   - Machine d'états portée en JS (`frontend/src/lib/stateMachine.js`) — 12 tests PASS.
   - Génération directe Google Gemini (`frontend/src/lib/gemini.js`) avec la clé gratuite de l'utilisateur.
   - Persistance locale via `chrome.storage`/`localStorage` (`frontend/src/lib/storage.js`, `api.js`).
   - Voix : Web Speech API (fr-FR) + prosodie côté client. Vision : image inline Gemini.
   - Réglages (clé + modèle) : `components/console/SettingsPanel.jsx`.
   - Empaquetée : `/app/interview-copilot-extension/` (+ `.zip`), Manifest V3, CSP MV3-safe.

## Modèle IA
- Extension : Gemini 2.5 Flash (défaut, gratuit) / 2.5 Pro / 2.0 Flash — clé Google AI Studio de l'utilisateur.
- App web serveur : Anthropic claude-sonnet-4-6 via EMERGENT_LLM_KEY.

## État (2026-06-26)
- ✅ Machine d'états déterministe (NEUTRE/CANDIDAT/RECRUTEUR), TM3/5/6/7, compteur → NEUTRE à n=3.
- ✅ 12 tests non-régression PASS (backend pytest + port JS node).
- ✅ Mode CANDIDAT (3 puces ≤12 mots, gras, reveal), RECRUTEUR (prose, 1 question), vision, barge-in.
- ✅ Extension Chrome autonome gratuite construite, CSP nettoyée (scripts inline/distants retirés).
- ✅ Guide d'installation FR inclus (`GUIDE-INSTALLATION.txt`).

## Backlog
- P1 : side panel Chrome (chrome.sidePanel) pour usage discret pendant l'entretien.
- P1 : layout mobile en onglets.
- P2 : feedback flash post-simulation (R3), export/score de session, escalade UI.

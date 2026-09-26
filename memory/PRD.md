# PRD — Copilote Entretien IA

## Livrables
1. App web (React) + backend FastAPI (proxy IA, extraction PDF, Whisper).
2. Extension Chrome (Manifest V3) empaquetée : /app/interview-copilot-extension/ (+ .zip).

## Architecture
- Machine d'états déterministe en JS (frontend/src/lib/stateMachine.js) — 12 tests PASS.
- Deux fournisseurs IA (Réglages) :
  - Gemini : navigateur -> Google (clé gratuite user, gemini-3.8-flash). 100% local.
  - Serveur : navigateur -> backend /api/generate (Emergent key, Anthropic). Marche si Google bloqué.
- Persistance locale (chrome.storage/localStorage).

## Fonctionnalités (2026-06-26)
- ✅ Modes NEUTRE / CANDIDAT / RECRUTEUR + TM3/5/6/7 + compteur NEUTRE à n=3 + barge-in.
- ✅ Provider Gemini (gratuit) + Serveur (secours sans clé).
- ✅ Import CV en PDF (/api/extract-pdf).
- ✅ Écoute Auto : Micro (Web Speech, tél. à proximité) + Onglet Teams/Zoom/WhatsApp Web (getDisplayMedia + Whisper), auto-génération.
- ✅ Récapitulatif d'entretien + export .txt.
- ✅ Panneau latéral Chrome (side_panel).
- ✅ Fenêtre FLOTTANTE (Document Picture-in-Picture) — toujours au-dessus, à placer sous la caméra.
- ✅ Style de réponse : « Phrases complètes » (à lire sans réfléchir, ancré CV+poste, DÉFAUT) vs « Télégraphique ».
- ✅ Multi-plateforme : Teams, Zoom, Google Meet, WhatsApp (Web = onglet, tél = micro proximité), téléphone.

## Modèles
- Gemini : gemini-3.8-flash / gemini-flash-latest / gemini-3.5-flash.
- Serveur : claude-sonnet-4-6 via EMERGENT_LLM_KEY.

## Vérifications
- iteration_1..5 : 100% (state machine, deux providers, recap, écoute UI, style de réponse, flottant, pas d'overflow).

## Backlog (P1/P2)
- P1 : détection auto « Gemini bloqué » -> bascule Serveur ; abort du récap à la fermeture.
- P2 : audio de l'entretien enregistré/exporté ; scores ; refactor InterviewConsole (hooks usePip/useStream) ; warning React clé dupliquée (dev only).

# PRD — Copilote Entretien IA

## Livrables
1. App web (React) + backend FastAPI (proxy IA + PDF + Whisper).
2. Extension Chrome (Manifest V3) 100% client-side, empaquetée : /app/interview-copilot-extension/ (+ .zip).

## Architecture
- Machine d'états déterministe en JS (frontend/src/lib/stateMachine.js) — 12 tests PASS.
- Deux fournisseurs IA (Réglages) :
  - Gemini : navigateur -> Google Gemini (clé gratuite utilisateur, gemini-3.8-flash). 100% local.
  - Serveur : navigateur -> backend /api/generate (Emergent key, Anthropic). Marche si Google bloqué.
- Persistance locale (chrome.storage/localStorage). Backend Mongo présent mais non utilisé par le chat.

## Fonctionnalités (2026-06-26)
- ✅ Modes NEUTRE / CANDIDAT (3 puces ≤12 mots, gras, reveal) / RECRUTEUR (prose, 1 question).
- ✅ Machine d'états + TM3/5/6/7 + compteur NEUTRE à n=3 + barge-in.
- ✅ Provider Gemini (gratuit) + Serveur (secours, sans clé) — testés 100%.
- ✅ Import CV en PDF (backend /api/extract-pdf via pypdf).
- ✅ Écoute Auto : source Micro (Web Speech, téléphone à proximité) + source Onglet Teams/Zoom (getDisplayMedia + Whisper /api/transcribe), auto-génération de la réponse.
- ✅ Récapitulatif d'entretien (résumé structuré via provider) + export .txt.
- ✅ Panneau latéral Chrome (manifest side_panel + chrome.sidePanel).
- ✅ Voix/prosodie (stress/monotone/débit/confiance), vision image, mode DEBUG.

## Modèles
- Gemini : gemini-3.8-flash (défaut) / gemini-flash-latest / gemini-3.5-flash.
- Serveur : claude-sonnet-4-6 via EMERGENT_LLM_KEY.

## Backlog
- P1 : Écoute Auto — abort du récap à la fermeture ; détection auto Gemini bloqué -> bascule Serveur.
- P2 : audio de l'entretien enregistré/exporté ; scores ; refactor InterviewConsole en hooks.

# PRD — Assistant d'entretien IA (Moteur temps réel v4)

## Problème / Objectif
Application web (Windows navigateur) implémentant le moteur IA d'entretien spécifié
(Production v4). Deux modes étanches pilotés par une machine d'états déterministe :
- MODE CANDIDAT : copilote discret, 3 puces ≤ 12 mots, 2–3 mots en gras, rendu progressif.
- MODE RECRUTEUR : simulateur immersif, une question à la fois, prose, zéro puce/gras.
- État NEUTRE : clarification ≤ 25 tokens.

## Stack / Architecture
- Frontend : React 19, Tailwind, framer-motion, lucide-react, sonner. Command-center 3 colonnes.
- Backend : FastAPI, MongoDB (motor). SSE streaming.
- LLM : Anthropic claude-sonnet-4-6 (texte + vision) via EMERGENT_LLM_KEY (emergentintegrations).
- STT : OpenAI Whisper (whisper-1) via EMERGENT_LLM_KEY.
- Voix live : Web Speech API (fr-FR) + analyse prosodique côté client (stress/monotone/débit/confiance).

## Décisions clés
- La machine d'états, le compteur de tours et le barge-in sont gérés PAR L'APPLICATION
  (BLOC 2.3/2.4). `state_machine.py` est pur et testable ; l'ÉTAT RÉSOLU est injecté au LLM
  comme AUTORITÉ ABSOLUE → garantit le passage déterministe des 12 tests de non-régression.

## Endpoints
- POST/GET /api/sessions, GET/PUT/DELETE /api/sessions/{id}
- POST /api/sessions/{id}/message (SSE : event meta/delta/done/error)
- POST /api/sessions/{id}/reset
- POST /api/state/resolve (résolution pure — tests)
- POST /api/transcribe (Whisper)

## Implémenté (2026-06-26)
- ✅ Machine d'états (NEUTRE/CANDIDAT/RECRUTEUR) + TM3/TM5/TM6/TM7, priorité §4/§5.
- ✅ Compteur [TOURS_SANS_MARQUEUR] → NEUTRE à n=3 exactement.
- ✅ 12 tests de non-régression (T1–T12) : PASS (backend pytest 22/22).
- ✅ Mode CANDIDAT : 3 puces ≤12 mots, gras, rendu progressif, alerte, format vision [RÉPONSE : X].
- ✅ Mode RECRUTEUR : prose, une question, zéro puce/gras, incarnation.
- ✅ Signaux voix (V7/V8/V9) via TM6 (conf ≥ 0.7), analyse prosodique client.
- ✅ Barge-in (annulation génération, état inchangé).
- ✅ Upload image (vision) + Whisper STT.
- ✅ Persistance MongoDB (sessions + messages), historique sidebar.
- ✅ Panneau contexte (CV/poste/entreprise/secteur), inspecteur d'état, mode DEBUG.

## Backlog (P1/P2)
- P1 : layout mobile en onglets (panneaux masqués < lg actuellement).
- P1 : feedback flash post-simulation (R3) sur bouton dédié.
- P2 : export/score de session, historique multi-utilisateur, auth.
- P2 : escalade (3 incompréhensions → NEUTRE) exposée dans l'UI.

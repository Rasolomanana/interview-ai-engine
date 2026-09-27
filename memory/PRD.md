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

## Fonctionnalités (2026-06-27)
- ✅ **Chaîne de secours multi-fournisseurs** (option c) : `/api/generate` essaie dans l'ordre **Claude (Emergent) → OpenAI gpt-5.4 (Emergent) → DeepSeek (clé user, dernier recours)**. N'avance au fournisseur suivant que si aucun token n'a encore été streamé. Combinée au fallback client Gemini→Serveur, la chaîne complète est : Gemini(user) → Claude → OpenAI → DeepSeek. Clé DeepSeek stockée dans backend/.env (`DEEPSEEK_API_KEY`), jamais dans le code/frontend. Vérifié curl (Claude streame). ⚠️ La clé DeepSeek est valide mais le compte a un **solde insuffisant (402)** → DeepSeek ne répondra qu'après recharge ; sans impact car Claude/OpenAI fonctionnent.
- ✅ **Bug corrigé — Gemini 429/quota** : bascule auto Gemini→Serveur (iteration_12).
- ✅ **Bug corrigé — import PDF Android** (extraction client pdfjs, iteration_11).
- ✅ **Bug corrigé (récurrent) — question de format** (iteration_10).
- ✅ **Bug corrigé — « Bonjour » répété** (iteration_9).
- ✅ **Clarté des deux zones de saisie** (Écoute Auto recruteur en haut / Votre saisie en bas).
- ✅ **Cadre « Question captée » redimensionnable** (`resize: vertical`).
- ✅ **Version courte polie si question incomprise** : rule (4) renvoie 2 courtes phrases (≤15 mots) préfixées « [À DIRE] » à dire au recruteur pour demander de reformuler. Vérifié curl E2E.
- ✅ **Robustesse candidat (anti-question + bruit)** : ne demande plus jamais le format, extrait les mots-clés des questions bruitées.
- ✅ **Bug corrigé — vidage auto de la question captée** (testing_agent iteration_8, 4/4).
- ✅ **Layout figé à la hauteur de l'écran** : la colonne centrale est bornée à `lg:h-[calc(100vh-2rem)]` (au lieu de grandir avec le contenu) → la page ne défile plus (scrollHeight = innerHeight), seul le fil scrolle en interne et le composer/micro reste toujours visible en bas. Fini le saut en haut de page après chaque génération/changement de fenêtre. Vérifié (PAGE_SCROLLS=False + screenshot).
- ✅ **Panneaux latéraux fixes (sticky)** : colonnes gauche et droite épinglées.
- ✅ **Transcript éditable + toujours visible** (AutoListenBar) : champ modifiable affiché en permanence (taper/coller/corriger/effacer) + bouton « Effacer ».
- ✅ **Analyse site + réponses STAR prêtes** (`/api/analyze-company`) : sections VALEURS & CULTURE, MISSION & PRIORITÉS, QUESTIONS PROBABLES, et **RÉPONSES STAR PRÊTES** — pour les 4 questions clés, une réponse STAR complète ancrée dans le CV (transmis) ET reliée explicitement aux valeurs (sécurité, innovation, collaboration) pour montrer les recherches. Vérifié par curl E2E (RTX + CV → STAR personnalisé chiffré).
- ✅ **Méthode STAR** (toggle Réglages, activé par défaut) : structure les réponses aux questions comportementales en Situation/Tâche/Action/Résultat.
- ✅ **Fix qualité réponses candidat (mode « Phrases complètes »)** : le prompt génère une VRAIE réponse d'entretien complète et cohérente (4 à 6 phrases fluides), répond à TOUTES les parties de la question, ancrée CV+poste+entreprise.
- ✅ Bouton unique **Live** (live-btn) : démarre l'écoute auto + ouvre la fenêtre flottante (PiP). Re-clic = arrête écoute + ferme flottant. Fermer le flottant (pagehide) arrête aussi l'écoute.
- ✅ **Ton des réponses** : confiant / humble / technique / neutre (persistant, injecté dans le prompt candidat).
- ✅ Correctif lint bloquant : `chrome` -> `globalThis.chrome` dans `storage.js` et `ext-bg.js` (0 erreur oxlint). Extension repackagée (446K, CSP MV3 propre, sans script distant).

## Vérifications
- iteration_1..6 : 100% (state machine, deux providers, recap, écoute UI, style de réponse, flottant, Live+ton).
- iteration_7 : 100% (5/5) — mode Serveur sans régression, persistance du ton, impact confiant vs humble, Live start/stop. Note : le trigger pagehide (fermeture flottant -> stop écoute) n'est pas pilotable en headless mais le handler code est correct (InterviewConsole.jsx l.285).

## Backlog (P1/P2)
- P1 : détection auto « Gemini bloqué » -> bascule Serveur ; abort du récap à la fermeture.
- P2 : audio de l'entretien enregistré/exporté ; scores ; refactor InterviewConsole (hooks usePip/useLive) ; accessibilité radiogroup/aria-pressed sur groupes de boutons (ton/style).

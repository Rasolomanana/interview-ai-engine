# PRD — Copilote Entretien IA

## Fix DÉFINITIF (juin 2026) — Question parasite NEUTRE "simuler ou aider ?" éliminée
- Symptôme récurrent : coller/saisir une question du recruteur en session neuve (état NEUTRE) faisait répondre le copilote par « Souhaitez-vous que je joue le recruteur en simulation ou que je vous aide à répondre ? » au lieu de générer une réponse.
- Cause racine : entrée libre sans marqueur en NEUTRE → l'état restait NEUTRE → reminder de clarification. Les correctifs précédents ne visaient qu'une variante du message.
- Fix SOURCE UNIQUE dans `stateMachine.js` (§4.5) : si l'état résolu est NEUTRE, sans reset, et que le texte est substantiel (≥ 4 mots, pas un simple accusé « ok/oui »), on force CANDIDAT (copilote par défaut = aider à répondre). Couvre TOUTES les voies d'entrée (composer, Live, auto-listen, futures). La simulation reste opt-in via les marqueurs explicites [MODE_SIMULATION]/"simule un entretien"/boutons.
- Vérifié navigateur : question recruteur saisie en session neuve → ÉTAT RÉSOLU CANDIDAT, réponse complète en 6 puces ancrées dans le poste, plus AUCUNE question méta.

## Fix (juin 2026) — Récap qui se coupe (Gemini 503/429)
- `streamRaw` (récap) : ajout du repli automatique vers le mode Serveur si Gemini échoue avant tout contenu (503 surcharge / 429 quota). Toast d'info. Chemin serveur vérifié (récap complet).


- Le streaming SSE ne suffisait pas : une connexion unique de ~40s est tronquée par les proxys d'entreprise / passerelles (échec récurrent 3x).
- Backend : POST /api/analyze-application crée un job (Mongo `analysis_jobs`), lance `asyncio.create_task(_run_application_analysis)`, renvoie `{job_id}` immédiatement. GET /api/analyze-application/{job_id} → `{status, result, error}`. Le worker fait fetch site + LLM (Claude→OpenAI→DeepSeek) + parse JSON puis persiste.
- Client `analyzeApplication` : POST puis polling toutes les 2s (requêtes <1s), tolérant aux coupures, timeout global 3 min → immunisé contre tout timeout de connexion longue.
- Vérifié via curl ingress (job done ~39s) ET navigateur preview (toast "Analyse terminée", score/mots-clés/signaux rendus). Extension repackagée (main.5b4752a4.js, 850K).
- Reste connu (dev-only, non bloquant, pré-existant) : warning React "duplicate key" hors panneau ATS.



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
- ✅ **Analyse de candidature « recruteur senior » (plein écran)** : le Contexte est désormais **plein écran, 2 colonnes**. Gauche = CV + offre + URL site. Bouton **« Analyser (CV + offre + site) »** → `/api/analyze-application` (JSON) qui produit à droite : **CV optimisé ATS éditable** (réalisations chiffrées, valeurs `[à confirmer]` rectifiables), **score de compatibilité /100**, **lacunes**, **5 mots-clés manquants**, **signaux d'alerte** vus par un recruteur, + récap valeurs/questions entreprise. Le **CV amélioré (`atsCv`) est prioritaire dans le BLOC CONTEXTE** → les réponses STAR d'entretien s'appuient dessus. Utilise la chaîne de secours Claude→OpenAI→DeepSeek. Vérifié testing_agent iteration_13 (backend 7/7, frontend e2e : score 68/100, CV ATS ~3000 car., 5 mots-clés, 5 alertes, 5 lacunes).
- ✅ **Chaîne de secours multi-fournisseurs** (Claude→OpenAI→DeepSeek).
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

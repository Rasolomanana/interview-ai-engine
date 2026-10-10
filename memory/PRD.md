# PRD — Copilote Entretien IA

## Amélioration (juin 2026) — Indicateur « capture locale » bien visible
- État `screenCapturing` : bannière verte proéminente au-dessus du composer pendant une capture d'écran active : « 🔒 Capture d'écran LOCALE active — invisible pour le recruteur. Ce n'est PAS le partage Teams/Zoom. » + bouton « Arrêter la capture » (`stop-screen-capture-btn`).
- Toast de capture renforcé (« 🔒 Capture LOCALE ajoutée — invisible pour le recruteur »). Titre du bouton capture mis à jour. data-testid `local-capture-banner`.
- Rappel : getDisplayMedia est local, non transmis à Teams/Zoom ; réserve proctoring/examen surveillé. Non testable headless (permission écran requise).


- Backend `/api/generate` : `images_base64: List[str]` (rétro-compat `image_base64`). `_stream_with_fallback` construit N `ImageContent`. Vérifié ingress : 2 images réelles → 2 problèmes résolus séparément (« 42 », « Paris »).
- Frontend : `image` state = tableau. Collage (Ctrl/Cmd+V) multiple, upload `multiple`, capture d'écran = append (n'envoie plus seul). Aperçus multiples avec suppression individuelle + « tout retirer ». `send` → `body.images` (array) ; `streamServer`/`streamGemini` bouclent sur les images ; `streamMessage` normalise en tableau.
- Prompt VISION multi : traite CHAQUE image et CHAQUE problème séparément (matrice/suite, association/glisser-déposer, QCM, schéma), titre en gras + réponse (appariement complet si association) + justification. Réponses persistées dans l'historique de session.


- `InterviewConsole.handlePaste` branché sur `onPaste` du textarea `message-input` : détecte une image dans le presse-papier → FileReader → `setImage` (data URL) → aperçu + toast. Même chemin vision que l'upload/capture d'écran. Titre du bouton image mis à jour.
- Vérifié navigateur : événement paste synthétique avec fichier image → aperçu `image-preview` visible + toast « Image collée ».


- Backend : `/api/cover-letter` (job+polling, réutilise `analysis_jobs` + poll `/analyze-application/{job_id}`). Worker `_run_cover_letter` via `_generate_text` (Claude Sonnet). Lettre 1 page (~300 mots), adaptée à l'offre + CV ATS + valeurs entreprise, dans la langue de l'offre. Testé ingress : job done ~14s, lettre FR valide.
- Frontend : `api.generateCoverLetter({cv,poste,entreprise})` (POST+poll) ; `docxExport.downloadCoverLetterDocx` (Word 1 page, marges 1", justifié, gras). ContextPanel : bloc « Lettre de motivation » (bouton Générer/Régénérer violet + textarea éditable + bouton Télécharger Word). Persisté dans context.coverLetter (saveContext).
- .docx lettre validé (test Node : PK, gras préservé). Téléchargement navigateur réel à confirmer côté utilisateur.


- Dépendance `docx@8.5.0` (yarn add ; version compatible node 20).
- `frontend/src/lib/docxExport.js` : `downloadAtsCvDocx(markdown, filename)` convertit le markdown ATS en .docx mis en forme (## → sections+filet, ### → sous-titres, **gras**, puces, --- ignoré ; Calibri 10-11pt, marges 0.5" pour ~2 pages).
- Bouton `download-ats-word-btn` dans ContextPanel (colonne droite, sous le CV ATS) : exporte UNIQUEMENT le CV optimisé ATS, nom de fichier basé sur poste/session.
- Vérifié : .docx valide (ZIP PK, word/document.xml, titres/gras/puces OK) via test Node. Téléchargement navigateur réel à valider côté utilisateur.


- `useAutoListen` : déclenchement de la génération sur (a) « ? », (b) mots interrogatifs FR&EN (`isLikelyQuestion`), (c) SILENCE après parole (fenêtre vide + buffer ≥ 5 mots) → mains-libres même sans ponctuation. Appliqué aux voies Whisper (onglet) et Web Speech (micro). Buffer vidé après chaque emit.
- `AutoListenBar` garde-fous : bouton visible « Réponse auto : ON / EN PAUSE » (coupe l'auto sans stopper l'écoute) + bandeau ambre en pause ; « Arrêter l'écoute » (rouge) ; « Interrompre » (barge-in composer) inchangé. `data-testid=listen-auto-toggle` conservé.
- NB : captation Teams réelle (audio+permission) non testable en env automatisé.


- Bouton « Capturer l'écran » (`InterviewConsole.captureScreen`, data-testid `capture-screen-btn`) : getDisplayMedia (vidéo) → frame sur canvas (JPEG 0.85, max 1600px) → envoyée via send() avec marqueur [REPONSE_ORALE] → état CANDIDAT + V1_VISION → analyse IA (tests psychotechniques/QCM/écran partagé). Stream écran gardé actif pour captures répétées ; nettoyage au démontage ; message clair si getDisplayMedia indisponible (mobile) ou refusé. Desktop uniquement.
- Warning React "duplicate key" : VÉRIFIÉ ÉLIMINÉ (chargement propre + flux complet envoi/réponse serveur = 0 warning/erreur). Provenait d'un build antérieur ; toutes les clés de liste sont en index ou id unique.
- NB : getDisplayMedia et micro réels non testables en env automatisé (écran/permission requis) — à valider sur la machine utilisateur.


- Architecture confirmée : app 100% client (état + prompts + persistance dans le navigateur) ; backend = 5 endpoints utilitaires (/generate, /transcribe, /analyze-company, /analyze-application, /extract-pdf).
- 🔧 Corrigé : `tests/test_analyze_application.py` réécrit pour le contrat job+polling → 30/30 tests backend passent.
- Dette technique identifiée (SANS impact utilisateur, non corrigée volontairement) :
  * `backend/state_machine.py` + `backend/prompt.py` + endpoints `/sessions/*`, `/sessions/{id}/message`, `/state/resolve` = code legacy non utilisé à l'exécution ; portent l'ancien prompt (3 puces + question NEUTRE, sans STAR/langue/anti-salutation). Divergent du frontend qui fait autorité.
  * Collection Mongo `analysis_jobs` sans purge.
  * Repli DeepSeek ignore l'image.
  * CORS allow_credentials=True + origins "*" (inoffensif, pas de credentials).
  * Warning React "duplicate key" (dev-only, cosmétique).
- Tous les correctifs récents confirmés présents dans le chemin actif (frontend) : §4.5, STAR bilingue, LANGUAGE_REMINDER, anti-salutation, robustesse, chien de garde Gemini, repli micro Whisper, job+polling.


- `useAutoListen.recordWindow` : sélection du codec réellement supporté (Android Chrome n'a souvent que opus) via MediaRecorder.isTypeSupported ; blob créé avec le vrai mimeType.
- `transcribeBlob` : extension de fichier dérivée du mimeType (webm/ogg/mp4/wav) pour que Whisper accepte l'audio.
- Scénarios Android : a (tel. écoute un entretien sur PC) et c (copilote sur 2e appareil) → OK via micro + Whisper. b (entretien ET copilote sur le MÊME tel. pendant un appel Teams/Zoom) → limité par Android (l'app d'appel monopolise le micro, navigateur en arrière-plan coupe la capture) ; recommander a ou c. Capture d'onglet (getDisplayMedia audio) NON supportée sur mobile.


- Cause : le micro utilisait l'API Web Speech de Chrome, qui dépend des serveurs de Google (bloqués par la politique réseau) → aucune détection, sans erreur visible. De plus un `getUserMedia` ouvert en parallèle pouvait entrer en conflit avec Web Speech.
- Fix (`useAutoListen.js`) : le micro tente Web Speech (live, gratuit) SANS flux getUserMedia concurrent ; il bascule automatiquement sur la transcription serveur Whisper (`recordWindow`) si Web Speech renvoie une erreur (network/audio-capture/service-not-allowed) OU reste 10s sans résultat. Whisper fonctionne même si Google est bloqué et détecte FR/EN.
- Vérifié : endpoint /api/transcribe (auto-langue) atteint bien Whisper et gère les erreurs proprement. NB : le micro réel (permission + voix + réseau du poste) ne peut être testé que sur la machine de l'utilisateur.


- Détection auto de la langue de la question (dans le MÊME appel LLM → zéro latence supplémentaire).
- La réponse (et les libellés STAR / phrases « [À DIRE] ») est rédigée dans la langue du recruteur (anglais → réponse en anglais, à lire à voix haute).
- Si la langue ≠ français : 1re ligne « 🌐 FR : <traduction concise> », affichée comme un bandeau bleu distinct (parse.js `translation` + CandidateBullets + FloatingAnswer). Aucune ligne vide / séparateur parasite.
- STAR : libellés adaptés à la langue (Situation:/Task:/Action:/Result: en anglais).
- Écoute auto : Whisper (onglet Teams/Zoom) passe en détection auto de langue (`language=auto` → None). Micro Web Speech : sélecteur FR/EN dans la barre d'écoute (`micLang`).
- Vérifié navigateur : question EN → bandeau FR + réponse STAR en anglais, état CANDIDAT.


- Symptôme : en mode Gemini, la 1re génération « bloquait » ; passer en Serveur (sans clé) débloquait.
- Cause racine : `gemini.js` n'avait AUCUN timeout. Un réseau d'entreprise qui bloque Google en laissant la connexion pendante (sans erreur) fige `fetch` indéfiniment → le repli auto (déclenché par une erreur) ne partait jamais.
- Fix 1 — chien de garde `gemini.js` : timeout « temps jusqu'au 1er token » de 9s. Sans réponse, on abandonne via une erreur normale (non-AbortError) → `streamMessage`/`streamRaw` basculent automatiquement sur le Serveur. Le barge-in utilisateur reste distingué (AbortError).
- Fix 2 — mémoire de session `api.js` (`geminiUnavailable`) : dès le 1er échec/timeout Gemini, tous les tours suivants passent DIRECTEMENT au Serveur (plus jamais d'attente de 9s en plein entretien). Réinitialisé au rechargement.
- Vérifié navigateur : clé Gemini invalide → toast « Gemini indisponible — bascule automatique sur le mode Serveur » + réponse STAR générée immédiatement, état CANDIDAT.


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

## Déploiement autonome (hors Emergent) + fiabilité réseau — Oct 2026
Export complet dans `/app/deploy-export/` + archive `/app/interview-ai-engine-standalone.zip`
(Cloudflare Pages + Render + MongoDB Atlas). Dépendance `emergentintegrations` remplacée
par un shim local `backend/emergentintegrations/`.

- ✅ **Fallback SSL/réseau Gemini→Serveur** (`lib/api.js`) : `isNetworkError()` détecte
  `Failed to fetch`/`ERR_SSL_*`/cipher/cert ; `activateServerFallback()` logue
  `[Gemini→Serveur] Fallback activé …`, expose `window.__geminiUnavailable=true`.
- ✅ **OpenRouter fournisseur serveur principal** (shim) : chaîne cheapest-first
  OpenRouter→Anthropic→OpenAI→DeepSeek, activée selon les clés présentes. Passe en
  réseau d'entreprise (endpoint openrouter.ai). Modèle via `OPENROUTER_MODEL`.
- ✅ **Logique hybride vision** : `OPENROUTER_VISION_MODEL` utilisé auto UNIQUEMENT quand
  des images sont jointes ; sinon modèle texte économique. Testé (texte→deepseek, image→gpt-4o-mini).
- ✅ **Modèle Anthropic** défaut mis à jour `claude-sonnet-4-6` (fix 404 claude-3-5-sonnet-20241022).
- ✅ **Fix build Cloudflare** : cause = `yarn.lock` non suivi par git → npm non-déterministe
  (date-fns ERESOLVE puis ajv/ajv-keywords codegen). `yarn.lock` (frontend + export) forcé en
  suivi git. `yarn build` validé. Builder avec yarn (lockfile déterministe), pas npm.
- ✅ **Gate mot de passe mode Serveur manuel** (`SettingsPanel.jsx` + `/api/verify-server-access`) :
  Gemini reste défaut ; clic manuel "Serveur" → mot de passe requis (backend `SERVER_ACCESS_PASSWORD`,
  hmac.compare_digest) ; correct → serveur activé + mémorisé (localStorage `serverAccessGranted`) ;
  incorrect → reste Gemini + erreur ; fallback auto NON gaté. Vérifié testing_agent iteration_14 (5/5, 100%).

## Backlog ajouté
- P1 : rate-limiting sur `/api/verify-server-access` (anti-brute-force) ; TTL/purge `analysis_jobs`.
- P2 : grant serveur via token signé court (au lieu d'un booléen localStorage) si enforcement backend requis.

## Compteur de coûts par entretien — Oct 2026
- ✅ **Badge estimation crédits** (`InterviewConsole.jsx` header, `lib/costEstimate.js`) :
  pastille `data-testid=cost-counter` à côté du turn-counter. Estime tokens (~4 car/token,
  +800/image) et coût USD par tour via `estimateTurnCost()`, émis par `streamMessage` → `onUsage`.
  Gemini = gratuit ($0) ; Serveur = estimation (défaut ~DeepSeek $0.30/$1.10 par M, surchargeable
  via localStorage.serverPricing). Cumul par session persisté dans localStorage `cost:<sessionId>`,
  tooltip détaillé (tokens entrée/sortie, tours, fournisseur), clic = remise à zéro.
  Vérifié testing_agent iteration_15 (4/4, 100% : badge, incrément serveur ≈$0.0010, persistance, reset).

## Espace administrateur (Lot A) — Oct 2026
Décisions user : email Resend différé (Lot B) ; CV complet stocké UNIQUEMENT si consentement opt-in ;
/admin protégé par ADMIN_PASSWORD (inaccessible si non défini) ; pas de pays ; visiteurs = sessions
ayant lancé une simulation ; rétention TTL 90j.

- ✅ **Backend `admin.py`** (`create_admin_router`): POST /api/admin/login, GET /api/admin/stats
  (header X-Admin-Password), GET /api/admin/export?fmt=csv|xlsx. Helpers record_event,
  record_ats_submission (CV stocké seulement si consent), anonymize_ip (IPv4→/16, IPv6→3 hextets),
  ensure_indexes (TTL 90j sur admin_events + ats_submissions). Lecture ADMIN_PASSWORD en lazy (load_dotenv order).
- ✅ **server.py** : POST /api/track (simulation + llm_call reportés par le CLIENT → couvre Gemini & Serveur),
  analyze-application accepte consent+session_id et enregistre l'analyse, cover-letter logue un event,
  startup ensure_indexes, include admin router.
- ✅ **Frontend** : page `/admin` (AdminDashboard.jsx, login + 5 cartes stats + conso LLM + séries jour/semaine/mois
  + tableau soumissions + export CSV/Excel), PrivacyBanner (bannière confidentialité dismiss persistant),
  case consentement opt-in NON pré-cochée dans ContextPanel, trackEvent dans onUsage, react-router (/ et /admin).
- ✅ Vérifié testing_agent iteration_16 (backend 11/11, frontend 100%). Tests: /app/backend/tests/test_admin.py.
- Preview creds : ADMIN_PASSWORD=admin2026, SERVER_ACCESS_PASSWORD=interview2026.

## Lot B (à faire, après feu vert + clé) — RGPD
- Email Resend vers raskint09@gmail.com (CV + rapport ATS + score + date) UNIQUEMENT si consentement.
  Nécessite RESEND_API_KEY + domaine expéditeur vérifié. Prévoir bouton d'effacement (droit à l'oubli) dans /admin.
- Note RGPD : transfert US (Gmail) sensible ; base légale/consentement sous responsabilité de l'exploitant.

## 2026-10-10 — Admin: Gemini vs Serveur split + per-simulation provider
- /api/generate SSE `done` event now carries {provider, model} (real server provider).
- Frontend tracks llm_call with real provider (gemini / anthropic / openrouter / openai / deepseek), mode, model.
- /api/admin/stats: llm.gemini_calls/server_calls/gemini_cost/server_cost + simulations_detail (last 100, mixed flag).
- Dashboard: Gemini vs Serveur cards + "Dernières simulations" table (components/admin/SimulationsTable.jsx). Mirrored in deploy-export.
- Tested: iteration_17 (100%). Temporary admin login debug display still active (remove once prod dashboard confirmed).
- Prod blocker found: Render cannot reach Atlas (ServerSelectionTimeout) → user must allow 0.0.0.0/0 in Atlas Network Access.

## 2026-10-10 — Gemini exact-error diagnostics
- lib/gemini.js classifies errors: KEY_INVALID, KEY_DENIED, QUOTA, MODEL_UNAVAILABLE, GOOGLE_DOWN, BAD_REQUEST, TIMEOUT (9 s first-token), NETWORK (browser/SSL/CORS), EMPTY (blocked/filtered).
- Fallback toast (15 s) + console + window.__geminiLastError + localStorage geminiLastError + trackEvent("gemini_error").
- Settings: GeminiDiagnostic component ("Tester Gemini" button + last error box). Mirrored in deploy-export.
- Self-tested: fake key → "Clé API invalide (HTTP 400) INVALID_ARGUMENT". Other branches not E2E-tested.

## 2026-10-10 — LLM chain: Gemini Flash → OpenRouter free → OpenRouter paid → Anthropic (last)
- deploy-export backend: SERVER_CHAIN = (label, provider, model): openrouter_free (OPENROUTER_FREE_MODEL, default openrouter/free) → openrouter (OPENROUTER_MODEL) → anthropic. OpenAI & DeepSeek removed from text chain (OPENAI_API_KEY only for Whisper).
- Free entries keep their model even with images (no forced paid vision swap).
- Frontend: default Gemini model gemini-flash-latest; cost estimate per real provider (free=0, anthropic 3/15 $/M); dashboard labels "OpenRouter gratuit"/"OpenRouter (payant)".
- Verified via mocked-provider unit run (free 429 → paid). Real provider calls not tested (user keys).

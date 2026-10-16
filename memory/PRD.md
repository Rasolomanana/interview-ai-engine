# PRD — Copilote Entretien IA / CareerOS

## Fonctionnalité (juin 2026) — Connecteurs à prévoir + UKG + portails bloqués
- Connecteur UKG (UltiPro) : `radar_sources.ukg` (POST JSON `/JobBoardView/LoadSearchResults`), URL `recruiting*.ultipro.(com|ca)/{TENANT}/JobBoard/{GUID}` → kind `ukg`, slug `host/TENANT/GUID` ; détecté sur les sites carrières.
- Portails bloqués : `radar_discovery.is_blocked` (403/429/503 + Cloudflare « Just a moment »/captcha) → `blocked: true`, message « bloqué volontairement par l'employeur (403 / protection anti-robot) », label entreprise « Bloqué (anti-robot) : X », 4e groupe du résumé, annuaire et carte Portails (run.portals.blocked). Pas de contournement (choix utilisateur).
- Admin onglet « Connecteurs » (`careeros/connectors.py`, GET `/api/admin/connectors`) : backlog classé par impact (entreprises, membres, offres Jooble 30 j, exemples, difficulté, score, priorité ; bloqués = « Aucune (protection) ») + connecteurs actifs (entreprises, membres, offres lues/retenues, % lecture, replis Jooble, bloqués).
- Priorités utilisateur : UKG ✅ → Avature → Taleo → Phenom (ordre final selon le tableau d'impact).
- Testé : iteration_29 (admin 7/7, UI 100 %) + curl (backlog seedé, UKG, Sobeys bloqué).

## Amélioration (juin 2026) — Ergonomie Réglages du Radar
- Dialog en colonne : hauteur max 94vh, largeur 3xl, en-tête et bouton « Enregistrer » fixes, corps défilant (`radar-settings-body`, `radar-settings-footer`). Liste d'entreprises sans défilement imbriqué.
- Loupe : lance la détection immédiatement + défilement automatique vers le résultat ; résultats dans une zone défilante dédiée (`portal-results-{i}`, max-h-64), compteur « N proposition(s) · M lisible(s) », URL sur ligne propre, bouton Associer toujours visible.
- Mobile (<640px) : suggestions dans un panneau bas dédié (Sheet `portal-sheet-{i}`).

## Amélioration (juin 2026) — Résumé des entreprises suivies
- `CompanySummary.jsx` (Réglages Radar) : Via portail employeur / Suivies via Jooble / Détectées mais non prises en charge (dépliables). Champ entreprise `detected` (persisté) rempli par la loupe, « Tout détecter » et l'annuaire (« Non pris en charge : Phenom », « Illisible : SuccessFactors », « Aucun portail détecté »).
- Annuaire : ATS nommé pour les employeurs sans flux (BNC Avature, Bell/Air Canada Phenom, CGI Njoyn, Metro propriétaire).
- Incident prod : « Not Found » sur la détection = Render pas sur le dernier commit (Cloudflare à jour) ; résolu par redéploiement utilisateur.
- BACKLOG P1 : lecteur Phenom (demandé par l'utilisateur pour une prochaine itération : Air Canada, Bell).

## Fonctionnalité (juin 2026) — Qualité des sources Radar : portails employeurs
- Nouveaux lecteurs (`radar_sources.py`) : SuccessFactors RMK (flux RSS public `/services/rss/job/`), Oracle Recruiting (REST `recruitingCEJobRequisitions`), iCIMS (HTML, au mieux), SmartRecruiters (API publique). parse_portal reconnaît Oracle/iCIMS/SmartRecruiters/RSS SF.
- `radar_discovery.py` : annuaire 26 employeurs QC/CA vérifiés en direct (cache 6 h) — Workday (Desjardins, Intact, iA, Beneva, Saputo, TD, CAE, Couche-Tard, Intelcom), SuccessFactors (Hydro-Québec, Rogers, Bombardier, TELUS, Hydro One, Scotia, CN, CPKC, Sobeys=403 illisible), Oracle (Ville de Montréal), SmartRecruiters (Ubisoft), Amazon ; sans flux public → Jooble (Banque Nationale, Bell/Phenom, Air Canada, Metro, CGI/Njoyn). Détection : annuaire + scan site (site web facultatif, sinon nom.com/.ca, careers./jobs.) + devinettes Greenhouse/Lever/Ashby/SmartRecruiters/Workday ; ATS non pris en charge signalés.
- Endpoints : POST `/api/careeros/radar/portal/discover`, GET `/api/careeros/radar/directory`, `/portal/detect` sonde SuccessFactors.
- Run : `portals` {entreprise: kind, ok, fetched, matched, error} ; Jooble interroge d'abord les entreprises sans portail (repli). UI : loupe « Trouver le portail » + « Associer » (validation explicite), « Tout détecter », « Annuaire » (ajout 1 clic), carte « Portails employeurs » (configurés, taux de lecture, offres lues/retenues, échecs).
- Testé : iteration_28 → backend 29/29, frontend 100 %.

## Correctif (juin 2026) — Radar automatique : 0 analysée / tout reporté
- Cause : la limite quotidienne (50 analyses, 5 IA) comptait depuis minuit UTC (= 20 h la veille à Toronto en heure d'été). Des analyses faites la veille au soir épuisaient le quota du passage de 6 h → budget 0 → tout « reporté ».
- Fix : `_day_start()` = minuit America/Toronto pour `_analyzed_today`, `_ai_today`, pool IA et dashboard. Le run enregistre `budget` et un message `errors.limite` si le quota est déjà atteint.
- Workday / sites carrières « Aucun portail configuré » : le compte du membre n'a aucune entreprise avec URL de portail ; la validation production utilisait un compte test avec Desjardins / Intelcom (Workday) + Amazon (amazon.jobs).

## Amélioration (juin 2026) — Facturation fournisseurs
- Fournisseur : `billing_day` (1-31), `billing_cycle` mensuel/annuel (annuel = mois anniversaire de start_month, récurrent proposé seulement ce mois-là). Catalogue : `last_invoice` (dernier montant réel saisi), `next_invoice` (prochaine date prévue).
- Ligne du mois : `billing_date` (DateField FR) + `note`. Sortie : `due_date`, `warnings` (date_missing, real_unconfirmed si échéance passée, estimate_only ≥ 0,01 $) ; compteurs `warnings` dans Alertes. Avertissements non bloquants.
- Testé : curl + parcours UI (date + note → avertissement disparaît, catalogue « Dernière / Prochaine facture »).

## Amélioration (juin 2026) — Rentabilité v2 : nature des données, catalogue, 2 marges
- Nature sur chaque valeur : Réel (facture/encaissé), Estimé (saisi, récurrent par défaut, jetons×tarif), Calculé (dérivé, « % réel »). Composant `Nature.jsx` + légende.
- Catalogue administrable : `finance_categories` (famille infrastructure/ia/developpement/marketing/autres) et `finance_providers` (récurrent/ponctuel/variable, montant habituel+devise, début/fin, suspension, lien journal IA google/openrouter/anthropic/autre, statut actif/archivé). Suppression seulement si non utilisé (409 sinon), archivage/réactivation, historique `finance_audit`. Seed + migration v1 au démarrage (`seed_catalog`).
- Mois : `lines[{provider_id, estimated, real, currency, note}]`, `revenue_real`. Récurrents proposés automatiquement (Estimé) ; facture → Réel ; bouton « confirmer ». Revenu théorique / attendu / encaissé / écart / non expliqué.
- Marge d'exploitation (hors dév.) + marge nette (tout inclus), investissements ponctuels du mois, 10 KPI, réponses clés, coût par membre actif / actif payant / payant, projections hors développement.
- Testé : iteration_27 → backend 14/14, frontend 100 %, mobile OK.

## Fonctionnalité (juin 2026) — Admin « Rentabilité CareerOS »
- Backend `careeros/finance.py` : journal `ai_usage` (chaque appel IA serveur : fournisseur, modèle, bucket, facturation, fonctionnalité copilote/analyse/premium/entreprise, jetons estimés ≈ 4 car./jeton) branché dans `_stream_with_fallback`, `_generate_text`, analyse entreprise (preview + deploy-export). `member_activity` (membre actif par mois, via current_user). `finance_months` (prix, payants forcés, ajustements, coûts plateforme CAD/USD, factures IA réelles). `admin_settings.finance` (taux USD→CAD, tarifs $/M jetons).
- Endpoints admin : GET `/api/admin/finance?month=`, PUT `/api/admin/finance/{month}`, PUT `/api/admin/finance-settings`, GET `/api/admin/members`, PUT `/api/admin/members/{id}/paid`.
- Frontend : onglet « Rentabilité CareerOS » (components/admin/finance/*) : KPI, 4 réponses clés, graphique 6 mois (recharts), revenus, coûts, IA par modèle, estimé vs réel, par membre, alertes/projection fin de mois, projections 100/500/1000, membres payants (switch), éditeur (Sheet).
- Testé : iteration_26 → backend 13/13, frontend 100 %, mobile sans débordement. Données de test saisies en preview pour 2026-10.
- Limites : jetons estimés (pas de comptage exact fournisseur) ; Gemini navigateur (clé du membre) non compté ; « actifs » des mois antérieurs au déploiement non disponibles.

## Amélioration (juin 2026) — Historique Radar : Trouvées / Nouvelles cliquables
- Backend : chaque offre garde `seen_runs` ($addToSet à chaque passage) ; runs marqués `tracked: True`. Endpoint `GET /api/careeros/radar/runs/{run_id}/offers?kind=found|new` (isolé par membre, 404 si autre membre, `complete` false pour anciennes recherches non suivies → seules les nouvelles sont listables).
- Frontend : `RunOffersDialog` (liste priorité, titre, entreprise, lieu, source, IPS, lien offre). Chiffres Trouvées/Nouvelles cliquables dans `RadarHistory` (testids `radar-run-found-*`, `radar-run-new-*`).
- Testé preview : nouvelle recherche suivie → found 94 / new 9 ; ancienne → message partiel. Bug corrigé : projection Mongo vide `{}` interprétée comme introuvable (`if run is None`).

## Amélioration (juin 2026) — Compteurs cliquables = filtres
- `StatFilter` + `FilterBanner` (components/careeros/StatFilter.jsx). Clic sur un compteur = filtre la liste, re-clic ou « Tout afficher » = retire.
- Radar : Analysées aujourd'hui / Nouvelles / Déjà connues / Priorité A. Backend dashboard renvoie aussi `known_last_run` (vues au dernier passage, déjà connues, max 200) et `analyzed_today_list` (max 100).
- Tableau de bord : Opportunités (= tout), Priorité A, Entrevues, Offres ; message « Aucune candidature pour ce filtre ».
- Testé preview (95 déjà connues ↔ 95 cartes ; filtre A dashboard ; mobile sans débordement). Export synchronisé. À PUBLIER avec les lots précédents.

## Amélioration (juin 2026) — Objectifs compacts, Copilote numéroté, mention de responsabilité
- Career Memory : « Objectifs de carrière » = une seule ligne (`GoalsSelect`, popover multi-cases à cocher, résumé 2 puces + « +N », compteur x/12, « Tout désélectionner »). testids `goals-select-trigger`, `goal-*`, `goals-count`.
- Copilote : boutons numérotés selon le parcours (1 Contexte, 2 Réglages, 3 Écoute, 4 Live, 5 Flottant, 6 Capture, 7 Envoyer, 8 Récap) + visite guidée 8 étapes (`CopilotTour`, carte flottante non modale, surbrillance du bouton ciblé, Passer/Précédent/Suivant/Terminer). Affichée une fois (localStorage `copilotTourDone`), relançable via bouton « Visite » (`copilot-tour-btn`). Masquée pendant l'ouverture de Réglages/Contexte/Récap.
- Bandeau confidentialité : ajout de la mention « CareerOS est un outil d'aide… responsabilité du membre » (`privacy-disclaimer`) ; clé `privacyAcceptedV2` pour réafficher le bandeau une fois à tous.
- Testé en preview (screenshots desktop + mobile, pas de débordement). Export deploy-export synchronisé. Lot UX GPS + ce lot : À PUBLIER (Save to GitHub → Render → Cloudflare) puis validation production.


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

## 2026-10-11 — CareerOS Lot 1 : « Pack candidature en un clic » + comptes membres + Career Memory
Vision : CareerOS = cerveau stratégique ; Interview AI Engine = moteur d'exécution ; Gemini/OpenRouter/Anthropic = moteurs IA ; LinkedIn/Indeed = sources.
- Backend package `backend/careeros/` (mirrored in deploy-export): auth.py (email/password, bcrypt, JWT Bearer 12h + refresh 30d, brute force 5→15 min), router.py (/api/careeros: meta, profile GET/PUT, packs POST, applications list/get/status/delete), ips.py (formule IPS propriétaire, 10 critères pondérés =100, knockout cap 40, A/B/C), prompts.py (prompts officiels CareerOS Brain + Interview AI Engine).
- Pack = 6 appels LLM parallèles (decision JSON, cv_ats, cv_humain, letter, questions JSON, star JSON), résultats progressifs, statut done/partial/error.
- Data model future-ready: applications.{pipeline_status, timeline, interviews, followups, calendar_events, emails}; career_profiles.skills_detected auto-enrichi.
- Frontend: /connexion, /careeros (dashboard trié par priorité), /careeros/nouveau, /careeros/candidature/:id (8 onglets, Copier/DOCX/PDF), /careeros/memoire. jsPDF ajouté. Bouton CareerOS dans le copilote.
- New env: JWT_SECRET (backend). Tested iteration_18: 23/23 backend, frontend 100%.

## Backlog CareerOS
- P1: Plan du Jour (actions priorisées impact/urgence/effort), suivi recruteurs, courriels (confirmation/remerciement), lancer simulation d'entrevue depuis un pack
- P1: Google Calendar / Outlook (détection entrevue → événement + préparation)
- P2: sources autorisées (API officielles, RSS) pour la veille marché ; CV exécutif ; mot de passe oublié (nécessite Resend) ; suppression de compte (RGPD)
- Still pending: retirer l'affichage DEBUG du login admin quand prod confirmée ; Atlas Network Access 0.0.0.0/0

## 2026-10-12 — CareerOS V1 finalisation (iteration_19, 100%)
- Application code CO-YYYY-NNNNNN (counters collection, unique index) + technical id; shown in dossier, history, PDF footer, DOCX/PDF filenames + stamp.
- Immutable versions: application_versions (inputs, profile_snapshot, parts, ips, decision_report); applications mirrors latest; ips_history; POST /reanalyze; GET /versions/{n}; GET /compare?a&b (careeros/compare.py).
- Mandatory Decision Report (careeros/decision_report.py): summary, why_priority, strengths, weaknesses, actions, potential_gains — shown on Décision tab, exports, dashboard "why" line.
- Career Score (careeros/career_score.py) 20/25/15/25/15, quality-not-volume, levels; stored on career_profiles.career_score + career_score_history; GET /api/careeros/career-score (not displayed in UI).
- Dossier entities (careeros/models.py): interviews, calendar_events, recruiters, followups, emails — POST/PATCH (revisions[]) + GET /dossier, linked by application_id + application_code.
- Delete = archive (history preserved). Profile snapshots in career_profile_versions. Profile adds education[], promotions.
- Startup recovery: versions stuck "generating" after a restart are marked error "interrompue" (relaunch via Réanalyser).

## 2026-10-12 — PRODUCTION VALIDÉE · CareerOS V1 GELÉE FONCTIONNELLEMENT
- Validation prod complète (commit 02fa6dd) : rapport + scripts dans /app/memory/prod_validation/ et deploy-export/docs/validation-production-v1/.
- Corrections post-validation autorisées : (1) Decision Report = seule valeur chiffrée l'IPS officiel (prompt + filtre déterministe _no_ai_numbers, résumé préfixé « IPS officiel CareerOS : N/100 — priorité X », impacts en mots, anciens rapports re-dérivés à la lecture, report.version=2) ; (2) /admin : debug retiré, messages propres, détail technique uniquement dans les logs (stats → 503 générique).
- Règle : AUCUNE nouvelle fonctionnalité avant usage réel. V2 = nouveau cycle de planification : Calendar Agent, Recruiter CRM, Follow-Up Agent, Plan du Jour, Notifications, Google Calendar, Outlook.

## 2026-10-12 — CAREEROS V1 OFFICIELLEMENT PUBLIÉ ET GELÉ
- Validation finale post-publication 17/17 + UI (admin propre, Decision Report officiel, pack CO-2026-000002, exports PDF/DOCX). Voir memory/prod_validation/REPORT.md.
- V2 suspendue jusqu'aux retours d'utilisation réels.

## 2026-10-12 — Navigation : CareerOS = produit principal
- "/" (et toute URL inconnue) → /careeros si connecté, sinon /connexion (RootRedirect dans AuthProvider.jsx).
- Copilote d'entrevue déplacé en fonctionnalité interne : /careeros/copilote (connexion requise ; retour à la page demandée après connexion). Liens : en-tête CareerOS (desktop + mobile), bouton CareerOS dans le copilote. Liens « Retour » de /admin → /careeros. /admin inchangé.

## 2026-10-12 — Thèmes clair/sombre + marque CareerOS
- Thèmes : html.light|dark ; défaut = thème OS sinon clair ; script pré-rendu dans index.html (pas de flash) ; ThemeToggle (soleil/lune) dans Shell, connexion, admin, copilote ; sauvegarde localStorage + profil membre (PATCH /api/auth/preferences, users.preferences.theme), restauré à la connexion. Mode clair = frontend/src/theme-light.css (remap des utilitaires sombres, WCAG AA ; boutons primaires indigo-600). Toaster suit le thème.
- Titres d'onglet « CareerOS | <page> » (usePageTitle) ; favicon CareerOS public/favicon.svg ; index.html deploy-export nettoyé (aucun script Emergent/PostHog).
- Prompt CAREEROS_BRAIN mis à jour avec l'identité officielle (pas un chatbot, résultats > volume, IPS officiel unique).
- Testé : iteration_20 (100 % fonctionnel ; 3 micro-contrastes corrigés ensuite).

## 2026-10-12 — V2 démarrée : CareerOS Radar — Lot 1 (iteration_21 : 18/18 backend, frontend 100 %)
- Sources légales : Adzuna API + Jooble API (clés ADZUNA_APP_ID/ADZUNA_APP_KEY/JOOBLE_API_KEY, non configurées en preview → ignorées), sites carrières publics Greenhouse/Lever/Ashby (radar_sources.py). Entreprises suivies (10 par défaut) = recherches ciblées Adzuna/Jooble (la plupart utilisent Workday/Taleo, pas Greenhouse/Lever).
- radar.py : radar_settings / radar_offers (dédoublonnage titre+entreprise+lieu par membre) / radar_runs ; 1 appel IA par NOUVELLE offre (IPS Radar = formule officielle, réseau « aucun », lettre neutre) + Decision Report ; limite RADAR_DAILY_LIMIT=50 ; /run en tâche de fond (409 si déjà en cours) ; /dashboard (nouvelles, top A, top B, ignorées, compteurs) ; /offers/{id}/ignore|pack (pack = flux existant, origin.type=radar) ; /cron (X-Cron-Secret = RADAR_CRON_SECRET) pour planificateur externe (cron-job.org à 6 h) car Render gratuit s'endort.
- followup.py : brouillons IA (confirmation/remerciement/relance) statut brouillon→pret→envoye uniquement par le membre ; .ics entrevue (Google/Outlook/Apple). UI : page /careeros/radar + Réglages, onglet « Suivi & agenda » dans le dossier.
- À FAIRE (Lot 2) : OAuth Google Calendar + Outlook (création directe d'événements, envoi direct de courriels après validation) — nécessite identifiants Google Cloud + Microsoft Entra fournis par l'utilisateur ; appeler integration_expert avant.

## 2026-06 — Radar V2.1 : Adzuna optionnel, Workday, entreprises configurables
- Sources : Jooble (principale, JOOBLE_API_KEY), Workday (public CXS, filtre pays Canada), sites carrières (Greenhouse/Lever/Ashby/amazon.jobs), Adzuna optionnel (non sélectionnable sans clé, rejeté côté serveur).
- Entreprises suivies 100 % configurables par le membre : objets {name, enabled, portal_url, kind, slug} ; ajout, retrait, import de liste (« Nom | URL »), activation/désactivation ; aucune liste codée en dur. Migration auto des anciens réglages (companies texte + boards).
- POST /api/careeros/radar/portal/detect : reconnaît et vérifie l'URL d'un portail carrières.
- Écran Radar : panneau Sources (Actif / Non configuré / Désactivé + offres par source) et total analysé ; last_run.by_source.
- Les offres reportées par la limite de 50/jour sont analysées lors des passages suivants (backlog).
- Portails vérifiés : Desjardins, Intelcom, Walmart, Couche-Tard (Workday) ; Amazon (amazon.jobs). SuccessFactors/Phenom/UKG (Hydro-Québec, Bombardier, Purolator, Air Canada, ABB, DHL, CPKC…) → via Jooble.
- Tests : iteration_22 — backend 23/23, frontend OK. Non publié en production.
- Backlog : publier V2 (Save to GitHub + Render + Cloudflare), ajouter JOOBLE_API_KEY sur Render, OAuth Google/Outlook (à cadrer).
- 2026-06 : lot Radar V2 validé par l'utilisateur. Script de validation production prêt : memory/prod_validation/radar_v2_check.py (copie deploy-export/docs/validation-production-v2/) — 40/40 sur la préversion (EXPECT_JOOBLE=0). Comptes de test dédiés créés à chaque exécution (radar.validation.*@careeros.dev, identifiants écrits dans radar_ctx.json local). En attente : Save to GitHub + redéploiement par l'utilisateur, puis exécution en production et configuration de cron-job.org (6 h, heure de l'Est).
- 2026-10 : Correctif « Expecting ',' delimiter » (onglets Décision & IPS + Simulation recruteur). Cause : la section decision (JSON ~13 k caractères, contient aussi recruiter_simulation) était parfois mal formée par l'IA ; _parse_json_object relançait l'exception JSONDecodeError dont le message brut était stocké dans errors.decision et affiché. Correctifs : parse tolérant (json_repair), validation des clés obligatoires (ats, ips_criteria, recruiter_simulation) + 1 nouvel essai, messages d'erreur membres propres (PartError/_friendly), assainissement des anciens messages techniques côté front (friendlyError), bouton « Régénérer les sections manquantes » → POST /api/careeros/applications/{id}/retry (même version, seules les sections manquantes, IPS recalculé). Non publié en production.
- 2026-10 : Validation prod Radar V2 = 39/40 (Workday 28, amazon.jobs 8, Jooble 0). Cause Jooble : appel sur jooble.org (index US) ; les clés Jooble sont par pays → JOOBLE_HOST (défaut ca.jooble.org) + clé à obtenir sur ca.jooble.org/api/about. Une requête Jooble par mot-clé (au lieu de mots-clés concaténés = ET), requêtes entreprise avec companysearch, alerte explicite si Jooble renvoie 0 résultat ou 403. Ajouts : GET /api/careeros/radar/runs (historique 30 j), marqueur « Recherche effectuée aujourd'hui / automatique faite à … », historique par jour (manuelle/automatique, trouvées/nouvelles/analysées/par source/alertes), « Aucun portail configuré » pour Workday/Sites carrières, correctif débordement mobile des cartes d'offres. Non publié.
- 2026-10 : Calibration IPS Radar validée par l'utilisateur — compute_ips(stage="radar") : 8 critères évaluables (exclut qualite_lettre, force_reseau), 90 pts ramenés sur 100, seuils A/B/C officiels inchangés ; résumé « IPS Radar CareerOS : N/100 — priorité X (provisoire, recalculé dans le pack). » ; offres Jooble/description < 600 car. marquées excerpt (« Analyse sur extrait Jooble ») + consigne IA de neutralité ; recalibrage automatique des offres déjà analysées au démarrage (sans appel IA). Le pack garde l'IPS officiel 10 critères. Portails : confirmation à la fermeture sans enregistrer, bouton Enregistrer collant, résumé des portails détectés, avertissement URL non reconnues, « À vérifier ». Tests iteration_23 : backend 24/24 (+1 skip), frontend OK. À publier par l'utilisateur.
- 2026-10 : VALIDATION FINALE PRODUCTION Radar V2 (commit 48ee940) : 43/43. Run 1 : 90 offres (Jooble 54, Workday 28, amazon.jobs 8), 50 analysées, 40 reportées ; run 2 : 88 connues, 0 réanalyse, limite respectée ; calibration radar OK ; pack/brouillon/.ics/isolation OK. Constat : les 50 analyses du jour sont parties sur Jooble (extraits) avant Workday/amazon (descriptions complètes) → proposer priorisation qualité (portails des entreprises suivies d'abord). Prochaine étape : cron-job.org 6 h America/Toronto.
- 2026-10 : Incident prod « packs Radar vides » (CO-2026-000006/7) : pas un bug Radar. La chaîne IA serveur en prod ne contient qu'Anthropic (OPENROUTER_API_KEY absente sur Render) et le crédit Anthropic est épuisé → toutes les sections échouent. Ajouts : message membre explicite (AI_DOWN), erreurs « réponse vide » journalisées, coupe-circuit Radar (3 échecs IA consécutifs → analyses suspendues, offres gardées pour la prochaine recherche, alerte errors.ia), GET /api/admin/llm-health + carte admin « Santé des fournisseurs IA » (test par fournisseur). À publier ; utilisateur doit ajouter OPENROUTER_API_KEY (+ crédits) ou recharger Anthropic.
- 2026-10 : LOT RÉDUCTION DES COÛTS IA (validé utilisateur) : radar_rules.py (pré-analyse déterministe sans IA : rôles/mots-clés, vocabulaire, compétences FR/EN, années, certifications, éliminatoires langue/habilitation/permis/hors Canada/écart d'expérience ≥4 ans/métier différent/compétences clés absentes) ; IA seulement sur les RADAR_AI_TOP=5 meilleures offres/jour + POST /radar/offers/{id}/deep (RADAR_DEEP_LIMIT=20) ; badges « Pré-analyse règles » / « Analyse IA » ; cron uniquement pour membres actifs 7 j (users.last_seen_at mis à jour par auth, max 1×/h) ; pack depuis offre IA réutilise les notes Radar ; routage modèles : eco (openrouter free → OPENROUTER_MODEL → Anthropic Haiku) pour analyses, premium (OPENROUTER_PREMIUM_MODEL → Anthropic Sonnet → eco) pour lettre + /api/generate (simulations). Admin : carte « Crédit IA restant » (OpenRouter /credits, total-utilisé, %), liens de recharge OpenRouter/Anthropic, alerte e-mail configurable (adresse + seuil, défaut 20 %, envoi unique par franchissement, vérif quotidienne via cron + à l'ouverture admin, e-mail de test) via e-mail géré Emergent (EMERGENT_EMAIL_KEY, EMAIL_FROM_NAME). Corrélation règles/IA ≈ 0,52 sur l'échantillon préversion. Tests iteration_24 : 17/17 backend + frontend OK. À publier.
- 2026-10 : Fournisseurs IA (validé utilisateur) — export : chaîne éco (analyses) = Gemini Flash direct (GEMINI_API_KEY, GEMINI_SERVER_MODEL=gemini-2.5-flash, AI Studio OpenAI-compatible) → OpenRouter free → OpenRouter DeepSeek, SANS Anthropic ; chaîne premium (lettre + simulations) = OpenRouter google/gemini-2.5-pro → Gemini Flash → DeepSeek → Anthropic Sonnet en dernier recours. Correctif shim : Anthropic utilisait toujours ANTHROPIC_MODEL (ignorait le modèle demandé). Budget jetons ≥16k pour modèles Gemini 2.5 (réflexion). Priorité d'analyse Radar : Workday → amazon.jobs → sites carrières → Jooble (file des règles + départage du top IA). À publier ; l'utilisateur doit créer GEMINI_API_KEY (aistudio.google.com) dans Render.
- 2026-10 : Prod (nouveau commit déployé) : test fournisseurs → Gemini 404 « gemini-2.5-flash no longer available to new users ». Correctif : alias auto-mis à jour gemini-flash-latest (direct) et ~google/gemini-pro-latest (OpenRouter premium), aussi dans render.yaml. Si GEMINI_SERVER_MODEL / OPENROUTER_PREMIUM_MODEL sont définies dans Render, les mettre à jour ou les supprimer.
- 2026-10 : VALIDATION PROD lot coûts IA + Gemini : 19/19 (memory/prod_validation/REPORT_radar_v3.md). Run : 94 offres (Jooble 57, Workday 29, amazon 8), 50 pré-analysées par règles (Workday 29/29 et amazon 8/8 avant Jooble 13), IA top 5 (78/63/62/62/40), analyse approfondie OK, pack CO-2026-000008 complet en 46 s, lettre FR 1985 car., simulation OK, isolation OK. Constat : les règles surévaluent des titres « Analyst » hors domaine (ex. Senior Cloud Security Operations Analyst : règles haut, IA 29) → piste : familles de domaine (sécurité, cloud, infra) dans radar_rules.
- 2026-10 : LOT UX « GPS de carrière » (validé utilisateur) : GET /api/careeros/journey (5 étapes, 6 jalons, prochaine étape unique calculée) ; PATCH /api/auth/preferences partiel (theme, guide_mode debutant|expert, tour_done) ; GuideProvider global (App.js) ; JourneyBar (fil d'étapes + x/6, compact mobile), bandeau « Que faire ensuite ? » (1 CTA, « vous êtes au bon endroit » sur la page cible), InfoTips + ConceptRow (glossaire lib/guide.js), visite guidée 5 étapes (temps estimé, Ouvrir cette page, Passer/Précédent/Suivant/Terminer, résumé final, une seule fois, relance via menu Aide), Mode Débutant/Expert ; hiérarchie des actions (menu « Plus » avec actions destructives séparées sur cartes Radar et dossier, « Préparer l'entrevue » primaire dans le dossier, Réanalyser secondaire, Nouveau pack secondaire en mode Débutant) ; date de publication = calendrier shadcn en français (jj/mm/aaaa). Tests iteration_25 : backend 10/10, frontend OK. Copilote (page hors Shell) sans fil d'étapes. À publier.

## 2026-06 — Connecteurs Avature, Taleo, Phenom (après UKG)
- radar_sources.py : taleo() (endpoint JSON careersection/rest/jobboard/searchjobs, FR+EN, « fiable »), avature() (pages SearchJobs HTML, « fragile »), phenom() (JSON phApp.ddo intégré à la page, « fragile ») ; parse_portal reconnaît les 3 ; quality() = fiable / fragile / bloquee / repli ; FRAGILE = icims, avature, phenom.
- Détection : Taleo/Avature/Phenom détectés sur site ou URL ; annuaire : Banque Nationale (Avature), Bell et Air Canada (Phenom) désormais lus à la source.
- Chaque passage Radar enregistre portals[*].quality ; PortalHealth affiche 4 pastilles (Lecture fiable / fragile / bloquée / Repli Jooble) ; PortalSuggest avertit des lectures fragiles.
- Admin Connecteurs : colonnes Fiable / Fragile / Bloquée / Repli Jooble, badge « au mieux », indication « à re-détecter » pour les anciennes détections UKG/Avature/Taleo/Phenom.
- Tests : iteration_30 → backend 11/11, frontend 100 % (preview). Pas encore validé en production par l'utilisateur.
- En attente : validation prod du correctif fuseau America/Toronto (Radar manuel du soir + ligne « Automatique » 06:00 du lendemain).
- Backlog : Njoyn (CGI), Jobvite, SilkRoad, portail propriétaire Metro ; surveiller les faux positifs du motif Avature /SearchJobs.

## 2026-06 — Lot A+B+C : détection corrigée, nouveaux lecteurs, guides Radar
- Nouveau connecteur générique « Site carrières (schema.org) » (kind `schema`) : plan du site public + données JobPosting (norme Google for Jobs), offres expirées (validThrough) exclues. Metro (talent.metro.ca) et Loblaw lus ainsi.
- Nouveau lecteur Taleo Business Edition (kind `taleobe`, fragile) : Costco (offres corporatives US uniquement → Costco Canada reste sur Jooble en pratique).
- Détection : essai careers.nom.ca (Walmart Canada = Workday walmart.wd504), faux positifs www/cdn iCIMS ignorés, plateformes « non prises en charge » retenues seulement sur un vrai lien, Taleo retiré si Taleo BE trouvé, iCIMS redirigé signalé.
- Annuaire : Metro (schema), Walmart Canada (Workday).
- Bouton « Re-détecter (N) » : relance la loupe sur les entreprises Non prises en charge / Illisibles (association toujours manuelle).
- Guides : PageTour générique (guide/PageTour.jsx) ; visite Radar 5 étapes + visite Réglages 5 étapes (auto en mode Débutant, relançables) ; InfoTips sources, portails, qualité, compteurs, couverture, loupe, détection, associer.
- Indeed / LinkedIn : pas d'API publique d'offres, et leurs conditions interdisent l'extraction automatisée, donc rien n'a été intégré.
- Tests : iteration_31 → backend 14/14, frontend 100 % (preview). Validation production en attente.

## 2026-06 — Sources et Portails cliquables
- SourceStatus : Jooble / Workday / Sites carrières sont des boutons filtrant la liste d'offres du dernier passage (FilterBanner « Source : X », 2e clic = retrait).
- PortalHealth : tableau triable (Entreprise, Plateforme, Qualité, Lues, Retenues, État) trié par Retenues décroissant ; pastilles qualité = filtre du tableau ; clic ligne = filtre offres « Entreprise : X » ; cartes sur mobile ; note explicative si 0 lue / 0 retenue / échec / bloqué.
- Vérifié par capture Playwright (bureau + 390 px) en preview ; testing agent non concluant (erreur de script de connexion, aucune anomalie applicative).
- Suite : Sources présentées en tableau (Source · Statut · Trouvées · Analysées) avec chiffres cliquables soulignés (même style que l'historique, composant Num exporté de RadarHistory) ; colonnes Lues et Retenues du tableau Portails cliquables (filtre entreprise). Vérifié par capture en preview (bureau + 390 px, sans débordement).

## 2026-06 — « Pourquoi ce score ? », exigences, règles corrigées, offre externe
- GET /api/careeros/radar/offers/{id}/explain : réévalue gratuitement les offres « règles » avec les règles actuelles et renvoie IPS, critères, requirements_rules (+ requirements_ai si analyse IA).
- POST /api/careeros/radar/external : offre collée (texte ; lien lu seulement s'il publie des données JobPosting ; LinkedIn → 422 « collez le texte »). source=externe, hors quota de 50/jour.
- radar_rules : exigences détectées (années, langues, diplômes, syndiqué, quart, centre de distribution, supervision, SST, permis, compétences, certifications, lieu) ✓/✗/? ; « chef » n'est plus senior ; équivalence chef/superviseur/gestionnaire/contremaître/directeur adjoint (encadrement) ; pluriels et écriture inclusive ; compétences opérations ajoutées (Office, Outlook, réception, expédition…).
- Prompt IA : renvoie requirements (étiquetées « Confirmé par l'analyse IA ») ; les exigences par règles restent affichées séparément.
- UI : bouton « Pourquoi ce score ? » (panneau : méthode règles / IA, ce qu'il manque pour la priorité A, critères triés par points perdus, éliminatoires, exigences X/Y, bouton analyse approfondie) ; bouton « Analyser une offre externe ».
- Tests : iteration_32 → backend 7/7, frontend 100 % (preview).

## 2026-06 — Comparer avec LinkedIn, recherche élargie, priorisation des 50 analyses
- POST /api/careeros/radar/compare : lignes « Entreprise – Titre » → couverture (portail / Jooble / non suivie), offre trouvée et statut (A/B/C, éliminée, reportée, ignorée, pack) avec 3 critères les plus pénalisants, sinon vérification Jooble en direct et explication. Correspondance d'entreprise par mots entiers.
- Recherche élargie (settings.expand, défaut vrai) : expand_terms → mots-clés + titres de la même famille FR/EN (opérations/logistique, données, projet, approvisionnement), max 8 requêtes Jooble × 2 pages. Réglages : case à cocher + aperçu des titres.
- Limite conservée à 50 analyses par règles/jour (choix utilisateur) ; la file est triée par proximité du titre avec les postes visés.
- Découverte : Airbus (Workday ag.wd3/Airbus) dans l'annuaire ; pages anti-robot (Incapsula/Cloudflare) signalées ; Dayforce reconnu « API protégée » (403, non contourné) → Jooble.
- Tests : iteration_33 → backend 11/11, frontend 100 % (preview).
- 2026-06 : en-têtes de priorité colorés (Radar.jsx SectionHead) : A émeraude avec halo pulsé + pastille animée quand ≥1 offre (« Agir maintenant »), B ambre (« Optimiser puis postuler »), C rose (« À éviter ») ; animation désactivée si prefers-reduced-motion. Vérifié par capture (bureau + mobile).

## 2026-06 — Découverte automatique des portails (A+B+C+D) + lecture « Pourquoi ce score ? »
- radar_auto.py : annuaire partagé anonyme (collection portal_directory : clé entreprise → portail public, membres hachés), association automatique si certitude (annuaire / annuaire partagé nommé ou ≥2 membres / lien officiel du site, lecture fiable, ≥1 offre), notifications radar_notices (OK / Modifier / Annuler ; annuler → auto_block), suggestions d'entreprises récurrentes non suivies, re-détection quotidienne (cron, 3 entreprises/membre, 1×/semaine/entreprise).
- radar.py : PUT settings partage les associations + détection auto en arrière-plan des nouvelles entreprises (retour auto_detecting) + blocage si retrait manuel ; POST /companies/follow ; GET /suggestions ; GET /notices ; POST /notices/{id}/ack|undo ; Company : auto, auto_block, checked_at.
- Annuaire statique : +15 employeurs vérifiés (Agropur, Molson Coors, Cascades, Purolator, Alstom, Kuehne+Nagel, Domtar, Home Depot Canada, Dollarama, Vidéotron, TD, BMO, Thales, Colabor, Cogeco).
- Frontend : AutoNotices, CompanySuggestions (« Entreprises qui recrutent pour vos postes »), badge « auto », toast de détection ; ScoreExplain : Fond clair (défaut) / Fond sombre / A+ (reading-light.css), critères lisibles sur mobile.
- Tests : iteration_34 → backend 11/11, frontend 100 % ; notifications dédupliquées et débordement mobile des suggestions corrigés ensuite (vérifié par capture).

## 2026-06 — Incident cron 06:00 sans ligne d'historique (15 oct.)
- Constat : cron-job.org a bien appelé à 06:00:22, mais aucune exécution « quotidien » n'est enregistrée. Les journaux Render ne sont pas accessibles à l'agent.
- Cause la plus probable (code) : la tâche de fond traitait les membres un par un et lançait d'abord la détection de portails (jusqu'à environ 150 s par membre) ; le membre réel pouvait passer après les comptes de test. De plus, la tâche asyncio n'était pas référencée : un arrêt ou un redémarrage du processus pouvait la perdre sans trace.
- Correctifs : journal radar_cron_log (écrit dès la réception, avec chaque étape par membre et les erreurs ; statut « interrompu » si le processus s'arrête) ; Radar de tous les membres d'abord, détection ensuite ; membres les plus récemment actifs en premier ; délais max (900 s Radar, 240 s détection) ; référence forte à la tâche ; réponse du cron {started, members, log_id}.
- Admin → Connecteurs → « Journal du passage quotidien ». Vérifié en preview : appel manuel du cron → 11 membres traités, journal complet (done).
- À valider : prochain 06:00 en production (journal + ligne Automatique).
- Suite incident cron : la réponse de production {"started":true,"members":2} n'a pas de log_id → la production exécute encore une version antérieure au correctif (non redéployée). Ajouts : la réponse du cron indique skipped_disabled et skipped_inactive ; GET /api/careeros/radar/cron-status (inclusion du membre + raison + dernier passage automatique), affiché sous le marqueur du jour dans Radar. Vérifié en preview (curl + capture).

## 2026-06 — Règle permanente : tous les chiffres sont cliquables
- RÈGLE PRODUIT : tout chiffre affiché (membre ou admin) doit être cliquable et ouvrir une liste ou un détail, avec un style souligné cohérent (Num / ClickNum / StatFilter). À appliquer à toute nouvelle fonction.
- Phase 1 (Radar) : historique (Analysées, reportées, J/W/S, alertes → AlertsDialog avec libellé, message nettoyé, conseil 403 anti-robot) ; run_offers kinds analyzed|skipped|src_* ; Sources : Analysées + totaux ; IPS des cartes → « Pourquoi ce score ? ».
- Phase 2 (Admin) : DetailDialog générique ; StatCards Activité → détail par jour ; chiffres LLM → par fournisseur ; Connecteurs (entreprises, membres, lues, retenues, réussite, fiable/fragile/bloquée/repli, backlog) → listes ; KPI Rentabilité → défilement vers la section détaillée avec surbrillance.
- Tests : iteration_35 → backend 16/16, frontend ~90 % puis correctifs (conseil 403, liste des reportées incluant celles analysées plus tard, filtre Analysées par passage, accessibilité clavier des cartes). Le correctif mobile de RunOffersDialog vient de l'agent de test.

## 2026-10-15 — Vérification cron 06h (sans action manuelle)
- Code cron revu (quota remis à zéro à minuit Toronto, aucun verrou bloquant pour le cron, membres actifs 7 j + Radar activé).
- Simulation preview « lendemain » : log radar_cron_log -> done, 11 membres, runs quotidien créés, 0 erreur.
- deploy-export/backend/careeros et frontend/src identiques au preview (server.py diffère volontairement : chaîne LLM autonome).

## 2026-10-15 — Base commune CareerOS + Réglages allégés
- backend/careeros/knowledge.py : collection portal_knowledge (1 fiche/employeur, clé normalisée, fusion, plus récent gagne), statut fiable/fragile/bloque, confiance (validations/jour, dernière réussite, offres lues). Aucune donnée membre. Migration depuis portal_directory.
- Alimentée par : passages Radar (portails lus avec offres, 403), loupe/discover (origines officielles). Utilisée par detect_one (association auto si fiable + confiance élevée/moyenne, annulable), ajout entreprise (frontend), /radar/knowledge/match.
- Réglages Radar : associées masquées par défaut + bouton Afficher/Masquer, bouton « Associer » 1 clic (base commune puis loupe), badge bloqué 403.
- Admin : onglet « Base commune » (GET /api/admin/knowledge). Tests iteration_36 + tests/test_knowledge_base.py (6/6).

## 2026-10-15 — Module Admin complet (RBAC, insights, géographie, partage membre)
- careeros/admin_rbac.py : rôles super_admin/support/marketing/conseiller (users.admin_roles), middleware RBAC (Bearer membre -> sections), /api/admin/me, /api/admin/roles. ADMIN_PASSWORD = Super Admin sans restriction. Export + llm-health = Super Admin.
- careeros/admin_insights.py : /insights/overview (membres, entonnoir Visiteurs>Inscrits>Actifs>Payants>Renouvellement, Radar), /geo (pays/province/ville, groupes <3 fusionnés hors super), /business (postes, entreprises, portails, offres, priorités A/B/C). Agrégats uniquement.
- careeros/geo.py : déduction pays/province/ville ; champs country/province/city dans Career Memory (pré-remplis, modifiables) ; Radar utilise la ville par défaut.
- careeros/sharing.py : autorisations explicites membre -> e-mail (conseiller/proche), par périmètre CV/Career Memory/Candidatures, révocables, compteur de consultations.
- users.paid_since suivi (renouvellement). Événement anonyme « visit » par session (entonnoir).
- Frontend : onglets Admin filtrés par rôle, connexion Admin avec compte CareerOS, Overview/Geography/Business/Roles, SharingPanel dans Career Memory.
- Tests : iteration_37 + tests/test_admin_rbac_insights_sharing.py (41/41).

## 2026-10-15 — Traçabilité de tous les chiffres Admin
- careeros/admin_trace.py : GET /api/admin/trace?metric=&key=&days= (m_*, f_*, r_*, g_*, b_*, a_*, fin_*) -> lignes réelles (1000 max). Super Admin : nom+e-mail ; autres rôles : « Membre #XXXXXX », petites villes regroupées ; packs/candidatures : poste+entreprise Super Admin seulement.
- RBAC : section de la trace selon le préfixe du metric.
- Frontend : useTrace() / TraceDialog (recherche, tri, compteur, CSV) branché sur Tableau de bord, Géographie, Analyse métier, Activité, Rentabilité (KPI, appels IA, par membre = formule, alertes, projections), Base commune.
- Tests : iteration_38 + tests/test_admin_trace.py (16/16).

## 2026-10-15 — Comptes de test
- careeros/testaccounts.py : compte de test = @careeros.dev par défaut ou users.is_test explicite ; exclusion par contextvar (scope/uf) dans insights, trace, finance (_members). Paramètre include_test=true.
- PUT /api/admin/roles/{id}/test ; Rôles : colonne « Compte de test », badge TEST, filtre « Afficher les comptes de test », confirmation avant rôle sur compte test.
- Admin : bouton global « Afficher les comptes de test » (sessionStorage adminIncludeTest) ; badge TEST dans Membres payants ; colonne test dans les traces membres.
- Démo réelle preview : membre.reel.demo@example.com / Reel2026!demo.

## 2026-10-15 — Où postuler / J'ai postulé
- router.py : _offer_link (offer_link membre > origin.url Radar > inputs.offer_url > 1re URL du texte), offer_source ; PUT offer-link, POST apply-opened / applied (jamais de rétrogradation) / apply-not-yet ; _summary.apply_pending ; set_status postule -> applied_at.
- ApplyBar.jsx dans PackView : étapes 1-2-3, bouton Postuler (nouvel onglet), hôte + source, copier, ajout du lien, J'ai postulé, dialogue « Avez-vous postulé ? » au retour / prochaine visite, rappel relance J+7 .ics. Badge Dashboard « Candidature à confirmer ».
- Tests : iteration_39 + tests/test_apply_flow.py (18/18).

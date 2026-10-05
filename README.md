# Interview‑AI‑Engine — Déploiement autonome (hors Emergent)

Copilote d'entretien : **React (CRA/CRACO)** en frontend + **FastAPI (Python 3.11)** en backend + **MongoDB**.
Ce dossier contient tout ce qu'il faut pour héberger l'app **sans Emergent** :
Frontend → **Cloudflare Pages** · Backend → **Render** · DB → **MongoDB Atlas**.

> ⚠️ Seule dépendance propre à Emergent = le package `emergentintegrations`.
> Il est **remplacé** ici par un shim local (`backend/emergentintegrations/`) qui appelle
> directement les SDK **Anthropic** + **OpenAI** avec **tes propres clés**. Aucune autre
> dépendance Emergent. `server.py` fonctionne tel quel.

---

## 1. Structure finale du dépôt

```
interview-ai-engine/
├── backend/
│   ├── server.py                 # API FastAPI (toutes les routes sous /api)
│   ├── state_machine.py          # (importé par server.py)
│   ├── prompt.py                 # (importé par server.py)
│   ├── requirements.txt          # sans emergentintegrations (+ anthropic/openai)
│   ├── .env                      # créé depuis .env.example (NE PAS committer)
│   ├── .env.example
│   └── emergentintegrations/     # SHIM local (remplace le package Emergent)
│       ├── __init__.py
│       └── llm/{__init__.py, chat.py, openai.py}
├── frontend/                     # ton dossier /app/frontend EXISTANT
│   ├── src/ ... public/ ...
│   ├── package.json              # scripts craco (start/build)
│   ├── craco.config.js, tailwind.config.js, postcss.config.js, jsconfig.json
│   ├── public/_redirects         # ajouté (SPA fallback Cloudflare)
│   └── .env                      # REACT_APP_BACKEND_URL
├── render.yaml                   # blueprint Render (backend)
└── README.md
```

### Comment assembler le dépôt
1. Récupère le dossier **`/app/frontend`** complet (sans `node_modules`) → `interview-ai-engine/frontend/`.
2. Récupère le dossier **`/app/deploy-export/backend`** → `interview-ai-engine/backend/`.
   (il contient déjà server.py, state_machine.py, prompt.py, le shim, requirements.txt, .env.example)
3. Copie `deploy-export/frontend_public/_redirects` → `frontend/public/_redirects`.
4. Copie `deploy-export/frontend.env.example` → `frontend/.env` (et ajuste l'URL).
5. Copie `deploy-export/render.yaml` à la racine.
6. Mets le `.gitignore` racine : `node_modules/`, `build/`, `.env`.

---

## 2. Variables d'environnement

### Backend (`backend/.env`)
| Variable | Rôle |
|---|---|
| `MONGO_URL` | URI MongoDB Atlas |
| `DB_NAME` | nom de la base (ex. `interview_ai`) |
| `ANTHROPIC_API_KEY` | clé Anthropic (fournisseur principal) |
| `OPENAI_API_KEY` | clé OpenAI (fallback **+ transcription Whisper**) |
| `ANTHROPIC_MODEL` | (optionnel) défaut `claude-3-5-sonnet-20241022` |
| `OPENAI_MODEL` | (optionnel) défaut `gpt-4o` |
| `EMERGENT_LLM_KEY` | **mets `local`** (valeur ignorée, sert juste d'interrupteur) |
| `DEEPSEEK_API_KEY` | (optionnel) dernier recours payant |
| `CORS_ORIGINS` | origines autorisées, ex. `https://ton-app.pages.dev` (ou `*`) |

### Frontend (`frontend/.env` + réglages Cloudflare Pages)
| Variable | Rôle |
|---|---|
| `REACT_APP_BACKEND_URL` | URL publique du backend Render, **sans slash final** |

---

## 3. Lancer en local

**Pré‑requis** : Python 3.11, Node 18/20, Yarn, un MongoDB (Atlas ou local).

```bash
# --- Backend ---
cd backend
python -m venv .venv && source .venv/bin/activate      # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env        # puis édite .env avec tes clés
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
# API dispo sur http://localhost:8001/api

# --- Frontend (autre terminal) ---
cd frontend
yarn install
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
yarn start                  # http://localhost:3000
```

---

## 4. Build du frontend

```bash
cd frontend
yarn install
yarn build                  # (= craco build) -> dossier de sortie: build/
```

## 5. Démarrage du backend (production)

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port $PORT
```

---

## 6. Déploiement

### MongoDB Atlas
1. https://cloud.mongodb.com → crée un cluster **M0 (gratuit)**.
2. Database Access : crée un utilisateur/mot de passe.
3. Network Access : autorise `0.0.0.0/0` (ou l'IP de Render).
4. Connect → Drivers → copie l'URI dans `MONGO_URL`.

### Backend sur Render
1. Pousse le dépôt sur GitHub.
2. Render → **New → Blueprint** (détecte `render.yaml`) **ou** New → Web Service :
   - Root Directory : `backend`
   - Build : `pip install -r requirements.txt`
   - Start : `uvicorn server:app --host 0.0.0.0 --port $PORT`
3. Ajoute les variables d'env (secrets) : `MONGO_URL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
   `EMERGENT_LLM_KEY=local`, `DB_NAME`, (`DEEPSEEK_API_KEY` optionnel), `CORS_ORIGINS`.
4. Note l'URL publique (ex. `https://interview-ai-backend.onrender.com`).

### Frontend sur Cloudflare Pages
1. Cloudflare → Pages → **Connect to Git** → ce dépôt.
2. Build settings :
   - Framework preset : **Create React App** (ou « None »)
   - Build command : `yarn build`
   - Build output directory : `build`
   - Root directory : `frontend`
3. Variable d'env : `REACT_APP_BACKEND_URL` = l'URL Render (sans slash final).
4. Vérifie que `frontend/public/_redirects` est présent (routing SPA).
5. Après le 1er déploiement, mets `CORS_ORIGINS` du backend = l'URL `*.pages.dev`.

---

## 7. Spécificités Emergent à remplacer — RÉCAP
| Élément Emergent | Remplacement dans ce paquet |
|---|---|
| `pip install emergentintegrations` | **supprimé** de requirements.txt ; shim local `backend/emergentintegrations/` |
| `EMERGENT_LLM_KEY` (clé universelle) | tes clés `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` ; mets `EMERGENT_LLM_KEY=local` |
| Modèles alias (`claude-sonnet-4-6`, `gpt-5.4`) | ids réels via `ANTHROPIC_MODEL` / `OPENAI_MODEL` |
| Déploiement/routing `/api` d'Emergent | reverse proxy inutile : le frontend appelle `REACT_APP_BACKEND_URL/api/...` en direct |

## 8. Points de vigilance
- L'app est surtout **côté client** (état, prompts, persistance locale `chrome.storage`/`localStorage`).
  Le backend ne sert que : génération IA serveur, transcription Whisper, analyse entreprise,
  analyse ATS, lettre de motivation, extraction PDF.
- L'**extension Chrome MV3** se build depuis `frontend/build` (voir ton guide d'installation existant) ;
  `REACT_APP_BACKEND_URL` est figée au build → rebuild après changement d'URL backend.
- Routes legacy `/api/sessions*` et `/api/state/resolve` : présentes mais non utilisées par l'app.
- Render (offre gratuite) met le service en veille après inactivité : 1ère requête plus lente (cold start).

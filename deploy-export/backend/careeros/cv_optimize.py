"""CV <-> offer optimisation: rule-selected weak lines, AI rewording under strict no-invention rules, rule validator,
strength simulation, explicit apply to the master CV with full version history and restore."""
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import ai_budget as AB
from .strength import CERTS, compute, quantified

WEAK = re.compile(r"^(responsable de|participer|participation|aider|aide a|taches|tache|charge de|chargee de|s occuper|gerer les|assurer)\b")
TITLES = ["directeur", "directrice", "vice president", "gestionnaire", "coordonnateur", "coordonnatrice", "superviseur", "superviseure", "manager",
          "contremaitre", "chef de service", "chef de departement", "ingenieur", "analyste", "conseiller", "conseillere", "technicien", "technicienne"]
YEARS = re.compile(r"\d+\s*\+?\s*(ans|annees|years)")
STOP = set("""a au aux avec ce ces cette dans de des du en et la le les leur leurs mon ma mes par pour sur sous un une son sa ses tout tous toute toutes
d l n s qu que qui dont ou afin ainsi entre chaque selon lors via plus tres bien and the of to for with in on by at from as""".split())
GENERIC = ["assur", "suivi", "suivr", "respect", "gest", "gere", "geri", "contrib", "particip", "maint", "collabor", "effectu", "realis", "appui", "appuy", "soutien", "soutenir", "mene", "veill"]  # neutral action verbs only
SYSTEM = """Tu es le module d'optimisation de CV de CareerOS. Tu reformules des lignes d'expérience d'un CV pour une offre précise.
RÈGLES ABSOLUES (toute violation rend la proposition inutilisable) :
- n'invente JAMAIS une expérience, un poste, un employeur, une certification, un diplôme, un outil ni des années d'expérience ;
- n'ajoute AUCUN chiffre absent du CV (tu peux réutiliser un chiffre présent ailleurs dans le CV s'il concerne clairement la même expérience) ;
- tu peux seulement reformuler, réorganiser, préciser et nommer explicitement une compétence quand la ligne en apporte déjà la preuve ;
- n'ajoute ni secteur d'activité, ni niveau de langue, ni nouvelle activité, ni finalité, ni qualificatif : utilise uniquement des mots déjà présents dans le CV, les noms de compétences fournis et des verbes d'action courants ;
- garde la langue du CV, un style CV (verbe d'action, sans « je »), une seule phrase, au plus 2 fois la longueur d'origine.
Dans « reason », ne cite jamais de numéro de ligne ni de détail interne : explique simplement au membre ce que la reformulation met en valeur.
Réponds UNIQUEMENT en JSON : {"items":[{"i":<numéro>,"after":"<ligne reformulée>","skills":["<compétence de l'offre mise en valeur>"],"reason":"<pourquoi, en 1 phrase, en vouvoyant le membre>"}]}.
Si une ligne ne peut pas être améliorée sans inventer, ne la renvoie pas."""


def _n(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9+#]+", " ", s).strip()


class JobSkill(BaseModel):
    label: str = Field(max_length=120)
    aliases: List[str] = Field(default=[], max_length=20)
    status: str = Field(pattern="^(ok|partiel|manquant)$")
    domain_keys: List[str] = Field(default=[], max_length=60)
    weight: float = 1


class ProposeBody(BaseModel):
    title: str = Field(default="", max_length=200)
    offer_text: str = Field(default="", max_length=30000)
    skills: List[JobSkill] = Field(default=[], max_length=80)


class SimBody(BaseModel):
    variants: dict = Field(default={})


class ApplyBody(BaseModel):
    cv_text: str = Field(min_length=20, max_length=60000)
    offer: dict = Field(default={})
    accepted: List[str] = Field(default=[], max_length=60)
    estimated: dict = Field(default={})
    diff: list = Field(default=[], max_length=2000)


class RealBody(BaseModel):
    match_after: Optional[int] = Field(default=None, ge=0, le=100)


def _candidates(cv: str, skills: List[JobSkill]) -> list:
    out = []
    relevant = [a for s in skills if s.status != "manquant" for a in s.aliases] + [k for s in skills for k in s.domain_keys]
    units = [(i, seg) for i, raw in enumerate(cv.splitlines())
             for seg in ([raw.strip()] if len(raw.strip()) <= 320 else [x.strip() for x in re.split(r"(?<=[.;])\s+", raw) if x.strip()])]
    first = [i for i, raw in enumerate(cv.splitlines()) if raw.strip()][:2]
    seen_first = set()
    for i, line in units:
        if i in first and i not in seen_first:  # name/title: the whole short line, or only the 1st sentence of a one-paragraph CV
            seen_first.add(i)
            continue
        if i in first and len(cv.splitlines()[i].strip()) < 120:
            continue
        body = line.lstrip("-•*●▪– ").strip()
        n = f" {_n(body)} "
        if (re.search(r"\b(19|20)\d{2}\b|aujourd|present", n) and len(body) < 90) or re.match(r" (formation|diplome|baccalaureat|langues?|education|competences?) ", n):
            continue
        if not (25 <= len(body) <= 320) or "@" in body or body.endswith(":") or body.isupper() or len(re.findall(r"[a-zA-Zà-ÿ]", body)) < 15:
            continue
        rel = sum(1 for a in relevant if a and f" {a}" in n)
        weak = (not quantified(body)) + bool(WEAK.match(_n(body))) + (len(body) < 70)
        if rel or weak >= 2:
            out.append((rel * 2 + weak, i, line))
    return [(i, line) for _, i, line in sorted(out, key=lambda x: -x[0])[:8]]


def invented(after: str, before: str, cv: str, skills: List[JobSkill]) -> str:
    """Reason why a reworded line adds facts absent from the CV ('' = acceptable)."""
    na, nb, ncv = f" {_n(after)} ", f" {_n(before)} ", f" {_n(cv)} "
    digits = set(re.findall(r"\d+", re.sub(r"(?<=\d)[\s.,](?=\d{3}\b)", "", cv)))
    for d in re.findall(r"\d+", re.sub(r"(?<=\d)[\s.,](?=\d{3}\b)", "", after)):
        if d not in digits:
            return f"chiffre « {d} » absent du CV"
    if YEARS.search(na) and not YEARS.search(nb):
        return "années d'expérience ajoutées"
    for w in TITLES:
        if f" {w}" in na and f" {w}" not in ncv:
            return f"intitulé de poste « {w} » absent du CV"
    for w in CERTS:
        if w not in ("certif", "attestation") and f" {w}" in na and f" {w}" not in ncv:
            return f"certification « {w} » absente du CV"
    proven = set()
    for s in skills:
        on_line = any(a and f" {a}" in nb for a in s.aliases) or (s.status == "partiel" and any(k and f" {k}" in nb for k in s.domain_keys))
        for a in s.aliases:
            if a and f" {a}" in na and f" {a}" not in ncv and not (on_line and s.status != "manquant"):
                return f"compétence « {s.label} » sans preuve dans cette ligne"
        if on_line and s.status != "manquant":
            proven.update(_n(a) for a in s.aliases)
    core = [w[:5] for w in nb.split() if len(w) >= 4 and w not in STOP and not any(w.startswith(g) for g in GENERIC)]
    if core and sum(1 for w in core if w in {x[:5] for x in na.split()}) < max(1, 0.5 * len(core)):
        return "la proposition ne correspond plus à la ligne d'origine"
    allowed = proven
    have = {w[:5] for w in ncv.split() if len(w) >= 3}
    for w in na.split():
        if len(w) < 4 or w in STOP or w.isdigit() or w[:5] in have or any(w.startswith(g) for g in GENERIC) or any(w in a.split() for a in allowed):
            continue
        return f"mot « {w} » absent du CV (information possiblement ajoutée)"
    if len(after) > 2.5 * len(before) + 120:
        return "reformulation trop longue"
    return ""


def create_cv_optimize_router(db, current_user, generate, parse_json):
    router = APIRouter(prefix="/api/careeros/cv-optimize")

    async def _cv(uid: str) -> tuple:
        p = await db.career_profiles.find_one({"user_id": uid}, {"_id": 0}) or {}
        return p, (p.get("cv_text") or "")

    @router.post("/propose")
    async def propose(body: ProposeBody, user: dict = Depends(current_user)):
        _, cv = await _cv(user["id"])
        if len(cv.strip()) < 80:
            raise HTTPException(status_code=400, detail="Collez d'abord votre CV maître dans la Career Memory.")
        cands = _candidates(cv, body.skills)
        items, rejected, ai = [], [], "ok"
        if cands:
            have = [s.label for s in body.skills if s.status == "ok"][:20]
            partial = [s.label for s in body.skills if s.status == "partiel"][:12]
            lines = "\n".join(f"{k}. {line}" for k, (_, line) in enumerate(cands))
            prompt = (f"POSTE VISÉ : {body.title or 'non précisé'}\nCOMPÉTENCES DE L'OFFRE DÉJÀ PROUVÉES DANS LE CV : {', '.join(have) or 'aucune'}\n"
                      f"COMPÉTENCES DE L'OFFRE À NOMMER SEULEMENT SI LA LIGNE EN APPORTE LA PREUVE : {', '.join(partial) or 'aucune'}\n\n"
                      f"CV COMPLET (référence des faits autorisés) :\n{cv[:9000]}\n\nLIGNES À AMÉLIORER :\n{lines}")
            async def ask(text):
                nonlocal ai
                try:
                    return (parse_json(await generate(SYSTEM, text)) or {}).get("items") or []
                except AB.QuotaReached:
                    ai = "quota"
                except Exception:  # noqa: BLE001 - provider failure: rules-only result, never a technical error for the member
                    ai = "indisponible"
                return []

            def check(raw_items, kmap):
                ok, bad = [], []
                for it in raw_items[:8]:
                    try:
                        k, after = int(it.get("i")), str(it.get("after") or "").strip()
                    except (TypeError, ValueError):
                        continue
                    if k not in kmap or not after:
                        continue
                    idx, before = cands[kmap[k]]
                    prefix = re.match(r"^\s*[-•*●▪–]\s*", before)
                    after = (prefix.group(0) if prefix else "") + after.lstrip("-•*●▪– ")
                    if _n(after) == _n(before):
                        continue
                    why = invented(after, before, cv, body.skills)
                    (bad if why else ok).append((kmap[k], idx, before, after, it, why))
                return ok, bad

            good, bad = check(await ask(prompt), {k: k for k in range(len(cands))})
            if bad:  # one correction round: the AI gets the exact reason and must remove the added information
                fix = "\n".join(f"{n}. LIGNE D'ORIGINE : {b[2]}\n   TA PROPOSITION REFUSÉE : {b[3]}\n   MOTIF : {b[5]} — retire cette information" for n, b in enumerate(bad))
                again, still = check(await ask(f"{prompt}\n\nCORRIGE CES PROPOSITIONS REFUSÉES (même format JSON, « i » = numéro ci-dessous) :\n{fix}"),
                                     {n: b[0] for n, b in enumerate(bad)})
                good += again
                bad = still + [b for b in bad if b[0] not in {g[0] for g in again}]
            seen = set()
            for k, idx, before, after, it, _ in good:
                if k in seen:
                    continue
                seen.add(k)
                items.append({"id": f"r{idx}-{k}", "type": "reformulation", "line": idx, "before": before, "after": after,
                              "skills": [str(x)[:80] for x in (it.get("skills") or [])][:5], "reason": str(it.get("reason") or "")[:300]})
            rejected = [{"before": b[2], "reason": b[5]} for b in bad if b[0] not in seen]
        return {"items": items, "rejected": rejected, "ai": ai, "cv_text": cv}

    @router.post("/simulate")
    async def simulate(body: SimBody, user: dict = Depends(current_user)):
        p, _ = await _cv(user["id"])
        if len(body.variants) > 40:
            raise HTTPException(status_code=400, detail="Trop de variantes")
        out = {}
        for k, cv in body.variants.items():
            r = compute({**p, "cv_text": str(cv)[:60000]})
            out[str(k)[:120]] = {"score": r["score"], "criteria": {c["key"]: c["score"] for c in r["criteria"]}, "labels": {c["key"]: c["label"] for c in r["criteria"]}}
        return out

    @router.post("/apply")
    async def apply(body: ApplyBody, user: dict = Depends(current_user)):
        p, before = await _cv(user["id"])
        now = datetime.now(timezone.utc).isoformat()
        ifp_before, ifp_after = compute(p)["score"], compute({**p, "cv_text": body.cv_text})["score"]
        v = {"id": str(uuid.uuid4()), "user_id": user["id"], "at": now, "kind": "optimisation", "cv_before": before, "cv_after": body.cv_text,
             "offer": {k: str(body.offer.get(k) or "")[:200] for k in ("title", "company", "kind", "id")}, "accepted": body.accepted,
             "diff": [{k: str(r.get(k) or "")[:2000] for k in ("tag", "text", "prev")} for r in body.diff if isinstance(r, dict)],
             "estimated": {k: body.estimated.get(k) for k in ("match_before", "match_after", "match_potential", "ifp_before", "ifp_after") if k in body.estimated},
             "real": {"ifp_before": ifp_before, "ifp_after": ifp_after}}
        await db.cv_versions.insert_one({**v})
        await db.career_profiles.update_one({"user_id": user["id"]}, {"$set": {"cv_text": body.cv_text, "updated_at": now}}, upsert=True)
        return {k: v[k] for k in ("id", "at", "real", "estimated")}

    @router.post("/versions/{vid}/real")
    async def real(vid: str, body: RealBody, user: dict = Depends(current_user)):
        r = await db.cv_versions.update_one({"id": vid, "user_id": user["id"]}, {"$set": {"real.match_after": body.match_after}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Version introuvable")
        return {"ok": True}

    @router.get("/versions")
    async def versions(user: dict = Depends(current_user)):
        return {"items": [v async for v in db.cv_versions.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).sort("at", -1).limit(100)]}

    @router.post("/versions/{vid}/restore")
    async def restore(vid: str, user: dict = Depends(current_user)):
        v = await db.cv_versions.find_one({"id": vid, "user_id": user["id"]}, {"_id": 0})
        if not v:
            raise HTTPException(status_code=404, detail="Version introuvable")
        p, cur = await _cv(user["id"])
        now = datetime.now(timezone.utc).isoformat()
        nv = {"id": str(uuid.uuid4()), "user_id": user["id"], "at": now, "kind": "restauration", "restored_from": vid, "cv_before": cur, "cv_after": v["cv_before"],
              "offer": v.get("offer") or {}, "accepted": [], "estimated": {},
              "real": {"ifp_before": compute(p)["score"], "ifp_after": compute({**p, "cv_text": v["cv_before"]})["score"]}}
        await db.cv_versions.insert_one({**nv})
        await db.career_profiles.update_one({"user_id": user["id"]}, {"$set": {"cv_text": v["cv_before"], "updated_at": now}})
        return {k: nv[k] for k in ("id", "at", "real")}

    return router

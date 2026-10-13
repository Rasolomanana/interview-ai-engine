"""CareerOS « GPS de carrière » : 5 steps, 6 milestones and ONE recommended next step, computed from real member data."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

STEPS = [("memory", "Career Memory", "/careeros/memoire"), ("radar", "Radar", "/careeros/radar"), ("pack", "Pack", "/careeros/nouveau"),
         ("interview", "Entrevue", "/careeros/copilote"), ("followup", "Suivi", "/careeros")]


def create_journey_router(db, current_user):
    router = APIRouter(prefix="/api/careeros")

    @router.get("/journey")
    async def journey(user: dict = Depends(current_user)):
        uid = user["id"]
        p = await db.career_profiles.find_one({"user_id": uid}, {"_id": 0, "cv_text": 1, "target_roles": 1, "location": 1}) or {}
        st = await db.radar_settings.find_one({"user_id": uid}, {"_id": 0, "keywords": 1}) or {}
        apps = [a async for a in db.applications.find({"user_id": uid, "archived": {"$ne": True}},
                                                      {"_id": 0, "id": 1, "code": 1, "status": 1, "pipeline_status": 1, "updated_at": 1}).sort("updated_at", -1)]
        offers = await db.radar_offers.count_documents({"user_id": uid})
        best_a = await db.radar_offers.find_one({"user_id": uid, "ips.priority": "A", "status": "nouvelle", "application_id": None}, {"_id": 0, "id": 1, "title": 1, "company": 1})
        now = datetime.now(timezone.utc).isoformat()
        ivs = [i async for i in db.interviews.find({"user_id": uid}, {"_id": 0, "application_id": 1, "scheduled_at": 1, "status": 1})]
        past_iv = next((i for i in ivs if i.get("scheduled_at") and i["scheduled_at"] < now and i.get("status") != "annule"), None)
        thanked = {e["application_id"] async for e in db.emails.find({"user_id": uid, "kind": "remerciement"}, {"_id": 0, "application_id": 1})}
        emails = await db.emails.count_documents({"user_id": uid})
        profile_ok = len(p.get("cv_text") or "") >= 200 and bool(p.get("target_roles")) and bool(p.get("location"))
        sent = [a for a in apps if a.get("pipeline_status") in ("postule", "entrevue", "offre", "refuse")]
        interviewed = bool(ivs) or any(a.get("pipeline_status") in ("entrevue", "offre") for a in apps)
        milestones = [
            {"key": "profile", "label": "Profil 100 %", "done": profile_ok},
            {"key": "radar", "label": "Radar configuré", "done": bool(st.get("keywords"))},
            {"key": "offer", "label": "Première offre trouvée", "done": offers > 0},
            {"key": "pack", "label": "Premier pack généré", "done": any(a.get("status") in ("done", "partial") for a in apps)},
            {"key": "sent", "label": "Première candidature envoyée", "done": bool(sent)},
            {"key": "interview", "label": "Première entrevue obtenue", "done": interviewed},
        ]
        done = {"memory": profile_ok, "radar": offers > 0, "pack": bool(apps), "interview": interviewed, "followup": emails > 0}
        ready = next((a for a in apps if a.get("status") == "done" and a.get("pipeline_status") == "a_postuler"), None)
        if not profile_ok:
            nxt = ("memory", "Complétez votre Career Memory", "Ajoutez votre CV, vos postes visés et votre ville : tout CareerOS s'appuie dessus.", "Compléter ma Career Memory", "/careeros/memoire", "2 min")
        elif not offers:
            nxt = ("radar", "Lancez votre premier Radar", "CareerOS cherche les offres pour vous et les classe par IPS.", "Ouvrir le Radar", "/careeros/radar", "3 min")
        elif past_iv and past_iv["application_id"] not in thanked:
            nxt = ("followup", "Envoyez le remerciement", "Votre entrevue est passée : un remerciement dans les 24 h fait la différence.", "Préparer le remerciement", f"/careeros/candidature/{past_iv['application_id']}", "2 min")
        elif ready:
            nxt = ("interview", "Préparez l'entrevue", f"Le pack {ready.get('code', '')} est prêt : entraînez-vous avec le Copilote avant de postuler.", "Préparer l'entrevue", f"/careeros/candidature/{ready['id']}", "5 min")
        elif best_a:
            nxt = ("pack", "Générez le pack", f"Offre priorité A : {best_a['title']} — {best_a['company']}.", "Voir l'offre et générer le pack", "/careeros/radar", "5 min")
        else:
            nxt = ("radar", "Consultez vos nouvelles opportunités", "Aucune offre A en attente : regardez les B ou ajustez vos mots-clés.", "Ouvrir le Radar", "/careeros/radar", "3 min")
        return {"steps": [{"key": k, "label": lbl, "to": to, "done": done[k]} for k, lbl, to in STEPS],
                "milestones": milestones, "completed": sum(m["done"] for m in milestones), "total": len(milestones),
                "next": dict(zip(("step", "title", "text", "cta", "to", "time"), nxt)),
                "preferences": user.get("preferences") or {}}

    return router

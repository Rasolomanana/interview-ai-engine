"""Admin roles (RBAC): the ADMIN_PASSWORD stays the unrestricted Super Admin; members can receive roles opening admin sections."""
from typing import List

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from admin import ADMIN_CTX, _check_admin
from .auth import _decode

ROLES = {"super_admin": "Super Admin", "support": "Support", "marketing": "Marketing", "conseiller": "Conseiller carrière"}
SECTIONS = ("overview", "geo", "business", "activite", "connecteurs", "finance", "roles")
ROLE_SECTIONS = {"super_admin": set(SECTIONS), "marketing": {"overview", "geo", "business", "activite"},
                 "support": {"overview", "activite", "connecteurs"}, "conseiller": {"business"}}
PATHS = [("/api/admin/stats", "activite"),  # export (ATS data) and llm-health (paid test calls) stay Super Admin only
         ("/api/admin/insights/overview", "overview"), ("/api/admin/insights/geo", "geo"), ("/api/admin/insights/business", "business"),
         ("/api/admin/connectors", "connecteurs"), ("/api/admin/radar-cron-log", "connecteurs"), ("/api/admin/knowledge", "connecteurs")]
OPEN = ("/api/admin/login", "/api/admin/me")


def sections_for(roles) -> list:
    out = set()
    for r in roles or []:
        out |= ROLE_SECTIONS.get(r, set())
    return [s for s in SECTIONS if s in out]


def section_of(path: str) -> str:
    return next((s for p, s in PATHS if path == p or path.startswith(p + "/")), "super")


def make_rbac_middleware(db):
    async def rbac(request: Request, call_next):
        p = request.url.path
        if p.startswith("/api/admin/") and p not in OPEN and request.method != "OPTIONS" and not request.headers.get("x-admin-password"):
            h = request.headers.get("authorization", "")
            if h.startswith("Bearer "):
                try:
                    uid = _decode(h[7:], "access")
                except HTTPException as e:
                    return JSONResponse({"detail": e.detail}, status_code=401)
                u = await db.users.find_one({"id": uid}, {"_id": 0, "admin_roles": 1}) or {}
                roles = u.get("admin_roles") or []
                sec = section_of(p)
                allowed = sections_for(roles)
                if sec not in allowed and not (sec == "super" and "super_admin" in roles):
                    return JSONResponse({"detail": "Accès refusé : votre rôle ne donne pas accès à cette section."}, status_code=403)
                ADMIN_CTX.set({"user_id": uid, "roles": roles, "super": "super_admin" in roles})
        return await call_next(request)
    return rbac


def is_super() -> bool:
    ctx = ADMIN_CTX.get()
    return ctx is None or ctx.get("super", False)  # no ctx = admin password (unrestricted Super Admin)


class RolesBody(BaseModel):
    roles: List[str] = []


def create_rbac_router(db):
    router = APIRouter(prefix="/api/admin")

    @router.get("/me")
    async def me(request: Request, x_admin_password: str = Header(None)):
        if x_admin_password:
            _check_admin(x_admin_password)
            return {"super": True, "via": "password", "roles": ["super_admin"], "sections": list(SECTIONS), "name": "Administrateur"}
        h = request.headers.get("authorization", "")
        if not h.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Connexion requise")
        u = await db.users.find_one({"id": _decode(h[7:], "access")}, {"_id": 0, "admin_roles": 1, "name": 1, "email": 1}) or {}
        roles = u.get("admin_roles") or []
        if not roles:
            raise HTTPException(status_code=403, detail="Aucun rôle Admin n'est attribué à ce compte. Demandez au Super Admin.")
        return {"super": "super_admin" in roles, "via": "member", "roles": roles, "sections": sections_for(roles), "name": u.get("name") or u.get("email")}

    @router.get("/roles")
    async def list_roles(q: str = "", x_admin_password: str = Header(None)):
        _check_admin(x_admin_password)
        flt = {"$or": [{"email": {"$regex": q, "$options": "i"}}, {"name": {"$regex": q, "$options": "i"}}]} if q.strip() else {}
        rows = [u async for u in db.users.find(flt, {"_id": 0, "id": 1, "email": 1, "name": 1, "created_at": 1, "admin_roles": 1}).sort("created_at", -1).limit(300)]
        return {"roles": ROLES, "role_sections": {k: sorted(v) for k, v in ROLE_SECTIONS.items()},
                "members": [{**u, "admin_roles": u.get("admin_roles") or []} for u in rows]}

    @router.put("/roles/{user_id}")
    async def set_roles(user_id: str, body: RolesBody, x_admin_password: str = Header(None)):
        _check_admin(x_admin_password)
        roles = [r for r in dict.fromkeys(body.roles) if r in ROLES]
        r = await db.users.update_one({"id": user_id}, {"$set": {"admin_roles": roles}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Membre introuvable")
        return {"ok": True, "admin_roles": roles}

    return router

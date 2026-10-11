"""CareerOS member accounts: email/password, bcrypt, JWT Bearer tokens.

Bearer tokens (not cookies) because frontend (pages.dev) and backend (onrender.com)
live on different sites. Access token 12 h, refresh token 30 days."""
import os
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr, Field

ALGO = "HS256"
ACCESS_TTL = timedelta(hours=12)
REFRESH_TTL = timedelta(days=30)
MAX_ATTEMPTS = 5
LOCKOUT = timedelta(minutes=15)


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def _now():
    return datetime.now(timezone.utc)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def _token(user_id: str, kind: str, ttl: timedelta) -> str:
    return jwt.encode({"sub": user_id, "type": kind, "exp": _now() + ttl}, _secret(), algorithm=ALGO)


def _tokens(user_id: str) -> dict:
    return {"access_token": _token(user_id, "access", ACCESS_TTL), "refresh_token": _token(user_id, "refresh", REFRESH_TTL)}


def _decode(token: str, kind: str) -> str:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expirée")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Jeton invalide")
    if payload.get("type") != kind:
        raise HTTPException(status_code=401, detail="Type de jeton invalide")
    return payload["sub"]


def _public(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "name": user.get("name", ""), "created_at": user.get("created_at")}


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshBody(BaseModel):
    refresh_token: str


def create_auth(db):
    """Returns (router, current_user dependency)."""
    router = APIRouter(prefix="/api/auth", tags=["auth"])

    async def current_user(request: Request) -> dict:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Connexion requise")
        user_id = _decode(header[7:], "access")
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Compte introuvable")
        return user

    @router.post("/register")
    async def register(body: RegisterBody):
        email = body.email.lower().strip()
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet e-mail")
        user = {"id": str(uuid.uuid4()), "email": email, "name": body.name.strip(),
                "password_hash": hash_password(body.password), "created_at": _now().isoformat()}
        await db.users.insert_one(user)
        return {"user": _public(user), **_tokens(user["id"])}

    @router.post("/login")
    async def login(body: LoginBody, request: Request):
        email = body.email.lower().strip()
        ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else ""))
        ident = f"{ip}:{email}"
        att = await db.login_attempts.find_one({"identifier": ident})
        if att and att.get("count", 0) >= MAX_ATTEMPTS and att.get("locked_until") and datetime.fromisoformat(att["locked_until"]) > _now():
            raise HTTPException(status_code=429, detail="Trop de tentatives. Réessayez dans 15 minutes.")
        user = await db.users.find_one({"email": email})
        if not user or not verify_password(body.password, user["password_hash"]):
            count = (att or {}).get("count", 0) + 1
            if att and att.get("locked_until") and datetime.fromisoformat(att["locked_until"]) <= _now():
                count = 1
            await db.login_attempts.update_one(
                {"identifier": ident},
                {"$set": {"count": count, "locked_until": (_now() + LOCKOUT).isoformat() if count >= MAX_ATTEMPTS else None, "updated_at": _now()}},
                upsert=True,
            )
            raise HTTPException(status_code=401, detail="E-mail ou mot de passe incorrect")
        await db.login_attempts.delete_one({"identifier": ident})
        return {"user": _public(user), **_tokens(user["id"])}

    @router.post("/refresh")
    async def refresh(body: RefreshBody):
        user_id = _decode(body.refresh_token, "refresh")
        if not await db.users.find_one({"id": user_id}, {"_id": 1}):
            raise HTTPException(status_code=401, detail="Compte introuvable")
        return {"access_token": _token(user_id, "access", ACCESS_TTL)}

    @router.get("/me")
    async def me(user: dict = Depends(current_user)):
        return _public(user)

    return router, current_user


async def ensure_auth_indexes(db):
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("updated_at", expireAfterSeconds=86400)

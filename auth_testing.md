# CareerOS auth testing
- Bearer JWT (no cookies). POST /api/auth/register {email,password(>=8),name} -> {user, access_token, refresh_token}
- POST /api/auth/login {email,password} -> same. 5 failures per ip:email -> 429 for 15 min.
- POST /api/auth/refresh {refresh_token} -> {access_token}
- GET /api/auth/me (Authorization: Bearer <access>) -> user
- Mongo: db.users (id uuid, email unique, password_hash bcrypt $2b$), db.login_attempts
- Frontend stores tokens in localStorage key "careeros.tokens"; routes /connexion, /careeros/*

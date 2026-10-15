"""Test accounts: any @careeros.dev address by default, or an explicit is_test flag set by the Super Admin. Excluded from production statistics."""
TEST_DOMAIN = "@careeros.dev"


def is_test(user: dict) -> bool:
    if isinstance(user.get("is_test"), bool):
        return user["is_test"]
    return (user.get("email") or "").lower().endswith(TEST_DOMAIN)


async def test_ids(db, include_test: bool = False) -> set:
    """Member ids to exclude from statistics (empty when test accounts are included)."""
    if include_test:
        return set()
    return {u["id"] async for u in db.users.find({}, {"_id": 0, "id": 1, "email": 1, "is_test": 1}) if is_test(u)}


import contextvars  # noqa: E402

EXCLUDE = contextvars.ContextVar("exclude_test_ids", default=frozenset())


async def scope(db, include_test: bool):
    """Set the test-account exclusion for the current admin request."""
    EXCLUDE.set(frozenset(await test_ids(db, include_test)))


def uf(flt: dict = None, field: str = "user_id") -> dict:
    """Mongo filter + exclusion of test accounts on `field` (user_id, or id for users)."""
    flt = flt or {}
    ex = EXCLUDE.get()
    if not ex:
        return flt
    cond = {field: {"$nin": list(ex)}}
    return {"$and": [flt, cond]} if field in flt else {**flt, **cond}

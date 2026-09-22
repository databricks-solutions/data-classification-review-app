from __future__ import annotations
import os
from fastapi import APIRouter, Request
from ..models import MeOut, PrincipalOut
from ..db.connection import query as db_query, execute
from ..core.dependencies import Dependencies

router = APIRouter()
IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"


def _principal_out(p: dict) -> PrincipalOut:
    return PrincipalOut(
        id=p["id"], name=p["name"], email=p.get("email"),
        kind=p["kind"], initials=p["initials"], accent=p["accent"],
        team=p.get("team"), members=p.get("members"), is_admin=p["is_admin"],
    )


@router.get("/me", response_model=MeOut, operation_id="getMe")
def get_me(request: Request, headers: Dependencies.Headers):
    if IS_MOCK:
        uid = request.headers.get("X-Mock-User", "jamie.diaz")
        rows = db_query("SELECT * FROM principals WHERE id = %s", (uid,))
        if not rows:
            rows = db_query("SELECT * FROM principals WHERE id = 'jamie.diaz'")
        user = rows[0]
        all_users = [_principal_out(r) for r in db_query("SELECT * FROM principals ORDER BY name")]
        return MeOut(
            id=user["id"], name=user["name"], email=user.get("email"),
            initials=user["initials"], accent=user["accent"], team=user.get("team"),
            is_admin=user["is_admin"], is_mock_mode=True, all_users=all_users,
        )

    # In local dev APX may not forward auth headers; fall back to DEV_USER_EMAIL.
    email = headers.user_email or os.environ.get("DEV_USER_EMAIL") or "unknown@example.com"
    admin_emails = {e.strip() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
    is_admin_override = email in admin_emails

    rows = db_query("SELECT * FROM principals WHERE id = %s", (email,))
    if rows:
        p = rows[0]
        effective_admin = p["is_admin"] or is_admin_override
        if is_admin_override and not p["is_admin"]:
            execute("UPDATE principals SET is_admin = true WHERE id = %s", (email,))
        return MeOut(id=p["id"], name=p["name"], email=p.get("email"),
                     initials=p["initials"], accent=p["accent"], team=p.get("team"),
                     is_admin=effective_admin, is_mock_mode=False)
    name = headers.user_name or email.split("@")[0]
    initials = "".join(w[0].upper() for w in name.split()[:2]) or "??"
    execute(
        "INSERT INTO principals (id,name,email,kind,initials,accent,is_admin) "
        "VALUES (%s,%s,%s,'user',%s,'#1B3139',%s) ON CONFLICT DO NOTHING",
        (email, name, email, initials, is_admin_override),
    )
    return MeOut(id=email, name=name, email=email, initials=initials,
                 accent="#1B3139", is_admin=is_admin_override, is_mock_mode=False)

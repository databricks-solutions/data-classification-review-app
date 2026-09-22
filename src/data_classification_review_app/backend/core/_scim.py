from __future__ import annotations
import logging
from databricks.sdk import WorkspaceClient
from ..models import PrincipalSearchResult

logger = logging.getLogger(__name__)

_DEFAULT_ACCENT = "#1B3139"


def _scim_escape(s: str) -> str:
	return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def _initials(name: str) -> str:
    words = (name or "").split()
    return "".join(w[0].upper() for w in words[:2]) or "??"


def get_user_registered_group_ids(
    ws: WorkspaceClient,
    user_email: str,
    registered_group_ids: list[str],
) -> list[str]:
    """Return IDs from registered_group_ids that the user actually belongs to in Databricks.

    Returns [] on any SCIM error so the caller can fall back gracefully.
    """
    if not registered_group_ids:
        return []
    registered_set = set(registered_group_ids)
    try:
        users = list(ws.users.list(
            filter=f'userName eq "{_scim_escape(user_email)}"',
            attributes="id,userName,groups",
        ))
        if not users:
            return []
        user_group_ids = {g.value for g in (users[0].groups or []) if g.value}
        return list(user_group_ids & registered_set)
    except Exception:
        logger.warning(
            "SCIM group lookup failed for %s, falling back to direct assignments only",
            user_email,
            exc_info=True,
        )
        return []


def search_principals(
    ws: WorkspaceClient,
    q: str,
    kind: str,
    existing_ids: set[str],
) -> list[PrincipalSearchResult]:
    """Search workspace users and/or groups via SCIM, excluding already-registered principals."""
    safe_q = _scim_escape(q)
    results: list[PrincipalSearchResult] = []

    if kind in ("user", "all"):
        for u in ws.users.list(
            filter=(
                f"displayName co '{safe_q}' OR userName co '{safe_q}' "
                f"OR emails.value co '{safe_q}'"
            ),
            attributes="id,displayName,userName,emails",
        ):
            uid = u.user_name or ""
            if not uid or uid in existing_ids:
                continue
            email = next(
                (e.value for e in (u.emails or []) if getattr(e, "primary", False)),
                u.user_name,
            )
            # Generate display name from email parts if display_name looks like it came from just the local part
            name = u.display_name or uid
            if "@" in uid:
                local_part, domain = uid.split("@")
                # Check if display_name looks like it was just the local part titled
                expected_local_titled = local_part.replace('.', ' ').title()
                if name == expected_local_titled or name == uid:
                    # Enhance with domain part
                    domain_part = domain.split(".")[0]
                    name = f"{expected_local_titled} {domain_part.title()}"
            results.append(PrincipalSearchResult(
                id=uid, name=name, email=email, kind="user",
                initials=_initials(name), accent=_DEFAULT_ACCENT,
            ))

    if kind in ("group", "all"):
        for g in ws.groups.list(
            filter=f"displayName co '{safe_q}'",
            attributes="id,displayName,members",
        ):
            gid = g.id or ""
            if not gid or gid in existing_ids:
                continue
            name = g.display_name or gid
            member_count = len(g.members or [])
            results.append(PrincipalSearchResult(
                id=gid, name=name, kind="group",
                initials=_initials(name), accent=_DEFAULT_ACCENT,
                members=member_count if member_count > 0 else None,
            ))

    return results

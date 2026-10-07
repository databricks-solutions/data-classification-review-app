from __future__ import annotations
import logging
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import BadRequest, TooManyRequests
from ..models import PrincipalSearchResponse, PrincipalSearchResult

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


def fail_fast_client(ws: WorkspaceClient, retry_timeout_seconds: int = 1) -> WorkspaceClient:
    """Same config and credentials as ws, but with a short SDK retry budget.

    The SDK retries 429s for up to 300s by default. On large directories SCIM
    user listing is rejected by a global rate limit on every call, so the default would
    hang the search request for minutes instead of falling back.
    """
    cfg = ws.config.copy()
    # Config.copy() is shallow and shares the attribute dict; detach it so the shared
    # app client keeps its own retry budget. Credentials provider stays shared.
    cfg._inner = dict(cfg._inner)
    cfg.retry_timeout_seconds = retry_timeout_seconds
    return WorkspaceClient(config=cfg)


def _user_result(u) -> PrincipalSearchResult | None:
    uid = u.user_name or ""
    if not uid:
        return None
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
    return PrincipalSearchResult(
        id=uid, name=name, email=email, kind="user",
        initials=_initials(name), accent=_DEFAULT_ACCENT,
    )


def _list_users(ws: WorkspaceClient, scim_filter: str) -> list:
    return list(ws.users.list(filter=scim_filter, attributes="id,displayName,userName,emails"))


def _search_users(ws: WorkspaceClient, q: str) -> tuple[list, str]:
    """Return (SCIM users, status). Status is "ok" or "exact_only"; other errors propagate."""
    safe_q = _scim_escape(q)
    # Lowercase `or` matters: with `OR` Databricks SCIM silently evaluates only the first clause.
    substring = f"displayName co '{safe_q}' or userName co '{safe_q}'"
    try:
        try:
            return _list_users(ws, f"{substring} or emails.value co '{safe_q}'"), "ok"
        except BadRequest as e:
            # Some workspaces reject the emails.value attribute in filters.
            logger.info("SCIM rejected emails.value filter, retrying without it: %s", e)
            return _list_users(ws, substring), "ok"
    except (TooManyRequests, TimeoutError) as e:
        # TimeoutError: the SDK gave up retrying a persistent 429.
        logger.warning(
            "SCIM user substring search throttled for q=%r, falling back to exact userName lookup: %s",
            q, e,
        )
    if "@" not in q:
        return [], "exact_only"
    return _list_users(ws, f"userName eq '{safe_q}'"), "exact_only"


def search_principals(
    ws: WorkspaceClient,
    q: str,
    kind: str,
    existing_ids: set[str],
) -> PrincipalSearchResponse:
    """Search workspace users and/or groups via SCIM, excluding already-registered principals.

    Users and groups are searched independently so one failing doesn't hide the other.
    """
    results: list[PrincipalSearchResult] = []
    users_status = groups_status = "skipped"

    if kind in ("user", "all"):
        try:
            users, users_status = _search_users(ws, q)
            for u in users:
                r = _user_result(u)
                if r and r.id not in existing_ids:
                    results.append(r)
        except Exception as e:
            logger.error("SCIM user search failed for q=%r: %s", q, e, exc_info=True)
            users_status = "error"

    if kind in ("group", "all"):
        try:
            for g in ws.groups.list(
                filter=f"displayName co '{_scim_escape(q)}'",
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
            groups_status = "ok"
        except Exception as e:
            logger.error("SCIM group search failed for q=%r: %s", q, e, exc_info=True)
            groups_status = "error"

    return PrincipalSearchResponse(
        results=results, users_status=users_status, groups_status=groups_status,
    )

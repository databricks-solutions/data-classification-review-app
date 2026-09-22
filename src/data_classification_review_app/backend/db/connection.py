from __future__ import annotations
import os
import time
import threading
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()
_token_expires_at: float = 0  # unix timestamp; 0 = not yet fetched
_TOKEN_REFRESH_BUFFER = 120   # rebuild pool this many seconds before token expires
_sdk_user: str | None = None  # cached SDK user for when LAKEBASE_USER is unset


def _is_local() -> bool:
    return not bool(os.environ.get("LAKEBASE_HOST"))


def _is_autoscale() -> bool:
    # Autoscaling Lakebase requires dynamic OAuth tokens; distinguished by this env var.
    return bool(os.environ.get("LAKEBASE_ENDPOINT_NAME"))


def _generate_token() -> tuple[str, float]:
    """Return (token, expiry_unix_ts) and cache the SDK user for _build_dsn."""
    global _sdk_user
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    if _sdk_user is None:
        _sdk_user = w.current_user.me().user_name
    cred = w.postgres.generate_database_credential(
        endpoint=os.environ["LAKEBASE_ENDPOINT_NAME"]
    )
    # expire_time is a google.protobuf.Timestamp with a .seconds attribute
    expiry = float(cred.expire_time.seconds)
    return cred.token, expiry


def _build_dsn(token: str | None = None) -> dict:
    if os.environ.get("LAKEBASE_HOST"):
        if token is None:
            token = os.environ.get("LAKEBASE_PASSWORD", "")
        user = os.environ.get("LAKEBASE_USER") or _sdk_user or ""
        return dict(
            host=os.environ["LAKEBASE_HOST"],
            port=int(os.environ.get("LAKEBASE_PORT", "5432")),
            dbname=os.environ.get("LAKEBASE_DATABASE", "databricks_postgres"),
            user=user,
            password=token,
            sslmode="require",
        )
    # Local dev: APX PGLite
    return dict(
        host=os.environ.get("APX_DEV_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("APX_DEV_DB_PORT", "4296")),
        dbname=os.environ.get("APX_DEV_DB_NAME", "postgres"),
        user=os.environ.get("APX_DEV_DB_USER", "postgres"),
        password=os.environ.get("APX_DEV_DB_PWD", "password"),
        sslmode="disable",
    )


def _get_pool() -> ThreadedConnectionPool:
    global _pool, _token_expires_at
    with _pool_lock:
        needs_rebuild = _pool is None or (
            _is_autoscale() and time.time() >= _token_expires_at - _TOKEN_REFRESH_BUFFER
        )
        if needs_rebuild:
            if _pool is not None:
                try:
                    _pool.closeall()
                except Exception:
                    pass
                _pool = None
            if _is_autoscale():
                token, _token_expires_at = _generate_token()
                dsn = _build_dsn(token=token)
            else:
                dsn = _build_dsn()
            _pool = ThreadedConnectionPool(minconn=1, maxconn=10, **dsn)
    return _pool


def get_conn():
    # PGLite drops idle pool connections; use fresh connections per call in local dev.
    if _is_local():
        return psycopg2.connect(**_build_dsn())
    return _get_pool().getconn()


def putconn(conn, *, broken: bool = False) -> None:
    if _is_local():
        conn.close()
    else:
        _get_pool().putconn(conn, close=broken)


async def init_db() -> None:
    """Run pending migrations in order, skipping already-applied ones."""
    import pathlib
    migrations_dir = pathlib.Path(__file__).parent / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    conn = get_conn()
    try:
        # Bootstrap migration tracking table (IF NOT EXISTS is ownership-free when table already exists).
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT now()
                )
            """)
        conn.commit()

        for mf in migration_files:
            version = mf.stem
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                if cur.fetchone():
                    continue  # Already applied by a previous deployment
            with conn.cursor() as cur:
                cur.execute(mf.read_text())
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
                    (version,),
                )
            conn.commit()
    finally:
        putconn(conn)


def close_pool() -> None:
    global _pool, _token_expires_at
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
        _token_expires_at = 0


def query(sql: str, params=None) -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        putconn(conn)


def execute(sql: str, params=None) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        putconn(conn)


def execute_returning(sql: str, params=None) -> dict:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            conn.commit()
            return dict(cur.fetchone())
    finally:
        putconn(conn)

import os
from .core import create_app
from .router import router

IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"

# Always initialise the workspace client gracefully — in local dev the
# Databricks profile may be expired or unavailable, but the app can still
# serve requests that don't need it (decisions, stewards, DB-backed routes).
try:
    from .core._defaults import _WorkspaceClientDependency
    from contextlib import asynccontextmanager
    from typing import AsyncGenerator
    from fastapi import FastAPI

    @asynccontextmanager
    async def _graceful_ws_lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        try:
            from databricks.sdk import WorkspaceClient
            app.state.workspace_client = WorkspaceClient()
        except Exception:
            app.state.workspace_client = None
        yield

    _WorkspaceClientDependency.lifespan = _graceful_ws_lifespan  # type: ignore[method-assign]
except Exception:
    pass

# Import DB lifespan dependency before create_app() so it auto-registers.
from .db import lifespan as _db_lifespan  # noqa: F401  (side-effect import)

app = create_app(routers=[router])

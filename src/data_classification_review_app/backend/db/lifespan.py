"""DB init LifespanDependency — auto-registered when this module is imported."""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from ..core._base import LifespanDependency


class _DbInitDependency(LifespanDependency):
    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        from .connection import init_db
        await init_db()
        if os.environ.get("USE_MOCK_DATA", "false").lower() == "true":
            from .seed import seed_db
            seed_db()
        else:
            # Provision the SP-owned view, synced table and refresh job off the request
            # path: the synced-table create (and waiting for its pipeline id) are slow
            # control-plane calls and provisioning is best-effort, so it must not block
            # or fail startup. Idempotent, so a later restart — or an admin's Retry on
            # the overview page — re-attempts anything that wasn't ready yet.
            from .classification_provision import start_provisioning
            start_provisioning()
        yield

    @staticmethod
    def __call__() -> None:  # no request-level injection needed
        return None

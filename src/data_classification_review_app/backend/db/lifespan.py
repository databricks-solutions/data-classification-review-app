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
        yield

    @staticmethod
    def __call__() -> None:  # no request-level injection needed
        return None

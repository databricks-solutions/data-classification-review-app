from databricks.sdk.service.iam import User as UserOut

from .core import Dependencies, create_router
from .models import VersionOut

# Import all route routers
from .routes.me import router as me_router
from .routes.proposals import router as proposals_router
from .routes.tables import router as tables_router
from .routes.decisions import router as decisions_router
from .routes.apply_tags import router as apply_tags_router
from .routes.stewards import router as stewards_router
from .routes.tags import router as tags_router

router = create_router()


@router.get("/version", response_model=VersionOut, operation_id="version")
async def version():
    return VersionOut.from_metadata()


@router.get("/current-user", response_model=UserOut, operation_id="currentUser")
def me(user_ws: Dependencies.UserClient):
    return user_ws.current_user.me()


# Include all route modules
router.include_router(me_router)
router.include_router(proposals_router)
router.include_router(tables_router)
router.include_router(decisions_router)
router.include_router(apply_tags_router)
router.include_router(stewards_router)
router.include_router(tags_router)

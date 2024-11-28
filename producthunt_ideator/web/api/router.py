from fastapi.routing import APIRouter

from producthunt_ideator.web.api import dummy, echo, ideator, monitoring, redis

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(echo.router, prefix="/echo", tags=["echo"])
api_router.include_router(dummy.router, prefix="/dummy", tags=["dummy"])
api_router.include_router(redis.router, prefix="/redis", tags=["redis"])
api_router.include_router(ideator.router, prefix="/ideator", tags=["ideator"])

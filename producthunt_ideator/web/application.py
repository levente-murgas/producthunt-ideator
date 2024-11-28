from importlib import metadata

from celery import Celery
from fastapi import FastAPI
from fastapi.responses import UJSONResponse, TemplateResponse

from producthunt_ideator.services.celery.dependency import get_celery_app
from producthunt_ideator.web.lifespan import lifespan_setup


def get_app() -> FastAPI:
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    app = FastAPI(
        title="producthunt_ideator",
        version=metadata.version("producthunt_ideator"),
        lifespan=lifespan_setup,
        docs_url="/",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=UJSONResponse,
    )

    # Ensure Celery app is created and tasks are registered
    app.celery_app = get_celery_app()
    app.celery_app.autodiscover_tasks()

    from producthunt_ideator.web.api.router import api_router

    # Main router for the API.
    app.include_router(router=api_router, prefix="/api")

    @app.get("/generated-content", response_class=TemplateResponse)
    async def render_generated_content():
        from producthunt_ideator.web.api.ideator.controller import retrieve_generated_content
        content = retrieve_generated_content()
        return TemplateResponse("generated_content.html", {"content": content})

    return app


app = get_app()
celery: Celery = app.celery_app

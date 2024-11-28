from celery import Celery

from producthunt_ideator.settings import settings

celery_app = Celery(
    __name__,
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "producthunt_ideator.web.api.ideator.controller",
    ],  # Ensure tasks are included
)


def get_celery_app() -> Celery:  # pragma: no cover
    """Returns celery app."""
    return celery_app

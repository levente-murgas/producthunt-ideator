import logging

from celery import Celery
from fastapi import APIRouter, Depends

from producthunt_ideator.services.celery.dependency import get_celery_app
from producthunt_ideator.web.api.ideator import controller
from producthunt_ideator.web.api.ideator.schema import TaskOut, RunWorkflowIn

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/")
async def run_workflow(body: RunWorkflowIn) -> TaskOut:
    logging.info("Running workflow")
    r = controller.run_workflow.delay(body.date)
    return controller._to_task_out(r)


@router.get("/status")
async def check_workflow_status(
    task_id: str,
    celery_app: Celery = Depends(get_celery_app),
) -> TaskOut:
    r = celery_app.AsyncResult(task_id)
    logging.info(f"Task {task_id} status: {r.status}")
    return controller._to_task_out(r)


@router.post("/publish")
async def publish_to_wordpress() -> TaskOut:
    logging.info("Publishing workflow")
    r = controller.publish_to_wordpress.delay()
    return controller._to_task_out(r)

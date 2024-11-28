import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status


@pytest.mark.anyio
async def test_run_workflow(client: AsyncClient, fastapi_app: FastAPI) -> None:
    url = fastapi_app.url_path_for("run_workflow")
    response = await client.get(url)
    assert response.status_code == status.HTTP_200_OK
    task_id = response.json()["id"]
    assert task_id is not None


@pytest.mark.anyio
async def test_check_workflow_status(client: AsyncClient, fastapi_app: FastAPI) -> None:
    url = fastapi_app.url_path_for("check_workflow_status")
    response = await client.get(url, params={"task_id": "some_task_id"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] is not None

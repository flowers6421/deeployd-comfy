"""Workflow API router."""

from typing import Any

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from src.api.exceptions import InvalidWorkflowError, WorkflowNotFoundError

router = APIRouter()


class WorkflowUploadResponse(BaseModel):
    """Workflow upload response."""

    workflow_id: str
    status: str
    message: str


class WorkflowListResponse(BaseModel):
    """Workflow list response."""

    workflows: list[dict[str, Any]]
    total: int


@router.post("/upload", response_model=WorkflowUploadResponse)
async def upload_workflow(file: UploadFile = File(...)):
    """Upload a workflow file.

    Args:
        file: Uploaded workflow file

    Returns:
        Upload response with workflow ID
    """
    if not file.filename.endswith(".json"):
        raise InvalidWorkflowError("File must be a JSON file")

    # For now, return mock response
    return WorkflowUploadResponse(
        workflow_id="workflow_123",
        status="uploaded",
        message="Workflow uploaded successfully",
    )


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows():
    """List all workflows.

    Returns:
        List of workflows
    """
    return WorkflowListResponse(workflows=[], total=0)


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow by ID.

    Args:
        workflow_id: Workflow identifier

    Returns:
        Workflow data
    """
    # For now, return mock response
    if workflow_id == "not_found":
        raise WorkflowNotFoundError(workflow_id)

    return {"id": workflow_id, "name": "Sample Workflow", "nodes": {}}


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete workflow by ID.

    Args:
        workflow_id: Workflow identifier

    Returns:
        Deletion status
    """
    return {"status": "deleted", "workflow_id": workflow_id}

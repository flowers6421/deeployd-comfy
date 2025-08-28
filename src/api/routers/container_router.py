"""Container API router."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class BuildRequest(BaseModel):
    """Container build request."""

    workflow_id: str
    base_image: str = "python:3.11-slim"
    optimize: bool = True


class BuildResponse(BaseModel):
    """Container build response."""

    build_id: str
    status: str
    message: str


@router.post("/build", response_model=BuildResponse)
async def build_container(request: BuildRequest) -> BuildResponse:  # noqa: ARG001
    """Build container from workflow.

    Args:
        request: Build request

    Returns:
        Build response with build ID
    """
    return BuildResponse(
        build_id="build_123", status="building", message="Container build started"
    )


@router.get("/builds/{build_id}")
async def get_build_status(build_id: str) -> dict[str, Any]:
    """Get build status by ID.

    Args:
        build_id: Build identifier

    Returns:
        Build status
    """
    return {"build_id": build_id, "status": "completed", "progress": 100}


@router.get("/images")
async def list_images() -> dict[str, Any]:
    """List built container images.

    Returns:
        List of container images
    """
    return {"images": [], "total": 0}


@router.delete("/images/{image_id}")
async def delete_image(image_id: str) -> dict[str, Any]:
    """Delete container image.

    Args:
        image_id: Image identifier

    Returns:
        Deletion status
    """
    return {"status": "deleted", "image_id": image_id}

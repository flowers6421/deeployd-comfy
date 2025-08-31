"""Workflow API router with database integration."""

import json
from typing import Any, List, Optional
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session

from src.api.exceptions import InvalidWorkflowError, WorkflowNotFoundError
from src.db.database import init_db
from src.db.repositories import WorkflowRepository
from src.workflows.parser import WorkflowParser
from src.workflows.dependencies import DependencyExtractor
from src.api.generator import WorkflowAPIGenerator

router = APIRouter()

# Initialize database
db = init_db()


def get_session():
    """Get database session."""
    with db.get_session() as session:
        yield session


class WorkflowResponse(BaseModel):
    """Workflow response model."""
    id: str
    name: str
    description: Optional[str]
    definition: dict
    dependencies: dict
    parameters: List[dict]
    version: int
    created_at: str
    updated_at: str


@router.post("/", response_model=WorkflowResponse)
async def create_workflow(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    description: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Create a new workflow from uploaded file.
    
    Args:
        file: Uploaded workflow JSON file
        name: Optional workflow name
        description: Optional workflow description
        
    Returns:
        Created workflow
    """
    if not file.filename.endswith(".json"):
        raise InvalidWorkflowError("File must be a JSON file")
    
    # Read and parse workflow
    content = await file.read()
    try:
        workflow_data = json.loads(content)
    except json.JSONDecodeError as e:
        raise InvalidWorkflowError(f"Invalid JSON: {e}")
    
    # Extract name from filename if not provided
    if not name:
        name = Path(file.filename).stem
    
    # Parse and validate workflow
    parser = WorkflowParser()
    try:
        parsed = parser.parse(workflow_data)
    except Exception as e:
        raise InvalidWorkflowError(f"Invalid workflow: {e}")
    
    # Extract dependencies
    extractor = DependencyExtractor()
    dependencies = extractor.extract_all(workflow_data)
    
    # Convert sets to lists for JSON serialization
    if isinstance(dependencies.get("custom_nodes"), set):
        dependencies["custom_nodes"] = list(dependencies["custom_nodes"])
    if isinstance(dependencies.get("python_packages"), set):
        dependencies["python_packages"] = list(dependencies["python_packages"])
    for key in dependencies.get("models", {}):
        if isinstance(dependencies["models"][key], set):
            dependencies["models"][key] = list(dependencies["models"][key])
    
    # Extract parameters
    api_generator = WorkflowAPIGenerator()
    parameters = api_generator.extract_input_parameters(workflow_data)
    param_dicts = [
        {
            "name": p.name,
            "type": p.type.value if hasattr(p.type, 'value') else str(p.type),
            "default": p.default,
            "required": p.required,
            "description": p.description
        }
        for p in parameters
    ]
    
    # Save to database
    repo = WorkflowRepository(session)
    workflow = repo.create(
        name=name,
        definition=workflow_data,
        dependencies=dependencies,
        parameters=param_dicts,
        description=description
    )
    
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        definition=workflow.definition,
        dependencies=workflow.dependencies,
        parameters=workflow.parameters,
        version=workflow.version,
        created_at=workflow.created_at.isoformat(),
        updated_at=workflow.updated_at.isoformat()
    )


@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows(
    limit: int = 100,
    offset: int = 0,
    name_filter: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """List all workflows.
    
    Args:
        limit: Maximum number of results
        offset: Number of results to skip
        name_filter: Optional name filter
        
    Returns:
        List of workflows
    """
    repo = WorkflowRepository(session)
    workflows = repo.list(limit=limit, offset=offset, name_filter=name_filter)
    
    return [
        WorkflowResponse(
            id=w.id,
            name=w.name,
            description=w.description,
            definition=w.definition,
            dependencies=w.dependencies,
            parameters=w.parameters,
            version=w.version,
            created_at=w.created_at.isoformat(),
            updated_at=w.updated_at.isoformat()
        )
        for w in workflows
    ]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    session: Session = Depends(get_session)
):
    """Get workflow by ID.
    
    Args:
        workflow_id: Workflow identifier
        
    Returns:
        Workflow data
    """
    repo = WorkflowRepository(session)
    workflow = repo.get(workflow_id)
    
    if not workflow:
        raise WorkflowNotFoundError(workflow_id)
    
    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        definition=workflow.definition,
        dependencies=workflow.dependencies,
        parameters=workflow.parameters,
        version=workflow.version,
        created_at=workflow.created_at.isoformat(),
        updated_at=workflow.updated_at.isoformat()
    )


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    session: Session = Depends(get_session)
):
    """Delete workflow by ID.
    
    Args:
        workflow_id: Workflow identifier
        
    Returns:
        Deletion status
    """
    repo = WorkflowRepository(session)
    deleted = repo.delete(workflow_id)
    
    if not deleted:
        raise WorkflowNotFoundError(workflow_id)
    
    return {"status": "deleted", "workflow_id": workflow_id}
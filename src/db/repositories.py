"""Repository pattern for database operations."""

import hashlib
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlmodel import Session, select, func

from src.db.models import (
    Workflow, WorkflowVersion, ContainerBuild,
    CustomNode, APIEndpoint, WorkflowExecution
)

logger = logging.getLogger(__name__)


class WorkflowRepository:
    """Repository for workflow CRUD operations."""
    
    def __init__(self, session: Session):
        """Initialize with database session.
        
        Args:
            session: SQLModel database session
        """
        self.session = session
    
    def create(
        self, 
        name: str,
        definition: Dict[str, Any],
        dependencies: Optional[Dict[str, Any]] = None,
        parameters: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None
    ) -> Workflow:
        """Create a new workflow.
        
        Args:
            name: Workflow name
            definition: Workflow JSON definition
            dependencies: Extracted dependencies
            parameters: API parameters
            description: Optional description
            
        Returns:
            Created workflow
        """
        workflow = Workflow(
            name=name,
            definition=definition,
            dependencies=dependencies or {},
            parameters=parameters or [],
            description=description
        )
        
        self.session.add(workflow)
        self.session.commit()
        self.session.refresh(workflow)
        
        # Create initial version
        self._create_version(workflow, "Initial version")
        
        logger.info(f"Created workflow {workflow.id}: {name}")
        return workflow
    
    def get(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by ID.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Workflow or None if not found
        """
        statement = select(Workflow).where(Workflow.id == workflow_id)
        return self.session.exec(statement).first()
    
    def get_by_name(self, name: str) -> Optional[Workflow]:
        """Get workflow by name.
        
        Args:
            name: Workflow name
            
        Returns:
            Most recent workflow with this name or None
        """
        statement = (
            select(Workflow)
            .where(Workflow.name == name)
            .order_by(Workflow.version.desc())
        )
        return self.session.exec(statement).first()
    
    def list(
        self, 
        limit: int = 10, 
        offset: int = 0,
        name_filter: Optional[str] = None
    ) -> List[Workflow]:
        """List workflows with pagination.
        
        Args:
            limit: Maximum number of results
            offset: Skip this many results
            name_filter: Optional name filter (substring match)
            
        Returns:
            List of workflows
        """
        statement = select(Workflow).order_by(Workflow.updated_at.desc())
        
        if name_filter:
            statement = statement.where(
                Workflow.name.contains(name_filter)
            )
        
        statement = statement.offset(offset).limit(limit)
        return list(self.session.exec(statement))
    
    def update(
        self,
        workflow_id: str,
        definition: Optional[Dict[str, Any]] = None,
        dependencies: Optional[Dict[str, Any]] = None,
        parameters: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None,
        version_message: str = "Updated workflow"
    ) -> Optional[Workflow]:
        """Update an existing workflow.
        
        Args:
            workflow_id: Workflow ID to update
            definition: New workflow definition
            dependencies: New dependencies
            parameters: New parameters
            description: New description
            version_message: Version commit message
            
        Returns:
            Updated workflow or None if not found
        """
        workflow = self.get(workflow_id)
        if not workflow:
            return None
        
        # Update fields
        if definition is not None:
            workflow.definition = definition
        if dependencies is not None:
            workflow.dependencies = dependencies
        if parameters is not None:
            workflow.parameters = parameters
        if description is not None:
            workflow.description = description
        
        workflow.version += 1
        workflow.updated_at = datetime.utcnow()
        
        self.session.add(workflow)
        self.session.commit()
        self.session.refresh(workflow)
        
        # Create new version
        self._create_version(workflow, version_message)
        
        logger.info(f"Updated workflow {workflow_id} to version {workflow.version}")
        return workflow
    
    def delete(self, workflow_id: str) -> bool:
        """Delete a workflow and all related data.
        
        Args:
            workflow_id: Workflow ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        workflow = self.get(workflow_id)
        if not workflow:
            return False
        
        # Delete related records first (cascade would handle this with proper FK setup)
        for model in [WorkflowVersion, ContainerBuild, APIEndpoint, WorkflowExecution]:
            statement = select(model).where(model.workflow_id == workflow_id)
            for record in self.session.exec(statement):
                self.session.delete(record)
        
        self.session.delete(workflow)
        self.session.commit()
        
        logger.info(f"Deleted workflow {workflow_id}")
        return True
    
    def _create_version(self, workflow: Workflow, message: str):
        """Create a workflow version record.
        
        Args:
            workflow: Workflow to version
            message: Version message
        """
        # Generate commit hash from workflow content
        content = json.dumps({
            "definition": workflow.definition,
            "dependencies": workflow.dependencies,
            "parameters": workflow.parameters
        }, sort_keys=True)
        commit_hash = hashlib.sha1(content.encode()).hexdigest()
        
        # Get parent hash if exists
        parent_statement = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow.id)
            .order_by(WorkflowVersion.version.desc())
        )
        parent = self.session.exec(parent_statement).first()
        
        version = WorkflowVersion(
            workflow_id=workflow.id,
            version=workflow.version,
            commit_hash=commit_hash,
            parent_hash=parent.commit_hash if parent else None,
            message=message,
            changes={}  # Could implement diff logic here
        )
        
        self.session.add(version)
        self.session.commit()


class BuildRepository:
    """Repository for container build operations."""
    
    def __init__(self, session: Session):
        """Initialize with database session.
        
        Args:
            session: SQLModel database session
        """
        self.session = session
    
    def create_build(
        self,
        workflow_id: str,
        image_name: str,
        tag: str = "latest",
        dockerfile: Optional[str] = None
    ) -> ContainerBuild:
        """Create a new build record.
        
        Args:
            workflow_id: Associated workflow ID
            image_name: Docker image name
            tag: Image tag
            dockerfile: Generated Dockerfile content
            
        Returns:
            Created build record
        """
        build = ContainerBuild(
            workflow_id=workflow_id,
            image_name=image_name,
            tag=tag,
            dockerfile=dockerfile,
            build_status="pending"
        )
        
        self.session.add(build)
        self.session.commit()
        self.session.refresh(build)
        
        logger.info(f"Created build {build.id} for workflow {workflow_id}")
        return build
    
    def update_build_status(
        self,
        build_id: str,
        status: str,
        logs: Optional[str] = None,
        image_size: Optional[int] = None,
        error: Optional[str] = None
    ) -> Optional[ContainerBuild]:
        """Update build status and metadata.
        
        Args:
            build_id: Build ID
            status: New status
            logs: Build logs
            image_size: Final image size
            error: Error message if failed
            
        Returns:
            Updated build or None if not found
        """
        statement = select(ContainerBuild).where(ContainerBuild.id == build_id)
        build = self.session.exec(statement).first()
        
        if not build:
            return None
        
        build.build_status = status
        
        if logs:
            build.build_logs = logs
        if image_size:
            build.image_size = image_size
        if error:
            build.build_logs = (build.build_logs or "") + f"\nERROR: {error}"
        
        if status in ["success", "failed"]:
            build.completed_at = datetime.utcnow()
            if build.created_at:
                duration = (build.completed_at - build.created_at).total_seconds()
                build.build_duration = duration
        
        self.session.add(build)
        self.session.commit()
        self.session.refresh(build)
        
        logger.info(f"Updated build {build_id} status to {status}")
        return build
    
    def get_build_history(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 10
    ) -> List[ContainerBuild]:
        """Get build history.
        
        Args:
            workflow_id: Filter by workflow ID
            limit: Maximum results
            
        Returns:
            List of builds
        """
        statement = select(ContainerBuild).order_by(ContainerBuild.created_at.desc())
        
        if workflow_id:
            statement = statement.where(ContainerBuild.workflow_id == workflow_id)
        
        statement = statement.limit(limit)
        return list(self.session.exec(statement))
    
    def get_latest_successful_build(
        self,
        workflow_id: str
    ) -> Optional[ContainerBuild]:
        """Get the most recent successful build for a workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Latest successful build or None
        """
        statement = (
            select(ContainerBuild)
            .where(
                ContainerBuild.workflow_id == workflow_id,
                ContainerBuild.build_status == "success"
            )
            .order_by(ContainerBuild.completed_at.desc())
        )
        return self.session.exec(statement).first()


class CustomNodeRepository:
    """Repository for custom node registry."""
    
    def __init__(self, session: Session):
        """Initialize with database session.
        
        Args:
            session: SQLModel database session
        """
        self.session = session
    
    def register_node(
        self,
        repository_url: str,
        commit_hash: str,
        node_types: List[str],
        python_dependencies: Optional[List[str]] = None
    ) -> CustomNode:
        """Register a custom node.
        
        Args:
            repository_url: Git repository URL
            commit_hash: Git commit hash
            node_types: List of node class types
            python_dependencies: Required Python packages
            
        Returns:
            Registered custom node
        """
        # Check if already exists
        statement = select(CustomNode).where(
            CustomNode.repository_url == repository_url,
            CustomNode.commit_hash == commit_hash
        )
        existing = self.session.exec(statement).first()
        
        if existing:
            # Update node types if needed
            existing.node_types = list(set(existing.node_types + node_types))
            existing.updated_at = datetime.utcnow()
            self.session.add(existing)
            self.session.commit()
            return existing
        
        node = CustomNode(
            repository_url=repository_url,
            commit_hash=commit_hash,
            node_types=node_types,
            python_dependencies=python_dependencies or []
        )
        
        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        
        logger.info(f"Registered custom node from {repository_url}")
        return node
    
    def find_by_node_type(self, node_type: str) -> Optional[CustomNode]:
        """Find custom node by node type.
        
        Args:
            node_type: Node class type to find
            
        Returns:
            Custom node or None
        """
        # This requires JSON contains query
        statement = select(CustomNode)
        nodes = self.session.exec(statement).all()
        
        for node in nodes:
            if node_type in node.node_types:
                return node
        
        return None
    
    def list_nodes(
        self,
        verified_only: bool = False,
        limit: int = 50
    ) -> List[CustomNode]:
        """List registered custom nodes.
        
        Args:
            verified_only: Only return verified nodes
            limit: Maximum results
            
        Returns:
            List of custom nodes
        """
        statement = select(CustomNode).order_by(CustomNode.updated_at.desc())
        
        if verified_only:
            statement = statement.where(CustomNode.verified == True)
        
        statement = statement.limit(limit)
        return list(self.session.exec(statement))
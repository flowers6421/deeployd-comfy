"""Repository pattern for database operations."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, func, select

from src.db.models import (
    APIEndpoint,
    BuildLog,
    ContainerBuild,
    CustomNode,
    Workflow,
    WorkflowExecution,
    WorkflowVersion,
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
        definition: dict[str, Any],
        dependencies: dict[str, Any] | None = None,
        parameters: list[dict[str, Any]] | None = None,
        description: str | None = None,
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
            description=description,
        )

        self.session.add(workflow)
        self.session.commit()
        self.session.refresh(workflow)

        # Create initial version
        self._create_version(workflow, "Initial version")

        logger.info(f"Created workflow {workflow.id}: {name}")
        return workflow

    def get(self, workflow_id: str) -> Workflow | None:
        """Get workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow or None if not found
        """
        statement = select(Workflow).where(Workflow.id == workflow_id)
        return self.session.exec(statement).first()

    def get_by_name(self, name: str) -> Workflow | None:
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
        self, limit: int = 10, offset: int = 0, name_filter: str | None = None
    ) -> list[Workflow]:
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
            statement = statement.where(Workflow.name.contains(name_filter))

        statement = statement.offset(offset).limit(limit)
        return list(self.session.exec(statement))

    def update(
        self,
        workflow_id: str,
        definition: dict[str, Any] | None = None,
        dependencies: dict[str, Any] | None = None,
        parameters: list[dict[str, Any]] | None = None,
        description: str | None = None,
        version_message: str = "Updated workflow",
    ) -> Workflow | None:
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
        content = json.dumps(
            {
                "definition": workflow.definition,
                "dependencies": workflow.dependencies,
                "parameters": workflow.parameters,
            },
            sort_keys=True,
        )
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
            changes={},  # Could implement diff logic here
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
        dockerfile: str | None = None,
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
            build_status="pending",
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
        logs: str | None = None,
        image_size: int | None = None,
        error: str | None = None,
    ) -> ContainerBuild | None:
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
        self._ensure_container_builds_schema()
        statement = select(ContainerBuild).where(ContainerBuild.id == build_id)
        build = self.session.exec(statement).first()

        if not build:
            return None

        build.build_status = status

        if logs is not None and logs.strip():
            try:
                # Also store as streaming row
                self.append_build_log(build_id, logs)
            except Exception:
                pass
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

    def append_build_log(self, build_id: str, line: str) -> int | None:
        """Append a log line as BuildLog and keep legacy field for short preview."""
        # maintain a short preview in ContainerBuild.build_logs (last ~2KB)
        statement = select(ContainerBuild).where(ContainerBuild.id == build_id)
        build = self.session.exec(statement).first()
        if not build:
            return None
        preview_prev = build.build_logs or ""
        preview = preview_prev + ("\n" if preview_prev else "") + line
        # truncate preview to last 2000 chars
        if len(preview) > 2000:
            preview = preview[-2000:]
        build.build_logs = preview
        self.session.add(build)

        # Append to BuildLog table
        seq_stmt = select(func.max(BuildLog.seq)).where(BuildLog.build_id == build_id)
        current = self.session.exec(seq_stmt).first() or 0
        next_seq = (current or 0) + 1
        row = BuildLog(build_id=build_id, seq=next_seq, line=line)
        try:
            self.session.add(row)
            self.session.commit()
        except Exception:
            # Rollback and continue if log table isn't available or schema mismatch
            self.session.rollback()
            return None
        return next_seq

    def get_build_logs(
        self, build_id: str, since: int | None = None, limit: int = 200
    ) -> list[BuildLog]:
        stmt = select(BuildLog).where(BuildLog.build_id == build_id)
        if since is not None:
            stmt = stmt.where(BuildLog.seq > since)
        stmt = stmt.order_by(BuildLog.seq.asc()).limit(limit)
        return list(self.session.exec(stmt))

    def cleanup_incomplete(self) -> int:
        """Mark all non-terminal builds as failed and return affected count."""
        self._ensure_container_builds_schema()
        statement = select(ContainerBuild)
        builds = list(self.session.exec(statement))
        count = 0
        for b in builds:
            if b.build_status not in ("success", "failed"):
                b.build_status = "failed"
                b.build_logs = (
                    b.build_logs or ""
                ) + "\nCANCELLED: Build marked as failed by cleanup"
                b.completed_at = datetime.utcnow()
                self.session.add(b)
                count += 1
        if count:
            self.session.commit()
        return count

    def get_build_history(
        self, workflow_id: str | None = None, limit: int = 10
    ) -> list[ContainerBuild]:
        """Get build history.

        Args:
            workflow_id: Filter by workflow ID
            limit: Maximum results

        Returns:
            List of builds
        """
        self._ensure_container_builds_schema()
        statement = select(ContainerBuild).order_by(ContainerBuild.created_at.desc())

        if workflow_id:
            statement = statement.where(ContainerBuild.workflow_id == workflow_id)

        statement = statement.limit(limit)
        return list(self.session.exec(statement))

    def get_by_id(self, build_id: str) -> ContainerBuild | None:
        self._ensure_container_builds_schema()
        stmt = select(ContainerBuild).where(ContainerBuild.id == build_id)
        return self.session.exec(stmt).first()

    def set_resolved_nodes(self, build_id: str, nodes: list[dict[str, Any]]):
        self._ensure_container_builds_schema()
        stmt = select(ContainerBuild).where(ContainerBuild.id == build_id)
        build = self.session.exec(stmt).first()
        if not build:
            return
        build.resolved_nodes = nodes
        self.session.add(build)
        self.session.commit()

    def _ensure_container_builds_schema(self) -> None:
        """Ensure optional columns exist for container_builds table (SQLite)."""
        try:
            cols = [
                row[1]
                for row in self.session.exec(
                    text("PRAGMA table_info(container_builds)")
                ).all()
            ]
            if "resolved_nodes" not in cols:
                self.session.exec(
                    text(
                        "ALTER TABLE container_builds ADD COLUMN resolved_nodes JSON DEFAULT '[]'"
                    )
                )
                self.session.commit()
        except OperationalError:
            # Ignore if PRAGMA not supported or table missing (will be created elsewhere)
            self.session.rollback()
        except Exception:
            # Be defensive; don't block normal operations
            self.session.rollback()

    def get_latest_successful_build(self, workflow_id: str) -> ContainerBuild | None:
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
                ContainerBuild.build_status == "success",
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
        node_types: list[str],
        python_dependencies: list[str] | None = None,
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
            CustomNode.commit_hash == commit_hash,
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
            python_dependencies=python_dependencies or [],
        )

        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)

        logger.info(f"Registered custom node from {repository_url}")
        return node

    def find_by_node_type(self, node_type: str) -> CustomNode | None:
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
        self, verified_only: bool = False, limit: int = 50
    ) -> list[CustomNode]:
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


class ExecutionRepository:
    """Repository for workflow executions."""

    def __init__(self, session: Session):
        self.session = session

    def list(self, limit: int = 50) -> list[WorkflowExecution]:
        stmt = (
            select(WorkflowExecution)
            .order_by(WorkflowExecution.started_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(stmt))

    def get(self, execution_id: str) -> WorkflowExecution | None:
        stmt = select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        return self.session.exec(stmt).first()

    def create(
        self,
        workflow_id: str,
        prompt_id: str,
        status: str = "pending",
        input_parameters: dict[str, Any] | None = None,
    ) -> WorkflowExecution:
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            prompt_id=prompt_id,
            status=status,
            input_parameters=input_parameters or {},
        )
        self.session.add(execution)
        self.session.commit()
        self.session.refresh(execution)
        return execution

    def cancel_all(self) -> int:
        """Cancel all executions that are not completed/failed."""
        stmt = select(WorkflowExecution)
        exes = list(self.session.exec(stmt))
        count = 0
        for e in exes:
            if e.status not in ("completed", "failed", "cancelled"):
                e.status = "cancelled"
                e.completed_at = datetime.utcnow()
                self.session.add(e)
                count += 1
        if count:
            self.session.commit()
        return count

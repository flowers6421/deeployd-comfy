"""Custom node installer for ComfyUI workflows."""

import ast
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packaging import version

from src.workflows.constants import BUILTIN_NODES


class NodeInstallationError(Exception):
    """Custom exception for node installation failures."""

    pass


@dataclass
class NodeMetadata:
    """Metadata for a custom node."""

    name: str
    repository: str
    commit_hash: str | None = None
    python_dependencies: list[str] = field(default_factory=list)
    system_dependencies: list[str] = field(default_factory=list)
    models_required: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    min_comfyui_version: str | None = None
    max_comfyui_version: str | None = None


class CustomNodeInstaller:
    """Handles installation of custom nodes for ComfyUI workflows."""

    def __init__(self, cache_dir: str | None = None):
        """Initialize custom node installer.

        Args:
            cache_dir: Optional directory for caching downloaded nodes
        """
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._dependency_map = {
            "PIL": "pillow",
            "cv2": "opencv-python",
            "sklearn": "scikit-learn",
            "yaml": "pyyaml",
        }

    def extract_custom_nodes(
        self, workflow_nodes: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract custom nodes from workflow.

        Args:
            workflow_nodes: Dictionary of workflow nodes

        Returns:
            List of custom node information
        """
        custom_nodes = []

        for node_id, node_data in workflow_nodes.items():
            class_type = node_data.get("class_type", "")

            # Check if it's a custom node
            if class_type and class_type not in BUILTIN_NODES:
                node_info = {
                    "class_type": class_type,
                    "node_id": node_id,
                }

                # Extract metadata if available
                if "_meta" in node_data:
                    meta = node_data["_meta"]
                    if "repository" in meta:
                        node_info["repository"] = meta["repository"]
                    if "commit" in meta:
                        node_info["commit"] = meta["commit"]

                custom_nodes.append(node_info)

        return custom_nodes

    def generate_install_commands(self, node_metadata: NodeMetadata) -> list[str]:
        """Generate installation commands for a custom node.

        Args:
            node_metadata: Metadata for the custom node

        Returns:
            List of installation commands
        """
        commands = []

        # Clone repository
        commands.append(
            f"RUN git clone {node_metadata.repository} "
            f"/app/custom_nodes/{node_metadata.name}"
        )

        # Checkout specific commit if provided
        if node_metadata.commit_hash:
            commands.append(
                f"RUN cd /app/custom_nodes/{node_metadata.name} && "
                f"git checkout {node_metadata.commit_hash}"
            )

        # Install Python dependencies
        if node_metadata.python_dependencies:
            deps = " ".join(node_metadata.python_dependencies)
            commands.append(f"RUN pip install --no-cache-dir {deps}")

        # Install system dependencies
        if node_metadata.system_dependencies:
            system_deps = " ".join(node_metadata.system_dependencies)
            commands.append(
                f"RUN apt-get update && apt-get install -y {system_deps} && "
                f"apt-get clean && rm -rf /var/lib/apt/lists/*"
            )

        return commands

    def generate_requirements_txt(self, nodes: list[NodeMetadata]) -> str:
        """Generate requirements.txt for custom nodes.

        Args:
            nodes: List of custom node metadata

        Returns:
            Requirements.txt content
        """
        requirements = set()

        for node in nodes:
            for dep in node.python_dependencies:
                requirements.add(dep)

        return "\n".join(sorted(requirements))

    def detect_dependencies_from_code(self, filepath: str) -> set[str]:
        """Detect Python dependencies from source code.

        Args:
            filepath: Path to Python file

        Returns:
            Set of detected dependencies
        """
        dependencies = set()

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Parse AST to find imports
        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                        # Map to proper package name
                        package = self._dependency_map.get(module, module)
                        # Skip standard library modules
                        if not self._is_stdlib(module):
                            dependencies.add(package)

                elif isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module.split(".")[0]
                    package = self._dependency_map.get(module, module)
                    if not self._is_stdlib(module):
                        dependencies.add(package)

        except SyntaxError:
            # If parsing fails, try regex fallback
            import_pattern = r"(?:from|import)\s+(\w+)"
            for match in re.finditer(import_pattern, content):
                module = match.group(1)
                package = self._dependency_map.get(module, module)
                if not self._is_stdlib(module):
                    dependencies.add(package)

        return dependencies

    def validate_repository_url(self, url: str) -> bool:
        """Validate repository URL.

        Args:
            url: Repository URL

        Returns:
            True if valid GitHub URL
        """
        github_patterns = [
            r"^https://github\.com/[\w-]+/[\w-]+(?:\.git)?$",
            r"^git@github\.com:[\w-]+/[\w-]+(?:\.git)?$",
        ]

        return any(re.match(pattern, url) for pattern in github_patterns)

    def generate_dockerfile_section(self, nodes: list[NodeMetadata]) -> str:
        """Generate Dockerfile section for custom nodes.

        Args:
            nodes: List of custom node metadata

        Returns:
            Dockerfile section as string
        """
        lines = ["# Install custom nodes"]
        lines.append("WORKDIR /app/custom_nodes")
        lines.append("")

        for node in nodes:
            lines.append(f"# Install {node.name}")
            lines.append(f"RUN git clone {node.repository} {node.name}")

            if node.commit_hash:
                lines.append(f"RUN cd {node.name} && git checkout {node.commit_hash}")

            if node.python_dependencies:
                deps = " ".join(node.python_dependencies)
                lines.append(f"RUN pip install --no-cache-dir {deps}")

            lines.append("")

        lines.append("WORKDIR /app")
        return "\n".join(lines)

    def resolve_dependency_order(self, nodes: list[NodeMetadata]) -> list[NodeMetadata]:
        """Resolve installation order based on dependencies.

        Args:
            nodes: List of custom nodes

        Returns:
            Ordered list with dependencies first
        """
        # Build dependency graph
        node_map = {node.name: node for node in nodes}
        visited = set()
        result = []

        def visit(node_name: str):
            if node_name in visited:
                return

            visited.add(node_name)
            node = node_map.get(node_name)

            if not node:
                return

            # Visit dependencies first
            for dep in node.depends_on:
                if dep in node_map:
                    visit(dep)

            result.append(node)

        # Visit all nodes
        for node in nodes:
            visit(node.name)

        return result

    def set_cache_directory(self, cache_dir: str):
        """Set cache directory for downloaded nodes.

        Args:
            cache_dir: Path to cache directory
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_and_cache_node(self, node_metadata: NodeMetadata):
        """Download and cache a custom node.

        Args:
            node_metadata: Node metadata
        """
        if not self.cache_dir:
            raise ValueError("Cache directory not set")

        # Create cache key
        cache_key = f"{node_metadata.name}_{node_metadata.commit_hash or 'latest'}"
        cache_path = self.cache_dir / cache_key

        # Check if already cached
        if cache_path.exists():
            return

        # Download node
        cmd = ["git", "clone", node_metadata.repository, str(cache_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise NodeInstallationError(f"Failed to clone repository: {result.stderr}")

        # Checkout specific commit if provided
        if node_metadata.commit_hash:
            cmd = ["git", "checkout", node_metadata.commit_hash]
            result = subprocess.run(
                cmd, cwd=str(cache_path), capture_output=True, text=True
            )

            if result.returncode != 0:
                raise NodeInstallationError(
                    f"Failed to checkout commit: {result.stderr}"
                )

    def install_node(self, node_metadata: NodeMetadata):
        """Install a custom node.

        Args:
            node_metadata: Node metadata

        Raises:
            NodeInstallationError: If installation fails
        """
        if not self.validate_repository_url(node_metadata.repository):
            raise NodeInstallationError(
                f"Invalid repository URL: {node_metadata.repository}"
            )

        # Generate and execute install commands
        commands = self.generate_install_commands(node_metadata)

        for cmd in commands:
            # This would execute the commands in a real implementation
            # For testing, we just validate the command format
            if not cmd.startswith("RUN "):
                raise NodeInstallationError(f"Invalid command format: {cmd}")

    def verify_installation(self, node_name: str, custom_nodes_dir: str) -> bool:
        """Verify if a custom node is properly installed.

        Args:
            node_name: Name of the node
            custom_nodes_dir: Path to custom nodes directory

        Returns:
            True if node is installed
        """
        node_path = Path(custom_nodes_dir) / node_name

        if not node_path.exists():
            return False

        # Check for basic module structure
        if not (node_path / "__init__.py").exists():
            return False

        # Check for at least one Python file
        python_files = list(node_path.glob("*.py"))
        return len(python_files) > 0

    def generate_batch_install_commands(self, nodes: list[NodeMetadata]) -> list[str]:
        """Generate batch installation commands for multiple nodes.

        Args:
            nodes: List of custom nodes

        Returns:
            Optimized list of commands
        """
        commands = []

        # Clone all repositories
        for node in nodes:
            commands.append(
                f"RUN git clone {node.repository} " f"/app/custom_nodes/{node.name}"
            )

        # Collect all Python dependencies
        all_deps = set()
        for node in nodes:
            all_deps.update(node.python_dependencies)

        # Install all dependencies in one command
        if all_deps:
            deps_str = " ".join(sorted(all_deps))
            commands.append(f"RUN pip install --no-cache-dir {deps_str}")

        return commands

    def extract_node_mappings(self, filepath: str) -> dict[str, Any]:
        """Extract node class mappings from custom node file.

        Args:
            filepath: Path to node mappings file

        Returns:
            Dictionary with class and display name mappings
        """
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        mappings = {
            "class_mappings": {},
            "display_names": {},
        }

        # Extract NODE_CLASS_MAPPINGS
        class_pattern = r"NODE_CLASS_MAPPINGS\s*=\s*{([^}]+)}"
        class_match = re.search(class_pattern, content, re.DOTALL)

        if class_match:
            entries = class_match.group(1)
            entry_pattern = r'"([^"]+)":\s*(\w+)'
            for match in re.finditer(entry_pattern, entries):
                mappings["class_mappings"][match.group(1)] = match.group(2)

        # Extract NODE_DISPLAY_NAME_MAPPINGS
        display_pattern = r"NODE_DISPLAY_NAME_MAPPINGS\s*=\s*{([^}]+)}"
        display_match = re.search(display_pattern, content, re.DOTALL)

        if display_match:
            entries = display_match.group(1)
            entry_pattern = r'"([^"]+)":\s*"([^"]+)"'
            for match in re.finditer(entry_pattern, entries):
                mappings["display_names"][match.group(1)] = match.group(2)

        return mappings

    def generate_custom_nodes_init(self, nodes: list[NodeMetadata]) -> str:
        """Generate __init__.py for custom nodes directory.

        Args:
            nodes: List of custom nodes

        Returns:
            Content for __init__.py file
        """
        lines = [
            '"""Custom nodes initialization."""',
            "",
        ]

        # Import statements
        for node in nodes:
            lines.append(f"from .{node.name} import *")

        lines.append("")
        lines.append("__all__ = [")

        for node in nodes:
            lines.append(f'    "{node.name}",')

        lines.append("]")

        return "\n".join(lines)

    def check_compatibility(self, node: NodeMetadata, comfyui_version: str) -> bool:
        """Check if node is compatible with ComfyUI version.

        Args:
            node: Node metadata
            comfyui_version: ComfyUI version string

        Returns:
            True if compatible
        """
        current_version = version.parse(comfyui_version)

        if node.min_comfyui_version:
            min_version = version.parse(node.min_comfyui_version)
            if current_version < min_version:
                return False

        if node.max_comfyui_version:
            max_version = version.parse(node.max_comfyui_version)
            if current_version > max_version:
                return False

        return True

    def _is_stdlib(self, module: str) -> bool:
        """Check if module is part of Python standard library.

        Args:
            module: Module name

        Returns:
            True if standard library module
        """
        stdlib_modules = {
            "os",
            "sys",
            "re",
            "json",
            "math",
            "random",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "pathlib",
            "typing",
            "subprocess",
            "threading",
            "multiprocessing",
            "asyncio",
            "urllib",
            "http",
            "socket",
            "time",
            "logging",
            "argparse",
            "configparser",
            "sqlite3",
            "csv",
            "xml",
            "html",
            "base64",
            "hashlib",
            "hmac",
            "uuid",
            "tempfile",
            "shutil",
            "glob",
            "ast",
            "inspect",
            "importlib",
            "copy",
            "pickle",
            "io",
        }
        return module in stdlib_modules

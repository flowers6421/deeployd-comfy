"""Node resolver using comfyui-json library for better custom node detection."""

import json
import logging
import subprocess
import typing as t
from pathlib import Path
from typing import Any

from src.containers.custom_node_installer import NodeMetadata

logger = logging.getLogger(__name__)


class ComfyUIJsonResolver:
    """Resolver for custom nodes using comfyui-json library."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize the resolver.

        Args:
            cache_dir: Optional directory for caching results
        """
        self.cache_dir = cache_dir
        self.node_bridge_path = Path(__file__).parent / "node_bridge.js"
        self._resolved_cache: dict[str, dict[str, Any]] = {}
        # Deprecated: prefer upstream comfyui-json + Manager maps
        self._known_mappings: dict[str, dict[str, Any]] = {}

        # Check if Node.js is available
        self._check_nodejs()

    def _check_nodejs(self) -> None:
        """Check if Node.js is available."""
        try:
            result = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, check=True
            )
            logger.debug(f"Node.js version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError(
                "Node.js is required for comfyui-json resolver. "
                "Please install Node.js: https://nodejs.org/"
            ) from e

        # Ensure we can load vendored comfyui-json via the node bridge
        try:
            bridge_dir = str(self.node_bridge_path.parent)
            vendored_loader = (
                "const fs=require('fs'); const p=require('path'); "
                "const mod=p.join(process.cwd(),'vendor','comfyui-json','dist','index.js'); "
                "if(!fs.existsSync(mod)){throw new Error('vendored comfyui-json not found at '+mod);} "
                "require(mod); console.log('ok')"
            )
            subprocess.run(
                ["node", "-e", vendored_loader],
                capture_output=True,
                text=True,
                check=True,
                cwd=bridge_dir,
            )
        except subprocess.CalledProcessError as e:
            msg = e.stderr.strip() or e.stdout.strip() or str(e)
            raise RuntimeError(
                "Vendored comfyui-json not found. Expected at "
                "src/workflows/vendor/comfyui-json/dist/index.js. "
                "Please vendor the library (copy dist files) into that path. "
                f"Details: {msg}"
            ) from e

    # Note: intentionally not loading local known mappings. We rely on
    # comfyui-json (which uses ComfyUI-Manager maps) for authoritative
    # resolution to avoid drift.
    def _load_known_mappings(self) -> dict[str, dict[str, Any]]:  # pragma: no cover
        return {}

    def resolve_workflow(
        self, workflow_path: Path, pull_latest_hash: bool = True
    ) -> dict[str, Any]:
        """Resolve all dependencies from a workflow file.

        Args:
            workflow_path: Path to the workflow JSON file
            pull_latest_hash: Whether to pull latest commit hash if missing

        Returns:
            Dictionary containing resolved custom nodes and dependencies
        """
        try:
            cmd = [
                "node",
                str(self.node_bridge_path),
                "resolve-workflow",
                str(workflow_path),
                str(pull_latest_hash).lower(),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self.node_bridge_path.parent),
            )

            return t.cast(dict[str, Any], json.loads(result.stdout))

        except subprocess.CalledProcessError as e:
            logger.error(f"Node.js bridge error: {e.stderr}")
            # Try to parse error output
            try:
                error_data = json.loads(e.stdout) if e.stdout else {}
                if not error_data.get("success", True):
                    logger.error(
                        f"Resolution failed: {error_data.get('error', 'Unknown error')}"
                    )
            except json.JSONDecodeError:
                pass
            raise RuntimeError(f"Failed to resolve workflow: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse resolver output: {e}")
            raise RuntimeError(f"Invalid JSON from resolver: {e}") from e

    def resolve_node_classes(
        self, node_classes: list[str]
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """Resolve a list of custom node class names to their repositories.

        Args:
            node_classes: List of node class names to resolve

        Returns:
            Tuple of (resolved nodes dict, unresolved node list)
        """
        # Check cache first
        uncached_nodes = []
        resolved = {}

        for node_class in node_classes:
            # Cache-only fast path; otherwise defer to comfyui-json resolution
            if node_class in self._resolved_cache:
                resolved[node_class] = self._resolved_cache[node_class]
            else:
                uncached_nodes.append(node_class)

        if not uncached_nodes:
            return resolved, []

        try:
            cmd = [
                "node",
                str(self.node_bridge_path),
                "resolve-nodes",
                ",".join(uncached_nodes),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self.node_bridge_path.parent),
            )

            data = json.loads(result.stdout)

            if data.get("success"):
                # Update cache and results
                for node_class, info in data.get("resolved", {}).items():
                    self._resolved_cache[node_class] = info
                    resolved[node_class] = info

                return resolved, data.get("unresolved", [])
            else:
                logger.error(f"Resolution failed: {data.get('error', 'Unknown error')}")
                return resolved, uncached_nodes

        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error(f"Failed to resolve node classes: {e}")
            return resolved, uncached_nodes

    def convert_to_node_metadata(
        self, resolved_nodes: dict[str, dict[str, Any]]
    ) -> list[NodeMetadata]:
        """Convert resolved node data to NodeMetadata objects.

        Args:
            resolved_nodes: Dictionary of resolved node information

        Returns:
            List of NodeMetadata objects
        """
        metadata_list = []

        for url, node_info in resolved_nodes.items():
            # Extract node name from URL or use provided name
            if "name" in node_info and node_info["name"]:
                name = node_info["name"]
            else:
                # Extract from URL (e.g., github.com/user/repo -> repo)
                name = url.rstrip("/").split("/")[-1].replace(".git", "")

            # Create safe filename
            safe_name = (
                name.replace(" ", "_")
                .replace("|", "_")
                .replace("(", "")
                .replace(")", "")
            )

            metadata = NodeMetadata(
                name=safe_name,
                repository=url,
                commit_hash=node_info.get("hash"),
                python_dependencies=node_info.get("pip", []),
            )

            metadata_list.append(metadata)

        return metadata_list

    def resolve_custom_nodes_from_workflow(
        self, workflow_data: dict[str, Any], manual_repos: dict[str, str] | None = None
    ) -> tuple[list[NodeMetadata], list[str]]:
        """Resolve custom nodes from workflow data.

        Args:
            workflow_data: The workflow dictionary
            manual_repos: Optional manual mappings of node_class -> repository_url

        Returns:
            Tuple of (resolved NodeMetadata list, unresolved node names)
        """
        # Extract custom node classes from workflow
        custom_node_classes = set()

        # Check if it's UI format or API format
        if "nodes" in workflow_data and isinstance(workflow_data["nodes"], list):
            # UI format
            for node in workflow_data["nodes"]:
                node_type = node.get("type", "")
                if node_type and not self._is_builtin_node(node_type):
                    custom_node_classes.add(node_type)
        else:
            # API format
            for _node_id, node_data in workflow_data.items():
                if isinstance(node_data, dict) and "class_type" in node_data:
                    class_type = node_data["class_type"]
                    if not self._is_builtin_node(class_type):
                        custom_node_classes.add(class_type)

        if not custom_node_classes:
            return [], []

        # Apply manual repos first
        manually_resolved = {}
        remaining_nodes = []

        for node_class in custom_node_classes:
            if manual_repos and node_class in manual_repos:
                manually_resolved[node_class] = {
                    "url": manual_repos[node_class],
                    "name": node_class,
                }
            else:
                remaining_nodes.append(node_class)

        # Resolve remaining nodes
        resolved, unresolved = self.resolve_node_classes(remaining_nodes)

        # Combine results
        all_resolved = {**manually_resolved}
        for _node_class, info in resolved.items():
            if info.get("url"):
                all_resolved[info["url"]] = info

        # Convert to NodeMetadata
        metadata_list = self.convert_to_node_metadata(all_resolved)

        return metadata_list, unresolved

    def _is_builtin_node(self, node_type: str) -> bool:
        """Check if a node type is a builtin ComfyUI node.

        Args:
            node_type: The node type/class name

        Returns:
            True if builtin, False otherwise
        """
        from src.workflows.constants import BUILTIN_NODES

        return node_type in BUILTIN_NODES

    def get_comprehensive_resolution(self, workflow_path: Path) -> dict[str, Any]:
        """Get comprehensive resolution data for a workflow.

        This method uses the comfyui-json library to get all dependency
        information including models, custom nodes, and file references.

        Args:
            workflow_path: Path to the workflow file

        Returns:
            Complete resolution data from comfyui-json
        """
        resolution = self.resolve_workflow(workflow_path)

        if not resolution.get("success"):
            raise RuntimeError(f"Failed to resolve workflow: {resolution.get('error')}")

        # Process and enrich the data
        result = {
            "format": resolution.get("format", "unknown"),
            "comfyui_hash": resolution.get("comfyui_hash"),
            "custom_nodes": {},
            "missing_nodes": resolution.get("missing_nodes", []),
            "conflicting_nodes": resolution.get("conflicting_nodes", {}),
            "models": resolution.get("models", {}),
            "files": resolution.get("files", {}),
        }

        # Process custom nodes
        for url, node_data in resolution.get("custom_nodes", {}).items():
            result["custom_nodes"][url] = {
                "url": url,
                "name": node_data.get("name", url.split("/")[-1]),
                "hash": node_data.get("hash"),
                "pip": node_data.get("pip", []),
                "files": node_data.get("files", []),
                "install_type": node_data.get("install_type", "git-clone"),
                "warning": node_data.get("warning"),
            }

        # Augment with injected extensions inferred from the workflow itself
        try:
            with open(workflow_path, encoding="utf-8") as f:
                wf_dict = json.load(f)
            injected = self._infer_injected_extensions(wf_dict)
            for url, meta in injected.items():
                if url not in result["custom_nodes"]:
                    result["custom_nodes"][url] = meta
        except Exception:
            pass

        return result

    def _infer_injected_extensions(
        self, workflow: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Infer extension repos that inject behavior into builtin nodes.

        Currently detects nonstandard KSampler/KSamplerAdvanced "scheduler" values
        and maps them to known repositories that provide those options.
        """
        # Core scheduler values (Comfy core). If a workflow uses a scheduler outside this set,
        # a third-party extension is likely required.
        core_schedulers = {
            "simple",
            "sgm_uniform",
            "karras",
            "exponential",
            "ddim_uniform",
            "beta",
            "normal",
            "linear_quadratic",
            "kl_optimal",
        }

        # Minimal curated mapping for injected scheduler tokens -> repo
        injected_map = {
            # RES4LYF injects additional beta schedule variants, including beta57
            "beta57": {
                "url": "https://github.com/ClownsharkBatwing/RES4LYF",
                "name": "RES4LYF",
            },
        }

        def iter_nodes_api(api_workflow: dict[str, Any]) -> t.Iterator[dict[str, Any]]:
            for k, v in api_workflow.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, dict) and "class_type" in v:
                    yield v

        # Convert UI->API if needed by inspecting keys
        if "nodes" in workflow and isinstance(workflow["nodes"], list):
            try:
                from src.workflows.converter import WorkflowConverter

                wf_api = WorkflowConverter().convert(workflow)
            except Exception:
                wf_api = {}
        else:
            wf_api = workflow

        required: dict[str, dict[str, Any]] = {}
        for node in iter_nodes_api(wf_api):
            ct = str(node.get("class_type", ""))
            if ct not in {"KSampler", "KSamplerAdvanced"}:
                continue
            inputs = node.get("inputs", {}) or {}
            sched = inputs.get("scheduler")
            if (
                isinstance(sched, str)
                and sched
                and sched not in core_schedulers
                and sched in injected_map
            ):
                info = injected_map[sched]
                required[info["url"]] = {
                    "url": info["url"],
                    "name": info.get("name", info["url"].rsplit("/", 1)[-1]),
                    "hash": None,
                    "pip": [],
                    "files": [],
                    "install_type": "git-clone",
                    "warning": "Inferred from scheduler value",
                }
        return required

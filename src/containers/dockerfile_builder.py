"""Dockerfile builder for ComfyUI containers."""

from typing import Any


class DockerfileBuilder:
    """Builder for generating optimized Dockerfiles."""

    def __init__(self) -> None:
        """Initialize Dockerfile builder."""
        self.instructions: list[str] = []

    def create_basic(self, base_image: str, workdir: str = "/app") -> str:
        """Create basic Dockerfile.

        Args:
            base_image: Base Docker image
            workdir: Working directory

        Returns:
            Dockerfile content
        """
        dockerfile = [
            f"FROM {base_image}",
            "",
            "# Create non-root user",
            "RUN useradd -m -u 1000 -s /bin/bash comfyuser",
            "",
            f"WORKDIR {workdir}",
            "",
        ]
        return "\n".join(dockerfile)

    def create_multi_stage(
        self,
        base_image: str,
        runtime_image: str,
        builder_name: str = "builder",
        runtime_name: str = "runtime",
    ) -> str:
        """Create multi-stage Dockerfile.

        Args:
            base_image: Base image for builder stage
            runtime_image: Base image for runtime stage
            builder_name: Name of builder stage
            runtime_name: Name of runtime stage

        Returns:
            Dockerfile content
        """
        dockerfile = [
            "# Builder stage",
            f"FROM {base_image} AS {builder_name}",
            "WORKDIR /build",
            "",
            "# Runtime stage",
            f"FROM {runtime_image} AS {runtime_name}",
            "",
            "# Copy from builder",
            f"COPY --from={builder_name} /build /app",
            "WORKDIR /app",
            "",
        ]
        return "\n".join(dockerfile)

    def add_python_packages(self, packages: list[str]) -> list[str]:
        """Add Python package installation commands.

        Args:
            packages: List of Python packages

        Returns:
            List of RUN commands
        """
        if not packages:
            return []

        packages_str = " ".join(sorted(packages))
        return [f"RUN pip install --no-cache-dir {packages_str}"]

    def add_system_packages(self, packages: list[str]) -> list[str]:
        """Add system package installation commands.

        Args:
            packages: List of system packages

        Returns:
            List of RUN commands
        """
        if not packages:
            return []

        packages_str = " ".join(sorted(packages))
        return [
            "RUN apt-get update && \\",
            f"    apt-get install -y --no-install-recommends {packages_str} && \\",
            "    apt-get clean && \\",
            "    rm -rf /var/lib/apt/lists/*",
        ]

    def create_with_cuda(
        self,
        cuda_version: str = "11.8",
        cudnn_version: str = "8",
        ubuntu_version: str = "22.04",
    ) -> str:
        """Create Dockerfile with CUDA support.

        Args:
            cuda_version: CUDA version
            cudnn_version: cuDNN version
            ubuntu_version: Ubuntu version

        Returns:
            Dockerfile content
        """
        dockerfile = [
            f"FROM nvidia/cuda:{cuda_version}.0-cudnn{cudnn_version}-runtime-ubuntu{ubuntu_version}",
            "",
            "# Install Python",
            "RUN apt-get update && \\",
            "    apt-get install -y python3 python3-pip && \\",
            "    apt-get clean && \\",
            "    rm -rf /var/lib/apt/lists/*",
            "",
            "WORKDIR /app",
            "",
        ]
        return "\n".join(dockerfile)

    def add_custom_nodes(self, custom_nodes: list[dict[str, Any]]) -> list[str]:
        """Add custom node installation commands.

        Args:
            custom_nodes: List of custom node configurations

        Returns:
            List of RUN commands
        """
        commands = []

        for node in custom_nodes:
            repository = node.get("repository")
            class_type = node.get("class_type", "custom_node")
            commit = node.get("commit")
            python_deps = node.get("python_dependencies", [])

            if repository:
                # Clone repository
                clone_cmd = f"RUN git clone {repository} /app/custom_nodes/{class_type}"
                if commit:
                    clone_cmd += f" && \\\n    cd /app/custom_nodes/{class_type} && \\\n    git checkout {commit}"
                commands.append(clone_cmd)

                # Install Python dependencies
                if python_deps:
                    deps_str = " ".join(python_deps)
                    commands.append(f"RUN pip install --no-cache-dir {deps_str}")

        return commands

    def add_model_downloads(self, models: dict[str, list[str]]) -> list[str]:
        """Add model download commands.

        Args:
            models: Dictionary of model types and files

        Returns:
            List of RUN commands
        """
        commands = []

        for model_type, model_files in models.items():
            if model_files:
                for model_file in model_files:
                    # Use wget for downloading (placeholder URL)
                    commands.append(
                        f"# Download {model_type}: {model_file}\n"
                        f"RUN wget -O /app/models/{model_type}/{model_file} \\\n"
                        f"    https://models.example.com/{model_type}/{model_file}"
                    )

        return commands

    def optimize_layers(self, commands: list[str]) -> list[str]:
        """Optimize Dockerfile layers by combining commands.

        Args:
            commands: List of Docker commands

        Returns:
            Optimized list of commands
        """
        optimized = []
        current_group = []

        for cmd in commands:
            if cmd.startswith("RUN apt-get") or cmd.startswith("RUN pip install"):
                current_group.append(cmd.replace("RUN ", ""))
            else:
                # Flush current group
                if current_group:
                    if all("apt-get" in c for c in current_group):
                        combined = " && \\\n    ".join(current_group)
                        optimized.append(f"RUN {combined}")
                    elif all("pip install" in c for c in current_group):
                        # Combine pip installs
                        packages = []
                        for c in current_group:
                            parts = c.split("pip install")[-1].strip()
                            packages.extend(parts.split())
                        optimized.append(
                            f"RUN pip install --no-cache-dir {' '.join(packages)}"
                        )
                    else:
                        optimized.extend([f"RUN {c}" for c in current_group])
                    current_group = []
                optimized.append(cmd)

        # Flush remaining
        if current_group:
            combined = " && \\\n    ".join(current_group)
            optimized.append(f"RUN {combined}")

        return optimized

    def add_healthcheck(
        self,
        command: str,
        interval: str = "30s",
        timeout: str = "10s",
        retries: int = 3,
        start_period: str = "0s",
    ) -> str:
        """Add healthcheck to Dockerfile.

        Args:
            command: Healthcheck command
            interval: Check interval
            timeout: Check timeout
            retries: Number of retries
            start_period: Start period

        Returns:
            HEALTHCHECK instruction
        """
        return (
            f"HEALTHCHECK --interval={interval} --timeout={timeout} "
            f"--retries={retries} --start-period={start_period} \\\n"
            f"    CMD {command}"
        )

    def add_environment_variables(self, env_vars: dict[str, str]) -> list[str]:
        """Add environment variables.

        Args:
            env_vars: Dictionary of environment variables

        Returns:
            List of ENV commands
        """
        return [f"ENV {key}={value}" for key, value in env_vars.items()]

    def add_volumes(self, volumes: list[str]) -> list[str]:
        """Add volume declarations.

        Args:
            volumes: List of volume paths

        Returns:
            List of VOLUME commands
        """
        if not volumes:
            return []

        volumes_str = " ".join(f'"{v}"' for v in volumes)
        return [f"VOLUME [{volumes_str}]"]

    def add_entrypoint(
        self, entrypoint: list[str] | None = None, command: list[str] | None = None
    ) -> str:
        """Add entrypoint and command.

        Args:
            entrypoint: Entrypoint command
            command: Default command

        Returns:
            ENTRYPOINT and CMD instructions
        """
        result = []

        if entrypoint:
            entrypoint_str = ", ".join(f'"{e}"' for e in entrypoint)
            result.append(f"ENTRYPOINT [{entrypoint_str}]")

        if command:
            command_str = ", ".join(f'"{c}"' for c in command)
            result.append(f"CMD [{command_str}]")

        return "\n".join(result)

    def build_for_workflow(
        self,
        dependencies: dict[str, Any],
        base_image: str = "python:3.12-slim",
        use_cuda: bool = False,
    ) -> str:
        """Build complete Dockerfile for workflow.

        Args:
            dependencies: Workflow dependencies
            base_image: Base Docker image
            use_cuda: Whether to use CUDA

        Returns:
            Complete Dockerfile
        """
        lines = []

        # Base image
        if use_cuda:
            lines.append(self.create_with_cuda())
        else:
            lines.append(f"FROM {base_image}")
            lines.append("")

        # System dependencies
        lines.append("# Install system dependencies")
        lines.extend(self.add_system_packages(["git", "wget", "curl"]))
        lines.append("")

        # Install ComfyUI
        lines.append("# Install ComfyUI")
        lines.append(
            "RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI"
        )
        lines.append("WORKDIR /app/ComfyUI")
        lines.append("")

        # Install PyTorch (CPU version for smaller image)
        lines.append("# Install PyTorch")
        lines.append(
            "RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu"
        )
        lines.append("")

        # Install ComfyUI requirements
        lines.append("# Install ComfyUI requirements")
        lines.append("RUN pip install --no-cache-dir -r requirements.txt")
        lines.append("")

        # Python packages
        python_packages = list(dependencies.get("python_packages", []))
        if python_packages:
            lines.append("# Install Python packages")
            lines.extend(self.add_python_packages(python_packages))
            lines.append("")

        # Custom nodes
        custom_nodes = dependencies.get("custom_nodes", [])
        if custom_nodes:
            lines.append("# Install custom nodes")
            lines.extend(self.add_custom_nodes(custom_nodes))
            lines.append("")

        # Expose port
        lines.append("EXPOSE 8188")
        lines.append("")

        # Default command
        lines.append(
            'CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]'
        )

        return "\n".join(lines)

    def create_with_cache_mounts(self) -> str:
        """Create Dockerfile with cache mount optimization.

        Returns:
            Dockerfile with cache mounts
        """
        dockerfile = [
            "# syntax=docker/dockerfile:1",
            "FROM python:3.12-slim",
            "",
            "WORKDIR /app",
            "",
            "# Use cache mount for pip",
            "RUN --mount=type=cache,target=/root/.cache/pip \\",
            "    pip install --upgrade pip && \\",
            "    pip install numpy torch",
            "",
        ]
        return "\n".join(dockerfile)

    def create_secure(self, base_image: str = "python:3.12-slim") -> str:
        """Create security-hardened Dockerfile.

        Args:
            base_image: Base Docker image

        Returns:
            Security-hardened Dockerfile
        """
        dockerfile = [
            f"FROM {base_image}",
            "",
            "# Create non-root user",
            "RUN useradd -m -u 1000 -s /bin/bash appuser && \\",
            "    mkdir -p /app && \\",
            "    chown -R appuser:appuser /app",
            "",
            "WORKDIR /app",
            "",
            "# Switch to non-root user",
            "USER appuser",
            "",
            "# Copy application files",
            "COPY --chown=appuser:appuser . /app",
            "",
        ]
        return "\n".join(dockerfile)

    def add_build_args(self, args: dict[str, str]) -> list[str]:
        """Add ARG instructions for build arguments.

        Args:
            args: Dictionary of build arguments

        Returns:
            List of ARG commands
        """
        return [f"ARG {key}={value}" for key, value in args.items()]

    def add_copy_instructions(self, copies: list[tuple[str, str]]) -> list[str]:
        """Add COPY instructions.

        Args:
            copies: List of (source, destination) tuples

        Returns:
            List of COPY commands
        """
        return [f"COPY {src} {dst}" for src, dst in copies]

    def setup_non_root_user(
        self, username: str = "appuser", uid: int = 1000
    ) -> list[str]:
        """Set up non-root user.

        Args:
            username: Username
            uid: User ID

        Returns:
            List of commands
        """
        return [
            f"RUN useradd -m -u {uid} -s /bin/bash {username}",
            f"USER {username}",
        ]

    def create_minimal(self, base_image: str, packages: list[str]) -> str:
        """Create minimal sized Dockerfile.

        Args:
            base_image: Base Docker image
            packages: Python packages to install

        Returns:
            Minimal Dockerfile
        """
        dockerfile = [
            "# Builder stage",
            f"FROM {base_image} AS builder",
            "",
            "WORKDIR /build",
            "",
            "# Install packages in virtual environment",
            "RUN python -m venv /opt/venv",
            'ENV PATH="/opt/venv/bin:$PATH"',
            "",
            f"RUN pip install --no-cache-dir {' '.join(packages)}",
            "",
            "# Runtime stage",
            f"FROM {base_image} AS runtime",
            "",
            "# Copy virtual environment",
            "COPY --from=builder /opt/venv /opt/venv",
            'ENV PATH="/opt/venv/bin:$PATH"',
            "",
            "WORKDIR /app",
            "",
            "# Clean up",
            "RUN apt-get clean && \\",
            "    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*",
            "",
        ]
        return "\n".join(dockerfile)

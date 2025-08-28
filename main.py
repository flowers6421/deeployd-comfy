#!/usr/bin/env python3
"""ComfyUI Workflow to Docker Translator - Main CLI Interface."""

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.api.generator import WorkflowAPIGenerator
from src.containers.docker_manager import DockerManager
from src.containers.dockerfile_builder import DockerfileBuilder
from src.workflows.analyzer import NodeAnalyzer
from src.workflows.dependencies import DependencyExtractor
from src.workflows.parser import WorkflowParser
from src.workflows.validator import WorkflowValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize CLI
app = typer.Typer(
    name="comfyui-deploy",
    help="Transform ComfyUI workflows into production-ready Docker containers",
)
console = Console()


@app.command()
def build_workflow(
    workflow_path: Path = typer.Argument(
        ..., help="Path to ComfyUI workflow JSON file"
    ),
    output_dir: Path = typer.Option(
        Path("./build"), help="Output directory for Dockerfile and artifacts"
    ),
    image_name: str = typer.Option(
        "comfyui-workflow", help="Name for the Docker image"
    ),
    tag: str = typer.Option("latest", help="Tag for the Docker image"),
    build_image: bool = typer.Option(
        True, help="Build Docker image after generating Dockerfile"
    ),
    push: bool = typer.Option(False, help="Push image to registry after building"),
    registry: str | None = typer.Option(None, help="Registry URL for pushing image"),
):
    """Build a Docker container from a ComfyUI workflow."""
    console.print(f"[bold blue]Processing workflow:[/bold blue] {workflow_path}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Parse workflow
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Parsing workflow...", total=None)

            with open(workflow_path) as f:
                workflow_data = json.load(f)

            parser = WorkflowParser()
            parser.parse(workflow_data)  # Result not needed, just parse
            progress.update(task, completed=True)
            console.print("[green]✓[/green] Workflow parsed successfully")

        # Step 2: Validate workflow
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Validating workflow...", total=None)

            validator = WorkflowValidator()
            validation_result = validator.validate(workflow_data)

            if not validation_result.is_valid:
                console.print("[red]✗ Workflow validation failed:[/red]")
                for error in validation_result.errors:
                    console.print(f"  - {error}")
                raise typer.Exit(1)

            progress.update(task, completed=True)
            console.print("[green]✓[/green] Workflow validated")

            if validation_result.warnings:
                console.print("[yellow]⚠ Warnings:[/yellow]")
                for warning in validation_result.warnings:
                    console.print(f"  - {warning}")

        # Step 3: Analyze workflow
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing nodes...", total=None)

            analyzer = NodeAnalyzer()
            analysis = analyzer.analyze(workflow_data)

            progress.update(task, completed=True)
            console.print(f"[green]✓[/green] Found {analysis['total_nodes']} nodes")
            console.print(f"  - Builtin: {analysis['builtin_nodes']}")
            console.print(f"  - Custom: {analysis['custom_nodes']}")

        # Step 4: Extract dependencies
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Extracting dependencies...", total=None)

            extractor = DependencyExtractor()
            dependencies = extractor.extract_all(workflow_data)

            progress.update(task, completed=True)
            console.print("[green]✓[/green] Dependencies extracted")

            # Display dependencies table
            table = Table(title="Workflow Dependencies")
            table.add_column("Type", style="cyan")
            table.add_column("Count", justify="right", style="green")
            table.add_column("Items", style="yellow")

            # Models
            model_count = sum(len(v) for v in dependencies["models"].values())
            if model_count > 0:
                model_items = []
                for model_type, models in dependencies["models"].items():
                    if models:
                        model_items.extend([f"{model_type}: {m}" for m in models])
                table.add_row("Models", str(model_count), ", ".join(model_items[:3]))

            # Custom nodes
            if dependencies["custom_nodes"]:
                custom_node_names = []
                for node in dependencies["custom_nodes"]:
                    if isinstance(node, dict):
                        custom_node_names.append(node.get("class_type", str(node)))
                    else:
                        custom_node_names.append(str(node))
                table.add_row(
                    "Custom Nodes",
                    str(len(dependencies["custom_nodes"])),
                    ", ".join(custom_node_names[:3]),
                )

            # Python packages
            if dependencies["python_packages"]:
                table.add_row(
                    "Python Packages",
                    str(len(dependencies["python_packages"])),
                    ", ".join(list(dependencies["python_packages"])[:3]),
                )

            console.print(table)

        # Step 5: Generate Dockerfile
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating Dockerfile...", total=None)

            # Initialize builder
            dockerfile_builder = DockerfileBuilder()

            # Use the build_for_workflow method which handles everything
            dockerfile_content = dockerfile_builder.build_for_workflow(
                dependencies=dependencies,
                base_image="python:3.11-slim",
                use_cuda=False,  # TODO: detect if CUDA is needed from workflow
            )
            dockerfile_path = output_dir / "Dockerfile"
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)

            progress.update(task, completed=True)
            console.print(f"[green]✓[/green] Dockerfile generated: {dockerfile_path}")

        # Step 6: Build Docker image (if requested)
        if build_image:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Building Docker image...", total=None)

                try:
                    docker_manager = DockerManager()

                    # Check if Docker is available
                    if not docker_manager.is_available():
                        console.print("[red]✗ Docker is not available[/red]")
                        console.print("Please ensure Docker daemon is running")
                        raise typer.Exit(1)

                    # Build image
                    full_image_name = f"{image_name}:{tag}"
                    if registry:
                        full_image_name = f"{registry}/{full_image_name}"

                    # Convert to absolute path for Docker
                    dockerfile_path = dockerfile_path.absolute()
                    context_path = output_dir.absolute()

                    success = docker_manager.build_image(
                        dockerfile_path=str(dockerfile_path),
                        context_path=str(context_path),
                        tag=full_image_name,
                    )

                    if success:
                        progress.update(task, completed=True)
                        console.print(
                            f"[green]✓[/green] Docker image built: {full_image_name}"
                        )

                        # Push to registry if requested
                        if push and registry:
                            console.print(f"Pushing to registry: {registry}")
                            if docker_manager.push_image(full_image_name):
                                console.print(
                                    "[green]✓[/green] Image pushed to registry"
                                )
                            else:
                                console.print("[red]✗ Failed to push image[/red]")
                    else:
                        console.print("[red]✗ Failed to build Docker image[/red]")
                        raise typer.Exit(1)

                except Exception as e:
                    console.print(f"[red]✗ Docker build failed: {e}[/red]")
                    raise typer.Exit(1) from e

        # Step 7: Generate API configuration
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating API configuration...", total=None)

            api_generator = WorkflowAPIGenerator()
            api_config = api_generator.generate_endpoint_config(workflow_data)
            parameters = api_generator.extract_input_parameters(workflow_data)

            # Save API configuration
            api_config_path = output_dir / "api_config.json"
            with open(api_config_path, "w") as f:
                # Convert parameters to JSON-serializable format
                param_list = []
                for p in parameters:
                    param_dict = {
                        "name": p.name,
                        "type": str(p.type.value)
                        if hasattr(p.type, "value")
                        else str(p.type),
                        "required": p.required,
                        "default": p.default,
                        "description": p.description,
                    }
                    if p.minimum is not None:
                        param_dict["minimum"] = p.minimum
                    if p.maximum is not None:
                        param_dict["maximum"] = p.maximum
                    if p.enum:
                        param_dict["enum"] = p.enum
                    param_list.append(param_dict)

                json.dump(
                    {
                        "endpoint": api_config.path,
                        "method": api_config.method,
                        "parameters": param_list,
                        "description": api_config.description,
                    },
                    f,
                    indent=2,
                )

            progress.update(task, completed=True)
            console.print(
                f"[green]✓[/green] API configuration saved: {api_config_path}"
            )

        console.print("\n[bold green]✨ Workflow processing complete![/bold green]")
        console.print(f"Output directory: {output_dir}")

    except FileNotFoundError:
        console.print(f"[red]Error: Workflow file not found: {workflow_path}[/red]")
        raise typer.Exit(1) from None
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON in workflow file: {e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Unexpected error during workflow processing")
        raise typer.Exit(1) from e


@app.command()
def validate_workflow(
    workflow_path: Path = typer.Argument(
        ..., help="Path to ComfyUI workflow JSON file"
    ),
    strict: bool = typer.Option(False, help="Enable strict validation"),
):
    """Validate a ComfyUI workflow file."""
    console.print(f"[bold blue]Validating workflow:[/bold blue] {workflow_path}")

    try:
        with open(workflow_path) as f:
            workflow_data = json.load(f)

        validator = WorkflowValidator()
        result = validator.validate(workflow_data, strict=strict)

        if result.is_valid:
            console.print("[bold green]✓ Workflow is valid![/bold green]")
        else:
            console.print("[bold red]✗ Workflow validation failed[/bold red]")
            for error in result.errors:
                console.print(f"  [red]Error:[/red] {error}")

        if result.warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  ⚠ {warning}")

        if result.metadata:
            console.print("\n[blue]Metadata:[/blue]")
            for key, value in result.metadata.items():
                console.print(f"  {key}: {value}")

    except FileNotFoundError:
        console.print(f"[red]Error: Workflow file not found: {workflow_path}[/red]")
        raise typer.Exit(1) from None
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def analyze_workflow(
    workflow_path: Path = typer.Argument(
        ..., help="Path to ComfyUI workflow JSON file"
    ),
):
    """Analyze a ComfyUI workflow and display detailed information."""
    console.print(f"[bold blue]Analyzing workflow:[/bold blue] {workflow_path}")

    try:
        with open(workflow_path) as f:
            workflow_data = json.load(f)

        # Parse and analyze
        parser = WorkflowParser()
        parsed = parser.parse(workflow_data)

        analyzer = NodeAnalyzer()
        analysis = analyzer.analyze(workflow_data)

        extractor = DependencyExtractor()
        dependencies = extractor.extract_all(workflow_data)

        # Display results
        console.print("\n[bold]Workflow Analysis[/bold]")
        console.print(f"Format: {parsed.format}")
        console.print(f"Total Nodes: {analysis['total_nodes']}")
        console.print(f"Builtin Nodes: {analysis['builtin_nodes']}")
        console.print(f"Custom Nodes: {analysis['custom_nodes']}")

        if analysis["custom_node_types"]:
            console.print("\n[bold]Custom Node Types:[/bold]")
            for node_type in analysis["custom_node_types"]:
                console.print(f"  • {node_type}")

        # Display dependencies
        console.print("\n[bold]Dependencies:[/bold]")

        if dependencies["models"]:
            console.print("\n[cyan]Models:[/cyan]")
            for model_type, models in dependencies["models"].items():
                if models:
                    console.print(f"  {model_type}:")
                    for model in models:
                        console.print(f"    • {model}")

        if dependencies["custom_nodes"]:
            console.print("\n[cyan]Custom Nodes:[/cyan]")
            for node in dependencies["custom_nodes"]:
                if isinstance(node, dict):
                    node_name = node.get("class_type", str(node))
                else:
                    node_name = str(node)
                console.print(f"  • {node_name}")

        if dependencies["python_packages"]:
            console.print("\n[cyan]Python Packages:[/cyan]")
            for package in dependencies["python_packages"]:
                console.print(f"  • {package}")

    except FileNotFoundError:
        console.print(f"[red]Error: Workflow file not found: {workflow_path}[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def version():
    """Display version information."""
    console.print("[bold]ComfyUI Workflow to Docker Translator[/bold]")
    console.print("Version: 1.0.0")
    console.print("Python: 3.11+")
    console.print("License: MIT")


if __name__ == "__main__":
    app()

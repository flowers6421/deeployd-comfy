# DeepLoyd ComfyUI Dockerizer

Transform ComfyUI workflows into Docker containers with API endpoints.

## What it does

Takes ComfyUI workflows → Makes Docker containers → Generates APIs

## Features

- Parse ComfyUI workflows (UI and API formats)
- Extract all dependencies automatically
- Generate optimized Dockerfiles
- Create REST APIs from workflows
- 90% test coverage

## Quick Start

```bash
# Clone
git clone https://github.com/flowers6421/deeployd-comfy.git
cd deeployd-comfy

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Use
python main.py build-workflow your_workflow.json
```

## Commands

```bash
# Build workflow into Docker container
python main.py build-workflow workflow.json

# Analyze workflow dependencies
python main.py analyze-workflow workflow.json

# Validate workflow
python main.py validate-workflow workflow.json
```

## Testing

```bash
pytest  # Run all tests
pytest --cov=src  # With coverage
```

## Output

The tool generates:
- `build/Dockerfile` - Optimized Docker configuration
- `build/api_config.json` - API endpoint configuration
- Docker image (if `--build-image` flag used)

## License

MIT

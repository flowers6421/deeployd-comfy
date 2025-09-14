# DeepLoyd Comfy

Transform ComfyUI workflows into production-ready Docker containers with automatic API generation and documentation.

## Monorepo Overview

This repository contains both the backend API and a modern web dashboard:

- `src/` – FastAPI backend exposing `/api/v1` endpoints and WebSocket updates
- `frontend/` – Next.js 15 + TypeScript dashboard for managing workflows, builds, and executions

## What it does

Takes ComfyUI workflows → Makes Docker containers → Generates APIs → Creates Documentation

## Features

- **Workflow Support**: Parse both UI and API format ComfyUI workflows
- **Dependency Detection**: Automatically extract models, custom nodes, and Python packages
- **Interactive Setup**: Prompts for custom node GitHub URLs and model paths
- **Docker Generation**: Create optimized Dockerfiles with GPU/CPU support
- **API Generation**: Generate REST API endpoints with full parameter extraction
- **Documentation**: Auto-generate HTML docs, OpenAPI specs, and Docker run scripts
- **Volume Mounting**: Automatic model folder mounting for easy model management
- **Custom Node Resolution**: Smart detection and installation of custom nodes
- **Test Coverage**: 90% test coverage with 253+ passing tests

## Quick Start

### Installation

```bash
# Clone
git clone https://github.com/flowers6421/deeployd-comfy.git
cd deeployd-comfy

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Install npm dependencies for node resolution
npm install

# Install frontend dependencies (if using the web dashboard)
cd frontend
npm install
cd ..
```

### Running the Development Environment

```bash
# The dev-up.sh script will automatically install missing dependencies and start both backend and frontend
./dev-up.sh

# Or use the Makefile for a complete setup
make install  # Installs all dependencies (Python, npm, frontend)
make dev-up   # Runs the development environment
```

### Building Workflows

```bash
# Build workflow (interactive mode)
python main.py build-workflow your_workflow.json

# Build with options
python main.py build-workflow workflow.json \
  --output-dir ./build \
  --models-path /path/to/ComfyUI/models
```

## Interactive Workflow Building

The tool now provides an interactive experience:

1. **Custom Node Detection**: Automatically detects custom nodes and prompts for GitHub URLs
2. **Model Path Configuration**: Asks for your ComfyUI models folder to set up volume mounts
3. **Documentation Generation**: Creates comprehensive HTML documentation automatically

## Commands

```bash
# Build workflow into Docker container (interactive)
python main.py build-workflow workflow.json

# Build without prompts
python main.py build-workflow workflow.json --no-interactive

# Specify models path
python main.py build-workflow workflow.json --models-path /path/to/models

# Skip Docker build (only generate files)
python main.py build-workflow workflow.json --no-build-image

# Analyze workflow dependencies
python main.py analyze-workflow workflow.json

# Validate workflow
python main.py validate-workflow workflow.json
```

## Generated Files

Each build creates:
- `Dockerfile` - Optimized Docker configuration
- `docker_run.sh` - Ready-to-use run script with volume mounts
- `api_config.json` - API endpoint configuration
- `openapi.json` - Full OpenAPI/Swagger specification
- `documentation.html` - Beautiful HTML documentation
- `.cache/` - Cached custom node information

## Testing

```bash
pytest  # Run all tests
pytest --cov=src  # With coverage
```

## Output

The tool generates:
- `build/Dockerfile` - Optimized Docker configuration
- `build/api_config.json` - API endpoint configuration with extracted parameters
- Docker image with ComfyUI and all dependencies installed

## Running the Container

### Single Container Mode (ComfyUI only)

```bash
# Build container from workflow
python main.py build-workflow tests/real_workflow.json --image-name comfyui-workflow --tag latest

# Run with shared model volume
docker run -d --name comfyui \
  -p 8188:8188 \
  -v /path/to/models:/app/ComfyUI/models \
  comfyui-workflow:latest
```

### Multi-Container Mode with API (Recommended)

```bash
# Build API container
docker build -f docker/api/Dockerfile -t workflow-api .

# Start both ComfyUI and API containers
docker-compose up -d

# The API will be available at http://localhost:8000
# ComfyUI interface at http://localhost:8188
```

## API Usage

### Generate Image

```bash
# Simple generation
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "positive_prompt": "a beautiful landscape",
    "negative_prompt": "ugly, blurry",
    "seed": 12345,
    "width": 1024,
    "height": 1024,
    "steps": 20
  }'

# Async generation (returns immediately)
curl -X POST "http://localhost:8000/api/generate?wait=false" \
  -H "Content-Type: application/json" \
  -d '{"positive_prompt": "a cat"}'
# Returns: {"prompt_id": "xxx", "status": "submitted"}
```

### Check Status

```bash
curl http://localhost:8000/api/status/{prompt_id}
# Returns: {"status": "completed", "images": [...]}
```

### WebSocket Progress

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/{prompt_id}');
ws.onmessage = (event) => {
  const status = JSON.parse(event.data);
  console.log('Progress:', status);
};
```

### API Documentation
Visit `http://localhost:8000/docs` for interactive OpenAPI documentation.

## Frontend Dashboard (Next.js)

An optional web UI lives under `frontend/` and provides:

- Upload/validate workflows, view parameters and dependencies
- Trigger and monitor container builds with live logs
- Browse executions (queue/history/gallery) and run presets
- Embedded API tester and generated cURL snippets

### Requirements

- Node.js 20+ (recommended) and npm 10+

### Quick start

```bash
cd frontend
npm install

# Configure API targets (defaults shown)
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_WS_URL=ws://localhost:8000" >> .env.local

# Run the dev server
npm run dev
# Open http://localhost:3000
```

Build and run in production:

```bash
cd frontend
npm run build
npm start
```

The dashboard talks to the backend at `NEXT_PUBLIC_API_URL` (REST) and `NEXT_PUBLIC_WS_URL` (WebSocket). If you run the API on a different host/port, update `.env.local` accordingly.

See `frontend/README.md` for more details on the tech stack and project layout.

### Local Dev (dev-up)

Run API + frontend together without extra tooling:

```bash
bash scripts/dev-up.sh
```

Environment overrides:

- `API_HOST` (default: `127.0.0.1`)
- `API_PORT` (default: `8000`)
- `FRONTEND_PORT` (default: `3000`)

The script forwards `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` to the Next.js dev server.

### Makefile Targets

Common tasks are available via `make`:

```bash
# Install backend venv + frontend deps
make install

# Run API + frontend together
make dev-up

# Run only frontend (using API_HOST/API_PORT)
make frontend-dev API_HOST=127.0.0.1 API_PORT=8000 FRONTEND_PORT=3000

# Run backend only
make backend-run API_PORT=8000

# Lint and type-check
make lint
make type-check
```

## Troubleshooting

### Node Resolution Error (502 Bad Gateway)

If you encounter a 502 error when resolving nodes with the message:
```
comfyui-json resolution failed: Failed to resolve workflow: comfyui-json not available
```

**Solution:**
1. Ensure npm dependencies are installed in the root directory:
   ```bash
   npm install
   ```
2. The `dev-up.sh` script will automatically install these dependencies on startup
3. Verify the dependencies are installed:
   ```bash
   node src/workflows/node_bridge.js  # Should show usage instructions
   ```

### Common Issues

- **Frontend not starting**: Make sure to run `npm install` in the `frontend/` directory
- **Python dependencies**: Ensure your virtual environment is activated before installing requirements
- **Port conflicts**: Check if ports 8000 or 3000 are already in use

## Acknowledgments

Special thanks to the following projects and contributors:

- **[comfyui-json](https://github.com/comfy-deploy/comfyui-json)** by ComfyDeploy team - and [BennyKok](https://github.com/BennyKok) - The core library for ComfyUI workflow parsing and dependency resolution
- **[ComfyUI Accelerator](https://github.com/loscrossos/helper_comfyUI_accel)** by [loscrossos](https://github.com/loscrossos/) - For acceleration techniques and optimizations
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)** - The amazing stable diffusion GUI and backend
- **[ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager)** - For the comprehensive node and model management system

## License

MIT

# DeepLoyd ComfyUI Dockerizer

Transform ComfyUI workflows into Docker containers with API endpoints.

## What it does

Takes ComfyUI workflows → Makes Docker containers → Generates APIs

## Features

- Parse ComfyUI workflows (UI and API formats)
- Extract all dependencies automatically (models, custom nodes, Python packages)
- Generate optimized Dockerfiles with GPU support
- Create REST API configurations from workflows
- 90% test coverage (253 tests passing)
- Successfully tested with production workflows

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

## License

MIT

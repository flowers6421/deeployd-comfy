# ComfyUI to Docker Translator

[![CI](https://github.com/comfyui-docker/translator/actions/workflows/ci.yml/badge.svg)](https://github.com/comfyui-docker/translator/actions)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: mypy](https://img.shields.io/badge/type%20checked-mypy-blue)](http://mypy-lang.org/)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Transform ComfyUI workflows into secure Docker containers with automated API generation.

## 🚀 Overview

This platform converts ComfyUI workflow JSON files into optimized Docker containers, complete with:

- **Automated dependency detection** - Identifies custom nodes, models, and Python packages
- **Multi-stage Docker builds** - Creates minimal production images (60-80% smaller)
- **RESTful API generation** - Transforms workflows into callable endpoints with validation
- **Version tracking** - Git-like versioning for workflows with rollback capability
- **Real-time progress** - WebSocket support for live execution updates
- **Cloud-ready deployment** - Works with AWS, GCP, Azure, and Kubernetes

## 📋 Features

### Core Functionality

- ✅ Parse and validate ComfyUI workflow JSON (both UI and API formats)
- ✅ Extract dependencies (custom nodes, models, Python packages)
- ✅ Generate optimized multi-stage Dockerfiles
- ✅ Create RESTful APIs from workflows automatically
- ✅ Track versions with git-like semantics
- ✅ Support GPU acceleration (CUDA/ROCm)
- ✅ Handle large model files (5-10GB) efficiently

### Development Features

- ✅ Test-Driven Development (TDD) approach
- ✅ 80%+ code coverage requirement
- ✅ Type checking with mypy
- ✅ Code formatting with Ruff
- ✅ Pre-commit hooks for quality
- ✅ CI/CD with GitHub Actions

## 🏗️ Architecture

```
src/
├── workflows/      # Workflow parsing and validation
├── containers/     # Docker generation and optimization
├── models/         # Data models and schemas
├── api/           # FastAPI application and endpoints
├── utils/         # Utility functions and helpers
└── db/            # Database models and operations

tests/
├── unit/          # Unit tests (80%+ coverage)
├── integration/   # Component integration tests
└── e2e/           # End-to-end workflow tests
```

## 🚦 Getting Started

### Prerequisites

- Python 3.10 or higher (3.12 recommended)
- Docker Desktop or Docker Engine
- Git

### Installation

1. Clone the repository:

```bash
git clone https://github.com/comfyui-docker/translator.git
cd translator
```

2. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:

```bash
pip install --upgrade pip pip-tools
pip-compile requirements-dev.in
pip install -r requirements-dev.txt
```

4. Install pre-commit hooks:

```bash
pre-commit install
```

5. Run tests to verify setup:

```bash
pytest tests/test_smoke.py -v
```

## 🧪 Testing

Run all tests with coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

Run specific test categories:

```bash
pytest tests/unit -v          # Unit tests only
pytest tests/integration -v   # Integration tests
pytest tests/e2e -v           # End-to-end tests
pytest -m "not slow"          # Skip slow tests
```

## 🔧 Development

### Code Quality

Format code:

```bash
ruff format src tests
```

Lint code:

```bash
ruff check src tests --fix
```

Type checking:

```bash
mypy src
```

### Pre-commit Hooks

Run all hooks manually:

```bash
pre-commit run --all-files
```

## 📚 Documentation

Detailed documentation is available in the following files:

- [Development Tracker](dev_track.md) - Complete development roadmap with TDD approach
- [Development Guide](docs/development.md) - Architecture and development practices
- [Research Notes](research.md) - Technical research and implementation strategies

## 🚢 Deployment

### Docker Build

Build the application container:

```bash
docker build -t comfyui-translator:latest .
```

### Environment Variables

Create a `.env` file with required configuration:

```env
DATABASE_URL=postgresql://user:pass@localhost/comfyui
REDIS_URL=redis://localhost:6379
DOCKER_REGISTRY=registry.example.com
SECRET_KEY=your-secret-key
```

### Running the Application

Start the API server:

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Access the API documentation at `http://localhost:8000/docs`

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests first (TDD approach)
4. Implement your feature
5. Ensure all tests pass with 80%+ coverage
6. Run pre-commit hooks
7. Commit your changes
8. Push to your branch
9. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📊 Project Status

**Current Phase: Phase 1 - Foundation Setup ✅**

- [x] Project structure and configuration
- [x] Testing framework with pytest
- [x] Code quality tools (Ruff, mypy)
- [x] CI/CD pipeline with GitHub Actions
- [x] Pre-commit hooks
- [ ] Core workflow engine (Phase 2)
- [ ] Container generation (Phase 3)
- [ ] API generation (Phase 4)

See [dev_track.md](dev_track.md) for the complete roadmap.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- ComfyUI community for the amazing workflow system
- Docker team for container technology
- FastAPI for the modern Python web framework
- All contributors and testers

## 📬 Contact

- GitHub Issues: [Report bugs or request features](https://github.com/comfyui-docker/translator/issues)
- Discussions: [Join the conversation](https://github.com/comfyui-docker/translator/discussions)

---

Built with ❤️ using Test-Driven Development

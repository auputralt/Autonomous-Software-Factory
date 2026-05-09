# FORGE v3.0 — Autonomous Software Factory

An AI-powered autonomous software factory that takes a natural language description and produces tested, runnable Python code — fully automated from specification to packaged artifact.

## Architecture

```
User Prompt
    │
    ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Manager  │────▶│Developer │────▶│  Tester  │────▶│ Executor │
│  Agent   │     │  Agent   │     │  Agent   │     │ (Sandbox)│
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                        │
                                          ┌─────────────┤
                                          │   Tests OK? │
                                          └─────────────┤
                                            Yes │    No │
                                                ▼       ▼
                                         ┌──────────┐  ┌──────────┐
                                         │ Packager │  │ Retry    │
                                         │   (ZIP)  │  │ (Dev     │
                                         └──────────┘  │  Agent)  │
                                                       └──────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Agents | LangGraph + Google Gemini (GenAI SDK 2026) |
| Sandbox | Rust (PyO3/abi3) with Python subprocess fallback |
| API | FastAPI + WebSocket real-time streaming |
| Task Queue | Celery + Redis |
| Frontend | Vanilla JS terminal-style UI |
| Deployment | Docker multi-stage build + docker-compose |

## Quick Start

### 1. Configure

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 2. Launch

```bash
docker compose up -d --build
```

### 3. Access

Open `http://localhost:8000` in your browser.

## Project Structure

```
├── forge/
│   ├── agents/          # LangGraph agent nodes
│   │   ├── manager.py   # Translates prompt → JSON blueprint
│   │   ├── developer.py # Blueprint → source code
│   │   ├── tester.py    # Source code → test suite
│   │   ├── executor.py  # Runs sandbox, evaluates results
│   │   ├── packager.py  # Creates downloadable ZIP
│   │   └── graph.py     # Orchestrates the workflow
│   ├── api/             # FastAPI routes + WebSocket
│   ├── sandbox/         # Rust/Python sandbox runner
│   ├── queue/           # Celery task definitions
│   └── utils/           # JSON extraction, packaging, progress
├── rust_engine/         # PyO3 sandbox (memory-safe code execution)
├── frontend/            # Terminal-style web UI
├── Dockerfile           # Multi-stage build
└── docker-compose.yml   # Full stack orchestration
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/build` | Submit a build request |
| GET | `/api/status/{request_id}` | Check build status |
| GET | `/api/download/{request_id}` | Download build artifact |
| GET | `/health` | Health check |
| WS | `/ws/build/{request_id}` | Real-time build streaming |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Google Gemini API key (required) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `MAX_BUILD_ATTEMPTS` | `5` | Max retry cycles for failing builds |
| `SANDBOX_TIMEOUT_SECS` | `30` | Code execution timeout |
| `SANDBOX_MAX_MEMORY_MB` | `512` | Memory limit per execution |
| `DAILY_REQUEST_LIMIT` | `200` | Daily API call cap |

## Security

- API key stored as `SecretStr` — never leaks into logs or tracebacks
- Prompt injection blocking on the `/api/build` endpoint
- IP-based sliding window rate limiting (10 req/min)
- Sandboxed execution with `setrlimit` constraints (memory, CPU, processes, file size, core dumps)
- Environment scrubbing in sandbox (no API keys leak to child processes)
- 24h TTL on all Redis request data

## License

MIT

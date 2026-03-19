# Repository Guidelines

## Project Structure & Module Organization

FinAlly (Finance Ally) is an AI-powered trading workstation — a simulated Bloomberg terminal with an LLM copilot. Single-container architecture: FastAPI serves a static Next.js export and all API routes on port 8000, with SQLite for persistence.

- **`planning/`** — Shared project documentation and agent contracts. `PLAN.md` is the canonical spec.
- **`frontend/`** — Self-contained Next.js (TypeScript) project, built as static export (`output: 'export'`). Communicates with backend via `/api/*` REST and `/api/stream/*` SSE endpoints only.
- **`backend/`** — Self-contained FastAPI (Python) project managed with `uv`. Owns all server logic: database init, schema, API routes, SSE streaming, market data, and LLM integration.
- **`backend/db/`** — Schema SQL definitions and seed logic. Backend lazily initializes the database on first request.
- **`db/`** — Runtime volume mount for SQLite (`db/finally.db`, gitignored). Persists across container restarts.
- **`test/`** — Playwright E2E tests (infra defined in root `docker-compose.yml` under `test` profile).
- **`scripts/`** — Start/stop scripts wrapping Docker commands.

Key boundary: frontend and backend are independent projects. Frontend knows nothing about Python; backend knows nothing about React.

## Build, Test, and Development Commands

No build system is configured yet. When scaffolded, expect:

- **Frontend**: `npm install`, `npm run dev`, `npm run build` (static export), `npm test` (inside `frontend/`)
- **Backend**: `uv sync`, `uv run uvicorn` or `uv run fastapi dev` (inside `backend/`), `uv run pytest`
- **Docker**: `docker build -t finally .` then `docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally`
- **E2E tests**: Run with `LLM_MOCK=true` for deterministic responses

## Environment Variables

```bash
OPENROUTER_API_KEY=...   # Required: LLM chat via OpenRouter
MASSIVE_API_KEY=         # Optional: real market data (simulator used if absent)
LLM_MOCK=false           # Optional: deterministic mock LLM responses for testing
```

## Agent Instructions

- All project documentation lives in `planning/`. The canonical spec is `planning/PLAN.md`.
- `CLAUDE.md` at the root references `planning/PLAN.md` as the key document.
- A custom Claude command `doc-review` exists in `.claude/commands/` for reviewing planning docs.
- LLM integration uses LiteLLM via OpenRouter with Cerebras inference (`openrouter/openai/gpt-oss-120b`). Use the `cerebras-inference` skill when writing LLM call code.

## Testing Guidelines

- **Backend**: pytest for unit tests (market data, portfolio logic, LLM parsing, API routes)
- **Frontend**: React Testing Library or similar for component tests
- **E2E**: Playwright via `docker compose --profile test up`, always run with `LLM_MOCK=true`

## Key Design Decisions

- SSE (not WebSockets) for real-time price streaming — one-way push, simpler
- Market orders only — no order book or limit order complexity
- Single user (`user_id="default"`) — no auth, schema supports future multi-user
- Fixed ticker universe (~50 supported tickers) — reject unknown tickers
- Delete position row on full sell (no zero-quantity phantom rows)
- Minimum order size: 0.001 shares

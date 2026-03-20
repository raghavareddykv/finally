# FinAlly — AI Trading Workstation

A real-time AI-powered trading terminal built entirely by coding agents. Stream live market data, trade a simulated portfolio, and chat with an AI assistant that can analyze positions and execute trades on your behalf.

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated trading** — $10k virtual cash, market orders, instant fills
- **Portfolio visualization** — heatmap, P&L chart, positions table
- **AI chat assistant** — natural language portfolio analysis and trade execution
- **Sparkline mini-charts** in the watchlist, full chart view per ticker
- **50-ticker universe** of major US equities

## Tech Stack

| Layer    | Technology                                   |
| -------- | -------------------------------------------- |
| Frontend | Next.js, TypeScript, Tailwind CSS, Lightweight Charts |
| Backend  | FastAPI, Python, SQLite                      |
| AI       | LiteLLM → OpenRouter (Cerebras inference)    |
| Infra    | Docker (single container), uv               |

## Quick Start

```bash
# 1. Copy env file and add your OpenRouter API key
cp .env.example .env

# 2. Build and run
docker build -t finally .
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally

# 3. Open http://localhost:8000
```

Or use the provided scripts:

```bash
./scripts/start_mac.sh    # macOS/Linux
./scripts/stop_mac.sh
```

## Environment Variables

| Variable             | Required | Description                                      |
| -------------------- | -------- | ------------------------------------------------ |
| `OPENROUTER_API_KEY` | Yes      | OpenRouter API key for AI chat                   |
| `MASSIVE_API_KEY`    | No       | Polygon.io key for real market data (simulator used if absent) |
| `LLM_MOCK`           | No       | Set `true` for deterministic mock LLM responses  |

## Project Structure

```
frontend/    → Next.js static export
backend/     → FastAPI + SQLite
planning/    → Project documentation
scripts/     → Docker start/stop helpers
test/        → Playwright E2E tests
db/          → SQLite volume mount (gitignored)
```

## Development

See [`planning/PLAN.md`](planning/PLAN.md) for the full project specification.

## License

See [LICENSE](LICENSE).

# Repository Guidelines

## Project Structure & Module Organization
- `src/ghl_base/` hosts the `aiohttp` server (`webhook_app.py`) and OAuth CLI (`oauth.py`). Add shared utilities here and expose public APIs via `__init__.py`.
- `handlers/` contains ready-to-use handler modules. Each module must declare `ROUTES` and IDs referenced in `config/routes.json` to enable/disable endpoints.
- `config/` stores routing and presets; `data/` holds sensitive tokens (`data/agency/location_token.json`) and spam dumps (`data/spam_emails/`). Treat all `data/` as secrets and keep out of Git.
- Tests should live in `tests/`, mirroring `src/ghl_base` and `handlers`.

## Build, Test, and Development Commands
- `python3 -m venv venv && source venv/bin/activate` — create and activate a virtualenv.
- `pip install -r requirements.txt && pip install -e .` — install dependencies and expose CLIs (`ghl-webhooks`, `ghl-oauth`).
- `WEBHOOK_HANDLERS=handlers.webhooks PORT=8081 ghl-webhooks` — run the webhook server.
- `OPENAI_API_KEY=xxx ghl-webhooks` — enable GPT-5.2 spam validation.
- `python -m pytest -q` — run tests (when present).

## Coding Style & Naming Conventions
- Python 3.9+, 4-space indentation, imports grouped as stdlib/third-party/internal.
- Prefer type hints and short docstrings (see `handlers/webhooks.py`).
- Handler names are `snake_case` (e.g., `health_detail`).
- Expose `ROUTES`, `MIDDLEWARES`, `on_startup`, `on_cleanup` when applicable.

## Testing Guidelines
- Use `pytest` with `aiohttp` fixtures and mocks for OpenAI/GoHighLevel.
- Name files like `tests/test_webhook_app.py`.
- Focus on critical flows: HMAC signature, idempotency, spam persistence.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (e.g., `feat: add spam persistence middleware`).
- Keep commits small and imperative; reference issues when available.
- PRs should include: objective, validation steps (e.g., `curl http://localhost:8081/healthz`), and relevant logs/prints.

## Security & Configuration Tips
- Use `.env` (copied from `.env.example`) for secrets; never hardcode credentials.
- Rotate `OPENAI_API_KEY`, `GHL_CLIENT_ID`, and `WEBHOOK_SECRET` regularly.
- For local safety: `git update-index --skip-worktree data/*.json`.

## Agent-Specific Instructions
- Before tasks, run `python3 scripts/current_time.py` to sync time and update `config/current_time.json`.
- If the script falls back to cached time, confirm with the user before relying on it.

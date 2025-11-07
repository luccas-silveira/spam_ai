# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`ghl-base` is a Python utility for GoHighLevel (GHL/LeadConnector) integrations providing:
- **OAuth 2.0 Flow**: CLI tool (`ghl-oauth`) for obtaining API tokens
- **Webhook Server**: Extensible aiohttp-based server (`ghl-webhooks`) for processing GHL webhook events with spam detection

## Time Awareness Requirement

- Antes de começar qualquer tarefa, rode `python3 scripts/current_time.py`.
- O script faz uma chamada HTTP (WorldTimeAPI); conceda acesso à rede quando solicitado pelo sandbox e avise o usuário se não conseguir.
- Esse script consulta `https://worldtimeapi.org/api/ip`, registra o resultado em `config/current_time.json` e imprime a data/hora reais.
- Comece toda resposta mencionando explicitamente a data/hora retornada. Se o script avisar "system" (fallback), confirme o dia com o usuário antes de assumir qualquer suposição temporal.

## Development Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies and project in editable mode
pip install -U pip
pip install -r requirements.txt
pip install -e .
```

## Common Commands

### Running the Webhook Server
```bash
# Start with .env configuration (default port: 8082)
ghl-webhooks

# Or with inline environment variables
WEBHOOK_HANDLERS=handlers.webhooks PORT=8081 ghl-webhooks
```

### Running OAuth Flow
```bash
# Interactive CLI for OAuth token generation
ghl-oauth
```

### Testing Webhooks
```bash
# Health check
curl -i http://localhost:8082/healthz

# Test InboundMessage event (if enabled in config/routes.json)
curl -i -X POST http://localhost:8082/webhook/InboundMessage \
  -H 'Content-Type: application/json' \
  -d '{"body": "Test message", "messageType": "SMS"}'
```

## Architecture

### Core Components

**src/ghl_base/webhook_app.py**: Main webhook server application
- Dynamic handler loading from `WEBHOOK_HANDLERS` env var (supports `module.*` wildcards)
- Middleware stack: request ID logging, HMAC signature validation, idempotency
- Auto-registration of routes from handler modules
- Built-in `/healthz` endpoint

**src/ghl_base/oauth.py**: OAuth 2.0 implementation
- Interactive flow with browser-based authorization
- Token exchange and persistence to `data/agency_token.json`
- Location token generation via `/oauth/locationToken`

**handlers/webhooks.py**: GHL webhook event handlers
- Route registry pattern with enable/disable via `config/routes.json`
- Factory function `_make_event_handler()` generates handlers for GHL events
- Spam detection integration using Google Gemini AI API for InboundMessage events
- Alias support: routes available at both `/webhook/*` and `/webhooks/*`

**config/routes.json**: Route configuration
- Controls which webhook routes are enabled/disabled
- Format: `{"routes": {"RouteID": true/false}}`
- Currently enabled: `InboundMessage`, `OutboundMessage`

### Middleware Stack

1. **Request ID Logging**: Adds `request_id` and logs request/response timing
2. **HMAC Signature Validation**: Validates webhook signatures when `WEBHOOK_SECRET` is set
   - Supports `sha256` (default) and `sha1` algorithms
   - Header: `X-Signature` (configurable via `WEBHOOK_SIGNATURE_HEADER`)
   - Stores validated body in `request["raw_body"]`
3. **Idempotency**: Prevents duplicate processing using in-memory TTL cache
   - Checks headers: `Idempotency-Key`, `X-Event-Id` (configurable)
   - Default TTL: 600 seconds
   - Returns `{"status": "duplicate"}` with `X-Idempotent-Replayed: true` header

### Handler Module Pattern

Handlers expose:
- `ROUTES`: List of `(method, path, handler)` tuples or aiohttp `RouteTableDef`
- `MIDDLEWARES`: Optional list of middleware functions
- `on_startup(app)`: Optional startup hook
- `on_cleanup(app)`: Optional cleanup hook

Route registry example:
```python
ROUTE_REGISTRY = {
    "route_id": ("POST", "/webhook/EventName", handler_function),
}
```

## Environment Variables

Key variables in `.env` (see `.env.example` for full template):
- `PORT`: Server port (default: 8081)
- `WEBHOOK_HANDLERS`: Comma-separated handler modules (e.g., `handlers.webhooks`, `examples.handlers.*`)
- `WEBHOOK_SECRET`: Shared secret for HMAC validation
- `WEBHOOK_SIGNATURE_HEADER`: Header name for signature (default: `X-Signature`)
- `WEBHOOK_SIGNATURE_ALGO`: Algorithm `sha256` or `sha1` (default: `sha256`)
- `IDEMPOTENCY_ENABLED`: Enable idempotency (default: `true`)
- `IDEMPOTENCY_TTL_SECONDS`: Cache TTL (default: `600`)
- `IDEMPOTENCY_HEADERS`: Headers to check (default: `Idempotency-Key,X-Event-Id`)
- `WEBHOOK_ROUTES_CONFIG`: Path to routes config (default: `config/routes.json`)
- **`GEMINI_API_KEY`**: Google Gemini AI API key for spam detection (get at https://aistudio.google.com/app/apikey)

## Adding New Webhook Handlers

1. Create handler function in `handlers/webhooks.py` or new module
2. Add to `ROUTE_REGISTRY` with unique ID
3. If adding new GHL event, add to `EVENT_NAMES` list
4. Enable route in `config/routes.json` by setting route ID to `true`
5. Access validated request body via `request.get("raw_body")` or `await request.read()`

## Spam Detection

The `InboundMessage` handler integrates Google Gemini AI API for intelligent spam detection with natural language understanding:

### Architecture

- **Async Initialization**: Gemini API is configured during server startup via `initialize_gemini()` hook
  - Validates API key from `GEMINI_API_KEY` environment variable
  - Tests connection by listing available models
  - Stored in `app["gemini_enabled"]` flag for access by all handlers
  - Graceful degradation: if Gemini fails to initialize, webhooks continue working (assumes non-spam)

- **LLM-Powered Detection**: Uses `gemini-2.5-flash` model for semantic analysis
  - Analyzes message content, context, and intent (not just keywords)
  - Returns structured JSON: `{"is_spam": bool, "confidence": 0.0-1.0, "reason": "explanation"}`
  - Prompts model to consider: unsolicited offers, phishing, aggressive marketing, sensationalist language, artificial urgency
  - Considers legitimate: personal messages, professional communication, confirmations, conversation replies
  - Provides detailed reasoning in Portuguese for transparency

- **Robust Error Handling**:
  - Validates payload structure (type, size limit of 10KB)
  - Fail-open strategy: assumes non-spam on API errors
  - Handles JSON parsing errors from LLM responses (strips markdown code blocks)
  - Comprehensive logging with `exc_info=True` for debugging

- **Email-Only Detection**: Spam detection runs ONLY for emails
  - Checks if `messageType` is `EMAIL`, `TYPE_EMAIL`, or `MAIL`
  - WhatsApp, SMS, and other channels skip spam analysis
  - Prevents unnecessary API calls for non-email channels

- **Spam Email Storage**: Emails detected as spam are automatically saved
  - Saved to `data/spam_emails/` directory
  - Each email saved as separate JSON file with timestamp filename (e.g., `20251107_113811_176124.json`)
  - Contains: timestamp, spam_score, confidence, **reason** (from Gemini), message_body, message_type, contact_id, location_id, full_payload
  - Errors in saving don't break webhook processing (fail-gracefully)

- **Color-Coded Console Output**:
  - Red: SPAM EMAIL Detected with confidence % and reasoning
  - Green: Email Legítimo with confidence %
  - Blue: Non-email messages (skipped spam detection)

### Configuration

Obtain free API key at https://aistudio.google.com/app/apikey

Add to `.env`:
```bash
GEMINI_API_KEY=your-gemini-api-key-here
```

**Free Tier Limits**:
- 15 requests/minute
- 1500 requests/day
- Model: gemini-2.5-flash (fast and economical)

### Advantages over Previous ML Approach

**No False Positives with Portuguese**: LLM understands context and language nuances
- Correctly classifies short Portuguese messages like "Certo", "Obrigado"
- No need for threshold tuning or language-specific training
- Semantic understanding vs. keyword matching

**Explainability**: Provides detailed reasoning in Portuguese for every classification
- Transparency for users and debugging
- Helps identify edge cases and improve prompts

**Performance**: ~3-4 seconds per request (API call latency)
- No model loading overhead at startup
- Suitable for webhook processing (async, non-blocking)

## GoHighLevel Event Types

Common webhook events registered in `EVENT_NAMES`:
- Contact events: ContactCreate, ContactUpdate, ContactDelete, ContactTagUpdate
- Conversation: InboundMessage, OutboundMessage, ConversationUnreadUpdate
- Appointments: AppointmentCreate, AppointmentUpdate, AppointmentDelete
- Opportunities: OpportunityCreate, OpportunityUpdate, OpportunityStatusUpdate
- And many more (see handlers/webhooks.py:63-122)

## Token Storage

OAuth tokens saved to:
- `data/agency_token.json`: Agency-level access token
- `data/location_token.json`: Location-level access token

Token structure includes: access_token, refresh_token, user_type, company_id, location_id, scope, expires_at

# Project Overview

This project, `ghl-base`, is a Python utility designed to simplify integrations with the GoHighLevel (GHL) platform. It provides two main functionalities:

1.  **OAuth 2.0 Flow:** A command-line interface (`ghl-oauth`) to guide developers through the GHL OAuth 2.0 process, enabling them to obtain API tokens for their applications.
2.  **Webhook Server:** A flexible and extensible webhook server (`ghl-webhooks`) built with `aiohttp`. This server is designed to receive and process webhook events from GHL, allowing for the development of custom automations and integrations.

The project is built using Python and leverages the `aiohttp` library for asynchronous HTTP handling, `httpx` for making API requests, and `python-dotenv` for managing environment variables.

## Time Awareness Requirement

- Sempre que iniciar uma sessão, execute `python3 scripts/current_time.py`.
- Este script requer internet para consultar o WorldTimeAPI; solicite aprovação de rede quando o sandbox pedir e registre falhas.
- O comando consulta `https://worldtimeapi.org/api/ip`, atualiza `config/current_time.json` e imprime a data/hora reais; cite esse valor antes de executar tarefas.
- Se a saída indicar `system` ou `cached`, mencione o desvio possível e confirme com o usuário o dia correto antes de prosseguir.

## Building and Running

### Prerequisites

*   Python 3.9+
*   `venv` (recommended)

### Installation

1.  **Create and activate a virtual environment:**

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    pip install -e .
    ```

### Running the Webhook Server

The webhook server can be started using the `ghl-webhooks` command. Configuration is managed through environment variables, which can be defined in a `.env` file.

```bash
# Start the server (reads .env automatically)
ghl-webhooks
```

### Running the OAuth Flow

The OAuth flow is initiated using the `ghl-oauth` command. The tool will prompt for the necessary credentials (client ID, client secret) and guide you through the authorization process.

```bash
# Start the OAuth flow
ghl-oauth
```

## Development Conventions

*   **Webhook Handlers:** New webhook handlers can be added by creating Python modules in the `handlers/` directory. Each module should expose a `ROUTES` list, which defines the HTTP method, path, and handler function for each webhook.
*   **Configuration:** The application is configured through environment variables. A `.env` file has been created with the default `PORT` and `WEBHOOK_HANDLERS` variables. The `config/routes.json` file can be used to enable or disable specific webhook routes. By default, all routes are disabled in the `config/routes.json` file. The `InboundMessage` and `OutboundMessage` routes have been enabled for testing purposes.
*   **Code Style:** The code follows standard Python conventions (PEP 8).
*   **Dependencies:** Project dependencies are managed in the `requirements.txt` file.

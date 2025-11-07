# GHL Base — OAuth e Webhooks (aiohttp)

Utilidades base para integrações com o GoHighLevel (LeadConnector):

- CLI para fluxo OAuth: `ghl-oauth`
- Servidor de Webhooks com `aiohttp`: `ghl-webhooks`

> Repositório preparado para desenvolvimento local com `pyproject.toml` e exemplos de handlers.

## Requisitos

- Python 3.9+
- Recomendado: `venv` (ambiente virtual)

## Instalação (dev local)

```bash
# 1) Crie e ative um ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2) Instale o projeto em modo editável
pip install -U pip
pip install -r requirements.txt
pip install -e .

# 3) Configure variáveis de ambiente (opcional)
cp .env.example .env  # edite conforme necessário
```

Os binários de CLI serão expostos como comandos do sistema após a instalação:

- `ghl-oauth`
- `ghl-webhooks`

## Docker / Deploy em VPS

> Requer Docker 24+ e, opcionalmente, Docker Compose v2.

### Build e execução direta

```bash
# Builda a imagem local (usa Python 3.11 slim)
docker build -t ghl-base:latest .

# Executa o servidor (porta padrão 8081) e monta a pasta de dados
docker run -d --name ghl-webhooks \
  --env-file .env \
  -v ghl_data:/app/data \
  -p 8081:8081 \
  ghl-base:latest
```

- O entrypoint (`docker-entrypoint.sh`) roda `python3 scripts/current_time.py` antes do servidor para garantir que os agentes saibam a data real. Se precisar pular (ex.: ambiente offline), exporte `SKIP_TIME_SYNC=1` no container.
- Tokens OAuth e dumps de spam ficam em `/app/data`; mantenha o volume `ghl_data` para não perder arquivos.

### Docker Compose

```bash
docker compose up -d --build
```

O arquivo `docker-compose.yml` incluído:

- monta `ghl_data:/app/data`;
- carrega variáveis de `.env` (copie de `.env.example` antes de subir);
- reinicia automaticamente (`restart: unless-stopped`).

Para executar o fluxo OAuth dentro do container e salvar tokens no mesmo volume:

```bash
docker compose run --rm ghl-webhooks ghl-oauth
```

O comando abre prompts no terminal (stdin/stdout). Após concluir, reinicie o serviço principal se necessário:

```bash
docker compose restart ghl-webhooks
```

## Configuração por ambiente (.env)

Veja o arquivo `./.env.example` para todas as opções. Principais variáveis:

- `PORT`: porta do servidor de webhooks (padrão `8081`).
- `WEBHOOK_HANDLERS`: módulos Python com rotas, separados por vírgula. Aceita sufixo `.*` para auto-carregar submódulos.
  - Ex.: `handlers.webhooks`, `examples.handlers.*`
- Assinatura opcional do corpo (HMAC):
  - `WEBHOOK_SECRET`: segredo compartilhado.
  - `WEBHOOK_SIGNATURE_HEADER`: cabeçalho onde a assinatura é enviada (padrão `X-Signature`).
  - `WEBHOOK_SIGNATURE_ALGO`: algoritmo `sha256` (padrão) ou `sha1`.
- Idempotência em memória:
  - `IDEMPOTENCY_ENABLED` (padrão `true`)
  - `IDEMPOTENCY_TTL_SECONDS` (padrão `600`)
  - `IDEMPOTENCY_HEADERS` (padrão `Idempotency-Key,X-Event-Id`)

## Servidor de Webhooks

Inicie o servidor lendo o `.env` automaticamente (via `python-dotenv`):

```bash
# Dentro do venv e com .env configurado
ghl-webhooks
```

Ou defina variáveis inline:

```bash
WEBHOOK_HANDLERS=handlers.webhooks PORT=8081 ghl-webhooks
```

Rotas embutidas:

- `GET /healthz` — health check básico do servidor.
- Rotas adicionais vêm dos módulos configurados em `WEBHOOK_HANDLERS`.

**Habilitar/Desabilitar Rotas (simples)**

- **Arquivo**: use `config/routes.json` com `{ "routes": { "id_da_rota": true|false } }`.
- **IDs de rota**: definidos no módulo do handler. No exemplo padrão (`handlers/webhooks.py`), existem `health_detail` e `health_basic`.
- **Fallback**: se não houver arquivo, todas as rotas do handler são habilitadas.
- **Variável**: opcionalmente aponte outro caminho com `WEBHOOK_ROUTES_CONFIG`.

Exemplo de handlers de demonstração (neste repositório):

- `examples/handlers/webhooks.py` expõe:
  - `GET /webhook/ping` → retorna `pong`
  - `POST /webhook/echo` → devolve o JSON recebido

Para usar os exemplos:

```bash
WEBHOOK_HANDLERS=examples.handlers.* PORT=8081 ghl-webhooks
```

### Testes rápidos (curl)

Health check:

```bash
curl -i http://localhost:8081/healthz
```

Ping (se usando os examples):

```bash
curl -i http://localhost:8081/webhook/ping
```

Echo com JSON (se usando os examples):

```bash
curl -i -X POST http://localhost:8081/webhook/echo \
  -H 'Content-Type: application/json' \
  -d '{"hello":"world"}'
```

Assinatura HMAC (opcional, se `WEBHOOK_SECRET` estiver definido):

- O servidor valida o corpo com HMAC (`sha256` por padrão) e cabeçalho `X-Signature`.
- São aceitos valores com ou sem prefixo `sha256=`. Ex.: `sha256=<hexdigest>`.

## Escrevendo seus próprios handlers

Crie um módulo e exponha uma lista `ROUTES` com tuplas `(method, path, handler)` ou um `RouteTableDef` do `aiohttp`.
Você também pode fornecer `MIDDLEWARES`, `on_startup(app)` e `on_cleanup(app)`.

Exemplo mínimo (`handlers/webhooks.py`):

```python
from aiohttp import web

async def health_detail(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "ghl-base"})

ROUTES = [
    ("GET", "/webhook/health-detail", health_detail),
]
```

Mais exemplos em `examples/handlers/webhooks.py` (inclui middlewares e startup/cleanup).

## OAuth (LeadConnector / GoHighLevel)

Use o comando `ghl-oauth` para executar o fluxo OAuth localmente:

```bash
ghl-oauth
```

O comando irá solicitar:

- `GHL_CLIENT_ID`
- `GHL_CLIENT_SECRET`
- `Redirect URI` (padrão `http://localhost:8080/oauth/callback` — precisa bater com seu app no Marketplace)
- `Callback server port` (padrão `8080`)

Fluxo resumido:

1. Abre o navegador em `marketplace.gohighlevel.com` para autorizar.
2. Recebe o `code` no callback local (`/oauth/callback`).
3. Troca o `code` por tokens e salva em `data/agency_token.json`.
4. Opcionalmente gera e salva um token de Location em `data/location_token.json` usando `/oauth/locationToken` (requer token de Agência válido).

Dicas:

- O arquivo `.env.example` possui chaves comentadas para `GHL_CLIENT_ID`, `GHL_CLIENT_SECRET` e `REDIRECT_URI`.
- O script imprime um resumo dos tokens e um caminho onde foram salvos.

## Estrutura do projeto

- `src/ghl_base/oauth.py` — CLI de OAuth e utilidades.
- `src/ghl_base/webhook_app.py` — servidor de webhooks (aiohttp) e auto-carga de handlers.
- `handlers/` — exemplo simples de handler incluído no projeto.
- `examples/handlers/` — exemplos mais completos (rotas, middlewares e hooks).
- `.env.example` — exemplo de configuração por ambiente.
- `pyproject.toml` — metadados do projeto e entry points de CLI.

## Problemas comuns

- 401 com assinatura inválida: verifique `WEBHOOK_SECRET`, algoritmo e se o header usa `sha256=<hexdigest>` (ou somente o hexdigest).
- Callback OAuth não dispara: confira se o `Redirect URI` no Marketplace é exatamente o informado no CLI e se a porta local está livre.
- Rotas não aparecem: confirme o valor de `WEBHOOK_HANDLERS` e se o módulo exporta `ROUTES` corretamente.

## Licença

MIT (ver metadados em `pyproject.toml`).

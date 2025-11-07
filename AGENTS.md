# Repository Guidelines

## Project Structure & Module Organization
- `src/ghl_base/` hospeda o servidor `aiohttp` (`webhook_app.py`) e a CLI OAuth (`oauth.py`). Amplie utilidades aqui e exponha APIs públicas via `__init__.py`.
- `handlers/` contém handlers prontos; cada módulo deve declarar `ROUTES` e IDs referenciados em `config/routes.json` para ativar/desativar endpoints.
- `config/` guarda roteamentos e presets, enquanto `data/` armazena tokens (`agency/location_token.json`) e dumps de spam (`data/spam_emails/`). Trate tudo como sigiloso e ignore no Git.
- Dependências vivem em `pyproject.toml`/`requirements.txt`; a instalação editável expõe os CLIs `ghl-webhooks` e `ghl-oauth` durante o desenvolvimento.

## Time Sync Checklist
- Antes de qualquer tarefa, execute `python3 scripts/current_time.py` para sincronizar a data real (usa https://worldtimeapi.org/api/ip e atualiza `config/current_time.json`).
- O script precisa de rede; se o sandbox pedir aprovação, solicite e reporte qualquer falha.
- Sempre mencione a data/hora exibida por esse comando na primeira resposta da sessão; se cair no fallback `system`, peça confirmação do usuário.
- Em ambientes offline, opere com o último cache e registre explicitamente que a informação pode estar desatualizada.

## Build, Test, and Development Commands
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && pip install -e .
WEBHOOK_HANDLERS=handlers.webhooks PORT=8081 ghl-webhooks
GEMINI_API_KEY=xxx ghl-webhooks                         # valida spam com Gemini
WEBHOOK_HANDLERS=examples.handlers.* ghl-webhooks       # carrega exemplos
ghl-oauth                                              # executa fluxo OAuth
python -m pytest -q                                     # execute testes
```
Use `.env` (copiado de `.env.example`) para variáveis e aponte outra rota via `WEBHOOK_ROUTES_CONFIG` quando precisar de toggles específicos.

## Coding Style & Naming Conventions
- Python 3.9+, 4 espaços, imports agrupados por (stdlib, terceiros, internos). Prefira type hints e docstrings sucintas como em `handlers/webhooks.py`.
- Nomine handlers com `snake_case` (`health_detail`) e exponha coleções `ROUTES`, `MIDDLEWARES`, `on_startup`, `on_cleanup` quando aplicável.
- Nunca hardcode segredos; leia com `os.getenv` e mantenha JSONs sensíveis fora dos commits.

## Testing Guidelines
Ainda não há suíte oficial; ao contribuir, crie `tests/` espelhando `src/ghl_base` e `handlers`. Utilize `pytest` com fixtures que simulem `aiohttp` e mocks para Gemini/GoHighLevel. Nomeie arquivos como `test_webhook_app.py`, valide fluxos críticos (assinatura HMAC, idempotência, persistência de spam) e exija `python -m pytest -q` nos PRs.

## Commit & Pull Request Guidelines
- O pacote chegou sem histórico visível; adote Conventional Commits (`feat: add spam persistence middleware`) para manter changelog claro.
- Faça commits pequenos, mensagens no imperativo e referências a issues. PRs devem listar objetivo, passos de validação (`curl http://localhost:8081/healthz`) e prints/logs relevantes.
- Remova artefatos locais (`data/*.json`, `.env`, `venv/`) antes de abrir o PR e descreva qualquer migração de configuração.

## Security & Configuration Tips
- Gere `.env` a partir de `.env.example` e compartilhe segredos via gerenciador seguro. Rotacione `GEMINI_API_KEY`, `GHL_CLIENT_ID` e `WEBHOOK_SECRET` regularmente.
- Dumps de spam podem conter PII; criptografe ou anonimize antes de exportar. Use `git update-index --skip-worktree data/*.json` para garantir que não retornem aos commits.

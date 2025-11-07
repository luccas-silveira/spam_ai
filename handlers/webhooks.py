"""Handlers de Webhook para o servidor aiohttp.

Este módulo foi pensado para ser didático e fácil de adaptar. Ele:

- expõe rotas simples de "health" (checagem de saúde);
- cria automaticamente rotas POST para eventos comuns do GoHighLevel (GHL);
- permite habilitar/desabilitar rotas via um arquivo de configuração JSON;
- funciona em conjunto com middlewares definidos no app (assinatura HMAC, idempotência, etc.).

Como usar no servidor:
- defina `WEBHOOK_HANDLERS=handlers.webhooks` no seu `.env` ou variável de ambiente;
- inicie o servidor com o comando `ghl-webhooks`.

Observação sobre segurança e validação:
- a validação de assinatura HMAC do corpo (quando `WEBHOOK_SECRET` é definido)
  acontece no middleware do app (em `src/ghl_base/webhook_app.py`).
  Aqui nos handlers, nós apenas lemos o corpo que já foi conferido pelo middleware
  através da chave `request["raw_body"]` (quando disponível).
"""

from aiohttp import web
import aiohttp
import os
import json
import logging
import asyncio
from datetime import datetime
import google.generativeai as genai


async def initialize_gemini(app: web.Application):
    """Inicializa a API do Gemini no startup do servidor.

    Configura a API key e valida conexão.
    """
    logging.info("🔄 Inicializando Gemini API para detecção de spam...")

    try:
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            logging.error("❌ GEMINI_API_KEY não encontrada no .env")
            app["gemini_enabled"] = False
            return

        genai.configure(api_key=api_key)

        # Testar conexão listando modelos disponíveis
        models = genai.list_models()
        logging.info(f"✅ Gemini API inicializada com sucesso! Modelos disponíveis: {len(list(models))}")
        app["gemini_enabled"] = True

    except Exception as e:
        logging.error(f"❌ Falha ao inicializar Gemini API: {e}", exc_info=True)
        app["gemini_enabled"] = False


async def detect_spam_with_gemini(message: str) -> tuple[bool, float, str]:
    """Detecta spam usando Gemini API.

    Args:
        message: Corpo do email a ser analisado

    Returns:
        Tupla (is_spam: bool, confidence: float, reason: str)
    """
    try:
        # Usar modelo Gemini 2.5 Flash (gratuito, rápido e eficiente)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""Analise este email e determine se é SPAM ou LEGÍTIMO.

Email: {message}

Responda APENAS com JSON neste formato exato:
{{"is_spam": true ou false, "confidence": 0.0 a 1.0, "reason": "explicação breve em português"}}

Considere SPAM:
- Ofertas não solicitadas
- Phishing ou golpes
- Marketing agressivo
- Linguagem sensacionalista (CLIQUE AQUI, GANHE DINHEIRO, etc)
- Urgência artificial

Considere LEGÍTIMO:
- Mensagens pessoais genuínas
- Comunicação profissional
- Confirmações e agendamentos
- Respostas a conversas anteriores"""

        response = model.generate_content(prompt)

        # Extrair JSON da resposta
        response_text = response.text.strip()

        # Remover markdown code blocks se existirem
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        result = json.loads(response_text)

        is_spam = result.get("is_spam", False)
        confidence = float(result.get("confidence", 0.5))
        reason = result.get("reason", "Sem razão fornecida")

        logging.info(f"Gemini analysis: is_spam={is_spam}, confidence={confidence:.2f}, reason={reason}")

        return is_spam, confidence, reason

    except json.JSONDecodeError as e:
        logging.error(f"❌ Erro ao parsear resposta do Gemini: {e}\nResposta: {response_text}", exc_info=True)
        # Fallback: assumir não-spam em caso de erro de parsing
        return False, 0.0, "Erro ao parsear resposta"
    except Exception as e:
        logging.error(f"❌ Erro na detecção com Gemini: {e}", exc_info=True)
        # Fail-open: assumir não-spam em caso de erro
        return False, 0.0, f"Erro: {str(e)}"


def save_spam_email(message_body: str, spam_score: float, payload: dict, reason: str = "") -> None:
    """Salva email marcado como spam em múltiplos arquivos.

    Salva 3 arquivos em data/spam_emails/:
    1. JSON de resumo com metadados
    2. JSON do payload completo do webhook
    3. HTML do corpo do email

    Args:
        message_body: Corpo do email
        spam_score: Score de spam (0.0 a 1.0)
        payload: Payload completo do webhook para contexto adicional
        reason: Razão da classificação como spam (fornecida pelo Gemini)
    """
    try:
        # Criar diretório se não existir
        spam_dir = "data/spam_emails"
        os.makedirs(spam_dir, exist_ok=True)

        # Gerar nome base único com timestamp
        timestamp = datetime.now()
        base_filename = timestamp.strftime("%Y%m%d_%H%M%S_%f")

        # 1. Salvar JSON de resumo
        summary_filepath = os.path.join(spam_dir, f"{base_filename}_summary.json")
        spam_data = {
            "timestamp": timestamp.isoformat(),
            "spam_score": spam_score,
            "reason": reason,
            "message_type": payload.get("messageType", "Unknown"),
            "contact_id": payload.get("contactId"),
            "location_id": payload.get("locationId"),
            "conversation_id": payload.get("conversationId"),
            "files": {
                "summary": f"{base_filename}_summary.json",
                "webhook": f"{base_filename}_webhook.json",
                "html": f"{base_filename}_body.html"
            }
        }

        with open(summary_filepath, 'w', encoding='utf-8') as f:
            json.dump(spam_data, f, ensure_ascii=False, indent=2)

        # 2. Salvar JSON completo do webhook
        webhook_filepath = os.path.join(spam_dir, f"{base_filename}_webhook.json")
        with open(webhook_filepath, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # 3. Salvar corpo HTML do email
        html_filepath = os.path.join(spam_dir, f"{base_filename}_body.html")
        with open(html_filepath, 'w', encoding='utf-8') as f:
            f.write(message_body)

        logging.info(f"💾 Email de spam salvo:")
        logging.info(f"   - Resumo: {summary_filepath}")
        logging.info(f"   - Webhook: {webhook_filepath}")
        logging.info(f"   - HTML: {html_filepath}")

    except Exception as e:
        logging.error(f"❌ Erro ao salvar email de spam: {e}", exc_info=True)
        # Não propagar erro para não quebrar o fluxo do webhook


def load_access_token() -> str | None:
    """Carrega access token do arquivo OAuth de location.

    Returns:
        Access token ou None se não encontrado/inválido
    """
    try:
        token_path = "data/location_token.json"

        if not os.path.exists(token_path):
            logging.warning(f"⚠️ Arquivo de token não encontrado: {token_path}")
            return None

        with open(token_path, 'r', encoding='utf-8') as f:
            token_data = json.load(f)

        access_token = token_data.get("access_token")

        if not access_token:
            logging.error("❌ access_token não encontrado no arquivo de token")
            return None

        return access_token

    except Exception as e:
        logging.error(f"❌ Erro ao carregar access token: {e}", exc_info=True)
        return None


async def delete_conversation(conversation_id: str) -> bool:
    """Deleta uma conversa do GoHighLevel usando a API.

    Args:
        conversation_id: ID da conversa a ser deletada

    Returns:
        True se deletado com sucesso, False caso contrário
    """
    try:
        access_token = load_access_token()

        if not access_token:
            logging.error("❌ Não foi possível carregar access token para deletar conversa")
            return False

        # Endpoint da API GHL
        url = f"https://services.leadconnectorhq.com/conversations/{conversation_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Version": "2021-07-28"
        }

        # Fazer requisição DELETE
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as response:
                if response.status == 200:
                    logging.info(f"✅ Conversa {conversation_id} deletada com sucesso")
                    return True
                else:
                    response_text = await response.text()
                    logging.error(f"❌ Erro ao deletar conversa {conversation_id}: {response.status} - {response_text}")
                    return False

    except Exception as e:
        logging.error(f"❌ Exceção ao deletar conversa {conversation_id}: {e}", exc_info=True)
        return False


async def health_detail(_request: web.Request) -> web.Response:
    """Retorna um JSON com informações básicas de saúde do serviço.

    Útil para monitoramento e para verificar rapidamente se o servidor
    está de pé e respondendo.
    """
    return web.json_response({"status": "ok", "service": "ghl-base"})


async def health_basic(_request: web.Request) -> web.Response:
    """Retorna um texto simples dizendo "ok".

    Pode ser utilizado como um health check ainda mais enxuto.
    """
    return web.Response(text="ok")


# Registro simples de rotas, onde a chave é um identificador da rota
# e o valor é uma tupla no formato: (método HTTP, caminho, função handler)
#
# Este dicionário serve como a “fonte da verdade” das rotas expostas por este
# módulo. Mais abaixo, existe uma etapa que lê um arquivo de configuração para
# decidir quais IDs de rotas ficam habilitados (ou não) na aplicação final.
ROUTE_REGISTRY = {
    "health_detail": ("GET", "/webhook/health-detail", health_detail),
    "health_basic": ("GET", "/webhook/health", health_basic),
}


# Eventos GHL mais comuns — cada nome abaixo vira uma rota POST dedicada em
# "/webhook/<EventName>". Ex.: "InboundMessage" vira POST "/webhook/InboundMessage".
#
# Se desejar, você pode remover, adicionar ou renomear eventos conforme a sua
# necessidade. Em projetos reais, costuma-se manter aqui somente os eventos que
# o seu produto realmente precisa tratar.
EVENT_NAMES = [
    "AppointmentCreate",
    "AppointmentDelete",
    "AppointmentUpdate",
    "AssociationCreate",
    "AssociationUpdate",
    "AssociationDelete",
    "CampaignStatusUpdate",
    "ContactCreate",
    "ContactDelete",
    "ContactUpdate",
    "ContactDndUpdate",
    "ContactTagUpdate",
    "ObjectCreate",
    "ObjectUpdate",
    "RecordCreate",
    "RecordUpdate",
    "RecordDelete",
    "ConversationUnreadUpdate",
    "InboundMessage",
    "InvoiceCreate",
    "InvoiceUpdate",
    "InvoiceSent",
    "InvoicePaid",
    "InvoicePartiallyPaid",
    "InvoiceVoid",
    "InvoiceDelete",
    "LCEmailStats",
    "LocationCreate",
    "LocationUpdate",
    "NoteCreate",
    "NoteDelete",
    "NoteUpdate",
    "OpportunityCreate",
    "OpportunityDelete",
    "OpportunityUpdate",
    "OpportunityStatusUpdate",
    "OpportunityAssignedToUpdate",
    "OpportunityMonetaryValueUpdate",
    "OutboundMessage",
    "OpportunityStageUpdate",
    "PriceCreate",
    "PriceUpdate",
    "PriceDelete",
    "ProductCreate",
    "ProductUpdate",
    "ProductDelete",
    "RelationCreate",
    "RelationDelete",
    "TaskCreate",
    "TaskDelete",
    "TaskComplete",
    "UserCreate",
    "UserDelete",
    "UserUpdate",
    "OrderCreate",
    "OrderStatusUpdate",
    "SaasPlanCreate",
    "VoiceAiCallEnd",
]


def _make_event_handler(event_name: str):
    """Fábrica de handlers para eventos.

    Dado o nome de um evento, cria e retorna uma função async que:
    - lê o corpo da requisição (preferindo `request["raw_body"]` quando já
      preenchido pelo middleware de assinatura HMAC);
    - tenta desserializar o corpo como JSON (ou retorna um texto bruto em caso
      de falha);
    - registra nos logs a chegada do webhook; e
    - responde um JSON confirmando o recebimento (útil para depuração).
    """

    async def _handler(request: web.Request) -> web.Response:
        # Corpo possivelmente já lido e verificado pelo middleware de assinatura
        body = request.get("raw_body")
        if body is None:
            body = await request.read()

        # Tenta decodificar como JSON; em caso de erro, devolve conteúdo textual
        try:
            payload = json.loads(body.decode() or "null")
        except Exception:
            payload = {"raw": body.decode(errors="ignore")}

        logging.info("Webhook recebido: event=%s path=%s", event_name, request.path)

        if event_name == "InboundMessage":
            # Validação robusta de payload
            message_body = payload.get("body", "")
            message_channel = payload.get("messageType", "Unknown")

            # Validar tipo e tamanho da mensagem
            if not isinstance(message_body, str):
                logging.warning(f"Invalid message body type: {type(message_body)}")
                message_body = str(message_body) if message_body else ""

            if len(message_body) > 10000:  # Limite de 10KB
                logging.warning(f"Message body too large: {len(message_body)} bytes, truncating")
                message_body = message_body[:10000]

            # ⚠️ DETECTOR DE SPAM COM GEMINI: Apenas para EMAILS
            # Verificar se é email antes de processar
            is_email = message_channel.upper() in ["EMAIL", "TYPE_EMAIL", "MAIL"]

            is_spam = False
            spam_confidence = 0.0
            spam_reason = ""

            if is_email:
                # Verificar se Gemini está habilitado
                gemini_enabled = request.app.get("gemini_enabled", False)

                if not gemini_enabled:
                    logging.warning("⚠️ Gemini API não está habilitada, assumindo não-spam")
                else:
                    # Detectar spam com Gemini API
                    try:
                        is_spam, spam_confidence, spam_reason = await detect_spam_with_gemini(message_body)
                        logging.info(f"Gemini detection: is_spam={is_spam}, confidence={spam_confidence:.2f}")

                        # Salvar email se detectado como spam
                        if is_spam:
                            save_spam_email(message_body, spam_confidence, payload, spam_reason)

                            # Deletar conversa do GoHighLevel
                            conversation_id = payload.get("conversationId")
                            if conversation_id:
                                deleted = await delete_conversation(conversation_id)
                                if deleted:
                                    logging.info(f"🗑️ Conversa de spam deletada: {conversation_id}")
                                else:
                                    logging.warning(f"⚠️ Não foi possível deletar conversa: {conversation_id}")
                            else:
                                logging.warning("⚠️ conversationId não encontrado no payload, não foi possível deletar conversa")

                    except Exception as e:
                        logging.error(f"❌ Erro no detector de spam com Gemini: {e}", exc_info=True)
                        # Fail open: em caso de erro, assumir não-spam para não bloquear mensagens
                        is_spam = False
            else:
                logging.debug(f"Ignorando spam detection para canal não-email: {message_channel}")

            # ANSI escape codes for colors
            GREEN = "\033[92m"
            RED = "\033[91m"
            BLUE = "\033[94m"
            YELLOW = "\033[93m"
            RESET = "\033[0m"

            if is_email and is_spam:
                print(f"{RED}📧 SPAM EMAIL Detected ({spam_confidence:.0%}): {message_body}")
                print(f"{YELLOW}   Razão: {spam_reason}{RESET}")
            elif is_email:
                print(f"{GREEN}📧 Email Legítimo ({spam_confidence:.0%}): {message_body}{RESET}")
            else:
                print(f"{BLUE}💬 Mensagem {message_channel} (sem análise de spam): {message_body}{RESET}")

        return web.json_response({
            "ok": True,
            "event": event_name,
            "path": str(request.rel_url),
            "data": payload,
        })

    return _handler


# Registra rotas POST /webhook/<EventName>
for _ev in EVENT_NAMES:
    # Para cada evento conhecido, registramos uma rota POST dedicada que chama
    # o handler gerado acima. Isso facilita isolar a lógica de cada evento.
    ROUTE_REGISTRY[_ev] = ("POST", f"/webhook/{_ev}", _make_event_handler(_ev))


def _load_enabled_route_ids():
    """Carrega a lista de IDs de rotas que devem ficar habilitados.

    A decisão é feita com base em um arquivo JSON (opcional) que pode estar em:
    - caminho apontado por `WEBHOOK_ROUTES_CONFIG` (variável de ambiente);
    - `config/routes.json` (padrão do projeto);
    - `routes.json` (fallback).

    O formato aceito pode ser:
    - objeto simples: `{ "MinhaRota": true, "OutraRota": false }`, ou
    - objeto aninhado: `{ "routes": { "MinhaRota": true, ... } }`.

    Quando não há configuração, o comportamento é permitir TODAS as rotas
    definidas em `ROUTE_REGISTRY`.
    """
    # Ordem de procura: env > config/routes.json > routes.json
    candidates = []
    env_path = (os.getenv("WEBHOOK_ROUTES_CONFIG") or "").strip()
    if env_path:
        candidates.append(env_path)
    candidates.extend(["config/routes.json", "routes.json"])

    cfg = None
    for path in candidates:
        if not path:
            continue
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Permite formato direto {id: bool} ou {"routes": {id: bool}}
                if isinstance(data, dict) and "routes" in data and isinstance(data["routes"], dict):
                    cfg = data["routes"]
                elif isinstance(data, dict):
                    cfg = data
                else:
                    raise ValueError("formato de JSON inválido para rotas")
                logging.info("Rotas: config carregada de %s", path)
            except Exception as e:
                logging.exception("Falha lendo config de rotas em %s: %s", path, e)
                cfg = None
            break

    # Sem config → todas habilitadas
    if cfg is None:
        return set(ROUTE_REGISTRY.keys())

    enabled: set[str] = set()
    for rid in ROUTE_REGISTRY.keys():
        val = cfg.get(rid, True)
        if isinstance(val, dict):
            val = val.get("enabled", True)
        if bool(val):
            enabled.add(rid)
    return enabled


_ENABLED = _load_enabled_route_ids()

"""Lista final de rotas expostas por este módulo.

O servidor (`ghl-webhooks`) irá percorrer `ROUTES` para registrar cada caminho.

Regras aplicadas abaixo:
- somente IDs presentes em `_ENABLED` entram em `ROUTES` (controle por config);
- além do caminho oficial começando com `/webhook/`, criamos um alias
  adicional em `/webhooks/` para tolerar typos e variações (singular/plural).
"""
ROUTES = []
for rid, spec in ROUTE_REGISTRY.items():
    if rid in _ENABLED:
        method, path, handler = spec
        ROUTES.append(spec)
        if path.startswith("/webhook/"):
            # Alias conveniente: também aceite '/webhooks/...'
            ROUTES.append((method, path.replace("/webhook/", "/webhooks/", 1), handler))

disabled = [rid for rid in ROUTE_REGISTRY.keys() if rid not in _ENABLED]
if disabled:
    # Mensagem de log para deixar claro o que ficou de fora.
    logging.info("Rotas desabilitadas: %s", ", ".join(disabled))


# Hook de startup para inicializar Gemini API
# Este hook é automaticamente descoberto e executado por webhook_app.py
on_startup = initialize_gemini

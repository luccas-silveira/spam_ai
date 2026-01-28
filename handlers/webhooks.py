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
from pathlib import Path
import sys

# Adicionar diretório raiz ao path para importar utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import AsyncOpenAI
from utils.two_pass_detector import TwoPassSpamDetector


async def initialize_openai(app: web.Application):
    """Inicializa a API da OpenAI e o sistema Two-Pass no startup do servidor.

    Configura a API key, valida conexão e carrega prompt otimizado.
    """
    logging.info("🔄 Inicializando sistema de detecção de spam...")

    try:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            logging.error("❌ OPENAI_API_KEY não encontrada no .env")
            app["openai_enabled"] = False
            app["spam_detector"] = None
            return

        # Criar cliente async da OpenAI
        client = AsyncOpenAI(api_key=api_key)

        # Testar conexão fazendo uma chamada simples
        try:
            models = await client.models.list()
            logging.info(f"✅ OpenAI API inicializada com sucesso! Modelos disponíveis: {len(models.data)}")
            app["openai_client"] = client
            app["openai_enabled"] = True
        except Exception as test_error:
            logging.error(f"❌ Falha ao validar conexão com OpenAI: {test_error}", exc_info=True)
            app["openai_enabled"] = False
            app["spam_detector"] = None
            return

        # Carregar prompt otimizado
        prompt_path = Path("config/optimized_prompt.txt")
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                optimized_prompt = f.read()
            logging.info(f"✅ Prompt otimizado carregado ({len(optimized_prompt)} chars)")
            app["optimized_prompt"] = optimized_prompt
        else:
            logging.warning(f"⚠️ Prompt otimizado não encontrado em {prompt_path}, usando prompt padrão")
            app["optimized_prompt"] = """Você é um especialista em detecção de spam.
Analise o email e retorne JSON: {"is_spam": bool, "confidence": 0-1, "reason": "explicação", "category": "tipo"}"""

        # Inicializar detector Two-Pass
        detector = TwoPassSpamDetector(openai_client=client)
        app["spam_detector"] = detector
        logging.info("✅ Sistema Two-Pass inicializado (economia estimada: 38%)")

    except Exception as e:
        logging.error(f"❌ Falha ao inicializar sistema de detecção: {e}", exc_info=True)
        app["openai_enabled"] = False
        app["spam_detector"] = None


# Função detect_spam_with_openai removida - agora usa TwoPassSpamDetector


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
        reason: Razão da classificação como spam (fornecida pela OpenAI)
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
    """Carrega PIT token master do .env.

    PIT token não expira e tem todas as permissões quando usado
    com locationId especificado.

    Returns:
        PIT token ou None se não encontrado
    """
    try:
        pit_token = os.getenv("PIT")

        if not pit_token:
            logging.error("❌ PIT token não encontrado no .env")
            return None

        logging.debug("Usando PIT token master do .env")
        return pit_token

    except Exception as e:
        logging.error(f"❌ Erro ao carregar PIT token: {e}", exc_info=True)
        return None


def get_location_id() -> str | None:
    """Retorna Location ID do ambiente.

    Returns:
        Location ID ou None se não encontrado
    """
    # Location ID fixo (do location_token.json)
    return "Wc3wencAfbxKbynASybx"


async def delete_contact(contact_id: str) -> bool:
    """Deleta um contato do GoHighLevel usando PIT token master.

    IMPORTANTE: PIT token requer locationId como query parameter para funcionar.

    Args:
        contact_id: ID do contato a ser deletado

    Returns:
        True se deletado com sucesso, False caso contrário
    """
    try:
        pit_token = load_access_token()
        location_id = get_location_id()

        if not pit_token:
            logging.error("❌ Não foi possível carregar PIT token para deletar contato")
            return False

        if not location_id:
            logging.error("❌ Location ID não configurado")
            return False

        # Endpoint da API GHL com locationId como query parameter
        url = f"https://services.leadconnectorhq.com/contacts/{contact_id}?locationId={location_id}"

        headers = {
            "Authorization": f"Bearer {pit_token}",
            "Version": "2021-07-28"
        }

        # Fazer requisição DELETE
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as response:
                if response.status == 200:
                    logging.info(f"✅ Contato {contact_id} deletado com sucesso (PIT master)")
                    return True
                else:
                    response_text = await response.text()
                    logging.error(f"❌ Erro ao deletar contato {contact_id}: {response.status} - {response_text}")
                    return False

    except Exception as e:
        logging.error(f"❌ Exceção ao deletar contato {contact_id}: {e}", exc_info=True)
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


async def spam_stats(request: web.Request) -> web.Response:
    """Retorna estatísticas do sistema Two-Pass de detecção de spam.

    Útil para monitorar economia e performance.
    """
    detector = request.app.get("spam_detector")

    if not detector:
        return web.json_response({
            "error": "Sistema de detecção não habilitado"
        }, status=503)

    stats = detector.get_stats()
    return web.json_response({
        "status": "ok",
        "two_pass_stats": stats,
        "description": "Estatísticas do sistema Two-Pass de detecção de spam"
    })


# Registro simples de rotas, onde a chave é um identificador da rota
# e o valor é uma tupla no formato: (método HTTP, caminho, função handler)
#
# Este dicionário serve como a "fonte da verdade" das rotas expostas por este
# módulo. Mais abaixo, existe uma etapa que lê um arquivo de configuração para
# decidir quais IDs de rotas ficam habilitados (ou não) na aplicação final.
ROUTE_REGISTRY = {
    "health_detail": ("GET", "/webhook/health-detail", health_detail),
    "health_basic": ("GET", "/webhook/health", health_basic),
    "spam_stats": ("GET", "/webhook/spam-stats", spam_stats),
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

            # ⚠️ DETECTOR DE SPAM TWO-PASS: Apenas para EMAILS
            # Verificar se é email antes de processar
            is_email = message_channel.upper() in ["EMAIL", "TYPE_EMAIL", "MAIL"]

            is_spam = False
            spam_confidence = 0.0
            spam_reason = ""
            detection_method = "none"

            if is_email:
                # Verificar se detector está habilitado
                detector = request.app.get("spam_detector")
                optimized_prompt = request.app.get("optimized_prompt", "")

                if not detector:
                    logging.warning("⚠️ Sistema de detecção não está habilitado, assumindo não-spam")
                else:
                    # Detectar spam com sistema Two-Pass
                    try:
                        # Extrair subject do payload se disponível
                        subject = payload.get("subject", "")
                        if not subject:
                            # Tentar extrair de estruturas alternativas
                            email_data = payload.get("emailData", {})
                            subject = email_data.get("subject", "")

                        result = await detector.detect(message_body, subject, optimized_prompt)

                        is_spam = result.get("is_spam", False)
                        spam_confidence = result.get("confidence", 0.0)
                        spam_reason = result.get("reason", "Sem razão fornecida")
                        detection_method = result.get("method", "unknown")

                        # Log com método de detecção
                        if detection_method == "fast_rule":
                            logging.info(f"✅ Detecção por REGRA: is_spam={is_spam}, confidence={spam_confidence:.2f}")
                        else:
                            logging.info(f"🤖 Detecção por GPT: is_spam={is_spam}, confidence={spam_confidence:.2f}")

                        # Salvar email se detectado como spam
                        if is_spam:
                            save_spam_email(message_body, spam_confidence, payload, spam_reason)

                            # Deletar contato do GoHighLevel
                            contact_id = payload.get("contactId")
                            if contact_id:
                                deleted = await delete_contact(contact_id)
                                if deleted:
                                    logging.info(f"🗑️ Contato de spam deletado: {contact_id}")
                                else:
                                    logging.warning(f"⚠️ Não foi possível deletar contato: {contact_id}")
                            else:
                                logging.warning("⚠️ contactId não encontrado no payload, não foi possível deletar contato")

                        # Logar estatísticas a cada 10 detecções
                        stats = detector.get_stats()
                        if stats["total"] % 10 == 0 and stats["total"] > 0:
                            logging.info(f"📊 Estatísticas Two-Pass: {stats['fast_rules_pct']:.1f}% regras, {stats['gpt_calls_pct']:.1f}% GPT, economia: {stats['estimated_savings_pct']:.1f}%")

                    except Exception as e:
                        logging.error(f"❌ Erro no detector de spam Two-Pass: {e}", exc_info=True)
                        # Fail open: em caso de erro, assumir não-spam para não bloquear mensagens
                        is_spam = False
            else:
                logging.debug(f"Ignorando spam detection para canal não-email: {message_channel}")

            # ANSI escape codes for colors
            GREEN = "\033[92m"
            RED = "\033[91m"
            BLUE = "\033[94m"
            YELLOW = "\033[93m"
            CYAN = "\033[96m"
            RESET = "\033[0m"

            if is_email and is_spam:
                method_icon = "⚡" if detection_method == "fast_rule" else "🤖"
                method_text = "REGRA" if detection_method == "fast_rule" else "GPT"
                print(f"{RED}📧 SPAM EMAIL Detected ({spam_confidence:.0%}) [{method_icon} {method_text}]: {message_body[:100]}")
                print(f"{YELLOW}   Razão: {spam_reason}{RESET}")
            elif is_email:
                method_icon = "⚡" if detection_method == "fast_rule" else "🤖"
                method_text = "REGRA" if detection_method == "fast_rule" else "GPT"
                print(f"{GREEN}📧 Email Legítimo ({spam_confidence:.0%}) [{method_icon} {method_text}]: {message_body[:100]}{RESET}")
            else:
                print(f"{BLUE}💬 Mensagem {message_channel} (sem análise de spam): {message_body[:100]}{RESET}")

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


# Hook de startup para inicializar OpenAI API
# Este hook é automaticamente descoberto e executado por webhook_app.py
on_startup = initialize_openai

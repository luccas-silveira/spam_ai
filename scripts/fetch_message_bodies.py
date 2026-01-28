#!/usr/bin/env python3
"""
Script para buscar o conteúdo completo (body) de mensagens coletadas.

Problema: API /conversations/{id}/messages retorna lista sem campo 'body'.
Solução: Para cada mensagem, fazer GET individual para obter body completo.

Uso:
    python scripts/fetch_message_bodies.py [--limit N]

Saída:
    data/spam_conversations/messages_with_bodies.json
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
import os

import aiohttp
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configurações da API GHL
GHL_API_BASE = "https://services.leadconnectorhq.com"
VERSION_CONVERSATIONS = "2021-04-15"

# Diretórios
INPUT_FILE = Path("data/spam_conversations/messages_by_conversation.json")
OUTPUT_FILE = Path("data/spam_conversations/messages_with_bodies.json")
OUTPUT_DIR = OUTPUT_FILE.parent


class MessageBodyFetcher:
    """Buscador de corpos de mensagens via API GHL."""

    def __init__(self, access_token: str, location_id: str):
        self.access_token = access_token
        self.location_id = location_id
        self.session: Optional[aiohttp.ClientSession] = None

        # Estatísticas
        self.stats = {
            "total_messages": 0,
            "fetched": 0,
            "already_has_body": 0,
            "errors": 0,
            "api_calls": 0
        }

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 0.5s entre requests

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers padrão para chamadas à API."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Version": VERSION_CONVERSATIONS,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def _rate_limit(self):
        """Implementa rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    async def _make_request_with_retry(
        self,
        method: str,
        endpoint: str,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Faz requisição à API com retry exponential backoff."""
        url = f"{GHL_API_BASE}{endpoint}"
        headers = self._get_headers()

        for attempt in range(max_retries):
            try:
                await self._rate_limit()

                self.stats["api_calls"] += 1

                async with self.session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    **kwargs
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:  # Rate limit
                        wait_time = 2 ** attempt  # Exponential backoff
                        logging.warning(f"Rate limit hit, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    elif resp.status == 404:
                        logging.debug(f"Message not found (404): {endpoint}")
                        return None
                    else:
                        error_text = await resp.text()
                        logging.error(f"API Error {resp.status} for {endpoint}: {error_text[:500]}")
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            logging.info(f"Retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            self.stats["errors"] += 1
                            return None
            except asyncio.TimeoutError:
                logging.error(f"Timeout on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    self.stats["errors"] += 1
                    return None
            except Exception as e:
                logging.error(f"Request error: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    self.stats["errors"] += 1
                    return None

        return None

    async def fetch_email_body(
        self,
        email_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Busca o body completo de um email específico.

        Endpoint: GET /conversations/messages/email/{emailId}

        Args:
            email_id: ID do email (de meta.email.messageIds[])

        Returns:
            Email object com body/html field
        """
        endpoint = f"/conversations/messages/email/{email_id}"

        result = await self._make_request_with_retry("GET", endpoint)

        if result:
            # A resposta pode ter diferentes estruturas dependendo da API
            # GHL retorna: {"emailMessage": {...}, "traceId": "..."}
            if "emailMessage" in result:
                return result["emailMessage"]
            elif "email" in result:
                return result["email"]
            else:
                return result

        return None

    async def process_messages(
        self,
        messages_by_conversation: Dict[str, List[Dict[str, Any]]],
        limit: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Processa todas as mensagens e busca seus bodies.

        Args:
            messages_by_conversation: Dicionário {conversation_id: [mensagens]}
            limit: Limite de mensagens para processar (para testes)

        Returns:
            Dicionário {message_id: {body, body_html, attachments, headers, ...}}
        """
        logging.info("🚀 Iniciando busca de message bodies...")

        messages_with_bodies = {}
        processed_count = 0

        # Flatten messages
        all_messages = []
        for conv_id, messages in messages_by_conversation.items():
            for msg in messages:
                all_messages.append({
                    "conversation_id": conv_id,
                    "message": msg
                })

        self.stats["total_messages"] = len(all_messages)

        if limit:
            all_messages = all_messages[:limit]
            logging.info(f"🔬 Modo teste: processando apenas {limit} mensagens")

        logging.info(f"📊 Total de mensagens para processar: {len(all_messages)}")

        # Processar mensagens
        for idx, item in enumerate(all_messages, 1):
            conv_id = item["conversation_id"]
            msg = item["message"]
            msg_id = msg.get("id")

            if not msg_id:
                logging.warning(f"Mensagem sem ID ignorada")
                continue

            # Verificar se já tem body no dado original
            if msg.get("body") or msg.get("bodyHtml") or msg.get("html"):
                logging.debug(f"Mensagem {msg_id} já tem body, pulando...")
                messages_with_bodies[msg_id] = msg
                self.stats["already_has_body"] += 1
                processed_count += 1
                continue

            # Extrair email ID do meta.email.messageIds[]
            meta = msg.get("meta", {})
            email_meta = meta.get("email", {})
            email_ids = email_meta.get("messageIds", [])

            if not email_ids:
                logging.warning(f"[{idx}/{len(all_messages)}] Mensagem {msg_id} não tem email IDs no meta")
                messages_with_bodies[msg_id] = msg
                processed_count += 1
                continue

            # Usar primeiro email ID (geralmente há apenas 1)
            email_id = email_ids[0]
            subject = email_meta.get("subject", "")

            # Buscar body via API
            logging.info(f"[{idx}/{len(all_messages)}] Buscando email {email_id} (subject: {subject[:50]}...)...")

            full_email = await self.fetch_email_body(email_id)

            if full_email:
                # Log estrutura retornada (primeira mensagem apenas)
                if idx == 1:
                    logging.debug(f"  DEBUG: Campos retornados pela API: {list(full_email.keys())}")

                # Combinar dados originais da mensagem com dados do email
                enriched_message = {**msg}
                enriched_message["email_data"] = full_email

                # Extrair body para facilitar acesso
                body = full_email.get("body") or full_email.get("html") or full_email.get("bodyHtml")
                if body:
                    enriched_message["body"] = body

                messages_with_bodies[msg_id] = enriched_message
                self.stats["fetched"] += 1

                # Log de sucesso
                if body:
                    body_preview = body[:100].replace("\n", " ")
                    logging.info(f"  ✅ Body encontrado ({len(body)} chars): {body_preview}...")
                else:
                    logging.warning(f"  ⚠️  API retornou email mas sem campo body/html/bodyHtml")
                    logging.warning(f"     Campos disponíveis: {list(full_email.keys())[:10]}")
            else:
                logging.warning(f"  ❌ Falha ao buscar email {email_id}")
                # Manter dados originais mesmo sem body
                messages_with_bodies[msg_id] = msg

            processed_count += 1

            # Progress tracking (a cada 50 mensagens)
            if processed_count % 50 == 0:
                self._log_progress(processed_count, len(all_messages))

        logging.info("✅ Busca de message bodies concluída!")
        return messages_with_bodies

    def _log_progress(self, current: int, total: int):
        """Log de progresso."""
        pct = (current / total) * 100 if total > 0 else 0
        logging.info(f"📊 Progresso: {current}/{total} ({pct:.1f}%) | "
                    f"Fetched: {self.stats['fetched']} | "
                    f"Errors: {self.stats['errors']}")

    def save_results(self, messages_with_bodies: Dict[str, Dict[str, Any]]):
        """Salva resultados em arquivo JSON."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Adicionar metadados
        output_data = {
            "collected_at": datetime.utcnow().isoformat() + "Z",
            "stats": self.stats,
            "messages": messages_with_bodies
        }

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logging.info(f"💾 Resultados salvos em: {OUTPUT_FILE}")
        logging.info(f"📊 Estatísticas finais:")
        logging.info(f"  - Total mensagens: {self.stats['total_messages']}")
        logging.info(f"  - Fetched via API: {self.stats['fetched']}")
        logging.info(f"  - Já tinham body: {self.stats['already_has_body']}")
        logging.info(f"  - Erros: {self.stats['errors']}")
        logging.info(f"  - API calls: {self.stats['api_calls']}")


async def main():
    """Função principal."""
    # Parse argumentos
    limit = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    # Verificar arquivo de entrada
    if not INPUT_FILE.exists():
        logging.error(f"❌ Arquivo não encontrado: {INPUT_FILE}")
        logging.error("Execute primeiro: python scripts/collect_spam_conversations.py")
        sys.exit(1)

    # Carregar mensagens
    logging.info(f"📂 Carregando mensagens de: {INPUT_FILE}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        messages_by_conversation = json.load(f)

    logging.info(f"✅ {len(messages_by_conversation)} conversações carregadas")

    # Carregar token - priorizar PIT do .env
    access_token = os.getenv("PIT")
    location_id = None

    if access_token:
        logging.info("🔑 Usando PIT do .env")
        # Extrair location_id das mensagens
        for conv_id, messages in messages_by_conversation.items():
            if messages and messages[0].get("locationId"):
                location_id = messages[0]["locationId"]
                break
        if not location_id:
            logging.error("❌ Não foi possível extrair location_id das mensagens")
            sys.exit(1)
    else:
        # Fallback: usar location_token.json
        token_file = Path("data/location_token.json")
        if not token_file.exists():
            logging.error(f"❌ Token não encontrado: {token_file}")
            sys.exit(1)

        with open(token_file, "r") as f:
            token_data = json.load(f)

        access_token = token_data.get("access_token")
        location_id = token_data.get("location_id") or token_data.get("locationId")

        if not access_token or not location_id:
            logging.error("❌ Token ou location_id inválido")
            sys.exit(1)

    logging.info(f"📍 Location ID: {location_id}")

    # Executar coleta
    async with MessageBodyFetcher(access_token, location_id) as fetcher:
        messages_with_bodies = await fetcher.process_messages(
            messages_by_conversation,
            limit=limit
        )

        fetcher.save_results(messages_with_bodies)

    logging.info("🎉 Processo concluído!")


if __name__ == "__main__":
    asyncio.run(main())

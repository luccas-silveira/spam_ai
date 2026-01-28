#!/usr/bin/env python3
"""
Script para coletar conversas marcadas como spam no GoHighLevel.

Segue o plano em plano_coleta.md:
1. Fase A: Buscar contatos com tag "spam"
2. Fase B: Buscar conversas desses contatos
3. Fase C: Baixar mensagens de cada conversa

Uso:
    python scripts/collect_spam_conversations.py

Saída:
    data/spam_conversations/
        contacts_with_spam_tag.json
        conversations_by_contact.json
        messages_by_conversation.json
        collected_at.txt
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import aiohttp

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configurações da API GHL
GHL_API_BASE = "https://services.leadconnectorhq.com"
VERSION_CONTACTS = "2021-07-28"
VERSION_CONVERSATIONS = "2021-04-15"

# Diretório de saída
OUTPUT_DIR = Path("data/spam_conversations")


class GHLspamCollector:
    """Coletor de conversas de spam do GoHighLevel."""

    def __init__(self, access_token: str, location_id: str):
        self.access_token = access_token
        self.location_id = location_id
        self.session: Optional[aiohttp.ClientSession] = None

        # Estatísticas
        self.stats = {
            "contacts_found": 0,
            "conversations_found": 0,
            "messages_collected": 0,
            "errors": 0
        }

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_headers(self, version: str) -> Dict[str, str]:
        """Retorna headers padrão para chamadas à API."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Version": version,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        version: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Faz requisição à API com tratamento de erros."""
        url = f"{GHL_API_BASE}{endpoint}"
        headers = self._get_headers(version)

        logging.debug(f"{method} {url}")

        try:
            async with self.session.request(method, url, headers=headers, **kwargs) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    logging.error(f"API Error {resp.status}: {error_text}")
                    self.stats["errors"] += 1
                    return None
        except Exception as e:
            logging.error(f"Request error: {e}", exc_info=True)
            self.stats["errors"] += 1
            return None

    async def search_contacts_with_tag(self, tag: str = "spam") -> List[Dict[str, Any]]:
        """
        FASE A: Buscar contatos com tag específica.

        Usa GET /contacts/ com filtro por tag.
        """
        logging.info(f"📋 FASE A: Buscando contatos com tag '{tag}'...")

        contacts = []
        seen_contact_ids = set()  # Rastrear IDs já vistos para detectar duplicatas
        start_after = None
        page = 1

        while True:
            logging.info(f"  Página {page}...")

            # Parâmetros da busca
            params = {
                "locationId": self.location_id,
                "limit": 100
            }

            # Paginação
            if start_after:
                params["startAfterId"] = start_after

            result = await self._make_request(
                "GET",
                "/contacts/",
                VERSION_CONTACTS,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            )

            if not result:
                logging.warning(f"  Falha na página {page}, parando busca.")
                break

            # Extrair contatos da resposta
            page_contacts = result.get("contacts", [])

            if not page_contacts:
                logging.info(f"  Nenhum contato encontrado na página {page}. Fim da busca.")
                break

            # Verificar duplicatas (bug da API GoHighLevel)
            page_contact_ids = {c.get("id") for c in page_contacts if c.get("id")}
            duplicates = page_contact_ids & seen_contact_ids

            if duplicates and page > 1:
                logging.warning(f"  ⚠️  API retornou {len(duplicates)} contatos duplicados (bug de paginação).")
                logging.info(f"  🛑 Parando coleta - todos os contatos únicos já foram processados.")
                break

            # DEBUG: Ver quantos contatos vieram na página
            logging.debug(f"  DEBUG: Página {page} retornou {len(page_contacts)} contatos totais")

            # Filtrar contatos que têm a tag desejada
            contacts_with_tag_in_page = 0
            for contact in page_contacts:
                contact_id = contact.get("id")
                if not contact_id:
                    continue

                # Adicionar ao conjunto de IDs vistos
                seen_contact_ids.add(contact_id)

                contact_tags = contact.get("tags", [])
                # DEBUG: Mostrar tags do primeiro contato da primeira página
                if page == 1 and len(contacts) == 0:
                    logging.debug(f"  DEBUG: Exemplo de tags no primeiro contato: {contact_tags}")

                if tag in contact_tags:
                    contacts.append(contact)
                    contacts_with_tag_in_page += 1

            logging.info(f"  ✅ {contacts_with_tag_in_page} contatos com tag '{tag}' na página {page} (de {len(page_contacts)} totais)")

            # Verificar se há próxima página
            meta = result.get("meta", {})
            start_after = meta.get("startAfterId")

            if not start_after:
                logging.info("  Última página alcançada.")
                break

            page += 1

            # Rate limiting (evitar sobrecarga)
            await asyncio.sleep(0.5)

        self.stats["contacts_found"] = len(contacts)
        logging.info(f"✅ FASE A concluída: {len(contacts)} contatos com tag '{tag}'")

        return contacts

    async def search_conversations_for_contact(
        self,
        contact_id: str
    ) -> List[Dict[str, Any]]:
        """
        FASE B: Buscar conversas de um contato específico.

        Usa GET /conversations/search com filtro por contactId.
        """
        conversations = []
        last_message_id = None
        page = 1

        while True:
            # Parâmetros da busca
            params = {
                "locationId": self.location_id,
                "contactId": contact_id,
                "limit": 20
            }

            if last_message_id:
                params["lastMessageId"] = last_message_id

            result = await self._make_request(
                "GET",
                "/conversations/search",
                VERSION_CONVERSATIONS,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            )

            if not result:
                break

            # Extrair conversas
            page_conversations = result.get("conversations", [])

            if not page_conversations:
                break

            conversations.extend(page_conversations)

            # Verificar paginação
            if not result.get("nextPage"):
                break

            last_message_id = result.get("lastMessageId")
            page += 1

            await asyncio.sleep(0.3)

        return conversations

    async def get_conversation_messages(
        self,
        conversation_id: str
    ) -> List[Dict[str, Any]]:
        """
        FASE C: Baixar mensagens de uma conversa.

        Usa GET /conversations/:conversationId/messages.
        Pagina com lastMessageId.
        """
        messages = []
        last_message_id = None
        page = 1

        while True:
            # Parâmetros
            params = {
                "limit": 100
            }

            if last_message_id:
                params["lastMessageId"] = last_message_id

            result = await self._make_request(
                "GET",
                f"/conversations/{conversation_id}/messages",
                VERSION_CONVERSATIONS,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            )

            if not result:
                break

            # Extrair mensagens (estrutura aninhada da API: result["messages"]["messages"])
            messages_obj = result.get("messages", {})
            page_messages = messages_obj.get("messages", [])

            if not page_messages:
                break

            messages.extend(page_messages)

            # Verificar paginação
            if not messages_obj.get("nextPage"):
                break

            last_message_id = messages_obj.get("lastMessageId")
            page += 1

            await asyncio.sleep(0.2)

        return messages

    async def collect_all(self, tag: str = "spam") -> Dict[str, Any]:
        """
        Executa coleta completa:
        - Fase A: Contatos com tag
        - Fase B: Conversas por contato
        - Fase C: Mensagens por conversa
        """
        logging.info("🚀 Iniciando coleta de conversas de spam...")
        start_time = datetime.now()

        # Fase A: Contatos
        contacts = await self.search_contacts_with_tag(tag)

        if not contacts:
            logging.warning("❌ Nenhum contato encontrado com a tag especificada.")
            return {
                "contacts": [],
                "conversations": {},
                "messages": {}
            }

        # Fase B: Conversas por contato
        logging.info(f"\n📞 FASE B: Buscando conversas para {len(contacts)} contatos...")
        conversations_by_contact = {}

        for i, contact in enumerate(contacts, 1):
            contact_id = contact.get("id")
            contact_name = f"{contact.get('firstName') or ''} {contact.get('lastName') or ''}".strip()

            logging.info(f"  [{i}/{len(contacts)}] Contato: {contact_name} ({contact_id})")

            conversations = await self.search_conversations_for_contact(contact_id)

            if conversations:
                conversations_by_contact[contact_id] = conversations
                self.stats["conversations_found"] += len(conversations)
                logging.info(f"    ✅ {len(conversations)} conversas encontradas")
            else:
                logging.info(f"    ℹ️  Nenhuma conversa encontrada")

            await asyncio.sleep(0.5)

        logging.info(f"✅ FASE B concluída: {self.stats['conversations_found']} conversas totais")

        # Fase C: Mensagens por conversa
        logging.info(f"\n💬 FASE C: Baixando mensagens das conversas...")
        messages_by_conversation = {}

        total_conversations = sum(len(convs) for convs in conversations_by_contact.values())
        conv_counter = 0

        for contact_id, conversations in conversations_by_contact.items():
            for conversation in conversations:
                conv_counter += 1
                conversation_id = conversation.get("id")

                logging.info(f"  [{conv_counter}/{total_conversations}] Conversa: {conversation_id}")

                messages = await self.get_conversation_messages(conversation_id)

                if messages:
                    messages_by_conversation[conversation_id] = messages
                    self.stats["messages_collected"] += len(messages)
                    logging.info(f"    ✅ {len(messages)} mensagens coletadas")
                else:
                    logging.info(f"    ℹ️  Nenhuma mensagem encontrada")

                await asyncio.sleep(0.3)

        logging.info(f"✅ FASE C concluída: {self.stats['messages_collected']} mensagens totais")

        # Estatísticas finais
        elapsed = (datetime.now() - start_time).total_seconds()

        logging.info(f"\n{'='*70}")
        logging.info(f"🎉 COLETA CONCLUÍDA!")
        logging.info(f"{'='*70}")
        logging.info(f"⏱️  Tempo total: {elapsed:.1f}s")
        logging.info(f"👥 Contatos com tag '{tag}': {self.stats['contacts_found']}")
        logging.info(f"💬 Conversas encontradas: {self.stats['conversations_found']}")
        logging.info(f"📧 Mensagens coletadas: {self.stats['messages_collected']}")
        logging.info(f"❌ Erros: {self.stats['errors']}")
        logging.info(f"{'='*70}\n")

        return {
            "contacts": contacts,
            "conversations_by_contact": conversations_by_contact,
            "messages_by_conversation": messages_by_conversation,
            "stats": self.stats,
            "collected_at": datetime.now().isoformat(),
            "elapsed_seconds": elapsed
        }


def load_location_token() -> tuple[str, str]:
    """Carrega access token do arquivo location_token.json ou variável de ambiente."""
    import os

    # Tentar token via argumento de linha de comando ou variável de ambiente
    pit_token = os.getenv("GHL_PIT_TOKEN")
    location_id_env = os.getenv("GHL_LOCATION_ID")

    if pit_token:
        logging.info("✅ Usando token PIT da variável de ambiente GHL_PIT_TOKEN")
        if not location_id_env:
            logging.error("❌ GHL_LOCATION_ID não definida")
            logging.error("   Defina: export GHL_LOCATION_ID=seu-location-id")
            sys.exit(1)
        return pit_token, location_id_env

    # Fallback: arquivo location_token.json
    token_path = Path("data/location_token.json")

    if not token_path.exists():
        logging.error(f"❌ Token não encontrado: {token_path}")
        logging.error("Execute 'ghl-oauth' para obter o token primeiro.")
        logging.error("Ou defina variáveis de ambiente:")
        logging.error("  export GHL_PIT_TOKEN=seu-token")
        logging.error("  export GHL_LOCATION_ID=seu-location-id")
        sys.exit(1)

    with open(token_path, 'r', encoding='utf-8') as f:
        token_data = json.load(f)

    access_token = token_data.get("access_token")
    location_id = token_data.get("location_id")

    if not access_token:
        logging.error("❌ access_token não encontrado no arquivo de token")
        sys.exit(1)

    if not location_id:
        logging.error("❌ location_id não encontrado no arquivo de token")
        sys.exit(1)

    # Verificar expiração
    expires_at = token_data.get("expires_at")
    if expires_at:
        try:
            from dateutil import parser
            expiry = parser.isoparse(expires_at)
            now = datetime.now(expiry.tzinfo)

            if now >= expiry:
                logging.error("❌ Token expirado!")
                logging.error(f"   Expirou em: {expires_at}")
                logging.error("   Execute 'ghl-oauth' para renovar o token.")
                sys.exit(1)

            remaining = (expiry - now).total_seconds() / 3600
            logging.info(f"✅ Token válido (expira em {remaining:.1f}h)")
        except Exception:
            logging.warning("⚠️  Não foi possível verificar expiração do token")

    return access_token, location_id


def save_results(data: Dict[str, Any]):
    """Salva resultados da coleta."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Salvar contatos
    contacts_file = OUTPUT_DIR / "contacts_with_spam_tag.json"
    with open(contacts_file, 'w', encoding='utf-8') as f:
        json.dump(data.get("contacts", []), f, indent=2, ensure_ascii=False)
    logging.info(f"💾 Contatos salvos: {contacts_file}")

    # Salvar conversas por contato
    conversations_file = OUTPUT_DIR / "conversations_by_contact.json"
    with open(conversations_file, 'w', encoding='utf-8') as f:
        json.dump(data.get("conversations_by_contact", {}), f, indent=2, ensure_ascii=False)
    logging.info(f"💾 Conversas salvas: {conversations_file}")

    # Salvar mensagens por conversa
    messages_file = OUTPUT_DIR / "messages_by_conversation.json"
    with open(messages_file, 'w', encoding='utf-8') as f:
        json.dump(data.get("messages_by_conversation", {}), f, indent=2, ensure_ascii=False)
    logging.info(f"💾 Mensagens salvas: {messages_file}")

    # Salvar metadados
    metadata = {
        "collected_at": data.get("collected_at", datetime.now().isoformat()),
        "elapsed_seconds": data.get("elapsed_seconds", 0),
        "stats": data.get("stats", {})
    }
    metadata_file = OUTPUT_DIR / "collection_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    logging.info(f"💾 Metadados salvos: {metadata_file}")

    # Timestamp simples
    timestamp_file = OUTPUT_DIR / "collected_at.txt"
    with open(timestamp_file, 'w', encoding='utf-8') as f:
        f.write(data.get("collected_at", datetime.now().isoformat()))

    logging.info(f"\n✅ Todos os arquivos salvos em: {OUTPUT_DIR.resolve()}")


async def main():
    """Função principal."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║          Coletor de Conversas de spam - GoHighLevel                 ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # Carregar token
    access_token, location_id = load_location_token()

    # Confirmar com usuário
    print(f"📍 Location ID: {location_id}")
    print(f"🏷️  Tag a buscar: spam")
    print()

    response = input("Deseja continuar com a coleta? (s/n): ").strip().lower()
    if response != 's':
        print("❌ Coleta cancelada pelo usuário.")
        sys.exit(0)

    print()

    # Executar coleta
    async with GHLspamCollector(access_token, location_id) as collector:
        data = await collector.collect_all(tag="spam")

    # Salvar resultados
    save_results(data)

    print(f"\n✅ Coleta concluída com sucesso!")
    print(f"📂 Verifique os arquivos em: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Coleta interrompida pelo usuário (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        logging.error(f"❌ Erro fatal: {e}", exc_info=True)
        sys.exit(1)

#!/usr/bin/env python3
"""
Coleta paralela de spam - 3 tokens coletando páginas diferentes da mesma location.
Token 1: páginas 1, 4, 7, 10...
Token 2: páginas 2, 5, 8, 11...
Token 3: páginas 3, 6, 9, 12...
"""

import asyncio
import aiohttp
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Token %(name)s] - %(message)s'
)

LOCATION_ID = "Wc3wencAfbxKbynASybx"
VERSION_CONTACTS = "2021-07-28"
VERSION_CONVERSATIONS = "2021-04-15"


async def make_request(session: aiohttp.ClientSession, token: str, method: str, path: str, version: str, params: dict = None) -> dict:
    """Faz request para API GHL."""
    url = f"https://services.leadconnectorhq.com{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Version": version,
        "Accept": "application/json"
    }

    async with session.request(method, url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
        if response.status == 200:
            return await response.json()
        return None


async def get_contacts_page(session: aiohttp.ClientSession, token: str, page_num: int, start_after_id: str = None, start_after: int = None) -> tuple:
    """Busca uma página específica de contatos."""
    params = {
        "locationId": LOCATION_ID,
        "limit": 100
    }

    if start_after_id and start_after:
        params["startAfterId"] = start_after_id
        params["startAfter"] = start_after

    result = await make_request(session, token, "GET", "/contacts/", VERSION_CONTACTS, params)

    if not result:
        return [], None, None

    contacts = result.get("contacts", [])
    meta = result.get("meta", {})
    next_start_id = meta.get("startAfterId")
    next_start = meta.get("startAfter")

    return contacts, next_start_id, next_start


async def get_conversations_for_contact(session: aiohttp.ClientSession, token: str, contact_id: str) -> list:
    """Busca conversas de um contato."""
    params = {
        "locationId": LOCATION_ID,
        "contactId": contact_id,
        "limit": 20
    }

    result = await make_request(session, token, "GET", "/conversations/search", VERSION_CONVERSATIONS, params)

    if not result:
        return []

    return result.get("conversations", [])


async def get_messages_for_conversation(session: aiohttp.ClientSession, token: str, conversation_id: str) -> list:
    """Busca mensagens de uma conversa."""
    params = {"limit": 100}

    result = await make_request(session, token, "GET", f"/conversations/{conversation_id}/messages", VERSION_CONVERSATIONS, params)

    if not result:
        return []

    messages_obj = result.get("messages", {})
    return messages_obj.get("messages", [])


async def worker(token: str, token_id: int, offset: int, total_workers: int) -> Dict[str, Any]:
    """
    Worker que coleta páginas específicas.

    Args:
        token: Token PIT
        token_id: ID do worker (1, 2, 3)
        offset: Offset inicial (0, 1, 2)
        total_workers: Total de workers (3)
    """
    logger = logging.getLogger(str(token_id))
    logger.info(f"Iniciando - pegará páginas {offset+1}, {offset+1+total_workers}, {offset+1+total_workers*2}...")

    contacts_collected = []
    conversations_by_contact = {}
    messages_by_conversation = {}
    seen_contact_ids = set()

    async with aiohttp.ClientSession() as session:
        start_after_id = None
        start_after = None

        # Navegar até a página inicial deste worker (pular offset páginas)
        for i in range(offset):
            _, start_after_id, start_after = await get_contacts_page(session, token, i + 1, start_after_id, start_after)
            if not start_after_id:
                logger.warning(f"Acabaram as páginas antes de chegar na página inicial {offset+1}")
                return {
                    "token_id": token_id,
                    "contacts": [],
                    "conversations_by_contact": {},
                    "messages_by_conversation": {},
                    "stats": {"contacts_found": 0, "conversations_found": 0, "messages_collected": 0}
                }
            await asyncio.sleep(0.2)

        # Agora processar páginas com stride de total_workers
        page_count = 0
        while page_count < 500:  # Limite de segurança
            current_page = offset + 1 + (page_count * total_workers)

            # Buscar página atual
            page_contacts, next_start_id, next_start = await get_contacts_page(session, token, current_page, start_after_id, start_after)

            if not page_contacts:
                logger.info(f"Fim das páginas (página {current_page} vazia)")
                break

            # Verificar duplicatas
            page_ids = {c.get("id") for c in page_contacts if c.get("id")}
            duplicates = page_ids & seen_contact_ids

            if duplicates:
                logger.warning(f"Duplicatas detectadas na página {current_page} ({len(duplicates)}/{len(page_ids)})")
                break

            logger.info(f"Processando página {current_page} ({len(page_contacts)} contatos)")

            # Identificar contatos spam
            spam_contacts = []
            for contact in page_contacts:
                contact_id = contact.get("id")
                if not contact_id:
                    continue

                seen_contact_ids.add(contact_id)

                if "spam" in contact.get("tags", []):
                    spam_contacts.append(contact)
                    contacts_collected.append(contact)

            if spam_contacts:
                logger.info(f"  → {len(spam_contacts)} contatos spam na página {current_page}")

                # Buscar conversas em paralelo
                conv_tasks = [get_conversations_for_contact(session, token, c.get("id")) for c in spam_contacts]
                conv_results = await asyncio.gather(*conv_tasks)

                # Processar conversas
                for contact, conversations in zip(spam_contacts, conv_results):
                    if conversations:
                        contact_id = contact.get("id")
                        conversations_by_contact[contact_id] = conversations

                        # Buscar mensagens em paralelo
                        msg_tasks = [get_messages_for_conversation(session, token, conv.get("id")) for conv in conversations]
                        msg_results = await asyncio.gather(*msg_tasks)

                        for conv, messages in zip(conversations, msg_results):
                            if messages:
                                messages_by_conversation[conv.get("id")] = messages

            if not next_start_id:
                logger.info(f"Fim da paginação na página {current_page}")
                break

            # Pular (total_workers - 1) páginas para chegar na próxima página deste worker
            start_after_id = next_start_id
            start_after = next_start

            for _ in range(total_workers - 1):
                _, start_after_id, start_after = await get_contacts_page(session, token, 0, start_after_id, start_after)
                if not start_after_id:
                    logger.info(f"Fim da paginação ao pular páginas")
                    break
                await asyncio.sleep(0.2)

            if not start_after_id:
                break

            page_count += 1
            await asyncio.sleep(0.2)

    logger.info(f"Finalizado: {len(contacts_collected)} contatos, {len(conversations_by_contact)} conversas, {sum(len(m) for m in messages_by_conversation.values())} mensagens")

    return {
        "token_id": token_id,
        "contacts": contacts_collected,
        "conversations_by_contact": conversations_by_contact,
        "messages_by_conversation": messages_by_conversation,
        "stats": {
            "contacts_found": len(contacts_collected),
            "conversations_found": len(conversations_by_contact),
            "messages_collected": sum(len(m) for m in messages_by_conversation.values())
        }
    }


async def main():
    """Executa coleta paralela com 3 tokens."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║          Coleta PARALELA - 3 Tokens Simultâneos                     ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    tokens = [
        "pit-b3d6fd3f-2b7d-4c85-981b-8772d97f4597",
        "pit-32b169d1-c26e-4b47-a20e-889f92ff5df4",
        "pit-58feffd8-dd00-4fbe-97e8-f809abb6a15b",
    ]

    print(f"📍 Location ID: {LOCATION_ID}")
    print(f"🏷️  Tag: spam")
    print(f"⚡ Workers: 3 em paralelo\n")

    start_time = datetime.now()

    # Criar tasks
    tasks = [
        worker(tokens[0], 1, 0, 3),
        worker(tokens[1], 2, 1, 3),
        worker(tokens[2], 3, 2, 3),
    ]

    # Executar em paralelo
    results = await asyncio.gather(*tasks)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Agregar resultados
    all_contacts = []
    all_conversations = {}
    all_messages = {}

    for result in results:
        all_contacts.extend(result["contacts"])
        all_conversations.update(result["conversations_by_contact"])
        all_messages.update(result["messages_by_conversation"])

    # Salvar resultados
    output_dir = Path("data/spam_conversations")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "contacts_with_spam_tag.json", 'w', encoding='utf-8') as f:
        json.dump(all_contacts, f, indent=2, ensure_ascii=False)

    with open(output_dir / "conversations_by_contact.json", 'w', encoding='utf-8') as f:
        json.dump(all_conversations, f, indent=2, ensure_ascii=False)

    with open(output_dir / "messages_by_conversation.json", 'w', encoding='utf-8') as f:
        json.dump(all_messages, f, indent=2, ensure_ascii=False)

    metadata = {
        "collected_at": datetime.now().isoformat(),
        "elapsed_seconds": elapsed,
        "parallel_workers": 3,
        "stats": {
            "contacts_found": len(all_contacts),
            "conversations_found": len(all_conversations),
            "messages_collected": sum(len(m) for m in all_messages.values())
        }
    }

    with open(output_dir / "collection_metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*70}")
    print(f"🎉 COLETA PARALELA CONCLUÍDA!")
    print(f"{'='*70}")
    print(f"⏱️  Tempo total: {elapsed:.1f}s")
    print(f"👥 Contatos: {len(all_contacts)}")
    print(f"💬 Conversas: {len(all_conversations)}")
    print(f"📧 Mensagens: {sum(len(m) for m in all_messages.values())}")
    print(f"📂 Salvos em: {output_dir.resolve()}")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())

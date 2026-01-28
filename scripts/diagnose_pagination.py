#!/usr/bin/env python3
"""
Script de diagnóstico para investigar o problema de contagem nas páginas.
Busca as primeiras 3 páginas e mostra detalhes sobre os contatos retornados.
"""

import os
import sys
import asyncio
import aiohttp
import json
from typing import Dict, Any


async def fetch_page(session: aiohttp.ClientSession, location_id: str, token: str, start_after: str = None) -> Dict[str, Any]:
    """Busca uma página de contatos da API GHL."""
    url = f"https://services.leadconnectorhq.com/contacts/"

    headers = {
        "Authorization": f"Bearer {token}",
        "Version": "2021-07-28",
        "Accept": "application/json"
    }

    params = {
        "locationId": location_id,
        "limit": 100
    }

    if start_after:
        params["startAfterId"] = start_after

    async with session.get(url, headers=headers, params=params) as response:
        if response.status == 200:
            return await response.json()
        else:
            print(f"❌ Erro na API: {response.status}")
            text = await response.text()
            print(f"Resposta: {text}")
            return None


async def diagnose():
    """Executa o diagnóstico das páginas."""
    # Obter credenciais
    pit_token = os.getenv("GHL_PIT_TOKEN")
    location_id = os.getenv("GHL_LOCATION_ID")

    if not pit_token or not location_id:
        print("❌ Erro: Defina GHL_PIT_TOKEN e GHL_LOCATION_ID nas variáveis de ambiente")
        sys.exit(1)

    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║            Diagnóstico de Paginação - GoHighLevel                   ║")
    print("╚══════════════════════════════════════════════════════════════════════╝\n")

    async with aiohttp.ClientSession() as session:
        start_after = None
        all_contact_ids = set()

        for page_num in range(1, 4):  # Buscar apenas 3 páginas
            print(f"\n{'='*70}")
            print(f"PÁGINA {page_num}")
            print('='*70)

            result = await fetch_page(session, location_id, pit_token, start_after)

            if not result:
                break

            contacts = result.get("contacts", [])

            print(f"\n📊 Total de contatos retornados: {len(contacts)}")

            # Coletar IDs dos contatos
            page_contact_ids = [c.get("id") for c in contacts if c.get("id")]
            print(f"📊 IDs de contatos únicos nesta página: {len(set(page_contact_ids))}")

            # Verificar duplicatas DENTRO da página
            if len(page_contact_ids) != len(set(page_contact_ids)):
                duplicates = [cid for cid in page_contact_ids if page_contact_ids.count(cid) > 1]
                print(f"⚠️  DUPLICATAS DENTRO DA PÁGINA: {set(duplicates)}")

            # Verificar duplicatas ENTRE páginas
            duplicates_across_pages = set(page_contact_ids) & all_contact_ids
            if duplicates_across_pages:
                print(f"⚠️  DUPLICATAS COM PÁGINAS ANTERIORES: {len(duplicates_across_pages)} contatos")
                print(f"    Primeiros 5 IDs duplicados: {list(duplicates_across_pages)[:5]}")

            all_contact_ids.update(page_contact_ids)

            # Analisar tags
            print(f"\n🏷️  Análise de tags:")
            all_tags = {}
            contacts_with_spam_tag = []

            for contact in contacts:
                contact_id = contact.get("id")
                contact_tags = contact.get("tags", [])

                # Contar ocorrências de cada tag
                for tag in contact_tags:
                    all_tags[tag] = all_tags.get(tag, 0) + 1

                # Verificar tag 'spam' (case-insensitive)
                if "spam" in [t.lower() for t in contact_tags]:
                    contacts_with_spam_tag.append({
                        "id": contact_id,
                        "tags": contact_tags,
                        "name": f"{contact.get('firstName') or ''} {contact.get('lastName') or ''}".strip()
                    })

            print(f"   Total de tags únicas encontradas: {len(all_tags)}")
            print(f"   Top 10 tags mais comuns:")
            sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
            for tag, count in sorted_tags[:10]:
                print(f"      - '{tag}': {count} contatos")

            print(f"\n🎯 Contatos com tag 'spam' (case-insensitive): {len(contacts_with_spam_tag)}")

            if contacts_with_spam_tag:
                print(f"   Primeiros 3 exemplos:")
                for contact in contacts_with_spam_tag[:3]:
                    print(f"      - ID: {contact['id']}")
                    print(f"        Nome: {contact['name']}")
                    print(f"        Tags: {contact['tags']}")

            # Mostrar primeiros e últimos IDs da página
            print(f"\n📝 Primeiros 3 IDs: {page_contact_ids[:3]}")
            print(f"📝 Últimos 3 IDs: {page_contact_ids[-3:]}")

            # Obter startAfterId para próxima página
            meta = result.get("meta", {})
            start_after = meta.get("startAfterId")

            if start_after:
                print(f"\n➡️  startAfterId para próxima página: {start_after}")
            else:
                print(f"\n🏁 Não há próxima página (startAfterId ausente)")
                break

    print(f"\n\n{'='*70}")
    print(f"RESUMO GERAL")
    print('='*70)
    print(f"Total de contatos únicos coletados em {page_num} páginas: {len(all_contact_ids)}")
    print(f"Esperado (sem duplicatas): {page_num * 100}")

    if len(all_contact_ids) < page_num * 100:
        print(f"⚠️  PROBLEMA DETECTADO: Há duplicatas entre páginas!")


if __name__ == "__main__":
    asyncio.run(diagnose())

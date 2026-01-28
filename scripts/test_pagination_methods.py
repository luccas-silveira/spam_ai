#!/usr/bin/env python3
"""
Testa diferentes métodos de paginação da API GHL.
"""

import asyncio
import aiohttp
import json
import os


TOKEN = "pit-b3d6fd3f-2b7d-4c85-981b-8772d97f4597"
LOCATION_ID = "Wc3wencAfbxKbynASybx"


async def test_method_1_startAfterId():
    """Método atual: usando startAfterId."""
    print("\n" + "="*70)
    print("TESTE 1: Paginação com startAfterId (método atual)")
    print("="*70)

    async with aiohttp.ClientSession() as session:
        url = "https://services.leadconnectorhq.com/contacts/"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Version": "2021-07-28",
            "Accept": "application/json"
        }

        # Página 1
        params = {"locationId": LOCATION_ID, "limit": 10}
        async with session.get(url, headers=headers, params=params) as response:
            page1 = await response.json()
            print(f"\nPágina 1:")
            print(f"  Status: {response.status}")
            print(f"  Contatos: {len(page1.get('contacts', []))}")
            if page1.get('contacts'):
                print(f"  Primeiro ID: {page1['contacts'][0]['id']}")
                print(f"  Último ID: {page1['contacts'][-1]['id']}")
            print(f"  meta.startAfterId: {page1.get('meta', {}).get('startAfterId')}")
            print(f"  meta.startAfter: {page1.get('meta', {}).get('startAfter')}")
            print(f"  meta.nextPageUrl: {page1.get('meta', {}).get('nextPageUrl')}")

        # Página 2 usando startAfterId
        start_after_id = page1.get('meta', {}).get('startAfterId')
        if start_after_id:
            params = {"locationId": LOCATION_ID, "limit": 10, "startAfterId": start_after_id}
            async with session.get(url, headers=headers, params=params) as response:
                page2 = await response.json()
                print(f"\nPágina 2 (com startAfterId={start_after_id}):")
                print(f"  Status: {response.status}")
                print(f"  Contatos: {len(page2.get('contacts', []))}")
                if page2.get('contacts'):
                    print(f"  Primeiro ID: {page2['contacts'][0]['id']}")
                    print(f"  Último ID: {page2['contacts'][-1]['id']}")

                    # Verificar se são os mesmos IDs
                    page1_ids = {c['id'] for c in page1['contacts']}
                    page2_ids = {c['id'] for c in page2['contacts']}
                    overlap = page1_ids & page2_ids
                    print(f"  IDs duplicados com página 1: {len(overlap)}/{len(page2_ids)}")


async def test_method_2_startAfter():
    """Teste: usando startAfter (sem Id)."""
    print("\n" + "="*70)
    print("TESTE 2: Paginação com startAfter (sem Id)")
    print("="*70)

    async with aiohttp.ClientSession() as session:
        url = "https://services.leadconnectorhq.com/contacts/"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Version": "2021-07-28",
            "Accept": "application/json"
        }

        # Página 1
        params = {"locationId": LOCATION_ID, "limit": 10}
        async with session.get(url, headers=headers, params=params) as response:
            page1 = await response.json()

        # Página 2 usando último ID como startAfter
        last_id = page1['contacts'][-1]['id']
        params = {"locationId": LOCATION_ID, "limit": 10, "startAfter": last_id}
        async with session.get(url, headers=headers, params=params) as response:
            page2 = await response.json()
            print(f"\nUsando startAfter={last_id}:")
            print(f"  Status: {response.status}")
            print(f"  Contatos: {len(page2.get('contacts', []))}")
            if page2.get('contacts'):
                page1_ids = {c['id'] for c in page1['contacts']}
                page2_ids = {c['id'] for c in page2['contacts']}
                overlap = page1_ids & page2_ids
                print(f"  IDs duplicados com página 1: {len(overlap)}/{len(page2_ids)}")


async def test_method_3_query_param():
    """Teste: usando query ou outros parâmetros."""
    print("\n" + "="*70)
    print("TESTE 3: Outros parâmetros de paginação")
    print("="*70)

    async with aiohttp.ClientSession() as session:
        url = "https://services.leadconnectorhq.com/contacts/"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Version": "2021-07-28",
            "Accept": "application/json"
        }

        # Tentar com offset
        print("\nTestando com offset=10:")
        params = {"locationId": LOCATION_ID, "limit": 10, "offset": 10}
        async with session.get(url, headers=headers, params=params) as response:
            result = await response.json()
            print(f"  Status: {response.status}")
            if response.status == 200:
                print(f"  Contatos: {len(result.get('contacts', []))}")
            else:
                print(f"  Erro: {result}")

        # Tentar com page
        print("\nTestando com page=2:")
        params = {"locationId": LOCATION_ID, "limit": 10, "page": 2}
        async with session.get(url, headers=headers, params=params) as response:
            result = await response.json()
            print(f"  Status: {response.status}")
            if response.status == 200:
                print(f"  Contatos: {len(result.get('contacts', []))}")
            else:
                print(f"  Erro: {result}")


async def test_method_4_search_endpoint():
    """Teste: usando endpoint /contacts/search."""
    print("\n" + "="*70)
    print("TESTE 4: Endpoint /contacts/search")
    print("="*70)

    async with aiohttp.ClientSession() as session:
        url = "https://services.leadconnectorhq.com/contacts/search"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Version": "2021-07-28",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Página 1
        body = {
            "locationId": LOCATION_ID,
            "limit": 10
        }
        async with session.post(url, headers=headers, json=body) as response:
            print(f"\nPágina 1 (POST /contacts/search):")
            print(f"  Status: {response.status}")
            if response.status == 200:
                page1 = await response.json()
                print(f"  Contatos: {len(page1.get('contacts', []))}")
                if page1.get('contacts'):
                    print(f"  Primeiro ID: {page1['contacts'][0]['id']}")
                    print(f"  Response keys: {list(page1.keys())}")
            else:
                text = await response.text()
                print(f"  Erro: {text}")


async def test_method_5_inspect_response():
    """Inspecionar completamente a resposta da API."""
    print("\n" + "="*70)
    print("TESTE 5: Inspeção completa da resposta")
    print("="*70)

    async with aiohttp.ClientSession() as session:
        url = "https://services.leadconnectorhq.com/contacts/"
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Version": "2021-07-28",
            "Accept": "application/json"
        }

        params = {"locationId": LOCATION_ID, "limit": 5}
        async with session.get(url, headers=headers, params=params) as response:
            result = await response.json()
            print(f"\nResposta completa da API:")
            print(json.dumps(result, indent=2))


async def test_method_6_different_versions():
    """Teste: versões diferentes da API."""
    print("\n" + "="*70)
    print("TESTE 6: Versões diferentes da API")
    print("="*70)

    versions = ["2021-07-28", "2021-04-15", "2020-10-06"]

    async with aiohttp.ClientSession() as session:
        url = "https://services.leadconnectorhq.com/contacts/"

        for version in versions:
            headers = {
                "Authorization": f"Bearer {TOKEN}",
                "Version": version,
                "Accept": "application/json"
            }

            params = {"locationId": LOCATION_ID, "limit": 5}
            async with session.get(url, headers=headers, params=params) as response:
                print(f"\nVersão {version}:")
                print(f"  Status: {response.status}")
                if response.status == 200:
                    result = await response.json()
                    print(f"  Contatos: {len(result.get('contacts', []))}")
                    print(f"  Keys na resposta: {list(result.keys())}")
                    if 'meta' in result:
                        print(f"  Keys em meta: {list(result['meta'].keys())}")


async def main():
    """Executa todos os testes."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║          Teste de Métodos de Paginação - GHL API                    ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    await test_method_1_startAfterId()
    await test_method_2_startAfter()
    await test_method_3_query_param()
    await test_method_4_search_endpoint()
    await test_method_5_inspect_response()
    await test_method_6_different_versions()

    print("\n" + "="*70)
    print("TESTES CONCLUÍDOS")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())

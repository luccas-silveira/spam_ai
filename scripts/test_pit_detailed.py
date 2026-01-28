#!/usr/bin/env python3
"""
Teste detalhado do PIT token master.

Testa diferentes endpoints e headers para diagnosticar o problema.
"""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv
import json

load_dotenv()


async def test_endpoint(name: str, method: str, url: str, headers: dict, params: dict = None, data: dict = None):
    """Testa um endpoint específico."""
    print(f"\n{'─'*80}")
    print(f"🧪 Testando: {name}")
    print(f"   Método: {method}")
    print(f"   URL: {url}")
    print(f"   Headers: {json.dumps({k: v[:20]+'...' if len(v) > 20 else v for k, v in headers.items()}, indent=6)}")
    if params:
        print(f"   Params: {params}")

    try:
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers, params=params) as response:
                    return await handle_response(response, name)
            elif method == "POST":
                async with session.post(url, headers=headers, json=data) as response:
                    return await handle_response(response, name)
            elif method == "DELETE":
                async with session.delete(url, headers=headers) as response:
                    return await handle_response(response, name)
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


async def handle_response(response, name):
    """Processa resposta da API."""
    status = response.status

    if status == 200:
        try:
            data = await response.json()
            print(f"   ✅ Sucesso (200)")

            # Mostrar estrutura da resposta
            if isinstance(data, dict):
                keys = list(data.keys())[:5]
                print(f"   Dados retornados: {keys}")
                if 'total' in data:
                    print(f"   Total: {data.get('total')}")

            return True
        except:
            text = await response.text()
            print(f"   ✅ Sucesso (200) - Resposta: {text[:100]}")
            return True

    elif status == 401:
        text = await response.text()
        print(f"   ❌ Não autorizado (401)")
        print(f"   Resposta: {text[:200]}")
        return False

    elif status == 403:
        text = await response.text()
        print(f"   ❌ Proibido (403)")
        print(f"   Resposta: {text[:200]}")
        return False

    elif status == 404:
        print(f"   ⚠️ Não encontrado (404) - Endpoint ou recurso não existe")
        return False

    else:
        text = await response.text()
        print(f"   ⚠️ Status {status}")
        print(f"   Resposta: {text[:200]}")
        return False


async def main():
    """Função principal."""
    print("="*80)
    print("🔍 TESTE DETALHADO DO PIT TOKEN MASTER")
    print("="*80)

    pit = os.getenv("PIT")

    if not pit:
        print("\n❌ PIT não encontrado no .env")
        return

    print(f"\n✅ PIT encontrado: {pit[:20]}...")

    # Diferentes combinações de headers para testar
    headers_variants = [
        {
            "name": "Headers Padrão (Version 2021-07-28)",
            "headers": {
                "Authorization": f"Bearer {pit}",
                "Version": "2021-07-28",
                "Content-Type": "application/json"
            }
        },
        {
            "name": "Headers sem Version",
            "headers": {
                "Authorization": f"Bearer {pit}",
                "Content-Type": "application/json"
            }
        },
        {
            "name": "Headers com Version antiga (2021-04-15)",
            "headers": {
                "Authorization": f"Bearer {pit}",
                "Version": "2021-04-15",
                "Content-Type": "application/json"
            }
        }
    ]

    # Endpoints para testar
    endpoints = [
        {
            "name": "Listar Locations",
            "method": "GET",
            "url": "https://services.leadconnectorhq.com/locations/",
            "params": {"limit": 1}
        },
        {
            "name": "Listar Contacts",
            "method": "GET",
            "url": "https://services.leadconnectorhq.com/contacts/",
            "params": {"limit": 1}
        },
        {
            "name": "Listar Conversations",
            "method": "GET",
            "url": "https://services.leadconnectorhq.com/conversations/search",
            "params": {"limit": 1}
        },
        {
            "name": "User Info (me)",
            "method": "GET",
            "url": "https://services.leadconnectorhq.com/users/",
            "params": {}
        }
    ]

    print("\n" + "="*80)
    print("TESTANDO DIFERENTES COMBINAÇÕES DE HEADERS E ENDPOINTS")
    print("="*80)

    results = {}

    # Testar cada endpoint com cada variante de headers
    for header_variant in headers_variants:
        print(f"\n{'═'*80}")
        print(f"📋 {header_variant['name']}")
        print(f"{'═'*80}")

        results[header_variant['name']] = {}

        for endpoint in endpoints:
            success = await test_endpoint(
                name=endpoint['name'],
                method=endpoint['method'],
                url=endpoint['url'],
                headers=header_variant['headers'],
                params=endpoint.get('params')
            )
            results[header_variant['name']][endpoint['name']] = success
            await asyncio.sleep(0.5)  # Rate limiting

    # Resumo
    print("\n" + "="*80)
    print("📊 RESUMO DOS TESTES")
    print("="*80)

    for header_name, endpoints_results in results.items():
        print(f"\n{header_name}:")
        for endpoint_name, success in endpoints_results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {endpoint_name}")

    # Verificar se algum funcionou
    any_success = any(any(endpoints.values()) for endpoints in results.values())

    if any_success:
        print("\n✅ SUCESSO! PIT token está funcionando em alguns endpoints.")
        print("   Identifique acima qual combinação funcionou.")
    else:
        print("\n❌ NENHUM ENDPOINT FUNCIONOU")
        print("   Possíveis causas:")
        print("   1. PIT token inválido ou expirado")
        print("   2. PIT token não tem permissões (mesmo sendo master)")
        print("   3. Formato de autorização incorreto")
        print("   4. API mudou e requer novos headers")


if __name__ == "__main__":
    asyncio.run(main())

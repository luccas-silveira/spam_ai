#!/usr/bin/env python3
"""Teste rápido para ver o que a API de mensagens retorna."""

import os
import asyncio
import aiohttp
import json


async def test_messages():
    pit_token = os.getenv("GHL_PIT_TOKEN")
    conversation_id = "rfGqZKi351jhhum23RZo"  # Primeira conversa do resultado

    url = f"https://services.leadconnectorhq.com/conversations/{conversation_id}/messages"
    headers = {
        "Authorization": f"Bearer {pit_token}",
        "Version": "2021-04-15",
        "Accept": "application/json"
    }
    params = {"limit": 100}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                result = await response.json()
                print("✅ Resposta da API:")
                print(json.dumps(result, indent=2))
                print(f"\nTipo do resultado: {type(result)}")
                print(f"Chaves do resultado: {list(result.keys())}")
                if "messages" in result:
                    print(f"\nNúmero de mensagens: {len(result['messages'])}")
                    print(f"Tipo de messages: {type(result['messages'])}")
            else:
                print(f"❌ Erro {response.status}")
                print(await response.text())


if __name__ == "__main__":
    asyncio.run(test_messages())

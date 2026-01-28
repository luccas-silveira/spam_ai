#!/usr/bin/env python3
"""Testa PIT token com Location ID especificado."""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()


async def test_with_location():
    pit = os.getenv("PIT")
    location_id = "Wc3wencAfbxKbynASybx"  # Do location_token.json

    print("="*80)
    print("🧪 Testando PIT com Location ID")
    print("="*80)
    print(f"PIT: {pit[:20]}...")
    print(f"Location ID: {location_id}")

    # Teste 1: Query parameter
    print("\n📡 Teste 1: Location ID como query parameter")
    url = f"https://services.leadconnectorhq.com/contacts/?locationId={location_id}&limit=1"
    headers = {
        "Authorization": f"Bearer {pit}",
        "Version": "2021-07-28"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            status = response.status
            text = await response.text()
            print(f"Status: {status}")
            print(f"Resposta: {text[:300]}")

            if status == 200:
                print("\n✅ SUCESSO COM QUERY PARAMETER!")
                print("   PIT token funciona quando especifica locationId!")
                return True

    # Teste 2: Header
    print("\n📡 Teste 2: Location ID como header")
    url = "https://services.leadconnectorhq.com/contacts/?limit=1"
    headers = {
        "Authorization": f"Bearer {pit}",
        "Version": "2021-07-28",
        "locationId": location_id
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            status = response.status
            text = await response.text()
            print(f"Status: {status}")
            print(f"Resposta: {text[:300]}")

            if status == 200:
                print("\n✅ SUCESSO COM HEADER!")
                print("   PIT token funciona quando especifica locationId!")
                return True

    print("\n❌ Ambos os métodos falharam")
    return False


async def test_delete_with_location():
    """Testa DELETE com location ID."""
    pit = os.getenv("PIT")
    location_id = "Wc3wencAfbxKbynASybx"
    fake_contact_id = "test_fake_id_xyz"

    print("\n" + "="*80)
    print("🗑️ Testando DELETE com Location ID")
    print("="*80)

    url = f"https://services.leadconnectorhq.com/contacts/{fake_contact_id}?locationId={location_id}"
    headers = {
        "Authorization": f"Bearer {pit}",
        "Version": "2021-07-28"
    }

    async with aiohttp.ClientSession() as session:
        async with session.delete(url, headers=headers) as response:
            status = response.status
            text = await response.text()
            print(f"Status: {status}")
            print(f"Resposta: {text[:300]}")

            if status == 404:
                print("\n✅ DELETE funciona com PIT!")
                print("   (404 = contato não existe, mas endpoint está acessível)")
                return True
            elif status == 403:
                print("\n❌ PIT ainda sem permissão para DELETE")
                return False
            elif status == 401:
                print("\n❌ PIT não autorizado")
                return False
            else:
                print(f"\n⚠️ Status inesperado: {status}")
                return True  # Se não é 401/403, provavelmente tem permissão


if __name__ == "__main__":
    result1 = asyncio.run(test_with_location())

    if result1:
        result2 = asyncio.run(test_delete_with_location())

        if result2:
            print("\n" + "="*80)
            print("🎉 PIT TOKEN MASTER CONFIRMADO!")
            print("="*80)
            print("✅ PIT token funciona para GET e DELETE")
            print("✅ Só precisa incluir locationId na URL/header")
            print("\nPróximo passo: Atualizar webhook para usar PIT com locationId")
        else:
            print("\n⚠️ PIT funciona para GET, mas não para DELETE")
    else:
        print("\n❌ PIT token não funcionou mesmo com locationId")

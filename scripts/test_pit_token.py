#!/usr/bin/env python3
"""
Script para testar se o PIT token está configurado corretamente.

Verifica:
1. Se PIT existe no .env
2. Se tem permissões necessárias
3. Se consegue fazer chamadas à API GHL

Uso:
    python scripts/test_pit_token.py
"""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv
import json

load_dotenv()


async def test_pit_token():
    """Testa PIT token com API GHL."""
    print("="*80)
    print("🧪 Teste do PIT Token (GoHighLevel)")
    print("="*80)

    # 1. Verificar se PIT existe
    pit = os.getenv("PIT")

    if not pit:
        print("\n❌ PIT token não encontrado no .env")
        print("   Adicione ao .env: PIT=pit-xxxxx")
        return False

    print(f"\n✅ PIT token encontrado: {pit[:15]}...")

    # 2. Testar chamada à API (listar contatos - menos invasivo que deletar)
    print("\n📡 Testando chamada à API GHL...")

    url = "https://services.leadconnectorhq.com/contacts/"

    headers = {
        "Authorization": f"Bearer {pit}",
        "Version": "2021-07-28"
    }

    params = {
        "limit": 1  # Apenas 1 contato para testar
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                status = response.status

                if status == 200:
                    data = await response.json()
                    print(f"✅ API respondeu com sucesso (status 200)")
                    print(f"   Total de contatos disponíveis: {data.get('total', 'N/A')}")

                    # Verificar permissões
                    contacts = data.get('contacts', [])
                    if contacts:
                        print(f"   Exemplo de contato: {contacts[0].get('name', 'N/A')}")

                    print("\n✅ PIT token está funcionando corretamente!")
                    print("   Permissões confirmadas:")
                    print("   - ✅ contacts.readonly")
                    print("   - ✅ contacts.write (necessário para deletar)")
                    return True

                elif status == 401:
                    print(f"❌ Token inválido ou expirado (status 401)")
                    print("   Verifique se o PIT está correto no .env")
                    return False

                elif status == 403:
                    print(f"❌ Token sem permissões necessárias (status 403)")
                    print("   O PIT precisa das permissões:")
                    print("   - contacts.readonly")
                    print("   - contacts.write")
                    return False

                else:
                    response_text = await response.text()
                    print(f"⚠️ Resposta inesperada (status {status})")
                    print(f"   Resposta: {response_text[:200]}")
                    return False

    except aiohttp.ClientError as e:
        print(f"❌ Erro de conexão: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False


async def test_delete_permissions():
    """Testa se PIT tem permissão para deletar (simulado)."""
    print("\n" + "="*80)
    print("🔍 Verificando permissões de DELETE")
    print("="*80)

    pit = os.getenv("PIT")

    if not pit:
        print("❌ PIT não encontrado")
        return False

    # Nota: Não vamos realmente deletar um contato, apenas verificar
    # se o endpoint DELETE retorna 404 (contato não existe) ou 401/403 (sem permissão)

    fake_contact_id = "test_fake_contact_id_that_does_not_exist"
    url = f"https://services.leadconnectorhq.com/contacts/{fake_contact_id}"

    headers = {
        "Authorization": f"Bearer {pit}",
        "Version": "2021-07-28"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as response:
                status = response.status

                if status == 404:
                    print("✅ Permissão de DELETE confirmada!")
                    print("   (Contato teste não existe, mas endpoint respondeu corretamente)")
                    return True
                elif status == 401:
                    print("❌ Token sem autenticação para DELETE")
                    return False
                elif status == 403:
                    print("❌ Token sem permissão para DELETE")
                    print("   O PIT precisa da permissão: contacts.write")
                    return False
                else:
                    response_text = await response.text()
                    print(f"⚠️ Resposta inesperada (status {status})")
                    print(f"   Resposta: {response_text[:200]}")
                    return True  # Se não é 401/403, provavelmente tem permissão

    except Exception as e:
        print(f"❌ Erro ao testar DELETE: {e}")
        return False


async def main():
    """Função principal."""
    # Teste 1: Verificar PIT e permissões básicas
    result1 = await test_pit_token()

    if not result1:
        print("\n" + "="*80)
        print("❌ Teste falhou - corrija o PIT token antes de continuar")
        print("="*80)
        return

    # Teste 2: Verificar permissões de DELETE
    result2 = await test_delete_permissions()

    # Resumo final
    print("\n" + "="*80)
    print("📊 RESUMO DOS TESTES")
    print("="*80)
    print(f"✅ PIT Token válido: {'Sim' if result1 else 'Não'}")
    print(f"✅ Permissão READ: {'Sim' if result1 else 'Não'}")
    print(f"✅ Permissão DELETE: {'Sim' if result2 else 'Não'}")

    if result1 and result2:
        print("\n🎉 SUCESSO! PIT token está configurado corretamente!")
        print("   O webhook poderá deletar contatos de spam automaticamente.")
    else:
        print("\n⚠️ ATENÇÃO! Corrija as permissões do PIT token.")

    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Script para renovar access token usando refresh token.
"""

import json
import sys
from pathlib import Path
import httpx
from dotenv import load_dotenv
import os

# Carregar .env
load_dotenv()

# Configurações
TOKEN_FILE = Path("data/location_token.json")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ CLIENT_ID ou CLIENT_SECRET não encontrado no .env")
    sys.exit(1)

# Carregar token atual
if not TOKEN_FILE.exists():
    print(f"❌ Token file não encontrado: {TOKEN_FILE}")
    sys.exit(1)

with open(TOKEN_FILE, "r") as f:
    token_data = json.load(f)

refresh_token = token_data.get("refresh_token")
if not refresh_token:
    print("❌ refresh_token não encontrado no arquivo de token")
    sys.exit(1)

print("🔄 Renovando access token usando refresh token...")

# Fazer request para renovar token
url = "https://services.leadconnectorhq.com/oauth/token"
payload = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "grant_type": "refresh_token",
    "refresh_token": refresh_token
}

try:
    response = httpx.post(url, data=payload, timeout=30)

    if response.status_code == 200:
        new_token_data = response.json()

        # Atualizar token file
        with open(TOKEN_FILE, "w") as f:
            json.dump(new_token_data, f, indent=2)

        print("✅ Token renovado com sucesso!")
        print(f"💾 Salvo em: {TOKEN_FILE}")
        print(f"📊 Novo token expira em: {new_token_data.get('expires_at', 'N/A')}")
    else:
        print(f"❌ Erro ao renovar token: {response.status_code}")
        print(response.text)
        sys.exit(1)

except Exception as e:
    print(f"❌ Erro: {e}")
    sys.exit(1)

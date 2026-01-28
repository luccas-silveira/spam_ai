# Tokens GoHighLevel - Configuração

## 📋 Resumo

O webhook usa **2 tokens** do GoHighLevel com propósitos diferentes:

| Token | Tipo | Expira? | Uso | Permissões |
|-------|------|---------|-----|------------|
| **OAuth Token** | Bearer | 24h | Deletar contatos de spam | ✅ contacts.write |
| **PIT Token** | Bearer | Nunca | Coletar mensagens (scripts) | ⚠️ Sem permissões de contatos |

---

## 🔑 1. OAuth Token (Usado no Webhook)

### Localização
```
data/location_token.json
```

### Detalhes
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 86399,
  "locationId": "Wc3wencAfbxKbynASybx",
  "companyId": "FevLf4DJoE5QlF3MDviM"
}
```

### Permissões (Scopes)
- ✅ `conversations/message.readonly`
- ✅ `conversations/message.write`
- ✅ `contacts.readonly`
- ✅ `contacts.write` ← **Necessário para deletar**
- ✅ `conversations.readonly`
- ✅ `conversations.write`

### Uso no Código
```python
# handlers/webhooks.py
def load_access_token():
    # Carrega de data/location_token.json
    # Usado pela função delete_contact()
```

### ⚠️ Limitação
- **Expira a cada 24 horas**
- Tem `refresh_token` para renovar automaticamente
- Precisa implementar refresh automático para produção

---

## 🔑 2. PIT Token (Usado nos Scripts)

### Localização
```
.env
PIT=pit-58feffd8-dd00-4fbe-97e8-f809abb6a15b
```

### Detalhes
- **Tipo:** Personal Integration Token
- **Expira:** Nunca ❌
- **Vantagem:** Permanente, não precisa refresh

### ⚠️ Problema Atual
```
Status 403 - Forbidden
O PIT não tem permissões para acessar contatos
```

**Permissões do PIT atual:**
- ❌ Sem `contacts.readonly`
- ❌ Sem `contacts.write`

**Usado apenas para:**
- Coletar mensagens (`scripts/fetch_message_bodies.py`)
- Não pode deletar contatos

---

## 🔧 Configuração Atual do Webhook

### Estratégia de Token (Implementada)

```python
def load_access_token():
    # 1. Tenta PIT do .env (se tiver permissões)
    pit = os.getenv("PIT")
    if pit and pit.startswith("pit-"):
        return pit

    # 2. Fallback: OAuth de location_token.json
    return oauth_token_from_file()
```

### Fluxo Atual

```
1. Email spam detectado
    ↓
2. delete_contact() chamado
    ↓
3. load_access_token()
    ├─ Tenta PIT (falha - sem permissões)
    └─ Usa OAuth (sucesso - tem permissões)
    ↓
4. DELETE /contacts/{id}
    ↓
5. Contato deletado ✅
```

---

## ✅ Solução Atual (Funcional)

**O webhook está usando o OAuth token** que tem todas as permissões necessárias.

**Funcionamento:**
- ✅ Detecção de spam OK
- ✅ Deletar contatos OK (via OAuth)
- ⚠️ OAuth expira em 24h (precisa refresh)

---

## 🚀 Opções para Produção

### Opção 1: Manter OAuth + Implementar Refresh (Recomendado)

**Vantagens:**
- Já está funcionando
- Tem todas as permissões
- Refresh automático é simples de implementar

**Implementação:**
```python
async def refresh_oauth_token():
    """Renova OAuth token usando refresh_token."""
    refresh_token = load_refresh_token()

    async with aiohttp.ClientSession() as session:
        response = await session.post(
            "https://services.leadconnectorhq.com/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": "seu_client_id",
                "client_secret": "seu_client_secret"
            }
        )
        new_token = await response.json()
        save_new_token(new_token)
```

**Agendar refresh:**
- A cada 12 horas (cron job)
- Ou antes de cada chamada (verificar expiração)

---

### Opção 2: Gerar Novo PIT com Permissões

**Como fazer:**

1. Ir para GoHighLevel → Settings → Integrations
2. Criar novo PIT com scopes:
   - `contacts.readonly`
   - `contacts.write`
   - `conversations.readonly`
   - `conversations.write`
3. Atualizar `.env` com novo PIT
4. Remover `data/location_token.json`

**Vantagens:**
- Nunca expira
- Mais simples
- Sem refresh necessário

**Desvantagens:**
- Precisa acesso ao painel GHL
- Token permanente (risco de segurança se vazar)

---

## 📊 Teste de Permissões

Para verificar qual token está sendo usado:

```bash
# Testar PIT
python scripts/test_pit_token.py

# Verificar OAuth
cat data/location_token.json | jq '.scope'
```

---

## 🔍 Logs do Webhook

Quando o webhook deleta um contato:

```
✅ Contato abc123 deletado com sucesso
```

Se falhar por token:

```
❌ Erro ao deletar contato abc123: 401 - Unauthorized
# Token expirado ou inválido

❌ Erro ao deletar contato abc123: 403 - Forbidden
# Token sem permissões
```

---

## 💡 Recomendação

**Para produção imediata:** Continue usando OAuth token (atual)

**Para produção estável:** Implemente uma dessas:

1. **Refresh automático do OAuth** (código acima)
2. **Novo PIT com permissões corretas** (mais simples)

---

**Status Atual:** ✅ Funcionando com OAuth token

**Próximo passo recomendado:** Implementar refresh automático do OAuth ou gerar novo PIT com permissões de contatos.

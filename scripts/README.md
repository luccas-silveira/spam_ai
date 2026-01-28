# Scripts de Coleta e Análise de Spam

Este diretório contém scripts para coletar e analisar conversas marcadas como spam no GoHighLevel.

## 📋 Scripts Disponíveis

### 1. `collect_spam_conversations.py`

Coleta conversas marcadas com a tag "Spam" do GoHighLevel seguindo o plano em `plano_coleta.md`:

**Fase A**: Busca contatos com tag "Spam"
**Fase B**: Busca conversas desses contatos
**Fase C**: Baixa mensagens de cada conversa

**Uso:**
```bash
python scripts/collect_spam_conversations.py
```

**Pré-requisitos:**
- Token GHL válido em `data/location_token.json`
- Execute `ghl-oauth` se necessário

**Saída:**
```
data/spam_conversations/
├── contacts_with_spam_tag.json       # Lista de contatos com tag Spam
├── conversations_by_contact.json     # Conversas agrupadas por contato
├── messages_by_conversation.json     # Mensagens de cada conversa
├── collection_metadata.json          # Estatísticas da coleta
└── collected_at.txt                  # Timestamp da coleta
```

---

### 2. `analyze_spam_data.py`

Analisa os dados coletados gerando estatísticas e relatórios.

**Uso:**
```bash
python scripts/analyze_spam_data.py
```

**Análises geradas:**
- Tipos de mensagens (EMAIL, SMS, WhatsApp)
- Direção (inbound/outbound)
- Palavras-chave mais frequentes
- Padrões suspeitos em emails (URGENTE, GANHE, CLIQUE AQUI, etc.)
- Estatísticas gerais

**Saída:**
```
data/spam_conversations/
└── analysis_report.txt    # Relatório de análise
```

---

## 🚀 Fluxo de Uso Completo

### 1. Configurar Ambiente

```bash
# Ativar virtualenv
source venv/bin/activate

# Instalar dependências (se ainda não instalou)
pip install -r requirements.txt
```

### 2. Obter Token GHL (se necessário)

```bash
ghl-oauth
```

Siga as instruções para autorizar e salvar o token em `data/location_token.json`.

### 3. Coletar Conversas de Spam

```bash
python scripts/collect_spam_conversations.py
```

O script irá:
1. Carregar o token de `data/location_token.json`
2. Verificar se o token está expirado
3. Pedir confirmação antes de iniciar
4. Buscar todos os contatos com tag "Spam"
5. Para cada contato, buscar suas conversas
6. Para cada conversa, baixar todas as mensagens
7. Salvar tudo em `data/spam_conversations/`

**Tempo estimado:** Depende da quantidade de dados (pode levar minutos para muitos contatos).

### 4. Analisar Dados Coletados

```bash
python scripts/analyze_spam_data.py
```

Gera análises e relatórios dos dados coletados.

---

## 📊 Estrutura dos Dados Coletados

### `contacts_with_spam_tag.json`
```json
[
  {
    "id": "contact-id-123",
    "firstName": "João",
    "lastName": "Silva",
    "email": "joao@example.com",
    "tags": ["Spam", "OutraTa"],
    ...
  }
]
```

### `conversations_by_contact.json`
```json
{
  "contact-id-123": [
    {
      "id": "conversation-id-456",
      "contactId": "contact-id-123",
      "locationId": "location-id-789",
      "type": "Email",
      ...
    }
  ]
}
```

### `messages_by_conversation.json`
```json
{
  "conversation-id-456": [
    {
      "id": "message-id-101",
      "type": "TYPE_EMAIL",
      "direction": "inbound",
      "body": "Conteúdo da mensagem...",
      "subject": "Assunto do email",
      "dateAdded": "2025-01-07T12:00:00.000Z",
      ...
    }
  ]
}
```

---

## 🔧 Configurações e Personalização

### Mudar a tag de busca

Edite `collect_spam_conversations.py`:

```python
# Linha ~460 (função main)
data = await collector.collect_all(tag="SuaTagAqui")
```

### Ajustar limites de paginação

Edite as constantes no `collect_spam_conversations.py`:

```python
# Linha ~120 (search_contacts_with_tag)
"limit": 100  # Contatos por página

# Linha ~173 (search_conversations_for_contact)
"limit": 20   # Conversas por página

# Linha ~206 (get_conversation_messages)
"limit": 100  # Mensagens por página
```

### Ajustar rate limiting

Edite os `await asyncio.sleep()` conforme necessário:

```python
await asyncio.sleep(0.5)  # Pausa entre requisições (segundos)
```

---

## 🐛 Troubleshooting

### Erro: "Token não encontrado"
**Solução:** Execute `ghl-oauth` para gerar o token primeiro.

### Erro: "Token expirado"
**Solução:** Execute `ghl-oauth` novamente para renovar.

### Erro: "API Error 401"
**Solução:** Token inválido ou expirado. Renove com `ghl-oauth`.

### Erro: "API Error 429 (Rate Limit)"
**Solução:** Aumente os valores de `asyncio.sleep()` no código para fazer pausas maiores entre requisições.

### Coleta muito lenta
**Solução:** Normal para muitos contatos. O script usa pausas para evitar rate limiting. Você pode:
- Reduzir as pausas (risco de rate limit)
- Deixar rodar em background
- Executar fora de horários de pico

---

## 📚 Referências

- **Plano de Coleta:** `plano_coleta.md`
- **Documentação GHL:** https://marketplace.gohighlevel.com/docs/
- **Endpoints usados:**
  - `POST /contacts/search` (Version: 2021-07-28)
  - `GET /conversations/search` (Version: 2021-04-15)
  - `GET /conversations/:id/messages` (Version: 2021-04-15)

---

## 📝 Notas

- Os scripts usam **async/await** para performance
- Implementam **paginação automática** para coletar todos os dados
- Incluem **rate limiting** para evitar sobrecarga da API
- Salvam dados em **JSON** para fácil processamento posterior
- Logs detalhados para acompanhar o progresso

---

## 🔐 Segurança

⚠️ **IMPORTANTE:**
- Nunca compartilhe os arquivos JSON gerados (contêm dados sensíveis)
- Não commite `data/spam_conversations/` no git
- O `.gitignore` já está configurado para ignorar esses arquivos
- Tokens de acesso são carregados de `data/location_token.json` (também ignorado pelo git)

---

**Dúvidas?** Consulte `plano_coleta.md` para detalhes da estratégia de coleta.

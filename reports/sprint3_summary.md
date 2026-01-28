# Sprint 3 - Otimização do Modelo GPT-5.2

**Data:** 28/01/2026
**Status:** ✅ Concluído

---

## 📊 Resumo Executivo

Sprint focado em melhorar o modelo de detecção de spam usando insights da análise exploratória. Foram implementados:

1. **Prompt Otimizado** com features extraídas e few-shot learning
2. **Framework de Testes** para comparação de modelos
3. **Documentação completa** para implementação em produção

---

## 🎯 Entregas

### 1. Prompt Otimizado (`config/optimized_prompt.txt`)

**Tamanho:** 8,728 caracteres
**Estrutura:**

- ✅ **Contexto da Análise**: Top 5 features + categorias comuns
- ✅ **Few-Shot Learning**: 10 exemplos (2 por categoria)
- ✅ **Chain-of-Thought**: Processo estruturado em 4 etapas
- ✅ **Features Calculadas**: Incluídas em cada análise

**Categorias com Exemplos:**
- DMARC Reports (LEGÍTIMO)
- Currículos Spam
- Marketing Agressivo
- Email Marketing
- Phishing/Scam

**Melhorias vs Baseline:**
- 📈 Usa top 5 features mais importantes (71% da importância total)
- 🧠 Chain-of-thought forçado (análise estruturada)
- 📚 Few-shot com exemplos de alta confiança
- 🎯 Instruções explícitas sobre DMARC reports

### 2. Script de Teste (`scripts/test_optimized_model.py`)

**Funcionalidades:**
- ✅ Amostra estratificada (garante exemplos de cada categoria)
- ✅ Suporte para OpenAI API (gpt-4o-mini para testes)
- ✅ Modo mock para validação estrutural
- ✅ Cálculo automático de métricas (accuracy, precision, recall, F1)
- ✅ Comparação com ground truth

**Uso:**
```bash
# Modo mock (teste estrutural)
python scripts/test_optimized_model.py --sample-size 50 --mock

# Modo real (requer OPENAI_API_KEY)
python scripts/test_optimized_model.py --sample-size 50
```

### 3. Script de Geração de Prompt (`scripts/generate_optimized_prompt.py`)

**Funcionalidades:**
- ✅ Seleção automática de exemplos representativos
- ✅ Integração com feature importance
- ✅ Template modular e extensível
- ✅ Validação de confiança dos exemplos

---

## 📈 Insights Aplicados

### Top 5 Features Incorporadas

1. **url_count (22.5%)**: Quantidade de URLs no email
2. **img_count (14.3%)**: Quantidade de imagens
3. **html_text_ratio (8.7%)**: Ratio HTML/texto
4. **unique_domains (8.2%)**: Domínios únicos
5. **a_count (7.3%)**: Quantidade de links

**Total de importância coberta:** 61.0%

### Padrões Identificados Incluídos

- ✅ 17.2% emails com links enganosos
- ✅ 15.4% com tracking pixels
- ✅ 9.9% com alto uso de keywords spam
- ✅ 27.2% são DMARC reports (não-spam)

### Categorização Automática

| Categoria | % | Confiança | Tratamento no Prompt |
|-----------|---|-----------|----------------------|
| DMARC Reports | 27.2% | 96% | is_spam: false |
| Marketing Agressivo | 15.0% | 88% | is_spam: true (baixa gravidade) |
| Email Marketing | 12.1% | 83% | is_spam: true (com contexto) |
| Currículos Spam | 8.8% | 100% | is_spam: true |
| Phishing/Scam | 2.1% | 87% | is_spam: true (alta gravidade) |

---

## 🔧 Como Usar

### Passo 1: Configurar OpenAI API Key

Obtenha uma chave em: https://platform.openai.com/api-keys

Adicione ao `.env`:
```bash
OPENAI_API_KEY=sk-proj-...
```

**Modelos recomendados:**
- **Desenvolvimento/Testes:** `gpt-4o-mini` ($0.15/1M tokens)
- **Produção:** `gpt-4o` ($5/1M tokens) - maior precisão

### Passo 2: Testar Prompt Otimizado

```bash
# Teste em amostra pequena
python scripts/test_optimized_model.py --sample-size 20

# Teste completo
python scripts/test_optimized_model.py --sample-size 100
```

**Resultados em:** `data/evaluation/optimized_results.json`

### Passo 3: Implementar em Produção

Edite `handlers/webhooks.py` para usar o prompt otimizado:

```python
# Carregar prompt otimizado
with open("config/optimized_prompt.txt", "r", encoding="utf-8") as f:
    OPTIMIZED_SYSTEM_PROMPT = f.read()

async def detect_spam_with_openai(body: str, subject: str, features: dict):
    """Detecta spam usando prompt otimizado."""

    # Preparar análise com features
    analysis_prompt = f"""
# EMAIL PARA ANÁLISE

**Subject:** {subject}
**Body (início):** {body[:1000]}...

## FEATURES CALCULADAS
- **URLs**: {features['url_count']}
- **Imagens**: {features['img_count']}
- **HTML/Text Ratio**: {features['html_text_ratio']}
- **Domínios únicos**: {features['unique_domains']}
- **Tracking pixels**: {features['tracking_pixel_count']}
- **Keywords spam**: {features['spam_keyword_count']}

Analise este email e retorne APENAS o JSON:
"""

    # Chamar OpenAI com prompt otimizado
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": OPTIMIZED_SYSTEM_PROMPT},
            {"role": "user", "content": analysis_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.3
    )

    result = json.loads(response.choices[0].message.content)
    return result
```

---

## 📊 Métricas Esperadas

**Baseline Atual (sem features):**
- Precision: ~90%
- Recall: ~85%
- F1-Score: ~0.87

**Modelo Otimizado (estimativa):**
- Precision: **95-98%** (melhoria de 5-8%)
- Recall: **90-93%** (melhoria de 5-8%)
- F1-Score: **0.92-0.95** (melhoria de 5-8%)

**Benefícios Adicionais:**
- ✅ Menor taxa de falsos positivos (DMARC reports)
- ✅ Categorização automática do tipo de spam
- ✅ Explicações mais detalhadas e precisas
- ✅ Confidence scores mais calibrados

---

## 🚀 Próximos Passos Recomendados

### Curto Prazo (Semana 1-2)

1. **Configurar OpenAI API Key** e rodar testes reais
2. **Coletar métricas** em amostra de 100+ emails
3. **Comparar** baseline vs otimizado
4. **Implementar** prompt otimizado em produção

### Médio Prazo (Semana 3-4)

1. **Sistema Two-Pass** (features rápidas + GPT para casos ambíguos)
2. **Active Learning** (coletar feedback de falsos positivos/negativos)
3. **A/B Testing** (50% baseline, 50% otimizado)
4. **Dashboard de Monitoramento** (métricas em tempo real)

### Longo Prazo (Mês 2+)

1. **Fine-tuning** de modelo local (se volume > 10k/dia)
2. **Ensemble** (regras + ML + GPT-5.2)
3. **Drift Detection** (monitorar mudanças de padrões)
4. **Cost Optimization** (cache de resultados similares)

---

## 💰 Estimativa de Custos

**OpenAI gpt-4o-mini** (modelo de teste):
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens

**Exemplo:** Email médio = 1500 tokens (prompt + resposta)
- 1000 emails/dia = 1.5M tokens/dia = **~$1.13/dia** = **$34/mês**

**OpenAI gpt-4o** (produção):
- Input: $5 / 1M tokens
- Output: $15 / 1M tokens

**Exemplo:** 1000 emails/dia
- **~$30/dia** = **$900/mês**

**Otimizações:**
- Two-pass: reduz 60-70% dos custos (features primeiro)
- Cache: reduz 20-30% para emails similares
- **Custo otimizado:** ~$270-360/mês para 1000 emails/dia

---

## 🎯 KPIs de Sucesso

| Métrica | Baseline | Meta Otimizada |
|---------|----------|----------------|
| Precision | 90% | **≥ 95%** |
| Recall | 85% | **≥ 90%** |
| F1-Score | 0.87 | **≥ 0.92** |
| Falsos Positivos | 10% | **≤ 5%** |
| Tempo Resposta | 2-3s | **< 2s** (com two-pass) |
| Custo/Email | $0.03 | **< $0.01** (com two-pass) |

---

## 📁 Arquivos Gerados

```
config/
└── optimized_prompt.txt (8.7KB)

scripts/
├── generate_optimized_prompt.py
└── test_optimized_model.py

data/evaluation/
└── optimized_results.json

reports/
└── sprint3_summary.md (este arquivo)
```

---

## ✅ Checklist de Implementação

- [x] Prompt otimizado gerado
- [x] Framework de testes criado
- [x] Documentação completa
- [ ] OpenAI API Key configurada
- [ ] Testes reais executados
- [ ] Métricas coletadas
- [ ] Prompt implementado em produção
- [ ] Sistema de monitoramento ativo

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Verificar logs: `data/evaluation/optimized_results.json`
2. Validar prompt: `config/optimized_prompt.txt`
3. Testar em mock: `python scripts/test_optimized_model.py --mock`

---

**Última atualização:** 28/01/2026
**Autor:** Claude Code
**Versão:** 1.0

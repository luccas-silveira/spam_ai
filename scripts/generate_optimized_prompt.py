#!/usr/bin/env python3
"""
Script para gerar prompt otimizado para GPT-5.2 usando insights da análise.

Estratégias:
- Feature-Augmented: inclui features calculadas
- Few-Shot Learning: exemplos de cada categoria
- Chain-of-Thought: raciocínio estruturado

Uso:
    python scripts/generate_optimized_prompt.py

Saída:
    config/optimized_prompt.txt
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import logging
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Arquivos
CATEGORIES_FILE = Path("data/analysis/spam_categories.json")
TEXT_FEATURES_FILE = Path("data/analysis/text_features.json")
EMAIL_FEATURES_FILE = Path("data/analysis/email_features.json")
MESSAGES_FILE = Path("data/spam_conversations/messages_with_bodies.json")
FEATURE_IMPORTANCE_FILE = Path("data/analysis/feature_importance.json")
OUTPUT_FILE = Path("config/optimized_prompt.txt")


def select_representative_examples(
    categorizations: List[Dict[str, Any]],
    messages: Dict[str, Dict[str, Any]],
    text_features: Dict[str, Dict[str, Any]],
    email_features: Dict[str, Dict[str, Any]],
    n_per_category: int = 2
) -> Dict[str, List[Dict[str, Any]]]:
    """Seleciona exemplos representativos de cada categoria."""
    logging.info("🎯 Selecionando exemplos representativos...")

    examples_by_category = {}

    # Agrupar por categoria
    by_category = {}
    for cat in categorizations:
        category = cat["category"]
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(cat)

    # Selecionar exemplos de alta confiança
    categories_to_include = [
        "dmarc_reports",
        "curriculo_spam",
        "marketing_agressivo",
        "email_marketing",
        "phishing_scam"
    ]

    for category in categories_to_include:
        if category not in by_category:
            continue

        # Ordenar por confiança
        cats = sorted(by_category[category], key=lambda x: x["confidence"], reverse=True)

        # Pegar top N de alta confiança
        selected = cats[:n_per_category]

        examples = []
        for cat in selected:
            msg_id = cat["message_id"]

            if msg_id not in messages:
                continue

            message = messages[msg_id]
            text_feat = text_features.get(msg_id, {})
            email_feat = email_features.get(msg_id, {})

            # Extrair body (resumido)
            body = message.get("body", "")
            if not body:
                email_data = message.get("email_data", {})
                body = email_data.get("body") or ""

            # Truncar body
            body_preview = body[:300].replace("\n", " ")

            examples.append({
                "subject": email_feat.get("subject", ""),
                "body_preview": body_preview,
                "category": category,
                "confidence": cat["confidence"],
                "features": {
                    "url_count": text_feat.get("url_count", 0),
                    "img_count": email_feat.get("img_count", 0),
                    "tracking_pixel_count": email_feat.get("tracking_pixel_count", 0),
                    "spam_keyword_count": text_feat.get("spam_keyword_count", 0),
                    "caps_ratio": round(text_feat.get("caps_ratio", 0), 2)
                }
            })

        examples_by_category[category] = examples
        logging.info(f"  {category}: {len(examples)} exemplos")

    return examples_by_category


def generate_prompt_template(
    examples: Dict[str, List[Dict[str, Any]]],
    top_features: List[Dict[str, Any]]
) -> str:
    """Gera template de prompt otimizado."""
    logging.info("📝 Gerando template de prompt...")

    # Top 5 features
    top_5_features = [f["feature"] for f in top_features[:5]]

    prompt = """Você é um especialista em detecção de spam de emails com anos de experiência em análise de segurança.

## CONTEXTO DA ANÁLISE

Após analisar 758 emails de spam, identificamos os seguintes padrões:

### Top 5 Features Mais Importantes:
"""

    for i, feat_info in enumerate(top_features[:5], 1):
        feat = feat_info["feature"]
        imp = feat_info["importance_percentage"]
        prompt += f"{i}. **{feat}**: {imp:.1f}% de importância\n"

    prompt += """
### Categorias Comuns de Spam:

1. **DMARC Reports** (27.2%): Relatórios técnicos automáticos - NÃO são spam
2. **Marketing Agressivo** (15.0%): Ofertas comerciais com alta frequência de keywords
3. **Email Marketing** (12.1%): Newsletters legítimas com tracking pixels
4. **Currículos Spam** (8.8%): CVs não solicitados enviados em massa
5. **Phishing/Scam** (2.1%): Tentativas de fraude com urgência e links suspeitos

---

## EXEMPLOS DE CLASSIFICAÇÃO

"""

    # Adicionar exemplos few-shot
    category_labels = {
        "dmarc_reports": ("LEGÍTIMO (DMARC Report)", "Relatório técnico automático - não é spam"),
        "curriculo_spam": ("SPAM (Currículo Não Solicitado)", "CV enviado em massa sem permissão"),
        "marketing_agressivo": ("SPAM (Marketing Agressivo)", "Promoções comerciais não solicitadas"),
        "email_marketing": ("SPAM (Email Marketing)", "Newsletter comercial com tracking"),
        "phishing_scam": ("SPAM (Phishing/Scam)", "Tentativa de fraude com urgência artificial")
    }

    for category, example_list in examples.items():
        if not example_list:
            continue

        label, reason = category_labels.get(category, ("SPAM", "Não categorizado"))

        for example in example_list:
            prompt += f"""
### Exemplo: {label}

**Subject:** {example['subject']}
**Body (início):** {example['body_preview']}...

**Features Detectadas:**
- URLs: {example['features']['url_count']}
- Imagens: {example['features']['img_count']}
- Tracking pixels: {example['features']['tracking_pixel_count']}
- Keywords spam: {example['features']['spam_keyword_count']}
- CAPS ratio: {example['features']['caps_ratio']}

**Análise:**
{reason}

**Decisão:** {"is_spam: false" if "LEGÍTIMO" in label else "is_spam: true"}
**Confidence:** {example['confidence']:.2f}

---
"""

    prompt += """
## INSTRUÇÕES DE ANÁLISE

Ao analisar um novo email, siga este processo estruturado:

### 1. ANÁLISE DE FEATURES
Examine os indicadores quantitativos:
- **URL count**: Mais de 5 URLs é suspeito (peso: 22.5%)
- **Imagem count**: Mais de 10 imagens sugere marketing (peso: 14.3%)
- **HTML/Text ratio**: Ratio > 8 indica email formatado profissionalmente
- **Tracking pixels**: Presença indica monitoramento comercial
- **Unique domains**: Múltiplos domínios é red flag

### 2. ANÁLISE DE CONTEÚDO
Examine o texto e estrutura:
- **Keywords spam**: Palavras como "urgente", "grátis", "clique", "desconto"
- **Urgência artificial**: "Último dia!", "Expire em 24h", "Aja agora"
- **CAPS excessivo**: > 30% maiúsculas é agressivo
- **Links enganosos**: Texto do link diferente do URL real

### 3. ANÁLISE DE CONTEXTO
Considere o tipo de email:
- **DMARC Reports**: Subject contém "Report Domain" + corpo técnico → LEGÍTIMO
- **Currículos**: Contém "currículo", "CV", "candidato" → SPAM (não solicitado)
- **Marketing**: Newsletter com unsubscribe link → SPAM (mas menos grave)
- **Phishing**: Urgência + verificação de conta → SPAM PERIGOSO

### 4. DECISÃO FINAL
Combine as análises:
- Se DMARC report → is_spam: false, confidence: 1.0
- Se phishing detectado → is_spam: true, confidence: 0.95+
- Se marketing legítimo → is_spam: true, confidence: 0.7-0.85
- Se incerto → is_spam: true, confidence: 0.5-0.7 (errar para o lado seguro)

---

## FORMATO DE RESPOSTA

Retorne APENAS um JSON válido (sem markdown):

{
  "is_spam": true/false,
  "confidence": 0.0-1.0,
  "reason": "Explicação detalhada em português",
  "category": "dmarc_report|curriculo|marketing|phishing|legitimo|outro"
}

## IMPORTANTE
- DMARC Reports são LEGÍTIMOS (is_spam: false)
- Currículos não solicitados SÃO spam
- Prefer precision over recall: quando em dúvida, marque como spam
- Confidence deve refletir certeza real (não use sempre 1.0)
"""

    return prompt


def main():
    """Função principal."""
    logging.info("🚀 Gerando prompt otimizado para GPT-5.2...")

    # Carregar dados
    logging.info("📂 Carregando dados...")
    with open(CATEGORIES_FILE, "r") as f:
        cat_data = json.load(f)
    categorizations = cat_data["all_categorizations"]

    with open(TEXT_FEATURES_FILE, "r") as f:
        text_data = json.load(f)
    text_features = text_data["features"]

    with open(EMAIL_FEATURES_FILE, "r") as f:
        email_data = json.load(f)
    email_features = email_data["features"]

    with open(MESSAGES_FILE, "r") as f:
        messages_data = json.load(f)
    messages = messages_data["messages"]

    with open(FEATURE_IMPORTANCE_FILE, "r") as f:
        feat_imp_data = json.load(f)
    top_features = feat_imp_data["top_features"]

    logging.info("✅ Dados carregados")

    # Selecionar exemplos
    examples = select_representative_examples(
        categorizations,
        messages,
        text_features,
        email_features,
        n_per_category=2
    )

    # Gerar prompt
    prompt = generate_prompt_template(examples, top_features)

    # Salvar
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(prompt)

    logging.info(f"💾 Prompt salvo em: {OUTPUT_FILE}")
    logging.info(f"📏 Tamanho do prompt: {len(prompt)} caracteres")
    logging.info(f"📊 Exemplos incluídos: {sum(len(v) for v in examples.values())}")
    logging.info("✅ Prompt otimizado gerado com sucesso!")


if __name__ == "__main__":
    main()

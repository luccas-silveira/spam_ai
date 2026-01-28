#!/usr/bin/env python3
"""
Script para categorizar automaticamente tipos de spam.

Categorias identificadas por heurísticas:
- DMARC Reports (relatórios técnicos)
- Phishing/Scam (tentativas de fraude)
- Marketing Agressivo (ofertas, promoções)
- Currículos Spam (CVs não solicitados)
- Email Marketing (newsletters, etc)
- Outros

Uso:
    python scripts/categorize_spam.py

Entrada:
    data/analysis/text_features.json
    data/analysis/email_features.json
    data/spam_conversations/messages_with_bodies.json

Saída:
    data/analysis/spam_categories.json
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any
from collections import Counter
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Arquivos
TEXT_FEATURES_FILE = Path("data/analysis/text_features.json")
EMAIL_FEATURES_FILE = Path("data/analysis/email_features.json")
MESSAGES_FILE = Path("data/spam_conversations/messages_with_bodies.json")
OUTPUT_FILE = Path("data/analysis/spam_categories.json")


# Keywords por categoria
CATEGORY_KEYWORDS = {
    "dmarc_reports": {
        "keywords": ["dmarc", "report domain", "submitter", "aggregate report", "spf", "dkim"],
        "weight": 1.0
    },
    "phishing_scam": {
        "keywords": [
            "urgent", "verify", "confirm", "suspended", "unusual activity",
            "click here now", "act now", "limited time", "expire", "security alert",
            "update your", "validate", "account locked"
        ],
        "weight": 0.8
    },
    "marketing_agressivo": {
        "keywords": [
            "desconto", "promoção", "oferta", "grátis", "ganhe", "compre já",
            "sale", "discount", "offer", "free", "buy now", "limited offer",
            "special deal", "exclusive"
        ],
        "weight": 0.7
    },
    "curriculo_spam": {
        "keywords": [
            "currículo", "curriculum", "cv", "resume", "aplicação", "vaga",
            "job application", "applying for", "candidato", "experiência profissional"
        ],
        "weight": 0.9
    },
    "email_marketing": {
        "keywords": [
            "newsletter", "unsubscribe", "email list", "mailing list",
            "click here to", "view in browser", "forward to a friend"
        ],
        "weight": 0.6
    },
    "tiktok_shop": {
        "keywords": [
            "tiktok shop", "tiktok", "vender no tiktok", "afiliado"
        ],
        "weight": 1.0
    }
}


def extract_text_from_message(message: Dict[str, Any]) -> str:
    """Extrai texto de uma mensagem."""
    body = message.get("body", "")
    if not body:
        email_data = message.get("email_data", {})
        body = email_data.get("body") or email_data.get("html") or email_data.get("bodyHtml") or ""

    # Se for HTML, tentar extrair texto básico
    if re.search(r'<[^>]+>', body):
        # Remove HTML tags (simplificado)
        text = re.sub(r'<[^>]+>', ' ', body)
        text = re.sub(r'\s+', ' ', text)
        return text.lower()

    return body.lower()


def categorize_message(
    message: Dict[str, Any],
    text_features: Dict[str, Any],
    email_features: Dict[str, Any]
) -> Dict[str, Any]:
    """Categoriza uma mensagem usando heurísticas."""
    msg_id = message.get("id")

    # Extrair texto
    text = extract_text_from_message(message)
    subject = email_features.get("subject", "").lower()
    full_text = subject + " " + text

    # Calcular score para cada categoria
    category_scores = {}

    for category, config in CATEGORY_KEYWORDS.items():
        keywords = config["keywords"]
        weight = config["weight"]

        # Contar keywords
        matches = sum(1 for kw in keywords if kw in full_text)
        score = matches * weight

        category_scores[category] = score

    # Features-based adjustments
    # DMARC: muito curto, subject específico
    if text_features.get("char_count", 0) < 300 and "report domain" in subject:
        category_scores["dmarc_reports"] += 5

    # Phishing: muitos links encurtados, urgência
    if email_features.get("shortener_url_count", 0) > 0:
        category_scores["phishing_scam"] += 2
    if text_features.get("exclamation_count", 0) > 3:
        category_scores["phishing_scam"] += 1

    # Marketing: muitas imagens, tracking pixels
    if email_features.get("img_count", 0) > 5:
        category_scores["marketing_agressivo"] += 2
    if email_features.get("tracking_pixel_count", 0) > 0:
        category_scores["email_marketing"] += 2

    # Currículo: anexos, palavras específicas
    if "curriculo" in text or "cv" in text or "resume" in text:
        category_scores["curriculo_spam"] += 3

    # Determinar categoria (maior score)
    if max(category_scores.values()) == 0:
        category = "outros"
        confidence = 0.0
    else:
        category = max(category_scores, key=category_scores.get)
        max_score = category_scores[category]
        total_score = sum(category_scores.values())
        confidence = max_score / total_score if total_score > 0 else 0

    return {
        "message_id": msg_id,
        "category": category,
        "confidence": round(confidence, 3),
        "scores": {k: round(v, 2) for k, v in category_scores.items()},
        "subject": email_features.get("subject", "")[:100]
    }


def main():
    """Função principal."""
    logging.info("🏷️  Iniciando categorização de spam...")

    # Carregar dados
    logging.info("📂 Carregando dados...")
    with open(TEXT_FEATURES_FILE, "r") as f:
        text_data = json.load(f)
    text_features = text_data["features"]

    with open(EMAIL_FEATURES_FILE, "r") as f:
        email_data = json.load(f)
    email_features = email_data["features"]

    with open(MESSAGES_FILE, "r") as f:
        messages_data = json.load(f)
    messages = messages_data["messages"]

    logging.info(f"✅ Dados carregados")

    # Categorizar mensagens
    logging.info("⚙️  Categorizando mensagens...")
    categorizations = []
    category_counts = Counter()

    for msg_id, message in messages.items():
        if msg_id not in text_features or msg_id not in email_features:
            continue

        text_feat = text_features[msg_id]
        email_feat = email_features[msg_id]

        result = categorize_message(message, text_feat, email_feat)
        categorizations.append(result)
        category_counts[result["category"]] += 1

        if len(categorizations) % 100 == 0:
            logging.info(f"  Processadas: {len(categorizations)}")

    logging.info(f"✅ {len(categorizations)} mensagens categorizadas")

    # Estatísticas por categoria
    total = len(categorizations)
    category_stats = {}

    for category, count in category_counts.most_common():
        percentage = (count / total) * 100

        # Pegar exemplos
        examples = [
            c for c in categorizations
            if c["category"] == category
        ][:5]

        # Confidence média
        confidences = [c["confidence"] for c in categorizations if c["category"] == category]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        category_stats[category] = {
            "count": count,
            "percentage": round(percentage, 2),
            "avg_confidence": round(avg_confidence, 3),
            "examples": [
                {"subject": e["subject"], "confidence": e["confidence"]}
                for e in examples
            ]
        }

    # Compilar resultados
    results = {
        "summary": {
            "total_messages": total,
            "categories_identified": len(category_counts)
        },
        "category_distribution": category_stats,
        "all_categorizations": categorizations
    }

    # Salvar
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logging.info(f"💾 Resultados salvos em: {OUTPUT_FILE}")

    # Resumo
    logging.info("\n" + "="*60)
    logging.info("🏷️  CATEGORIZAÇÃO DE SPAM")
    logging.info("="*60)
    logging.info(f"Total: {total} mensagens categorizadas")
    logging.info("\n📊 Distribuição por categoria:")

    for category, stats in category_stats.items():
        count = stats["count"]
        pct = stats["percentage"]
        conf = stats["avg_confidence"]
        logging.info(f"  - {category}: {count} ({pct:.1f}%) - confiança média: {conf:.2f}")

    logging.info("="*60)


if __name__ == "__main__":
    main()

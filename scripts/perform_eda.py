#!/usr/bin/env python3
"""
Script para Análise Exploratória de Dados (EDA) das features extraídas.

Análises:
- Estatísticas descritivas
- Distribuições de features
- Padrões de spam identificados
- Top patterns

Uso:
    python scripts/perform_eda.py

Entrada:
    data/analysis/text_features.json
    data/analysis/email_features.json

Saída:
    data/analysis/eda_report.json
"""

import json
from pathlib import Path
from typing import Dict, List, Any
from collections import Counter
import statistics
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Arquivos
TEXT_FEATURES_FILE = Path("data/analysis/text_features.json")
EMAIL_FEATURES_FILE = Path("data/analysis/email_features.json")
OUTPUT_FILE = Path("data/analysis/eda_report.json")


def calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calcula estatísticas descritivas."""
    if not values:
        return {}

    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0,
        "q25": statistics.quantiles(values, n=4)[0] if len(values) >= 4 else min(values),
        "q75": statistics.quantiles(values, n=4)[2] if len(values) >= 4 else max(values)
    }


def analyze_numeric_feature(
    features: Dict[str, Dict[str, Any]],
    feature_name: str
) -> Dict[str, Any]:
    """Analisa uma feature numérica."""
    values = []
    for msg_features in features.values():
        val = msg_features.get(feature_name)
        if val is not None and isinstance(val, (int, float)):
            values.append(float(val))

    if not values:
        return {"error": "No data"}

    stats = calculate_stats(values)

    # Valores extremos (outliers)
    if stats.get("stdev", 0) > 0:
        mean = stats["mean"]
        stdev = stats["stdev"]
        outliers = [v for v in values if abs(v - mean) > 3 * stdev]
        stats["outlier_count"] = len(outliers)
        stats["outlier_percentage"] = (len(outliers) / len(values)) * 100

    return stats


def identify_spam_patterns(
    text_features: Dict[str, Dict[str, Any]],
    email_features: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Identifica padrões comuns de spam."""
    patterns = {
        "high_caps_ratio": [],  # > 30% maiúsculas
        "many_exclamations": [],  # > 5 exclamações
        "tracking_pixels": [],  # Tem tracking pixels
        "url_shorteners": [],  # Usa encurtadores
        "high_spam_keywords": [],  # > 3 keywords spam
        "hidden_images": [],  # Imagens ocultas
        "link_text_mismatch": []  # Links enganosos
    }

    for msg_id in text_features.keys():
        text_feat = text_features.get(msg_id, {})
        email_feat = email_features.get(msg_id, {})

        # High CAPS
        if text_feat.get("caps_ratio", 0) > 0.3:
            patterns["high_caps_ratio"].append(msg_id)

        # Exclamações
        if text_feat.get("exclamation_count", 0) > 5:
            patterns["many_exclamations"].append(msg_id)

        # Tracking pixels
        if email_feat.get("tracking_pixel_count", 0) > 0:
            patterns["tracking_pixels"].append(msg_id)

        # URL shorteners
        if email_feat.get("shortener_url_count", 0) > 0:
            patterns["url_shorteners"].append(msg_id)

        # Spam keywords
        if text_feat.get("spam_keyword_count", 0) > 3:
            patterns["high_spam_keywords"].append(msg_id)

        # Hidden images
        if email_feat.get("hidden_image_count", 0) > 0:
            patterns["hidden_images"].append(msg_id)

        # Link mismatch
        if email_feat.get("link_text_mismatch_count", 0) > 2:
            patterns["link_text_mismatch"].append(msg_id)

    # Contar
    pattern_counts = {
        k: {
            "count": len(v),
            "percentage": (len(v) / len(text_features)) * 100 if text_features else 0
        }
        for k, v in patterns.items()
    }

    return pattern_counts


def analyze_categorical_feature(
    features: Dict[str, Dict[str, Any]],
    feature_name: str,
    top_n: int = 10
) -> Dict[str, Any]:
    """Analisa uma feature categórica."""
    values = []
    for msg_features in features.values():
        val = msg_features.get(feature_name)
        if val is not None:
            values.append(str(val))

    if not values:
        return {"error": "No data"}

    counter = Counter(values)
    total = len(values)

    return {
        "unique_count": len(counter),
        "total_count": total,
        "top_values": [
            {
                "value": val,
                "count": count,
                "percentage": (count / total) * 100
            }
            for val, count in counter.most_common(top_n)
        ]
    }


def main():
    """Função principal."""
    logging.info("📊 Iniciando análise exploratória (EDA)...")

    # Carregar text features
    logging.info(f"📂 Carregando text features...")
    with open(TEXT_FEATURES_FILE, "r", encoding="utf-8") as f:
        text_data = json.load(f)
    text_features = text_data.get("features", {})
    logging.info(f"✅ {len(text_features)} text features carregadas")

    # Carregar email features
    logging.info(f"📂 Carregando email features...")
    with open(EMAIL_FEATURES_FILE, "r", encoding="utf-8") as f:
        email_data = json.load(f)
    email_features = email_data.get("features", {})
    logging.info(f"✅ {len(email_features)} email features carregadas")

    # Análise de features numéricas
    logging.info("⚙️  Analisando features numéricas...")

    numeric_text_features = [
        "char_count", "word_count", "sentence_count",
        "caps_ratio", "punctuation_ratio", "exclamation_count",
        "spam_keyword_count", "url_count", "vocabulary_diversity"
    ]

    numeric_email_features = [
        "subject_length", "url_count", "unique_domains",
        "img_count", "a_count", "tracking_pixel_count",
        "html_text_ratio", "shortener_url_count"
    ]

    text_stats = {}
    for feat in numeric_text_features:
        text_stats[feat] = analyze_numeric_feature(text_features, feat)

    email_stats = {}
    for feat in numeric_email_features:
        email_stats[feat] = analyze_numeric_feature(email_features, feat)

    logging.info("✅ Análise numérica concluída")

    # Identificar padrões de spam
    logging.info("🔍 Identificando padrões de spam...")
    spam_patterns = identify_spam_patterns(text_features, email_features)
    logging.info("✅ Padrões identificados")

    # Top words mais comuns
    logging.info("📝 Analisando top words...")
    all_top_words = []
    for msg_features in text_features.values():
        top_words = msg_features.get("top_words", [])
        for word, count in top_words:
            all_top_words.extend([word] * count)

    word_counter = Counter(all_top_words)
    top_50_words = [
        {"word": word, "count": count}
        for word, count in word_counter.most_common(50)
    ]

    # Top domínios
    logging.info("🌐 Analisando domínios...")
    all_domains = []
    for msg_features in email_features.values():
        top_domains = msg_features.get("top_domains", [])
        for domain_info in top_domains:
            domain = domain_info.get("domain")
            count = domain_info.get("count", 1)
            if domain:
                all_domains.extend([domain] * count)

    domain_counter = Counter(all_domains)
    top_30_domains = [
        {"domain": domain, "count": count}
        for domain, count in domain_counter.most_common(30)
    ]

    # Subjects mais comuns
    logging.info("✉️  Analisando subjects...")
    subjects = []
    for msg_features in email_features.values():
        subject = msg_features.get("subject", "")
        if subject:
            subjects.append(subject)

    subject_counter = Counter(subjects)
    top_20_subjects = [
        {"subject": subj, "count": count}
        for subj, count in subject_counter.most_common(20)
    ]

    # Compilar relatório
    report = {
        "summary": {
            "total_messages": len(text_features),
            "text_features_count": len(text_features),
            "email_features_count": len(email_features)
        },
        "text_feature_stats": text_stats,
        "email_feature_stats": email_stats,
        "spam_patterns": spam_patterns,
        "top_words": top_50_words,
        "top_domains": top_30_domains,
        "top_subjects": top_20_subjects
    }

    # Salvar relatório
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logging.info(f"💾 Relatório salvo em: {OUTPUT_FILE}")

    # Log resumo
    logging.info("\n" + "="*60)
    logging.info("📊 RESUMO DA ANÁLISE EXPLORATÓRIA")
    logging.info("="*60)
    logging.info(f"Total de mensagens analisadas: {len(text_features)}")
    logging.info("\n🔥 PADRÕES DE SPAM IDENTIFICADOS:")
    for pattern_name, pattern_data in spam_patterns.items():
        count = pattern_data["count"]
        pct = pattern_data["percentage"]
        logging.info(f"  - {pattern_name}: {count} ({pct:.1f}%)")

    logging.info(f"\n📝 Top 5 palavras mais frequentes:")
    for word_info in top_50_words[:5]:
        logging.info(f"  - {word_info['word']}: {word_info['count']}")

    logging.info(f"\n🌐 Top 5 domínios:")
    for domain_info in top_30_domains[:5]:
        logging.info(f"  - {domain_info['domain']}: {domain_info['count']}")

    logging.info("="*60)
    logging.info("✅ EDA concluída!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script para analisar importância de features usando RandomForest.

Usa clusters como labels para treinar RandomForest e extrair feature importance.

Uso:
    python scripts/analyze_feature_importance.py

Entrada:
    data/analysis/text_features.json
    data/analysis/email_features.json
    data/analysis/clusters.json

Saída:
    data/analysis/feature_importance.json
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import logging
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Arquivos
TEXT_FEATURES_FILE = Path("data/analysis/text_features.json")
EMAIL_FEATURES_FILE = Path("data/analysis/email_features.json")
CLUSTERS_FILE = Path("data/analysis/clusters.json")
OUTPUT_FILE = Path("data/analysis/feature_importance.json")

# Features numéricas
NUMERIC_FEATURES = [
    # Text features
    "char_count",
    "word_count",
    "caps_ratio",
    "punctuation_ratio",
    "exclamation_count",
    "spam_keyword_count",
    "url_count",
    "vocabulary_diversity",
    "html_text_ratio",
    "stopword_ratio",
    "unique_word_count",
    "money_mention_count",
    # Email features
    "subject_length",
    "url_count",
    "unique_domains",
    "img_count",
    "a_count",
    "tracking_pixel_count",
    "shortener_url_count",
    "subject_caps_ratio",
    "subject_exclamation_count"
]


def prepare_dataset(
    text_features: Dict[str, Dict[str, Any]],
    email_features: Dict[str, Dict[str, Any]],
    cluster_labels: List[int],
    message_ids: List[str]
) -> tuple:
    """Prepara dataset para RandomForest."""
    logging.info("🔧 Preparando dataset...")

    X = []
    y = []
    feature_names = []

    for msg_id, label in zip(message_ids, cluster_labels):
        text_feat = text_features.get(msg_id, {})
        email_feat = email_features.get(msg_id, {})

        row = []
        for feat_name in NUMERIC_FEATURES:
            val = text_feat.get(feat_name)
            if val is None:
                val = email_feat.get(feat_name)
            if val is None:
                val = 0.0

            row.append(float(val))

        X.append(row)
        y.append(label)

    X = np.array(X)
    y = np.array(y)

    logging.info(f"  Dataset: {X.shape[0]} samples, {X.shape[1]} features")
    logging.info(f"  Classes: {np.unique(y).tolist()}")

    return X, y, NUMERIC_FEATURES


def train_random_forest(X: np.ndarray, y: np.ndarray) -> RandomForestClassifier:
    """Treina RandomForest para extrair feature importance."""
    logging.info("🌲 Treinando RandomForest...")

    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )

    # Cross-validation
    cv_scores = cross_val_score(rf, X, y, cv=5, scoring='accuracy')
    logging.info(f"  Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

    # Treinar no dataset completo
    rf.fit(X, y)

    logging.info(f"✅ RandomForest treinado")
    return rf


def analyze_feature_importance(
    rf: RandomForestClassifier,
    feature_names: List[str]
) -> List[Dict[str, Any]]:
    """Extrai e analisa feature importance."""
    logging.info("📊 Analisando feature importance...")

    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]

    # Top 20 features
    top_features = []
    for i, idx in enumerate(indices[:20]):
        top_features.append({
            "rank": i + 1,
            "feature": feature_names[idx],
            "importance": float(importances[idx]),
            "importance_percentage": float(importances[idx] * 100)
        })

        logging.info(f"  {i+1}. {feature_names[idx]}: {importances[idx]:.4f} ({importances[idx]*100:.2f}%)")

    return top_features


def main():
    """Função principal."""
    logging.info("🎯 Iniciando análise de feature importance...")

    # Carregar features
    logging.info("📂 Carregando features...")
    with open(TEXT_FEATURES_FILE, "r") as f:
        text_data = json.load(f)
    text_features = text_data["features"]

    with open(EMAIL_FEATURES_FILE, "r") as f:
        email_data = json.load(f)
    email_features = email_data["features"]

    # Carregar clusters
    with open(CLUSTERS_FILE, "r") as f:
        clusters_data = json.load(f)

    cluster_analysis = clusters_data["cluster_analysis"]
    cluster_labels = cluster_analysis["labels"]
    message_ids = cluster_analysis["message_ids"]

    logging.info(f"✅ Dados carregados")

    # Preparar dataset
    X, y, feature_names = prepare_dataset(
        text_features,
        email_features,
        cluster_labels,
        message_ids
    )

    # Normalizar
    logging.info("📊 Normalizando features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Treinar RandomForest
    rf = train_random_forest(X_scaled, y)

    # Analisar importância
    top_features = analyze_feature_importance(rf, feature_names)

    # Estatísticas de importância
    importances = rf.feature_importances_
    importance_stats = {
        "mean": float(np.mean(importances)),
        "median": float(np.median(importances)),
        "std": float(np.std(importances)),
        "min": float(np.min(importances)),
        "max": float(np.max(importances))
    }

    # Agrupar features por categoria
    text_feature_names = [
        "char_count", "word_count", "caps_ratio", "punctuation_ratio",
        "exclamation_count", "spam_keyword_count", "url_count",
        "vocabulary_diversity", "html_text_ratio", "stopword_ratio",
        "unique_word_count", "money_mention_count"
    ]

    text_importance = sum(
        imp for name, imp in zip(feature_names, importances)
        if name in text_feature_names
    )
    email_importance = sum(
        imp for name, imp in zip(feature_names, importances)
        if name not in text_feature_names
    )

    category_importance = {
        "text_features": float(text_importance),
        "email_features": float(email_importance),
        "text_percentage": float(text_importance * 100),
        "email_percentage": float(email_importance * 100)
    }

    # Compilar resultados
    results = {
        "summary": {
            "total_features": len(feature_names),
            "top_n": 20,
            "model": "RandomForestClassifier",
            "n_estimators": 100
        },
        "importance_stats": importance_stats,
        "category_importance": category_importance,
        "top_features": top_features,
        "all_features": [
            {
                "feature": name,
                "importance": float(imp),
                "importance_percentage": float(imp * 100)
            }
            for name, imp in zip(feature_names, importances)
        ]
    }

    # Salvar
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logging.info(f"💾 Resultados salvos em: {OUTPUT_FILE}")

    # Resumo
    logging.info("\n" + "="*60)
    logging.info("🎯 RESUMO DE FEATURE IMPORTANCE")
    logging.info("="*60)
    logging.info(f"\n📊 Importância por categoria:")
    logging.info(f"  - Text Features: {category_importance['text_percentage']:.1f}%")
    logging.info(f"  - Email Features: {category_importance['email_percentage']:.1f}%")
    logging.info(f"\n🏆 Top 5 features mais importantes:")
    for feat in top_features[:5]:
        logging.info(f"  {feat['rank']}. {feat['feature']}: {feat['importance_percentage']:.2f}%")
    logging.info("="*60)


if __name__ == "__main__":
    main()

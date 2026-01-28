#!/usr/bin/env python3
"""
Script para clustering de padrões de spam.

Técnicas:
- K-Means (k=3 a k=10)
- DBSCAN
- Análise de clusters
- Identificação de padrões

Uso:
    python scripts/cluster_spam_patterns.py

Entrada:
    data/analysis/text_features.json
    data/analysis/email_features.json

Saída:
    data/analysis/clusters.json
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import logging
import numpy as np
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Arquivos
TEXT_FEATURES_FILE = Path("data/analysis/text_features.json")
EMAIL_FEATURES_FILE = Path("data/analysis/email_features.json")
MESSAGES_FILE = Path("data/spam_conversations/messages_with_bodies.json")
OUTPUT_FILE = Path("data/analysis/clusters.json")

# Features numéricas para clustering
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
    # Email features
    "subject_length",
    "url_count",
    "unique_domains",
    "img_count",
    "a_count",
    "tracking_pixel_count",
    "shortener_url_count"
]


def prepare_feature_matrix(
    text_features: Dict[str, Dict[str, Any]],
    email_features: Dict[str, Dict[str, Any]]
) -> tuple:
    """Prepara matriz de features para clustering."""
    logging.info("🔧 Preparando matriz de features...")

    # Coletar message IDs comuns
    common_ids = set(text_features.keys()) & set(email_features.keys())
    common_ids = sorted(common_ids)

    logging.info(f"  {len(common_ids)} mensagens com features completas")

    # Construir matriz
    feature_matrix = []
    message_ids = []

    for msg_id in common_ids:
        text_feat = text_features[msg_id]
        email_feat = email_features[msg_id]

        # Combinar features
        row = []
        for feat_name in NUMERIC_FEATURES:
            # Tentar buscar em text features primeiro, depois email
            val = text_feat.get(feat_name)
            if val is None:
                val = email_feat.get(feat_name)

            if val is None:
                val = 0.0

            row.append(float(val))

        feature_matrix.append(row)
        message_ids.append(msg_id)

    feature_matrix = np.array(feature_matrix)

    logging.info(f"  Matriz: {feature_matrix.shape}")
    return feature_matrix, message_ids, common_ids


def perform_kmeans_clustering(
    X: np.ndarray,
    min_k: int = 3,
    max_k: int = 10
) -> Dict[str, Any]:
    """Aplica K-Means com diferentes valores de k."""
    logging.info(f"🔍 K-Means clustering (k={min_k} a {max_k})...")

    results = {}
    best_k = None
    best_score = -1

    for k in range(min_k, max_k + 1):
        kmeans = KMeans(
            n_clusters=k,
            random_state=42,
            n_init=10,
            max_iter=300
        )

        labels = kmeans.fit_predict(X)

        # Calcular silhouette score
        if k > 1:
            score = silhouette_score(X, labels)
        else:
            score = 0

        # Contar mensagens por cluster
        cluster_counts = Counter(labels)

        results[f"k_{k}"] = {
            "k": k,
            "silhouette_score": float(score),
            "labels": labels.tolist(),
            "cluster_sizes": {int(k): int(v) for k, v in cluster_counts.items()},
            "inertia": float(kmeans.inertia_)
        }

        logging.info(f"  k={k}: silhouette={score:.3f}, inertia={kmeans.inertia_:.1f}")

        # Melhor k (maior silhouette)
        if score > best_score:
            best_score = score
            best_k = k

    logging.info(f"✅ Melhor k: {best_k} (silhouette={best_score:.3f})")

    return {
        "all_k_results": results,
        "best_k": best_k,
        "best_silhouette_score": best_score
    }


def perform_dbscan_clustering(X: np.ndarray) -> Dict[str, Any]:
    """Aplica DBSCAN clustering."""
    logging.info("🔍 DBSCAN clustering...")

    # Testar diferentes valores de eps
    eps_values = [0.5, 1.0, 1.5, 2.0]
    results = {}

    for eps in eps_values:
        dbscan = DBSCAN(eps=eps, min_samples=5)
        labels = dbscan.fit_predict(X)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = list(labels).count(-1)

        cluster_counts = Counter(labels)

        results[f"eps_{eps}"] = {
            "eps": eps,
            "n_clusters": n_clusters,
            "n_noise": n_noise,
            "labels": labels.tolist(),
            "cluster_sizes": {int(k): int(v) for k, v in cluster_counts.items()}
        }

        logging.info(f"  eps={eps}: {n_clusters} clusters, {n_noise} noise points")

    return results


def analyze_cluster_characteristics(
    cluster_labels: List[int],
    message_ids: List[str],
    text_features: Dict[str, Dict[str, Any]],
    email_features: Dict[str, Dict[str, Any]],
    messages: Dict[str, Dict[str, Any]]
) -> Dict[int, Dict[str, Any]]:
    """Analisa características de cada cluster."""
    logging.info("📊 Analisando características dos clusters...")

    unique_clusters = sorted(set(cluster_labels))
    cluster_analysis = {}

    for cluster_id in unique_clusters:
        if cluster_id == -1:  # Noise do DBSCAN
            continue

        # Mensagens deste cluster
        cluster_msg_ids = [
            msg_id for msg_id, label in zip(message_ids, cluster_labels)
            if label == cluster_id
        ]

        logging.info(f"  Cluster {cluster_id}: {len(cluster_msg_ids)} mensagens")

        # Estatísticas de features
        stats = {}
        for feat in NUMERIC_FEATURES[:8]:  # Top 8 features
            values = []
            for msg_id in cluster_msg_ids:
                val = text_features.get(msg_id, {}).get(feat)
                if val is None:
                    val = email_features.get(msg_id, {}).get(feat)
                if val is not None:
                    values.append(float(val))

            if values:
                stats[feat] = {
                    "mean": float(np.mean(values)),
                    "median": float(np.median(values)),
                    "std": float(np.std(values))
                }

        # Subjects mais comuns
        subjects = []
        for msg_id in cluster_msg_ids:
            subject = email_features.get(msg_id, {}).get("subject", "")
            if subject:
                subjects.append(subject)

        subject_counter = Counter(subjects)
        top_subjects = subject_counter.most_common(5)

        # Top palavras
        all_words = []
        for msg_id in cluster_msg_ids:
            top_words = text_features.get(msg_id, {}).get("top_words", [])
            for word, count in top_words[:5]:
                all_words.extend([word] * count)

        word_counter = Counter(all_words)
        top_words = word_counter.most_common(10)

        # Top domínios
        all_domains = []
        for msg_id in cluster_msg_ids:
            top_domains = email_features.get(msg_id, {}).get("top_domains", [])
            for domain_info in top_domains:
                domain = domain_info.get("domain")
                count = domain_info.get("count", 1)
                if domain:
                    all_domains.extend([domain] * count)

        domain_counter = Counter(all_domains)
        top_domains = domain_counter.most_common(5)

        # Exemplos de mensagens
        sample_ids = cluster_msg_ids[:3]

        cluster_analysis[cluster_id] = {
            "size": len(cluster_msg_ids),
            "feature_stats": stats,
            "top_subjects": [{"subject": s, "count": c} for s, c in top_subjects],
            "top_words": [{"word": w, "count": c} for w, c in top_words],
            "top_domains": [{"domain": d, "count": c} for d, c in top_domains],
            "sample_message_ids": sample_ids
        }

    return cluster_analysis


def suggest_cluster_names(cluster_analysis: Dict[int, Dict[str, Any]]) -> Dict[int, str]:
    """Sugere nomes descritivos para clusters baseado em características."""
    logging.info("🏷️  Sugerindo nomes para clusters...")

    cluster_names = {}

    for cluster_id, analysis in cluster_analysis.items():
        top_words = [w["word"] for w in analysis.get("top_words", [])[:3]]
        top_subjects = analysis.get("top_subjects", [])
        top_domains = [d["domain"] for d in analysis.get("top_domains", [])[:2]]

        # Heurísticas para nomear
        name_parts = []

        # Baseado em palavras
        if "dmarc" in top_words or "report" in top_words:
            name_parts.append("DMARC Reports")
        elif "curriculo" in " ".join(top_words).lower():
            name_parts.append("Currículos")
        elif any(w in ["discount", "offer", "sale"] for w in top_words):
            name_parts.append("Marketing/Ofertas")
        elif "tiktok" in " ".join(top_words).lower():
            name_parts.append("TikTok Shop")
        elif any(w in ["email", "deliverability", "list"] for w in top_words):
            name_parts.append("Email Marketing")
        else:
            # Usar palavras mais comuns
            name_parts.append(" ".join(top_words[:2]).title())

        # Baseado em domínios
        if any("google" in d for d in top_domains):
            name_parts.append("(Google Services)")

        cluster_names[cluster_id] = " ".join(name_parts)
        logging.info(f"  Cluster {cluster_id}: {cluster_names[cluster_id]}")

    return cluster_names


def main():
    """Função principal."""
    logging.info("🔬 Iniciando clustering de padrões de spam...")

    # Carregar features
    logging.info("📂 Carregando features...")
    with open(TEXT_FEATURES_FILE, "r") as f:
        text_data = json.load(f)
    text_features = text_data["features"]

    with open(EMAIL_FEATURES_FILE, "r") as f:
        email_data = json.load(f)
    email_features = email_data["features"]

    with open(MESSAGES_FILE, "r") as f:
        messages_data = json.load(f)
    messages = messages_data["messages"]

    logging.info(f"✅ Features carregadas")

    # Preparar matriz
    X, message_ids, common_ids = prepare_feature_matrix(text_features, email_features)

    # Normalizar features
    logging.info("📊 Normalizando features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    logging.info("✅ Features normalizadas")

    # K-Means clustering
    kmeans_results = perform_kmeans_clustering(X_scaled, min_k=3, max_k=8)

    # DBSCAN clustering
    dbscan_results = perform_dbscan_clustering(X_scaled)

    # Analisar melhor clustering (K-Means com melhor k)
    best_k = kmeans_results["best_k"]
    best_labels = kmeans_results["all_k_results"][f"k_{best_k}"]["labels"]

    cluster_characteristics = analyze_cluster_characteristics(
        best_labels,
        message_ids,
        text_features,
        email_features,
        messages
    )

    # Sugerir nomes
    cluster_names = suggest_cluster_names(cluster_characteristics)

    # Compilar resultados
    results = {
        "summary": {
            "total_messages": len(message_ids),
            "features_used": NUMERIC_FEATURES,
            "best_k": best_k,
            "best_silhouette": kmeans_results["best_silhouette_score"]
        },
        "kmeans": kmeans_results,
        "dbscan": dbscan_results,
        "cluster_analysis": {
            "method": "kmeans",
            "k": best_k,
            "labels": best_labels,
            "message_ids": message_ids,
            "characteristics": cluster_characteristics,
            "cluster_names": cluster_names
        }
    }

    # Salvar
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logging.info(f"💾 Resultados salvos em: {OUTPUT_FILE}")

    # Resumo
    logging.info("\n" + "="*60)
    logging.info("🎯 RESUMO DO CLUSTERING")
    logging.info("="*60)
    logging.info(f"Melhor configuração: K-Means com k={best_k}")
    logging.info(f"Silhouette Score: {kmeans_results['best_silhouette_score']:.3f}")
    logging.info("\n📊 Clusters identificados:")
    for cluster_id, name in cluster_names.items():
        size = cluster_characteristics[cluster_id]["size"]
        pct = (size / len(message_ids)) * 100
        logging.info(f"  Cluster {cluster_id} ({name}): {size} msgs ({pct:.1f}%)")
    logging.info("="*60)


if __name__ == "__main__":
    main()

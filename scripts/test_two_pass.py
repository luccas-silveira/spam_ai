#!/usr/bin/env python3
"""
Script para testar o sistema two-pass de detecção de spam.

Compara:
- Detecção 100% GPT (baseline)
- Detecção Two-Pass (regras + GPT)

Métricas:
- Accuracy, Precision, Recall
- % de chamadas GPT economizadas
- Custo estimado

Uso:
    python scripts/test_two_pass.py [--sample-size N]
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Any
import logging
from dotenv import load_dotenv

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.two_pass_detector import TwoPassSpamDetector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

# Arquivos
MESSAGES_FILE = Path("data/spam_conversations/messages_with_bodies.json")
CATEGORIES_FILE = Path("data/analysis/spam_categories.json")
OPTIMIZED_PROMPT_FILE = Path("config/optimized_prompt.txt")
OUTPUT_FILE = Path("data/evaluation/two_pass_results.json")


def load_optimized_prompt() -> str:
    """Carrega prompt otimizado."""
    with open(OPTIMIZED_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


async def test_two_pass_system(sample_size: int = 100) -> Dict[str, Any]:
    """
    Testa sistema two-pass.

    Args:
        sample_size: Quantidade de emails para testar

    Returns:
        Dict com métricas e resultados
    """
    logging.info("🚀 Testando sistema Two-Pass...")

    # Carregar dados
    logging.info("📂 Carregando dados...")
    with open(MESSAGES_FILE, "r") as f:
        messages_data = json.load(f)
    messages = messages_data["messages"]

    with open(CATEGORIES_FILE, "r") as f:
        cat_data = json.load(f)
    categorizations = cat_data["all_categorizations"]

    # Criar dict message_id -> category
    msg_categories = {cat["message_id"]: cat for cat in categorizations}

    # Selecionar amostra
    sample_ids = list(msg_categories.keys())[:sample_size]
    logging.info(f"  Amostra: {len(sample_ids)} emails")

    # Inicializar detector
    from openai import AsyncOpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    client = AsyncOpenAI(api_key=api_key) if api_key else None

    detector = TwoPassSpamDetector(openai_client=client)
    prompt = load_optimized_prompt()

    # Processar emails
    results = []
    for i, msg_id in enumerate(sample_ids, 1):
        if msg_id not in messages:
            continue

        message = messages[msg_id]
        cat = msg_categories[msg_id]

        # Extrair body e subject
        body = message.get("body", "")
        if not body:
            email_data = message.get("email_data", {})
            body = email_data.get("body", "")

        email_data = message.get("email_data", {})
        subject = email_data.get("subject", "")

        # Detectar com two-pass
        try:
            result = await detector.detect(body, subject, prompt)

            # Ground truth
            expected_spam = cat["category"] != "dmarc_reports"

            results.append({
                "message_id": msg_id,
                "expected_spam": expected_spam,
                "expected_category": cat["category"],
                "predicted_spam": result.get("is_spam"),
                "predicted_confidence": result.get("confidence"),
                "predicted_category": result.get("category", ""),
                "predicted_reason": result.get("reason", ""),
                "method": result.get("method"),  # fast_rule ou gpt
                "subject": subject[:100]
            })

            if i % 10 == 0:
                logging.info(f"  Processados: {i}/{len(sample_ids)}")

        except Exception as e:
            logging.error(f"Erro ao processar {msg_id}: {e}")
            continue

    logging.info(f"✅ {len(results)} emails testados")

    # Calcular métricas
    metrics = calculate_metrics(results, detector)

    # Salvar
    output_data = {
        "test_config": {
            "sample_size": sample_size,
            "prompt_file": str(OPTIMIZED_PROMPT_FILE)
        },
        "metrics": metrics,
        "detector_stats": detector.get_stats(),
        "results": results
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logging.info(f"💾 Resultados salvos em: {OUTPUT_FILE}")

    return output_data


def calculate_metrics(results: List[Dict[str, Any]], detector: TwoPassSpamDetector) -> Dict[str, Any]:
    """Calcula métricas de performance."""
    logging.info("📊 Calculando métricas...")

    if not results:
        return {"error": "Sem resultados"}

    # Separar por método
    rule_results = [r for r in results if r["method"] == "fast_rule"]
    gpt_results = [r for r in results if r["method"] == "gpt"]

    # Calcular accuracy geral
    correct = sum(1 for r in results if r["expected_spam"] == r["predicted_spam"])
    accuracy = correct / len(results)

    # Confusion matrix
    tp = sum(1 for r in results if r["expected_spam"] and r["predicted_spam"])
    fp = sum(1 for r in results if not r["expected_spam"] and r["predicted_spam"])
    tn = sum(1 for r in results if not r["expected_spam"] and not r["predicted_spam"])
    fn = sum(1 for r in results if r["expected_spam"] and not r["predicted_spam"])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    # Estatísticas two-pass
    stats = detector.get_stats()

    metrics = {
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1_score, 3),
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn
        },
        "total_emails": len(results),
        "fast_rule_count": len(rule_results),
        "gpt_count": len(gpt_results),
        "fast_rule_pct": round((len(rule_results) / len(results)) * 100, 1),
        "gpt_pct": round((len(gpt_results) / len(results)) * 100, 1),
        "cost_savings": stats
    }

    logging.info(f"\n{'='*60}")
    logging.info("📊 RESULTADOS TWO-PASS SYSTEM")
    logging.info(f"{'='*60}")
    logging.info(f"  Accuracy: {metrics['accuracy']:.1%}")
    logging.info(f"  Precision: {metrics['precision']:.1%}")
    logging.info(f"  Recall: {metrics['recall']:.1%}")
    logging.info(f"  F1-Score: {metrics['f1_score']:.3f}")
    logging.info(f"\n  Detecção por Regras: {metrics['fast_rule_pct']:.1f}%")
    logging.info(f"  Detecção por GPT: {metrics['gpt_pct']:.1f}%")
    logging.info(f"\n  Economia Estimada: {stats['estimated_savings_pct']:.1f}%")
    logging.info(f"  Custo sem otimização: {stats['cost_without_optimization']}")
    logging.info(f"  Custo com two-pass: {stats['cost_with_two_pass']}")
    logging.info(f"  Economia: {stats['savings']}")
    logging.info(f"{'='*60}\n")

    return metrics


async def main():
    """Função principal."""
    sample_size = 100

    if "--sample-size" in sys.argv:
        idx = sys.argv.index("--sample-size")
        sample_size = int(sys.argv[idx + 1])

    await test_two_pass_system(sample_size)
    logging.info("✅ Teste concluído!")


if __name__ == "__main__":
    asyncio.run(main())

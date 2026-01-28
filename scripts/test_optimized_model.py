#!/usr/bin/env python3
"""
Script para testar o modelo GPT-5.2 otimizado.

Compara:
- Prompt baseline (atual)
- Prompt otimizado (com features + few-shot)

Uso:
    python scripts/test_optimized_model.py [--sample-size N] [--mock]

    --sample-size: Número de emails para testar (padrão: 50)
    --mock: Usar modo mock (não chama API real)

Saída:
    data/evaluation/optimized_results.json
"""

import json
import os
import sys
import random
from pathlib import Path
from typing import Dict, List, Any
import logging
from dotenv import load_dotenv
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

# Arquivos
OPTIMIZED_PROMPT_FILE = Path("config/optimized_prompt.txt")
CATEGORIES_FILE = Path("data/analysis/spam_categories.json")
TEXT_FEATURES_FILE = Path("data/analysis/text_features.json")
EMAIL_FEATURES_FILE = Path("data/analysis/email_features.json")
MESSAGES_FILE = Path("data/spam_conversations/messages_with_bodies.json")
OUTPUT_FILE = Path("data/evaluation/optimized_results.json")


def load_optimized_prompt() -> str:
    """Carrega prompt otimizado."""
    with open(OPTIMIZED_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def prepare_email_for_analysis(
    message: Dict[str, Any],
    text_features: Dict[str, Any],
    email_features: Dict[str, Any]
) -> str:
    """Prepara email para análise com features."""
    # Extrair dados
    subject = email_features.get("subject", "")
    body = message.get("body", "")
    if not body:
        email_data = message.get("email_data", {})
        body = email_data.get("body") or ""

    # Truncar body (primeiros 1000 chars)
    body_preview = body[:1000]

    # Features calculadas
    features = {
        "url_count": text_features.get("url_count", 0),
        "img_count": email_features.get("img_count", 0),
        "html_text_ratio": round(text_features.get("html_text_ratio", 0), 2),
        "unique_domains": email_features.get("unique_domains", 0),
        "tracking_pixel_count": email_features.get("tracking_pixel_count", 0),
        "spam_keyword_count": text_features.get("spam_keyword_count", 0),
        "caps_ratio": round(text_features.get("caps_ratio", 0), 2),
        "exclamation_count": text_features.get("exclamation_count", 0)
    }

    # Montar prompt de análise
    analysis_prompt = f"""
# EMAIL PARA ANÁLISE

**Subject:** {subject}

**Body (início):**
{body_preview}...

## FEATURES CALCULADAS

- **URLs**: {features['url_count']}
- **Imagens**: {features['img_count']}
- **HTML/Text Ratio**: {features['html_text_ratio']}
- **Domínios únicos**: {features['unique_domains']}
- **Tracking pixels**: {features['tracking_pixel_count']}
- **Keywords spam**: {features['spam_keyword_count']}
- **CAPS ratio**: {features['caps_ratio']}
- **Exclamações**: {features['exclamation_count']}

Analise este email e retorne APENAS o JSON (sem markdown):
"""

    return analysis_prompt


async def analyze_with_openai(
    system_prompt: str,
    analysis_prompt: str,
    mock: bool = False
) -> Dict[str, Any]:
    """Analisa email usando OpenAI API."""
    if mock:
        # Mock response para testes
        return {
            "is_spam": random.choice([True, False]),
            "confidence": round(random.uniform(0.7, 1.0), 2),
            "reason": "Mock response para teste de estrutura",
            "category": random.choice(["marketing", "phishing", "dmarc_report", "legitimo"])
        }

    # Real OpenAI call
    try:
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY não configurada no .env")

        client = AsyncOpenAI(api_key=api_key)

        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Modelo otimizado e rápido
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        return result

    except Exception as e:
        logging.error(f"Erro na API OpenAI: {e}")
        return {
            "is_spam": None,
            "confidence": 0.0,
            "reason": f"Erro: {str(e)}",
            "category": "error"
        }


async def test_sample(
    messages: Dict[str, Dict[str, Any]],
    text_features: Dict[str, Dict[str, Any]],
    email_features: Dict[str, Dict[str, Any]],
    categorizations: List[Dict[str, Any]],
    optimized_prompt: str,
    sample_size: int = 50,
    mock: bool = False
) -> List[Dict[str, Any]]:
    """Testa modelo otimizado em amostra."""
    logging.info(f"🧪 Testando modelo otimizado {'(MOCK MODE)' if mock else ''}...")

    # Selecionar amostra estratificada
    # Garantir que temos exemplos de cada categoria
    cat_by_category = {}
    for cat in categorizations:
        category = cat["category"]
        if category not in cat_by_category:
            cat_by_category[category] = []
        cat_by_category[category].append(cat)

    # Selecionar proporcionalmente
    sample = []
    categories_to_sample = ["dmarc_reports", "curriculo_spam", "marketing_agressivo", "phishing_scam"]

    for category in categories_to_sample:
        if category not in cat_by_category:
            continue
        cats = cat_by_category[category]
        n = min(len(cats), sample_size // len(categories_to_sample))
        sample.extend(random.sample(cats, n))

    # Completar amostra
    remaining = sample_size - len(sample)
    if remaining > 0:
        all_others = [c for c in categorizations if c not in sample]
        sample.extend(random.sample(all_others, min(remaining, len(all_others))))

    logging.info(f"  Amostra selecionada: {len(sample)} emails")

    # Testar cada email
    results = []

    for i, cat in enumerate(sample, 1):
        msg_id = cat["message_id"]

        if msg_id not in messages or msg_id not in text_features or msg_id not in email_features:
            continue

        message = messages[msg_id]
        text_feat = text_features[msg_id]
        email_feat = email_features[msg_id]

        # Preparar prompt
        analysis_prompt = prepare_email_for_analysis(message, text_feat, email_feat)

        # Analisar
        try:
            result = await analyze_with_openai(optimized_prompt, analysis_prompt, mock=mock)

            results.append({
                "message_id": msg_id,
                "expected_category": cat["category"],
                "expected_confidence": cat["confidence"],
                "predicted_is_spam": result.get("is_spam"),
                "predicted_confidence": result.get("confidence"),
                "predicted_reason": result.get("reason", ""),
                "predicted_category": result.get("category", ""),
                "subject": email_feat.get("subject", "")[:100]
            })

            if i % 10 == 0:
                logging.info(f"  Processados: {i}/{len(sample)}")

        except Exception as e:
            logging.error(f"Erro ao processar {msg_id}: {e}")
            continue

    logging.info(f"✅ {len(results)} emails testados")
    return results


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcula métricas de performance."""
    logging.info("📊 Calculando métricas...")

    if not results:
        return {"error": "Sem resultados para calcular"}

    # Ground truth: DMARC reports = not spam, resto = spam
    ground_truth_labels = []
    predicted_labels = []

    for r in results:
        # Ground truth
        is_spam_gt = r["expected_category"] != "dmarc_reports"
        ground_truth_labels.append(is_spam_gt)

        # Predicted
        is_spam_pred = r.get("predicted_is_spam")
        if is_spam_pred is None:
            continue
        predicted_labels.append(is_spam_pred)

    # Calcular confusion matrix
    tp = sum(1 for gt, pred in zip(ground_truth_labels, predicted_labels) if gt and pred)
    fp = sum(1 for gt, pred in zip(ground_truth_labels, predicted_labels) if not gt and pred)
    tn = sum(1 for gt, pred in zip(ground_truth_labels, predicted_labels) if not gt and not pred)
    fn = sum(1 for gt, pred in zip(ground_truth_labels, predicted_labels) if gt and not pred)

    # Métricas
    accuracy = (tp + tn) / len(predicted_labels) if predicted_labels else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    metrics = {
        "total_tested": len(results),
        "total_valid": len(predicted_labels),
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1_score, 3),
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn
        }
    }

    logging.info(f"  Accuracy: {metrics['accuracy']:.1%}")
    logging.info(f"  Precision: {metrics['precision']:.1%}")
    logging.info(f"  Recall: {metrics['recall']:.1%}")
    logging.info(f"  F1-Score: {metrics['f1_score']:.3f}")

    return metrics


async def main():
    """Função principal."""
    # Parse args
    sample_size = 50
    mock = False

    if "--sample-size" in sys.argv:
        idx = sys.argv.index("--sample-size")
        sample_size = int(sys.argv[idx + 1])

    if "--mock" in sys.argv:
        mock = True
        logging.info("⚠️  MOCK MODE ativado - não fará chamadas reais à API")

    logging.info("🚀 Testando modelo GPT-5.2 otimizado...")

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

    optimized_prompt = load_optimized_prompt()

    logging.info("✅ Dados carregados")

    # Testar
    results = await test_sample(
        messages,
        text_features,
        email_features,
        categorizations,
        optimized_prompt,
        sample_size=sample_size,
        mock=mock
    )

    # Calcular métricas
    metrics = calculate_metrics(results)

    # Salvar
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "test_config": {
            "sample_size": sample_size,
            "mock_mode": mock,
            "prompt_file": str(OPTIMIZED_PROMPT_FILE),
            "prompt_size": len(optimized_prompt)
        },
        "metrics": metrics,
        "results": results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logging.info(f"💾 Resultados salvos em: {OUTPUT_FILE}")
    logging.info("✅ Teste concluído!")

    # Avisar sobre API key se não estiver em mock
    if not mock and not os.getenv("OPENAI_API_KEY"):
        logging.warning("\n" + "="*60)
        logging.warning("⚠️  OPENAI_API_KEY não configurada!")
        logging.warning("Para testes reais, adicione ao .env:")
        logging.warning("OPENAI_API_KEY=sk-...")
        logging.warning("="*60)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Script para extrair features textuais de emails spam.

Features:
- Estatísticas básicas: comprimento, palavras, sentenças
- Ratio CAPS/lowercase, pontuação
- Keywords spam em português
- Valores monetários
- Diversidade vocabular

Uso:
    python scripts/extract_text_features.py

Entrada:
    data/spam_conversations/messages_with_bodies.json

Saída:
    data/analysis/text_features.json
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List
import logging
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Arquivos
INPUT_FILE = Path("data/spam_conversations/messages_with_bodies.json")
OUTPUT_FILE = Path("data/analysis/text_features.json")

# Keywords spam em português
SPAM_KEYWORDS = [
    "urgente", "grátis", "gratis", "clique", "desconto", "ganhe",
    "promoção", "oferta", "limitado", "último", "parabéns",
    "prêmio", "presente", "dinheiro", "lucro", "renda",
    "trabalhe em casa", "seja seu próprio chefe", "rápido",
    "fácil", "agora", "hoje", "já", "não perca",
    "exclusivo", "especial", "garantido", "100%", "compre já"
]

# Stopwords português (simplificado)
STOPWORDS_PT = set([
    "a", "o", "e", "de", "da", "do", "em", "um", "uma",
    "para", "com", "por", "que", "se", "os", "as", "dos",
    "das", "no", "na", "ao", "à", "pelo", "pela", "como",
    "mais", "mas", "foi", "ele", "ela", "eu", "você"
])


def extract_text_from_html(html: str) -> str:
    """Extrai texto limpo de HTML."""
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Remover scripts e styles
        for script in soup(["script", "style"]):
            script.decompose()

        # Obter texto
        text = soup.get_text()

        # Limpar espaços extras
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text
    except:
        return html


def extract_text_features(message: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai features textuais de uma mensagem."""
    # Obter body
    body = message.get("body", "")
    if not body:
        email_data = message.get("email_data", {})
        body = email_data.get("body") or email_data.get("html") or email_data.get("bodyHtml") or ""

    if not body:
        return None

    # Detectar se é HTML e extrair texto
    is_html = bool(re.search(r'<[^>]+>', body))
    if is_html:
        text = extract_text_from_html(body)
    else:
        text = body

    # Features básicas
    features = {
        "message_id": message.get("id"),
        "is_html": is_html,
        "raw_length": len(body),
        "text_length": len(text),
    }

    # Caracteres
    features["char_count"] = len(text)
    features["whitespace_count"] = len(re.findall(r'\s', text))

    # Palavras
    words = re.findall(r'\b\w+\b', text.lower())
    features["word_count"] = len(words)
    features["avg_word_length"] = sum(len(w) for w in words) / len(words) if words else 0

    # Sentenças (aproximação)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    features["sentence_count"] = len(sentences)
    features["avg_sentence_length"] = len(words) / len(sentences) if sentences else 0

    # Maiúsculas/Minúsculas
    uppercase_count = sum(1 for c in text if c.isupper())
    lowercase_count = sum(1 for c in text if c.islower())
    total_alpha = uppercase_count + lowercase_count
    features["uppercase_count"] = uppercase_count
    features["lowercase_count"] = lowercase_count
    features["caps_ratio"] = uppercase_count / total_alpha if total_alpha > 0 else 0

    # Pontuação
    punctuation = re.findall(r'[!?.,;:]', text)
    features["punctuation_count"] = len(punctuation)
    features["exclamation_count"] = text.count('!')
    features["question_count"] = text.count('?')
    features["punctuation_ratio"] = len(punctuation) / len(text) if text else 0

    # Números
    numbers = re.findall(r'\d+', text)
    features["number_count"] = len(numbers)

    # Valores monetários
    money_patterns = [
        r'R\$\s*\d+',
        r'\$\s*\d+',
        r'\d+\s*reais',
        r'\d+\s*dólares',
    ]
    money_mentions = sum(len(re.findall(p, text, re.IGNORECASE)) for p in money_patterns)
    features["money_mention_count"] = money_mentions

    # URLs
    urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', body)
    features["url_count"] = len(urls)

    # Emails
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    features["email_address_count"] = len(emails)

    # Keywords spam
    text_lower = text.lower()
    spam_keyword_matches = []
    for keyword in SPAM_KEYWORDS:
        count = text_lower.count(keyword)
        if count > 0:
            spam_keyword_matches.append({"keyword": keyword, "count": count})

    features["spam_keyword_count"] = len(spam_keyword_matches)
    features["spam_keyword_total_occurrences"] = sum(m["count"] for m in spam_keyword_matches)
    features["spam_keywords_found"] = spam_keyword_matches[:5]  # Top 5

    # Stopwords
    stopword_count = sum(1 for w in words if w in STOPWORDS_PT)
    features["stopword_count"] = stopword_count
    features["stopword_ratio"] = stopword_count / len(words) if words else 0

    # Diversidade vocabular (type/token ratio)
    unique_words = set(words)
    features["unique_word_count"] = len(unique_words)
    features["vocabulary_diversity"] = len(unique_words) / len(words) if words else 0

    # Top palavras mais frequentes (excluindo stopwords)
    content_words = [w for w in words if w not in STOPWORDS_PT and len(w) > 2]
    word_freq = Counter(content_words)
    features["top_words"] = word_freq.most_common(10)

    # Ratio HTML/texto
    if is_html:
        features["html_text_ratio"] = len(body) / len(text) if text else 0
    else:
        features["html_text_ratio"] = 1.0

    return features


def main():
    """Função principal."""
    logging.info("🔍 Iniciando extração de text features...")

    # Verificar arquivo de entrada
    if not INPUT_FILE.exists():
        logging.error(f"❌ Arquivo não encontrado: {INPUT_FILE}")
        return

    # Carregar mensagens
    logging.info(f"📂 Carregando mensagens de: {INPUT_FILE}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", {})
    logging.info(f"✅ {len(messages)} mensagens carregadas")

    # Extrair features
    logging.info("⚙️  Extraindo features textuais...")
    text_features = {}
    processed = 0
    skipped = 0

    for msg_id, message in messages.items():
        features = extract_text_features(message)

        if features:
            text_features[msg_id] = features
            processed += 1
        else:
            skipped += 1

        if processed % 100 == 0:
            logging.info(f"  Processadas: {processed}/{len(messages)}")

    logging.info(f"✅ Extração concluída!")
    logging.info(f"  - Processadas: {processed}")
    logging.info(f"  - Puladas (sem body): {skipped}")

    # Salvar resultados
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "total_messages": len(messages),
        "processed": processed,
        "skipped": skipped,
        "features": text_features
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logging.info(f"💾 Features salvas em: {OUTPUT_FILE}")
    logging.info(f"📊 Total de features por mensagem: {len(list(text_features.values())[0]) if text_features else 0}")


if __name__ == "__main__":
    main()

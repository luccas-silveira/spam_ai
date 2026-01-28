#!/usr/bin/env python3
"""
Script para extrair features técnicas de emails.

Features:
- Estrutura HTML: tags count, ratio
- URLs: quantidade, domínios, shorteners
- Tracking: pixels, hidden images
- Subject analysis

Uso:
    python scripts/extract_email_features.py

Entrada:
    data/spam_conversations/messages_with_bodies.json

Saída:
    data/analysis/email_features.json
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Set
from urllib.parse import urlparse
import logging
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Arquivos
INPUT_FILE = Path("data/spam_conversations/messages_with_bodies.json")
OUTPUT_FILE = Path("data/analysis/email_features.json")

# URL shorteners conhecidos
URL_SHORTENERS = [
    'bit.ly', 'tinyurl.com', 'goo.gl', 'ow.ly', 't.co',
    'is.gd', 'buff.ly', 'adf.ly', 'bit.do', 'mcaf.ee',
    'su.pr', 'tiny.cc', 'bc.vc'
]


def extract_urls_from_body(body: str) -> List[Dict[str, Any]]:
    """Extrai URLs do body e analisa."""
    urls_info = []

    # Encontrar URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, body)

    for url in urls:
        try:
            parsed = urlparse(url)
            url_info = {
                "url": url,
                "domain": parsed.netloc.lower(),
                "scheme": parsed.scheme,
                "has_query": bool(parsed.query),
                "is_shortener": any(short in parsed.netloc.lower() for short in URL_SHORTENERS),
                "is_ip": bool(re.match(r'\d+\.\d+\.\d+\.\d+', parsed.netloc))
            }
            urls_info.append(url_info)
        except:
            continue

    return urls_info


def extract_html_features(body: str) -> Dict[str, Any]:
    """Extrai features de estrutura HTML."""
    try:
        soup = BeautifulSoup(body, 'html.parser')

        features = {}

        # Contagem de tags
        features["img_count"] = len(soup.find_all('img'))
        features["a_count"] = len(soup.find_all('a'))
        features["script_count"] = len(soup.find_all('script'))
        features["iframe_count"] = len(soup.find_all('iframe'))
        features["form_count"] = len(soup.find_all('form'))
        features["table_count"] = len(soup.find_all('table'))
        features["div_count"] = len(soup.find_all('div'))

        # Tracking pixels (imagens 1x1 ou muito pequenas)
        tracking_pixels = 0
        hidden_images = 0

        for img in soup.find_all('img'):
            width = img.get('width', '0')
            height = img.get('height', '0')
            style = img.get('style', '')

            try:
                w = int(re.sub(r'[^\d]', '', str(width)) or '0')
                h = int(re.sub(r'[^\d]', '', str(height)) or '0')

                if w <= 1 and h <= 1:
                    tracking_pixels += 1
                if 'display:none' in style.replace(' ', '') or 'visibility:hidden' in style.replace(' ', ''):
                    hidden_images += 1
            except:
                continue

        features["tracking_pixel_count"] = tracking_pixels
        features["hidden_image_count"] = hidden_images

        # Links com texto diferente do href
        link_text_mismatch = 0
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.get_text().strip()

            if href and text and href.startswith('http'):
                try:
                    domain_in_href = urlparse(href).netloc.lower()
                    if domain_in_href not in text.lower():
                        link_text_mismatch += 1
                except:
                    continue

        features["link_text_mismatch_count"] = link_text_mismatch

        # Obter texto para calcular ratio
        text = soup.get_text()
        text_length = len(text.strip())

        features["html_length"] = len(body)
        features["text_length"] = text_length
        features["html_text_ratio"] = len(body) / text_length if text_length > 0 else 0

        return features

    except Exception as e:
        logging.debug(f"Erro ao extrair HTML features: {e}")
        return {}


def extract_subject_features(message: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai features do subject."""
    meta = message.get("meta", {})
    email_meta = meta.get("email", {})
    subject = email_meta.get("subject", "")

    features = {
        "subject": subject,
        "subject_length": len(subject),
        "subject_word_count": len(subject.split()),
        "subject_has_emojis": bool(re.search(r'[^\x00-\x7F]', subject)),
        "subject_caps_ratio": 0,
        "subject_has_re": subject.lower().startswith(('re:', 'fwd:', 'fw:')),
        "subject_exclamation_count": subject.count('!'),
        "subject_question_count": subject.count('?')
    }

    # CAPS ratio
    if subject:
        uppercase = sum(1 for c in subject if c.isupper())
        lowercase = sum(1 for c in subject if c.islower())
        total_alpha = uppercase + lowercase
        features["subject_caps_ratio"] = uppercase / total_alpha if total_alpha > 0 else 0

    return features


def extract_email_features(message: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai features técnicas de email."""
    # Obter body
    body = message.get("body", "")
    if not body:
        email_data = message.get("email_data", {})
        body = email_data.get("body") or email_data.get("html") or email_data.get("bodyHtml") or ""

    if not body:
        return None

    features = {
        "message_id": message.get("id"),
        "message_type": message.get("messageType", "")
    }

    # Subject features
    subject_features = extract_subject_features(message)
    features.update(subject_features)

    # Detectar se é HTML
    is_html = bool(re.search(r'<[^>]+>', body))
    features["is_html"] = is_html

    # URLs
    urls_info = extract_urls_from_body(body)
    features["url_count"] = len(urls_info)
    features["unique_domains"] = len(set(u["domain"] for u in urls_info))
    features["shortener_url_count"] = sum(1 for u in urls_info if u["is_shortener"])
    features["ip_url_count"] = sum(1 for u in urls_info if u["is_ip"])
    features["https_url_count"] = sum(1 for u in urls_info if u["scheme"] == "https")
    features["http_url_count"] = sum(1 for u in urls_info if u["scheme"] == "http")
    features["urls_with_query"] = sum(1 for u in urls_info if u["has_query"])

    # Top domínios
    domain_counts = {}
    for u in urls_info:
        domain_counts[u["domain"]] = domain_counts.get(u["domain"], 0) + 1

    top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    features["top_domains"] = [{"domain": d, "count": c} for d, c in top_domains]

    # HTML features (se for HTML)
    if is_html:
        html_features = extract_html_features(body)
        features.update(html_features)
    else:
        # Preencher com zeros para manter schema consistente
        features.update({
            "img_count": 0,
            "a_count": 0,
            "script_count": 0,
            "iframe_count": 0,
            "form_count": 0,
            "table_count": 0,
            "div_count": 0,
            "tracking_pixel_count": 0,
            "hidden_image_count": 0,
            "link_text_mismatch_count": 0,
            "html_length": len(body),
            "text_length": len(body),
            "html_text_ratio": 1.0
        })

    return features


def main():
    """Função principal."""
    logging.info("📧 Iniciando extração de email features...")

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
    logging.info("⚙️  Extraindo email features...")
    email_features = {}
    processed = 0
    skipped = 0

    for msg_id, message in messages.items():
        features = extract_email_features(message)

        if features:
            email_features[msg_id] = features
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
        "features": email_features
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logging.info(f"💾 Features salvas em: {OUTPUT_FILE}")
    logging.info(f"📊 Total de features por mensagem: {len(list(email_features.values())[0]) if email_features else 0}")


if __name__ == "__main__":
    main()

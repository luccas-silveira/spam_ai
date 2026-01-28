#!/usr/bin/env python3
"""
Script para analisar os dados de spam coletados do GoHighLevel.

Gera relatórios e estatísticas sobre:
- Tipos de mensagens
- Canais (email, SMS, WhatsApp)
- Padrões comuns
- Palavras-chave frequentes

Uso:
    python scripts/analyze_spam_data.py
"""

import json
from pathlib import Path
from collections import Counter
from datetime import datetime
from typing import Dict, List, Any
import re

# Diretório de entrada
DATA_DIR = Path("data/spam_conversations")


def load_collected_data() -> Dict[str, Any]:
    """Carrega dados coletados."""
    print("📂 Carregando dados coletados...")

    if not DATA_DIR.exists():
        print(f"❌ Diretório não encontrado: {DATA_DIR}")
        print("   Execute 'python scripts/collect_spam_conversations.py' primeiro.")
        return None

    contacts_file = DATA_DIR / "contacts_with_spam_tag.json"
    conversations_file = DATA_DIR / "conversations_by_contact.json"
    messages_file = DATA_DIR / "messages_by_conversation.json"
    metadata_file = DATA_DIR / "collection_metadata.json"

    # Verificar arquivos
    if not all([f.exists() for f in [contacts_file, conversations_file, messages_file]]):
        print("❌ Arquivos de dados incompletos!")
        return None

    with open(contacts_file, 'r', encoding='utf-8') as f:
        contacts = json.load(f)

    with open(conversations_file, 'r', encoding='utf-8') as f:
        conversations = json.load(f)

    with open(messages_file, 'r', encoding='utf-8') as f:
        messages = json.load(f)

    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

    print(f"✅ Dados carregados com sucesso!")
    print(f"   - {len(contacts)} contatos")
    print(f"   - {len(conversations)} grupos de conversas")
    print(f"   - {len(messages)} conversas com mensagens\n")

    return {
        "contacts": contacts,
        "conversations": conversations,
        "messages": messages,
        "metadata": metadata
    }


def analyze_message_types(data: Dict[str, Any]):
    """Analisa tipos de mensagens."""
    print("=" * 70)
    print("📊 ANÁLISE DE TIPOS DE MENSAGENS")
    print("=" * 70)

    messages_dict = data["messages"]
    type_counter = Counter()
    direction_counter = Counter()
    channel_counter = Counter()

    total_messages = 0

    for conversation_id, messages in messages_dict.items():
        for msg in messages:
            total_messages += 1

            # Tipo de mensagem
            msg_type = msg.get("type", "unknown")
            type_counter[msg_type] += 1

            # Direção
            direction = msg.get("direction", "unknown")
            direction_counter[direction] += 1

            # Canal (inferido do tipo ou dados)
            if "email" in msg_type.lower():
                channel_counter["EMAIL"] += 1
            elif "sms" in msg_type.lower():
                channel_counter["SMS"] += 1
            elif "whatsapp" in msg_type.lower() or "FB" in msg_type:
                channel_counter["WhatsApp/Social"] += 1
            else:
                channel_counter["Outro"] += 1

    print(f"\n📧 Total de mensagens: {total_messages}\n")

    print("Tipos de mensagem:")
    for msg_type, count in type_counter.most_common():
        pct = (count / total_messages) * 100
        print(f"  {msg_type:20s}: {count:5d} ({pct:5.1f}%)")

    print("\nDireção das mensagens:")
    for direction, count in direction_counter.most_common():
        pct = (count / total_messages) * 100
        print(f"  {direction:20s}: {count:5d} ({pct:5.1f}%)")

    print("\nCanais identificados:")
    for channel, count in channel_counter.most_common():
        pct = (count / total_messages) * 100
        print(f"  {channel:20s}: {count:5d} ({pct:5.1f}%)")


def extract_text_from_messages(data: Dict[str, Any]) -> List[str]:
    """Extrai texto de todas as mensagens."""
    texts = []

    for conversation_id, messages in data["messages"].items():
        for msg in messages:
            body = msg.get("body", "")
            if body and isinstance(body, str):
                texts.append(body)

    return texts


def analyze_keywords(texts: List[str], top_n: int = 50):
    """Analisa palavras-chave mais frequentes."""
    print("\n" + "=" * 70)
    print("🔤 ANÁLISE DE PALAVRAS-CHAVE")
    print("=" * 70)

    # Combinar todos os textos
    combined = " ".join(texts).lower()

    # Remover HTML tags
    combined = re.sub(r'<[^>]+>', '', combined)

    # Tokenizar (palavras de 3+ caracteres)
    words = re.findall(r'\b[a-záàâãéèêíïóôõöúçñ]{3,}\b', combined)

    # Stop words básicas em português
    stop_words = {
        'que', 'para', 'com', 'uma', 'por', 'de', 'da', 'do', 'em', 'no', 'na',
        'os', 'as', 'um', 'ao', 'ou', 'se', 'dos', 'das', 'pelo', 'pela',
        'seu', 'sua', 'seus', 'suas', 'mais', 'sem', 'não', 'são', 'nos',
        'the', 'and', 'for', 'you', 'your', 'our', 'this', 'that', 'from'
    }

    # Filtrar stop words
    filtered = [w for w in words if w not in stop_words]

    # Contar frequências
    word_counter = Counter(filtered)

    print(f"\n📝 Total de palavras (após filtros): {len(filtered)}")
    print(f"🔢 Palavras únicas: {len(word_counter)}\n")

    print(f"Top {top_n} palavras mais frequentes:")
    for word, count in word_counter.most_common(top_n):
        print(f"  {word:20s}: {count:5d}")


def analyze_email_patterns(data: Dict[str, Any]):
    """Analisa padrões específicos de emails."""
    print("\n" + "=" * 70)
    print("📧 ANÁLISE DE PADRÕES DE EMAIL")
    print("=" * 70)

    email_messages = []

    for conversation_id, messages in data["messages"].items():
        for msg in messages:
            msg_type = msg.get("type", "").lower()
            if "email" in msg_type:
                email_messages.append(msg)

    print(f"\n📧 Total de emails encontrados: {len(email_messages)}\n")

    if not email_messages:
        print("ℹ️  Nenhum email encontrado nos dados coletados.")
        return

    # Analisar assuntos
    subjects = [msg.get("subject", "") for msg in email_messages if msg.get("subject")]
    print(f"Emails com assunto: {len(subjects)}")

    # Padrões suspeitos comuns
    patterns = {
        "URGENTE/IMPORTANTE": r'(?i)(urgente|importante|atenção|acao.*imediata)',
        "GANHE/DESCONTO": r'(?i)(ganhe|grátis|desconto|promoção|oferta)',
        "CLIQUE AQUI": r'(?i)(clique.*aqui|click.*here|acesse.*agora)',
        "R$ valores": r'R\$\s*[\d.,]+',
        "Links": r'https?://[^\s]+',
        "CAPSLOCK": r'\b[A-Z]{4,}\b'
    }

    pattern_counts = Counter()

    for email in email_messages:
        body = email.get("body", "")
        subject = email.get("subject", "")
        combined = f"{subject} {body}"

        for pattern_name, regex in patterns.items():
            if re.search(regex, combined):
                pattern_counts[pattern_name] += 1

    print("\nPadrões detectados:")
    for pattern, count in pattern_counts.most_common():
        pct = (count / len(email_messages)) * 100
        print(f"  {pattern:25s}: {count:5d} emails ({pct:5.1f}%)")


def generate_report(data: Dict[str, Any]):
    """Gera relatório completo."""
    print("\n" + "=" * 70)
    print("📈 RELATÓRIO GERAL")
    print("=" * 70)

    metadata = data.get("metadata", {})
    stats = metadata.get("stats", {})

    print(f"\n🕐 Coleta realizada em: {metadata.get('collected_at', 'N/A')}")
    print(f"⏱️  Tempo de coleta: {metadata.get('elapsed_seconds', 0):.1f}s")
    print()
    print(f"👥 Contatos com tag Spam: {stats.get('contacts_found', 0)}")
    print(f"💬 Conversas encontradas: {stats.get('conversations_found', 0)}")
    print(f"📧 Mensagens coletadas: {stats.get('messages_collected', 0)}")
    print(f"❌ Erros durante coleta: {stats.get('errors', 0)}")

    # Salvar relatório em arquivo
    report_file = DATA_DIR / "analysis_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO DE ANÁLISE DE SPAM - GoHighLevel\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Data da análise: {datetime.now().isoformat()}\n")
        f.write(f"Data da coleta: {metadata.get('collected_at', 'N/A')}\n")
        f.write(f"\nEstatísticas:\n")
        f.write(f"  Contatos: {stats.get('contacts_found', 0)}\n")
        f.write(f"  Conversas: {stats.get('conversations_found', 0)}\n")
        f.write(f"  Mensagens: {stats.get('messages_collected', 0)}\n")

    print(f"\n💾 Relatório salvo em: {report_file}")


def main():
    """Função principal."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║          Análise de Dados de Spam - GoHighLevel                     ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    # Carregar dados
    data = load_collected_data()

    if not data:
        return

    # Análises
    analyze_message_types(data)

    texts = extract_text_from_messages(data)
    if texts:
        analyze_keywords(texts)

    analyze_email_patterns(data)

    generate_report(data)

    print("\n✅ Análise concluída!")


if __name__ == "__main__":
    main()

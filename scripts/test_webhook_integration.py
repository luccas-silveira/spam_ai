#!/usr/bin/env python3
"""
Script para testar integração do sistema Two-Pass no webhook.

Envia emails de teste via curl para o webhook local.

Uso:
    1. Inicie o servidor: ghl-webhooks
    2. Execute este script: python scripts/test_webhook_integration.py
"""

import json
import subprocess
import time

# Emails de teste
TEST_EMAILS = [
    {
        "name": "DMARC Report (deve ser detectado por REGRA como NÃO-SPAM)",
        "payload": {
            "messageType": "EMAIL",
            "contactId": "test_contact_dmarc",
            "locationId": "test_location",
            "conversationId": "test_conv_1",
            "subject": "Report Domain: example.com Submitter: google.com Report-ID: 12345",
            "body": "This is an aggregated report for domain example.com",
            "type": "TYPE_EMAIL"
        },
        "expected": "não-spam (regra)"
    },
    {
        "name": "Currículo (deve ser detectado por REGRA como SPAM)",
        "payload": {
            "messageType": "EMAIL",
            "contactId": "test_contact_cv",
            "locationId": "test_location",
            "conversationId": "test_conv_2",
            "subject": "Currículo João Silva",
            "body": "Segue meu currículo em anexo para a vaga disponível.",
            "type": "TYPE_EMAIL"
        },
        "expected": "spam (regra)"
    },
    {
        "name": "Marketing com muitas URLs (deve ser detectado por REGRA como SPAM)",
        "payload": {
            "messageType": "EMAIL",
            "contactId": "test_contact_marketing",
            "locationId": "test_location",
            "conversationId": "test_conv_3",
            "subject": "SUPER OFERTA! Clique aqui",
            "body": """
                <html>
                <body>
                <a href="http://example.com/1">Link 1</a>
                <a href="http://example.com/2">Link 2</a>
                <a href="http://example.com/3">Link 3</a>
                <a href="http://example.com/4">Link 4</a>
                <a href="http://example.com/5">Link 5</a>
                <a href="http://example.com/6">Link 6</a>
                <a href="http://example.com/7">Link 7</a>
                <a href="http://example.com/8">Link 8</a>
                <a href="http://example.com/9">Link 9</a>
                <a href="http://example.com/10">Link 10</a>
                <a href="http://example.com/11">Link 11</a>
                <a href="http://example.com/12">Link 12</a>
                <a href="http://example.com/13">Link 13</a>
                <a href="http://example.com/14">Link 14</a>
                <a href="http://example.com/15">Link 15</a>
                <a href="http://example.com/16">Link 16</a>
                <img src="http://tracking.com/pixel.gif" width="1" height="1">
                <img src="http://tracking.com/pixel2.gif" width="1" height="1">
                <img src="http://tracking.com/pixel3.gif" width="1" height="1">
                </body>
                </html>
            """,
            "type": "TYPE_EMAIL"
        },
        "expected": "spam (regra)"
    },
    {
        "name": "Email ambíguo (deve usar GPT)",
        "payload": {
            "messageType": "EMAIL",
            "contactId": "test_contact_ambiguous",
            "locationId": "test_location",
            "conversationId": "test_conv_4",
            "subject": "Proposta de parceria",
            "body": "Olá, gostaria de discutir uma possível parceria para nossos negócios. Podemos agendar uma reunião?",
            "type": "TYPE_EMAIL"
        },
        "expected": "não-spam (GPT)"
    },
    {
        "name": "WhatsApp (não deve ser analisado)",
        "payload": {
            "messageType": "SMS",
            "contactId": "test_contact_whatsapp",
            "locationId": "test_location",
            "conversationId": "test_conv_5",
            "body": "Oi, tudo bem?",
            "type": "SMS"
        },
        "expected": "ignorado (não é email)"
    }
]


def send_webhook(payload: dict, test_name: str, expected: str):
    """Envia payload para webhook local."""
    print(f"\n{'='*80}")
    print(f"🧪 Teste: {test_name}")
    print(f"   Esperado: {expected}")
    print(f"{'='*80}")

    url = "http://localhost:8082/webhook/InboundMessage"

    try:
        # Converter payload para JSON
        payload_json = json.dumps(payload)

        # Enviar com curl
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", url,
             "-H", "Content-Type: application/json",
             "-d", payload_json],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print(f"✅ Resposta do webhook:")
            try:
                response = json.loads(result.stdout)
                print(json.dumps(response, indent=2))
            except:
                print(result.stdout)
        else:
            print(f"❌ Erro ao enviar webhook: {result.stderr}")

    except subprocess.TimeoutExpired:
        print(f"⏱️ Timeout ao enviar webhook")
    except Exception as e:
        print(f"❌ Erro: {e}")

    # Aguardar um pouco antes do próximo teste
    time.sleep(2)


def check_server():
    """Verifica se servidor está rodando."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8082/healthz"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def get_stats():
    """Busca estatísticas do sistema Two-Pass."""
    print(f"\n{'='*80}")
    print("📊 Estatísticas do Sistema Two-Pass")
    print(f"{'='*80}")

    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8082/webhook/spam-stats"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            stats = json.loads(result.stdout)
            if "two_pass_stats" in stats:
                s = stats["two_pass_stats"]
                print(f"\n  Total de emails: {s['total']}")
                print(f"  Detectados por regras: {s['fast_rules']} ({s['fast_rules_pct']}%)")
                print(f"  Detectados por GPT: {s['gpt_calls']} ({s['gpt_calls_pct']}%)")
                print(f"  Economia estimada: {s['estimated_savings_pct']}%")
                print(f"  Custo sem otimização: {s['cost_without_optimization']}")
                print(f"  Custo com two-pass: {s['cost_with_two_pass']}")
                print(f"  Economia: {s['savings']}\n")
            else:
                print(json.dumps(stats, indent=2))
        else:
            print(f"❌ Erro ao buscar estatísticas")

    except Exception as e:
        print(f"❌ Erro: {e}")


def main():
    """Função principal."""
    print("="*80)
    print("🧪 Teste de Integração do Sistema Two-Pass no Webhook")
    print("="*80)

    # Verificar se servidor está rodando
    if not check_server():
        print("\n❌ Servidor não está rodando em http://localhost:8082")
        print("   Inicie o servidor com: ghl-webhooks")
        return

    print("\n✅ Servidor está rodando\n")

    # Executar testes
    for test in TEST_EMAILS:
        send_webhook(test["payload"], test["name"], test["expected"])

    # Buscar estatísticas finais
    get_stats()

    print("\n✅ Testes concluídos!")
    print("\nPara ver os logs do servidor, verifique a saída do terminal onde executou 'ghl-webhooks'\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Two-Pass Spam Detection System

1ª Passagem: Regras rápidas baseadas em features (GRÁTIS, <100ms)
2ª Passagem: GPT-4o-mini para casos ambíguos (PAGO, ~2-3s)

Economia estimada: 60-70% de custos de API
"""

import re
import json
from typing import Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class TwoPassSpamDetector:
    """Detector de spam com sistema two-pass."""

    def __init__(self, openai_client=None):
        """
        Inicializa detector.

        Args:
            openai_client: Cliente OpenAI async (opcional, para 2ª passagem)
        """
        self.openai_client = openai_client
        self.stats = {
            "total": 0,
            "fast_rules": 0,
            "gpt_calls": 0
        }

    def extract_features(self, body: str, subject: str = "") -> Dict[str, Any]:
        """
        Extrai features rápidas do email.

        Args:
            body: Corpo do email (pode ser HTML)
            subject: Subject do email

        Returns:
            Dict com features calculadas
        """
        soup = BeautifulSoup(body, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)

        # URLs
        urls = soup.find_all('a', href=True)
        url_count = len(urls)

        # Extrair domínios únicos
        domains = []
        for url in urls:
            href = url.get('href', '')
            matches = re.findall(r'https?://([^/]+)', href)
            if matches:
                domains.append(matches[0])
        unique_domains = len(set(domains))

        # Imagens
        imgs = soup.find_all('img')
        img_count = len(imgs)

        # Tracking pixels (1x1 images)
        tracking_pixels = 0
        for img in imgs:
            width = img.get('width', '0')
            height = img.get('height', '0')
            w = int(re.sub(r'[^\d]', '', str(width)) or '0')
            h = int(re.sub(r'[^\d]', '', str(height)) or '0')
            if w <= 1 and h <= 1:
                tracking_pixels += 1

        # HTML/Text ratio
        html_length = len(body)
        text_length = len(text)
        html_text_ratio = html_length / max(text_length, 1)

        # Keywords spam
        spam_keywords = [
            'grátis', 'gratis', 'gratuito', 'free',
            'clique', 'click', 'urgente', 'urgent',
            'desconto', 'promoção', 'oferta', 'ganhe',
            'parabéns', 'congratulations', 'premio', 'prize'
        ]
        text_lower = text.lower()
        spam_keyword_count = sum(1 for kw in spam_keywords if kw in text_lower)

        # CAPS ratio
        caps_count = sum(1 for c in text if c.isupper())
        caps_ratio = caps_count / max(len(text), 1)

        # Exclamações
        exclamation_count = text.count('!')

        return {
            'url_count': url_count,
            'img_count': img_count,
            'unique_domains': unique_domains,
            'tracking_pixel_count': tracking_pixels,
            'html_text_ratio': html_text_ratio,
            'spam_keyword_count': spam_keyword_count,
            'caps_ratio': caps_ratio,
            'exclamation_count': exclamation_count,
            'subject': subject,
            'text_preview': text[:200]
        }

    def apply_fast_rules(
        self,
        features: Dict[str, Any]
    ) -> Tuple[Optional[bool], Optional[float], str]:
        """
        Aplica regras rápidas de detecção.

        Args:
            features: Features extraídas do email

        Returns:
            Tuple (is_spam, confidence, reason)
            - None se não conclusivo (precisa 2ª passagem)
        """
        subject = features.get('subject', '').lower()

        # REGRA 1: DMARC Reports (27.2% do dataset)
        if 'report domain:' in subject or 'dmarc' in subject:
            return False, 1.0, "DMARC report (regra)"

        # REGRA 2: Spam óbvio - Muitas URLs + tracking pixels
        if features['url_count'] > 15 and features['tracking_pixel_count'] > 2:
            return True, 0.95, "Alto volume URLs + tracking (regra)"

        # REGRA 3: Marketing agressivo - URLs + imagens + keywords
        if (features['url_count'] > 10 and
            features['img_count'] > 5 and
            features['spam_keyword_count'] > 3):
            return True, 0.92, "Marketing agressivo (regra)"

        # REGRA 4: Legítimo óbvio - Sem URLs, sem keywords spam
        if (features['url_count'] == 0 and
            features['spam_keyword_count'] == 0 and
            features['tracking_pixel_count'] == 0):
            return False, 0.90, "Email limpo sem sinais spam (regra)"

        # REGRA 5: HTML excessivo (típico de spam)
        if features['html_text_ratio'] > 20 and features['url_count'] > 5:
            return True, 0.88, "HTML pesado + URLs (regra)"

        # REGRA 6: Currículos - Subject pattern
        if 'currículo' in subject or 'curriculo' in subject or 'cv ' in subject:
            return True, 0.85, "Currículo não solicitado (regra)"

        # REGRA 7: CAPS excessivo (spam)
        if features['caps_ratio'] > 0.4 and len(features['text_preview']) > 50:
            return True, 0.87, "CAPS excessivo (regra)"

        # NÃO CONCLUSIVO - precisa GPT
        return None, None, "Ambíguo - requer análise GPT"

    async def detect_with_gpt(
        self,
        body: str,
        features: Dict[str, Any],
        system_prompt: str
    ) -> Dict[str, Any]:
        """
        Detecção usando GPT-4o-mini (2ª passagem).

        Args:
            body: Corpo do email
            features: Features calculadas
            system_prompt: Prompt otimizado

        Returns:
            Dict com is_spam, confidence, reason, category
        """
        if not self.openai_client:
            logger.warning("OpenAI client não configurado, assumindo não-spam")
            return {
                "is_spam": False,
                "confidence": 0.5,
                "reason": "OpenAI não disponível",
                "category": "unknown",
                "method": "fallback"
            }

        # Preparar prompt com features
        body_preview = body[:1000] if len(body) > 1000 else body

        analysis_prompt = f"""
# EMAIL PARA ANÁLISE

**Subject:** {features['subject']}

**Body (início):**
{body_preview}...

## FEATURES CALCULADAS

- **URLs**: {features['url_count']}
- **Imagens**: {features['img_count']}
- **HTML/Text Ratio**: {features['html_text_ratio']:.2f}
- **Domínios únicos**: {features['unique_domains']}
- **Tracking pixels**: {features['tracking_pixel_count']}
- **Keywords spam**: {features['spam_keyword_count']}
- **CAPS ratio**: {features['caps_ratio']:.2f}
- **Exclamações**: {features['exclamation_count']}

Analise este email e retorne APENAS o JSON (sem markdown):
"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content

            # Remover markdown se presente
            if result_text.startswith('```'):
                result_text = re.sub(r'^```(?:json)?\s*|\s*```$', '', result_text, flags=re.MULTILINE)

            result = json.loads(result_text)
            result['method'] = 'gpt'
            return result

        except Exception as e:
            logger.error(f"Erro na API OpenAI: {e}", exc_info=True)
            return {
                "is_spam": False,
                "confidence": 0.5,
                "reason": f"Erro GPT: {str(e)}",
                "category": "error",
                "method": "error"
            }

    async def detect(
        self,
        body: str,
        subject: str = "",
        system_prompt: str = None
    ) -> Dict[str, Any]:
        """
        Detecta spam usando two-pass system.

        Args:
            body: Corpo do email
            subject: Subject do email
            system_prompt: Prompt para GPT (se necessário)

        Returns:
            Dict com is_spam, confidence, reason, method
        """
        self.stats['total'] += 1

        # Extrair features
        features = self.extract_features(body, subject)

        # 1ª PASSAGEM - Regras rápidas
        is_spam, confidence, reason = self.apply_fast_rules(features)

        if is_spam is not None:
            # Conclusivo com regras
            self.stats['fast_rules'] += 1
            logger.info(f"✅ Detectado por REGRA: {reason}")
            return {
                "is_spam": is_spam,
                "confidence": confidence,
                "reason": reason,
                "method": "fast_rule",
                "features": features
            }

        # 2ª PASSAGEM - GPT para casos ambíguos
        self.stats['gpt_calls'] += 1
        logger.info(f"🤖 Caso ambíguo, chamando GPT... (Razão: {reason})")

        if not system_prompt:
            # Prompt padrão simples
            system_prompt = """Você é um especialista em detecção de spam.
Analise o email e retorne JSON: {"is_spam": bool, "confidence": 0-1, "reason": "explicação", "category": "tipo"}"""

        gpt_result = await self.detect_with_gpt(body, features, system_prompt)
        gpt_result['features'] = features

        return gpt_result

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso."""
        total = self.stats['total']
        if total == 0:
            return {
                "total": 0,
                "fast_rules_pct": 0,
                "gpt_calls_pct": 0,
                "estimated_savings": 0
            }

        fast_pct = (self.stats['fast_rules'] / total) * 100
        gpt_pct = (self.stats['gpt_calls'] / total) * 100

        # Custo estimado: $0.0003 por email GPT
        cost_with_gpt = total * 0.0003
        cost_two_pass = self.stats['gpt_calls'] * 0.0003
        savings_pct = ((cost_with_gpt - cost_two_pass) / cost_with_gpt) * 100 if cost_with_gpt > 0 else 0

        return {
            "total": total,
            "fast_rules": self.stats['fast_rules'],
            "gpt_calls": self.stats['gpt_calls'],
            "fast_rules_pct": round(fast_pct, 1),
            "gpt_calls_pct": round(gpt_pct, 1),
            "estimated_savings_pct": round(savings_pct, 1),
            "cost_without_optimization": f"${cost_with_gpt:.4f}",
            "cost_with_two_pass": f"${cost_two_pass:.4f}",
            "savings": f"${cost_with_gpt - cost_two_pass:.4f}"
        }

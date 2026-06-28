import json
import logging

import httpx

from app.core.config import settings
from app.models.models import ComplaintType, Sentiment, Severity
from app.schemas.schemas import ClassificationResult

logger = logging.getLogger(__name__)

CLASSIFICATION_SYSTEM_PROMPT = """You are a complaint classification assistant. Given a customer complaint, classify it and return ONLY valid JSON matching this exact schema — no preamble, no markdown fences:
{
  "type": "billing | service | product_defect | delay | other",
  "product": "string — the product or service name",
  "severity": "critical | high | medium | low",
  "sentiment": "negative | neutral | positive",
  "key_issues": ["short phrase", "short phrase"],
  "confidence": 0.0
}
Rules:
- type must be one of: billing, service, product_defect, delay, other
- severity: critical = system down / financial loss / safety; high = major feature broken; medium = workaround exists; low = cosmetic / minor
- confidence: your estimated confidence between 0.0 and 1.0
- key_issues: 1-5 short phrases capturing the core problems
"""

VALID_TYPES = {t.value for t in ComplaintType}
VALID_SEVERITIES = {s.value for s in Severity}
VALID_SENTIMENTS = {s.value for s in Sentiment}


def default_classification() -> ClassificationResult:
    return ClassificationResult(
        type=ComplaintType.other,
        product="unknown",
        severity=Severity.medium,
        sentiment=Sentiment.neutral,
        key_issues=["needs manual review"],
        confidence=0.0,
    )


def _validate_classification(raw: dict) -> ClassificationResult:
    try:
        comp_type = raw.get("type", "other")
        if comp_type not in VALID_TYPES:
            comp_type = "other"

        severity = raw.get("severity", "medium")
        if severity not in VALID_SEVERITIES:
            severity = "medium"

        sentiment = raw.get("sentiment", "neutral")
        if sentiment not in VALID_SENTIMENTS:
            sentiment = "neutral"

        return ClassificationResult(
            type=ComplaintType(comp_type),
            product=str(raw.get("product", "unknown")),
            severity=Severity(severity),
            sentiment=Sentiment(sentiment),
            key_issues=raw.get("key_issues", ["needs manual review"])[:5],
            confidence=float(raw.get("confidence", 0.0)),
        )
    except Exception as exc:
        logger.warning("Classification validation failed: %s — raw: %s", exc, raw)
        return default_classification()


async def classify_complaint(title: str, description: str) -> ClassificationResult:
    user_content = f"Title: {title}\nDescription: {description}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            raw = json.loads(content)
            return _validate_classification(raw)
    except Exception as exc:
        logger.error("LLM classification call failed: %s", exc)
        return default_classification()

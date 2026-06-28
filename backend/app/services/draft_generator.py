import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DRAFT_SYSTEM_PROMPT = """You are a customer support agent drafting a professional response to a customer complaint.
Write a compassionate, clear, and actionable response. Address the customer by name if provided.
Keep the tone professional and empathetic. Suggest next steps where appropriate.
Do not make promises about specific timelines unless provided in the context.
Return only the response text — no preamble, no JSON, no markdown fences."""


async def generate_draft_response(
    complaint_title: str,
    complaint_description: str,
    customer_name: str,
    complaint_type: str | None = None,
    product: str | None = None,
    severity: str | None = None,
    resolution_template: str | None = None,
) -> str | None:
    context_parts = [
        f"Complaint Title: {complaint_title}",
        f"Complaint Description: {complaint_description}",
        f"Customer Name: {customer_name}",
    ]
    if complaint_type:
        context_parts.append(f"Complaint Type: {complaint_type}")
    if product:
        context_parts.append(f"Product: {product}")
    if severity:
        context_parts.append(f"Severity: {severity}")
    if resolution_template:
        context_parts.append(f"Suggested Resolution Template: {resolution_template}")

    user_content = "\n".join(context_parts)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.4,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("Draft response generation failed: %s", exc)
        return None

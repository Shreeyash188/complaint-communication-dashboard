import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_SYSTEM_PROMPT = ""


async def generate_embedding(text: str) -> list[float] | None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.llm_base_url}/embeddings",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.embedding_model,
                    "input": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    except Exception as exc:
        logger.error("Embedding generation failed: %s", exc)
        return None

"""Embedding generation using OpenAI."""

from typing import List, Optional
import asyncio

from openai import AsyncOpenAI

from ..utils import get_settings, get_logger, get_rate_limiter

logger = get_logger(__name__)


class EmbeddingGenerator:
    """Generate embeddings using OpenAI's API."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "text-embedding-3-small"
        self.rate_limiter = get_rate_limiter("openai")

    async def generate(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text."""
        if not text or len(text.strip()) == 0:
            return None

        try:
            await self.rate_limiter.acquire()

            # Truncate if too long (8191 tokens max, roughly 32k chars)
            text = text[:30000]

            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding", error=str(e))
            return None

    async def generate_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts."""
        # Process in batches of 100 (API limit)
        results = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                await self.rate_limiter.acquire()

                # Filter and truncate
                processed_batch = [
                    t[:30000] if t and len(t.strip()) > 0 else ""
                    for t in batch
                ]

                # Track which indices had empty text
                empty_indices = {
                    j for j, t in enumerate(processed_batch)
                    if not t or len(t.strip()) == 0
                }

                # Filter out empty texts for API call
                non_empty = [t for t in processed_batch if t and len(t.strip()) > 0]

                if non_empty:
                    response = await self.client.embeddings.create(
                        model=self.model,
                        input=non_empty
                    )

                    # Map embeddings back to original indices
                    embedding_iter = iter(response.data)
                    for j in range(len(processed_batch)):
                        if j in empty_indices:
                            results.append(None)
                        else:
                            results.append(next(embedding_iter).embedding)
                else:
                    results.extend([None] * len(batch))

            except Exception as e:
                logger.error(f"Failed to generate batch embeddings", error=str(e))
                results.extend([None] * len(batch))

        return results


# Singleton
_generator: Optional[EmbeddingGenerator] = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get embedding generator singleton."""
    global _generator
    if _generator is None:
        _generator = EmbeddingGenerator()
    return _generator

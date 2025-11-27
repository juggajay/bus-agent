"""Signal classification using LLM."""

from typing import Dict, Any, Optional
import json

from anthropic import AsyncAnthropic

from ..database import RawSignal, EntityExtraction
from ..utils import get_settings, get_logger, get_rate_limiter, SIGNAL_TYPES

logger = get_logger(__name__)

CLASSIFICATION_PROMPT = """You are classifying a signal for a business intelligence system.

Signal source: {source_type}
Signal category: {source_category}
Signal content: {content}

Classify this signal:
1. Primary type (one of: trend, complaint, regulatory, funding, job_market, builder_activity, consumer_behaviour, competitive)
2. Subtype (specific category within the type)
3. Brief summary (1-2 sentences)
4. Key entities:
   - companies: List of company names mentioned
   - technologies: List of technologies, frameworks, tools mentioned
   - industries: List of industries/sectors mentioned
   - locations: List of geographic locations mentioned
5. Relevant keywords for search (5-10 keywords)

Respond ONLY with valid JSON in this exact format:
{{
    "signal_type": "string",
    "signal_subtype": "string",
    "summary": "string",
    "entities": {{
        "companies": ["string"],
        "technologies": ["string"],
        "industries": ["string"],
        "locations": ["string"]
    }},
    "keywords": ["string"]
}}"""


class SignalClassifier:
    """Classify signals using Claude."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")

    async def classify(self, signal: RawSignal) -> Dict[str, Any]:
        """Classify a raw signal."""
        try:
            await self.rate_limiter.acquire()

            # Prepare content for classification
            content = json.dumps(signal.raw_content, indent=2)[:10000]

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": CLASSIFICATION_PROMPT.format(
                        source_type=signal.source_type,
                        source_category=signal.source_category,
                        content=content
                    )
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Try to extract JSON from response
            if response_text.startswith("```"):
                # Remove markdown code blocks if present
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result = json.loads(response_text)

            # Validate signal type
            if result.get("signal_type") not in SIGNAL_TYPES:
                logger.warning(f"Invalid signal type: {result.get('signal_type')}")
                result["signal_type"] = "trend"

            return {
                "signal_type": result.get("signal_type", "trend"),
                "signal_subtype": result.get("signal_subtype", ""),
                "title": result.get("summary", "")[:200],
                "summary": result.get("summary", ""),
                "entities": EntityExtraction(
                    companies=result.get("entities", {}).get("companies", []),
                    technologies=result.get("entities", {}).get("technologies", []),
                    industries=result.get("entities", {}).get("industries", []),
                    locations=result.get("entities", {}).get("locations", [])
                ),
                "keywords": result.get("keywords", [])
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse classification response", error=str(e))
            return self._default_classification(signal)
        except Exception as e:
            logger.error(f"Classification failed", error=str(e))
            return self._default_classification(signal)

    def _default_classification(self, signal: RawSignal) -> Dict[str, Any]:
        """Return default classification when processing fails."""
        return {
            "signal_type": "trend",
            "signal_subtype": "unknown",
            "title": f"Signal from {signal.source_type}",
            "summary": f"Unclassified signal from {signal.source_type}",
            "entities": EntityExtraction(),
            "keywords": []
        }


# Singleton
_classifier: Optional[SignalClassifier] = None


def get_classifier() -> SignalClassifier:
    """Get classifier singleton."""
    global _classifier
    if _classifier is None:
        _classifier = SignalClassifier()
    return _classifier

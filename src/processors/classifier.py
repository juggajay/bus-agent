"""Signal classification using LLM - Solo SaaS Finder v2.0"""

from typing import Dict, Any, Optional
import json

from anthropic import AsyncAnthropic

from ..database import RawSignal, EntityExtraction
from ..utils import get_settings, get_logger, get_rate_limiter, SIGNAL_TYPES
from ..reasoning.prompts import CLASSIFICATION_PROMPT

logger = get_logger(__name__)


class SignalClassifier:
    """Classify signals using Claude for SaaS business opportunity discovery."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")

    async def classify(self, signal: RawSignal) -> Dict[str, Any]:
        """
        Classify a raw signal for SaaS opportunity discovery.

        Returns:
            Dict containing:
            - signal_type: One of demand_signal, complaint, trend, competition_intel, market_shift, builder_activity
            - signal_subtype: Specific subtype
            - title: Short title for the signal
            - summary: Brief summary
            - problem_summary: One-sentence problem description
            - demand_evidence_level: high/medium/low/none
            - industry: Specific industry/niche
            - entities: EntityExtraction object
            - keywords: List of keywords
        """
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

            # Validate signal type against new types
            valid_types = list(SIGNAL_TYPES.keys())
            signal_type = result.get("signal_type", "trend")
            if signal_type not in valid_types:
                logger.warning(f"Invalid signal type: {signal_type}, defaulting to trend")
                signal_type = "trend"

            return {
                "signal_type": signal_type,
                "signal_subtype": result.get("signal_subtype", ""),
                "title": result.get("summary", "")[:200],
                "summary": result.get("summary", ""),
                "problem_summary": result.get("problem_summary", ""),
                "demand_evidence_level": result.get("demand_evidence_level", "none"),
                "industry": result.get("industry", ""),
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
            "problem_summary": "",
            "demand_evidence_level": "none",
            "industry": "",
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

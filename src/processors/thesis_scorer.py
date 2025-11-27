"""Thesis scoring using LLM."""

from typing import Dict, Any, Optional
import json

from anthropic import AsyncAnthropic

from ..database import ThesisScores
from ..utils import get_settings, get_logger, get_rate_limiter, THESIS, OPERATOR_PROFILE

logger = get_logger(__name__)

THESIS_PROMPT = """You are evaluating a signal against a specific investment thesis for business opportunities.

THE THESIS:
1. AI Leverage - Opportunities where AI enables a solo operator or small team to do what previously required 20+ people
2. Trust Scarcity - Opportunities leveraging verified credentials, provable data, or authentic expertise as moats
3. Physical-Digital Intersection - Where real-world friction meets software solutions
4. Incumbent Decay - Markets where existing players are slow, bloated, or failing to adapt
5. Speed Advantage - Opportunities where fast execution and iteration provide competitive advantage
6. Execution Fit - Match with operator strengths: construction/trades, technical ability, solo operation, Australia/SEA geography

OPERATOR PROFILE:
- Background: {operator_background}
- Technical ability: {operator_technical}
- Geography: {operator_geography}
- Preferences: {operator_preferences}

SIGNAL:
Type: {signal_type}
Summary: {summary}
Entities: {entities}
Keywords: {keywords}

Score each thesis element 1-10 (1 = no alignment, 10 = perfect alignment). Use null if not applicable.
Provide brief reasoning for scores 7+.

Respond ONLY with valid JSON in this exact format:
{{
    "ai_leverage": {{"score": null, "reasoning": ""}},
    "trust_scarcity": {{"score": null, "reasoning": ""}},
    "physical_digital": {{"score": null, "reasoning": ""}},
    "incumbent_decay": {{"score": null, "reasoning": ""}},
    "speed_advantage": {{"score": null, "reasoning": ""}},
    "execution_fit": {{"score": null, "reasoning": ""}},
    "overall_reasoning": "brief summary of how this signal relates to the thesis"
}}"""


class ThesisScorer:
    """Score signals against the thesis using Claude."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")

    async def score(
        self,
        signal_type: str,
        summary: str,
        entities: Dict[str, Any],
        keywords: list
    ) -> Dict[str, Any]:
        """Score a signal against the thesis."""
        try:
            await self.rate_limiter.acquire()

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": THESIS_PROMPT.format(
                        operator_background=OPERATOR_PROFILE["background"],
                        operator_technical=OPERATOR_PROFILE["technical_ability"],
                        operator_geography=OPERATOR_PROFILE["geography"],
                        operator_preferences=", ".join(OPERATOR_PROFILE["preferences"]),
                        signal_type=signal_type,
                        summary=summary,
                        entities=json.dumps(entities),
                        keywords=", ".join(keywords)
                    )
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result = json.loads(response_text)

            # Extract scores
            scores = ThesisScores(
                ai_leverage=self._extract_score(result.get("ai_leverage")),
                trust_scarcity=self._extract_score(result.get("trust_scarcity")),
                physical_digital=self._extract_score(result.get("physical_digital")),
                incumbent_decay=self._extract_score(result.get("incumbent_decay")),
                speed_advantage=self._extract_score(result.get("speed_advantage")),
                execution_fit=self._extract_score(result.get("execution_fit"))
            )

            # Combine all reasoning
            reasoning_parts = []
            for key in ["ai_leverage", "trust_scarcity", "physical_digital",
                       "incumbent_decay", "speed_advantage", "execution_fit"]:
                item = result.get(key, {})
                if isinstance(item, dict) and item.get("reasoning"):
                    reasoning_parts.append(f"{key}: {item['reasoning']}")

            overall = result.get("overall_reasoning", "")
            if overall:
                reasoning_parts.insert(0, f"Overall: {overall}")

            return {
                "scores": scores,
                "reasoning": "\n".join(reasoning_parts)
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse thesis response", error=str(e))
            return {"scores": ThesisScores(), "reasoning": ""}
        except Exception as e:
            logger.error(f"Thesis scoring failed", error=str(e))
            return {"scores": ThesisScores(), "reasoning": ""}

    def _extract_score(self, item: Any) -> Optional[int]:
        """Extract score from response item."""
        if item is None:
            return None
        if isinstance(item, dict):
            score = item.get("score")
            if score is not None and isinstance(score, (int, float)):
                return max(1, min(10, int(score)))
        if isinstance(item, (int, float)):
            return max(1, min(10, int(item)))
        return None


# Singleton
_scorer: Optional[ThesisScorer] = None


def get_thesis_scorer() -> ThesisScorer:
    """Get thesis scorer singleton."""
    global _scorer
    if _scorer is None:
        _scorer = ThesisScorer()
    return _scorer

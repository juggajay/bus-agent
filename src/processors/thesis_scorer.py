"""Thesis scoring using LLM - Solo SaaS Finder v2.0"""

from typing import Dict, Any, Optional
import json

from anthropic import AsyncAnthropic

from ..database import ThesisScores
from ..utils import get_settings, get_logger, get_rate_limiter, THESIS, OPERATOR_PROFILE, is_disqualified_industry

logger = get_logger(__name__)

# Import the new thesis scoring prompt
from ..reasoning.prompts import THESIS_SCORING_PROMPT


class ThesisScorer:
    """Score signals against the Solo SaaS Finder thesis using Claude."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")

    async def score(
        self,
        signal_type: str,
        summary: str,
        entities: Dict[str, Any],
        keywords: list,
        industry: str = "",
        problem_summary: str = "",
        demand_evidence: str = "",
        raw_content: str = ""
    ) -> Dict[str, Any]:
        """
        Score a signal against the Solo SaaS Finder thesis.

        Returns:
            Dict containing:
            - scores: ThesisScores object with new 6 factors
            - reasoning: Combined reasoning text
            - is_disqualified: Whether the signal is from a disqualified industry
            - disqualification_reason: Reason for disqualification (if any)
        """
        try:
            # Check for disqualified industries first
            industries_to_check = entities.get("industries", []) if isinstance(entities, dict) else []
            if industry:
                industries_to_check.append(industry)

            for ind in industries_to_check:
                if is_disqualified_industry(ind):
                    logger.info(f"Signal disqualified due to industry: {ind}")
                    return {
                        "scores": ThesisScores(
                            demand_evidence=1,
                            competition_gap=1,
                            trend_timing=1,
                            solo_buildability=1,
                            clear_monetisation=1,
                            regulatory_simplicity=1
                        ),
                        "reasoning": f"Automatically disqualified: {ind} is a regulated industry",
                        "is_disqualified": True,
                        "disqualification_reason": f"Industry '{ind}' is in the disqualified list (regulated)"
                    }

            await self.rate_limiter.acquire()

            # Prepare content for scoring
            content = raw_content[:5000] if raw_content else summary

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": THESIS_SCORING_PROMPT.format(
                        signal_type=signal_type,
                        industry=industry or ", ".join(industries_to_check) or "Unknown",
                        problem_summary=problem_summary or summary,
                        demand_evidence=demand_evidence or "Not specified",
                        content=content
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

            # Check if LLM flagged as disqualified
            is_disqualified = result.get("disqualified", False)
            disqualification_reason = result.get("disqualification_reason")

            # Extract scores
            scores = ThesisScores(
                demand_evidence=self._extract_score(result.get("demand_evidence")),
                competition_gap=self._extract_score(result.get("competition_gap")),
                trend_timing=self._extract_score(result.get("trend_timing")),
                solo_buildability=self._extract_score(result.get("solo_buildability")),
                clear_monetisation=self._extract_score(result.get("clear_monetisation")),
                regulatory_simplicity=self._extract_score(result.get("regulatory_simplicity"))
            )

            # Combine all reasoning
            reasoning_parts = []
            for key in ["demand_evidence", "competition_gap", "trend_timing",
                       "solo_buildability", "clear_monetisation", "regulatory_simplicity"]:
                item = result.get(key, {})
                if isinstance(item, dict) and item.get("reasoning"):
                    reasoning_parts.append(f"{key}: {item['reasoning']}")

            overall = result.get("overall_saas_potential", "")
            if overall:
                reasoning_parts.insert(0, f"Overall: {overall}")

            return {
                "scores": scores,
                "reasoning": "\n".join(reasoning_parts),
                "is_disqualified": is_disqualified,
                "disqualification_reason": disqualification_reason
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse thesis response", error=str(e))
            return {
                "scores": ThesisScores(),
                "reasoning": "",
                "is_disqualified": False,
                "disqualification_reason": None
            }
        except Exception as e:
            logger.error(f"Thesis scoring failed", error=str(e))
            return {
                "scores": ThesisScores(),
                "reasoning": "",
                "is_disqualified": False,
                "disqualification_reason": None
            }

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

    def calculate_weighted_score(self, scores: ThesisScores) -> float:
        """
        Calculate a weighted overall score from individual thesis scores.

        Weights from config:
        - demand_evidence: 1.0
        - competition_gap: 1.0
        - trend_timing: 0.8
        - solo_buildability: 1.0
        - clear_monetisation: 1.0
        - regulatory_simplicity: 1.0

        Returns:
            Weighted average score (0-10 scale)
        """
        weights = {
            "demand_evidence": THESIS["demand_evidence"]["weight"],
            "competition_gap": THESIS["competition_gap"]["weight"],
            "trend_timing": THESIS["trend_timing"]["weight"],
            "solo_buildability": THESIS["solo_buildability"]["weight"],
            "clear_monetisation": THESIS["clear_monetisation"]["weight"],
            "regulatory_simplicity": THESIS["regulatory_simplicity"]["weight"],
        }

        total_weight = 0
        weighted_sum = 0

        score_values = {
            "demand_evidence": scores.demand_evidence,
            "competition_gap": scores.competition_gap,
            "trend_timing": scores.trend_timing,
            "solo_buildability": scores.solo_buildability,
            "clear_monetisation": scores.clear_monetisation,
            "regulatory_simplicity": scores.regulatory_simplicity,
        }

        for key, score in score_values.items():
            if score is not None:
                weight = weights.get(key, 1.0)
                weighted_sum += score * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight


# Singleton
_scorer: Optional[ThesisScorer] = None


def get_thesis_scorer() -> ThesisScorer:
    """Get thesis scorer singleton."""
    global _scorer
    if _scorer is None:
        _scorer = ThesisScorer()
    return _scorer

"""Opportunity generation from patterns."""

from typing import List, Optional, Dict, Any
from uuid import UUID
import json

from anthropic import AsyncAnthropic

from ..database import (
    PatternMatch, ProcessedSignal,
    OpportunityCreate, Opportunity,
    get_database
)
from ..utils import get_settings, get_logger, get_rate_limiter
from .prompts import OPPORTUNITY_GENERATION_PROMPT

logger = get_logger(__name__)


class OpportunityGenerator:
    """Generate opportunities from detected patterns."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")
        self.db = get_database()

    async def generate_from_pattern(
        self,
        pattern: PatternMatch,
        signals: List[ProcessedSignal]
    ) -> Optional[Opportunity]:
        """
        Generate an opportunity from a detected pattern.

        Args:
            pattern: The pattern to analyze
            signals: Related signals for context

        Returns:
            Generated and stored opportunity, or None if generation fails
        """
        try:
            await self.rate_limiter.acquire()

            # Format pattern details
            pattern_details = {
                "type": pattern.pattern_type,
                "title": pattern.title,
                "description": pattern.description,
                "hypothesis": pattern.hypothesis,
                "confidence": pattern.confidence_score,
                "opportunity_score": pattern.opportunity_score,
                "primary_thesis": pattern.primary_thesis_alignment
            }

            # Format signals
            formatted_signals = [{
                "type": s.signal_type,
                "title": s.title,
                "summary": s.summary,
                "keywords": s.keywords,
                "entities": s.entities.model_dump() if s.entities else {},
                "thesis_scores": s.thesis_scores.model_dump() if s.thesis_scores else {},
                "timing_stage": s.timing_stage,
                "velocity": s.velocity_score,
                "novelty": s.novelty_score
            } for s in signals[:10]]

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                messages=[{
                    "role": "user",
                    "content": OPPORTUNITY_GENERATION_PROMPT.format(
                        pattern_details=json.dumps(pattern_details, indent=2),
                        formatted_signals=json.dumps(formatted_signals, indent=2)
                    )
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result = json.loads(response_text)

            # Create opportunity
            opportunity_create = OpportunityCreate(
                title=result.get("title", pattern.title),
                summary=result.get("summary", ""),
                detailed_analysis=json.dumps(result.get("detailed_analysis", {})),
                pattern_ids=[pattern.id],
                signal_ids=list(pattern.signal_ids) if pattern.signal_ids else [],
                opportunity_type=result.get("opportunity_type", "product"),
                industries=self._extract_industries(signals),
                geographies=self._extract_geographies(signals),
                thesis_scores=result.get("thesis_alignment", {}),
                primary_thesis=result.get("primary_thesis", pattern.primary_thesis_alignment),
                execution_fit_reasoning=result.get("execution_fit_reasoning", ""),
                timing_stage=result.get("timing", {}).get("stage", "emerging"),
                time_sensitivity=result.get("timing", {}).get("window", ""),
                existing_players=result.get("competitive_landscape", {}).get("existing_players", []),
                incumbent_weakness=result.get("competitive_landscape", {}).get("incumbent_weakness", ""),
                estimated_complexity=self._estimate_complexity(result),
                key_requirements=result.get("key_requirements", []),
                potential_moats=result.get("competitive_landscape", {}).get("potential_moats", []),
                risks=result.get("risks", [])
            )

            # Store opportunity
            opportunity = await self.db.insert_opportunity(opportunity_create)

            logger.info(
                f"Generated opportunity",
                opportunity_id=str(opportunity.id),
                title=opportunity.title
            )

            return opportunity

        except json.JSONDecodeError as e:
            logger.error("Failed to parse opportunity response", error=str(e))
            return None
        except Exception as e:
            logger.error("Opportunity generation failed", error=str(e))
            return None

    async def generate_from_patterns(
        self,
        patterns: List[PatternMatch],
        signals: List[ProcessedSignal],
        min_score: float = 0.5
    ) -> List[Opportunity]:
        """
        Generate opportunities from multiple patterns.

        Args:
            patterns: Patterns to analyze
            signals: All signals for context
            min_score: Minimum opportunity score to consider

        Returns:
            List of generated opportunities
        """
        opportunities = []

        # Filter patterns by score
        high_score_patterns = [
            p for p in patterns
            if p.opportunity_score >= min_score
        ]

        for pattern in high_score_patterns:
            # Get related signals
            related_signals = [
                s for s in signals
                if s.id in (pattern.signal_ids or [])
            ]

            opportunity = await self.generate_from_pattern(pattern, related_signals)
            if opportunity:
                opportunities.append(opportunity)

        return opportunities

    def _extract_industries(self, signals: List[ProcessedSignal]) -> List[str]:
        """Extract unique industries from signals."""
        industries = set()
        for s in signals:
            if s.entities and s.entities.industries:
                industries.update(s.entities.industries)
        return list(industries)[:10]

    def _extract_geographies(self, signals: List[ProcessedSignal]) -> List[str]:
        """Extract unique geographies from signals."""
        geographies = set()
        for s in signals:
            if s.geography:
                geographies.add(s.geography)
            if s.entities and s.entities.locations:
                geographies.update(s.entities.locations)
        return list(geographies)[:5]

    def _estimate_complexity(self, result: Dict[str, Any]) -> str:
        """Estimate complexity based on requirements."""
        requirements = result.get("key_requirements", [])
        risks = result.get("risks", [])

        if len(requirements) <= 2 and len(risks) <= 2:
            return "low"
        elif len(requirements) <= 4 and len(risks) <= 4:
            return "medium"
        else:
            return "high"


# Singleton
_generator: Optional[OpportunityGenerator] = None


def get_opportunity_generator() -> OpportunityGenerator:
    """Get opportunity generator singleton."""
    global _generator
    if _generator is None:
        _generator = OpportunityGenerator()
    return _generator

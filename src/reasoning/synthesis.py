"""Synthesis and quarterly review generation."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from anthropic import AsyncAnthropic

from ..database import (
    ProcessedSignal, PatternMatch, Opportunity,
    get_database
)
from ..utils import get_settings, get_logger, get_rate_limiter
from .prompts import QUARTERLY_SYNTHESIS_PROMPT, DIGEST_GENERATION_PROMPT

logger = get_logger(__name__)


class Synthesizer:
    """Generate synthesis reports and digests."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")
        self.db = get_database()

    async def generate_quarterly_synthesis(
        self,
        quarter: str,
        signals: List[ProcessedSignal],
        patterns: List[PatternMatch],
        opportunities: List[Opportunity]
    ) -> Dict[str, Any]:
        """
        Generate a quarterly synthesis report.

        Args:
            quarter: Quarter identifier (e.g., "Q4 2024")
            signals: Signals from the quarter
            patterns: Patterns detected in the quarter
            opportunities: Opportunities identified in the quarter

        Returns:
            Synthesis report as dictionary
        """
        try:
            await self.rate_limiter.acquire()

            # Prepare summaries
            patterns_summary = self._summarize_patterns(patterns)
            opportunities_summary = self._summarize_opportunities(opportunities)
            thesis_distribution = self._calculate_thesis_distribution(signals)

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": QUARTERLY_SYNTHESIS_PROMPT.format(
                        quarter=quarter,
                        signal_count=len(signals),
                        pattern_count=len(patterns),
                        opportunity_count=len(opportunities),
                        patterns_summary=json.dumps(patterns_summary, indent=2),
                        opportunities_summary=json.dumps(opportunities_summary, indent=2),
                        thesis_distribution=json.dumps(thesis_distribution, indent=2)
                    )
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result = json.loads(response_text)

            return {
                "quarter": quarter,
                "generated_at": datetime.utcnow().isoformat(),
                "statistics": {
                    "signals": len(signals),
                    "patterns": len(patterns),
                    "opportunities": len(opportunities)
                },
                **result
            }

        except json.JSONDecodeError as e:
            logger.error("Failed to parse synthesis response", error=str(e))
            return self._default_synthesis(quarter, signals, patterns, opportunities)
        except Exception as e:
            logger.error("Synthesis generation failed", error=str(e))
            return self._default_synthesis(quarter, signals, patterns, opportunities)

    async def generate_digest(
        self,
        period: str,
        signals: List[ProcessedSignal],
        patterns: List[PatternMatch],
        opportunities: List[Opportunity]
    ) -> Dict[str, Any]:
        """
        Generate a periodic digest (weekly/monthly).

        Args:
            period: "weekly" or "monthly"
            signals: Recent signals
            patterns: Recent patterns
            opportunities: Recent opportunities

        Returns:
            Digest content as dictionary
        """
        try:
            await self.rate_limiter.acquire()

            # Prepare summaries
            top_patterns = [{
                "title": p.title,
                "type": p.pattern_type,
                "score": p.opportunity_score,
                "description": p.description
            } for p in sorted(patterns, key=lambda x: x.opportunity_score, reverse=True)[:5]]

            new_opportunities = [{
                "title": o.title,
                "summary": o.summary,
                "timing": o.timing_stage,
                "action": o.status
            } for o in opportunities[:5]]

            velocity_spikes = [{
                "keywords": s.keywords[:3] if s.keywords else [],
                "velocity": s.velocity_score,
                "type": s.signal_type
            } for s in signals if s.velocity_score and s.velocity_score > 0.7][:5]

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": DIGEST_GENERATION_PROMPT.format(
                        period=period,
                        signal_count=len(signals),
                        pattern_count=len(patterns),
                        opportunity_count=len(opportunities),
                        top_patterns=json.dumps(top_patterns, indent=2),
                        new_opportunities=json.dumps(new_opportunities, indent=2),
                        velocity_spikes=json.dumps(velocity_spikes, indent=2)
                    )
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result = json.loads(response_text)

            return {
                "period": period,
                "generated_at": datetime.utcnow().isoformat(),
                "signals_processed": len(signals),
                "patterns_detected": len(patterns),
                "opportunities_identified": len(opportunities),
                **result
            }

        except json.JSONDecodeError as e:
            logger.error("Failed to parse digest response", error=str(e))
            return self._default_digest(period, signals, patterns, opportunities)
        except Exception as e:
            logger.error("Digest generation failed", error=str(e))
            return self._default_digest(period, signals, patterns, opportunities)

    def _summarize_patterns(self, patterns: List[PatternMatch]) -> List[Dict]:
        """Summarize patterns for synthesis."""
        by_type = {}
        for p in patterns:
            ptype = p.pattern_type
            if ptype not in by_type:
                by_type[ptype] = []
            by_type[ptype].append({
                "title": p.title,
                "score": p.opportunity_score,
                "thesis": p.primary_thesis_alignment
            })

        return [
            {"type": t, "count": len(ps), "top": ps[:3]}
            for t, ps in by_type.items()
        ]

    def _summarize_opportunities(self, opportunities: List[Opportunity]) -> List[Dict]:
        """Summarize opportunities for synthesis."""
        return [{
            "title": o.title,
            "type": o.opportunity_type,
            "timing": o.timing_stage,
            "primary_thesis": o.primary_thesis,
            "status": o.status
        } for o in opportunities[:10]]

    def _calculate_thesis_distribution(self, signals: List[ProcessedSignal]) -> Dict[str, Dict]:
        """Calculate thesis score distribution across signals."""
        distributions = {
            "ai_leverage": {"count": 0, "avg": 0, "high_count": 0},
            "trust_scarcity": {"count": 0, "avg": 0, "high_count": 0},
            "physical_digital": {"count": 0, "avg": 0, "high_count": 0},
            "incumbent_decay": {"count": 0, "avg": 0, "high_count": 0},
            "speed_advantage": {"count": 0, "avg": 0, "high_count": 0},
            "execution_fit": {"count": 0, "avg": 0, "high_count": 0}
        }

        for s in signals:
            if not s.thesis_scores:
                continue

            for key in distributions:
                score = getattr(s.thesis_scores, key, None)
                if score:
                    distributions[key]["count"] += 1
                    distributions[key]["avg"] += score
                    if score >= 7:
                        distributions[key]["high_count"] += 1

        # Calculate averages
        for key in distributions:
            if distributions[key]["count"] > 0:
                distributions[key]["avg"] /= distributions[key]["count"]
                distributions[key]["avg"] = round(distributions[key]["avg"], 2)

        return distributions

    def _default_synthesis(
        self,
        quarter: str,
        signals: List[ProcessedSignal],
        patterns: List[PatternMatch],
        opportunities: List[Opportunity]
    ) -> Dict[str, Any]:
        """Return default synthesis when generation fails."""
        return {
            "quarter": quarter,
            "generated_at": datetime.utcnow().isoformat(),
            "statistics": {
                "signals": len(signals),
                "patterns": len(patterns),
                "opportunities": len(opportunities)
            },
            "error": "Synthesis generation failed",
            "macro_trends": {"big_shifts": [], "landscape_changes": "Unable to analyze"},
            "top_opportunities": [],
            "recommended_focus": {"next_quarter_focus": ["Review manually"]}
        }

    def _default_digest(
        self,
        period: str,
        signals: List[ProcessedSignal],
        patterns: List[PatternMatch],
        opportunities: List[Opportunity]
    ) -> Dict[str, Any]:
        """Return default digest when generation fails."""
        return {
            "period": period,
            "generated_at": datetime.utcnow().isoformat(),
            "signals_processed": len(signals),
            "patterns_detected": len(patterns),
            "opportunities_identified": len(opportunities),
            "error": "Digest generation failed",
            "key_insight": "Unable to generate insight",
            "recommended_actions": ["Review data manually"]
        }


# Singleton
_synthesizer: Optional[Synthesizer] = None


def get_synthesizer() -> Synthesizer:
    """Get synthesizer singleton."""
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = Synthesizer()
    return _synthesizer

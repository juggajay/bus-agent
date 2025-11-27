"""Timing analysis for opportunities."""

from typing import List, Dict, Optional
import json

from anthropic import AsyncAnthropic

from ..database import ProcessedSignal, PatternMatch
from ..utils import get_settings, get_logger, get_rate_limiter

logger = get_logger(__name__)

TIMING_PROMPT = """You are analyzing the timing stage of an emerging opportunity.

OPPORTUNITY: {opportunity_summary}

SIGNALS:
{formatted_signals}

Determine the timing stage:

EARLY (score 1-3):
- Only appearing in builder/developer spaces
- No mainstream coverage
- Few if any existing players
- 12-24 months before mainstream

EMERGING (score 4-6):
- Starting to appear in business/startup press
- Early startups getting seed funding
- Growing search interest
- 6-12 months before mainstream

GROWING (score 7-8):
- Mainstream awareness building
- Multiple funded startups
- Established players starting to notice
- 0-6 months / happening now

CROWDED (score 9-10):
- Everyone talking about it
- Multiple well-funded players
- Big tech/incumbents actively competing
- Difficult to differentiate

Provide analysis in JSON:
{{
    "timing_stage": "early/emerging/growing/crowded",
    "timing_score": 1-10,
    "evidence": ["point 1", "point 2"],
    "timing_risks": ["risk 1", "risk 2"],
    "recommended_action": "act now/prepare/monitor/avoid",
    "window_estimate": "estimated time until window closes",
    "confidence": 0.0-1.0
}}"""


class TimingAnalyzer:
    """Analyze timing stage of opportunities."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")

    async def analyze(
        self,
        pattern: PatternMatch,
        signals: List[ProcessedSignal]
    ) -> Dict:
        """
        Analyze the timing stage of an opportunity.

        Args:
            pattern: The pattern to analyze
            signals: Related signals for context

        Returns:
            Timing analysis results
        """
        try:
            await self.rate_limiter.acquire()

            # Format signals
            formatted_signals = [{
                "type": s.signal_type,
                "title": s.title,
                "summary": s.summary,
                "timing_stage": s.timing_stage,
                "velocity": s.velocity_score,
                "novelty": s.novelty_score
            } for s in signals[:10]]

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": TIMING_PROMPT.format(
                        opportunity_summary=f"{pattern.title}: {pattern.description}",
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

            return {
                "timing_stage": result.get("timing_stage", "emerging"),
                "timing_score": result.get("timing_score", 5),
                "evidence": result.get("evidence", []),
                "timing_risks": result.get("timing_risks", []),
                "recommended_action": result.get("recommended_action", "monitor"),
                "window_estimate": result.get("window_estimate", "unknown"),
                "confidence": result.get("confidence", 0.5)
            }

        except json.JSONDecodeError as e:
            logger.error("Failed to parse timing analysis", error=str(e))
            return self._default_timing()
        except Exception as e:
            logger.error("Timing analysis failed", error=str(e))
            return self._default_timing()

    def _default_timing(self) -> Dict:
        """Return default timing analysis."""
        return {
            "timing_stage": "emerging",
            "timing_score": 5,
            "evidence": [],
            "timing_risks": ["Insufficient data for timing analysis"],
            "recommended_action": "monitor",
            "window_estimate": "unknown",
            "confidence": 0.3
        }

    def infer_timing_from_signals(
        self,
        signals: List[ProcessedSignal]
    ) -> str:
        """
        Quick timing inference from signal characteristics.

        Args:
            signals: List of signals to analyze

        Returns:
            Timing stage string
        """
        if not signals:
            return "emerging"

        # Calculate averages
        avg_novelty = sum(s.novelty_score or 0.5 for s in signals) / len(signals)
        avg_velocity = sum(s.velocity_score or 0.5 for s in signals) / len(signals)

        # Count signal types
        builder_count = sum(1 for s in signals if s.signal_type == "builder_activity")
        consumer_count = sum(1 for s in signals if s.signal_type == "consumer_behaviour")
        funding_count = sum(1 for s in signals if s.signal_type == "funding")

        # Inference logic
        if avg_novelty > 0.7 and builder_count > consumer_count:
            return "early"
        elif avg_novelty > 0.5 and avg_velocity > 0.5:
            return "emerging"
        elif avg_velocity > 0.7 or funding_count > 2:
            return "growing"
        elif avg_novelty < 0.3 and avg_velocity < 0.3:
            return "crowded"
        else:
            return "emerging"


# Singleton
_analyzer: Optional[TimingAnalyzer] = None


def get_timing_analyzer() -> TimingAnalyzer:
    """Get timing analyzer singleton."""
    global _analyzer
    if _analyzer is None:
        _analyzer = TimingAnalyzer()
    return _analyzer

"""Convergence pattern detection."""

from typing import List, Dict, Any, Optional
from uuid import UUID
import json

from anthropic import AsyncAnthropic

from ..database import ProcessedSignal, PatternMatchCreate, get_database
from ..processors import cluster_by_embedding, average_embedding
from ..utils import get_settings, get_logger, get_rate_limiter

logger = get_logger(__name__)

CONVERGENCE_PROMPT = """You are analyzing a convergence pattern - multiple unrelated signals that may point to the same business opportunity.

SIGNALS:
{formatted_signals}

These signals come from different sources ({source_categories}) but cluster together semantically.

Analyze this convergence:
1. What common opportunity or theme connects these signals?
2. Is this a genuine opportunity pattern or coincidental clustering?
3. What hypothesis does this suggest about market direction?
4. What additional signals would validate or invalidate this hypothesis?
5. If this is a real opportunity, what's the timing - early/emerging/growing/crowded?

Respond ONLY with valid JSON:
{{
    "title": "short title for this pattern",
    "theme": "the common theme connecting these signals",
    "is_genuine": true/false,
    "confidence": 0.0-1.0,
    "hypothesis": "what this suggests about the market",
    "validation_signals": ["signal 1", "signal 2"],
    "timing": "early/emerging/growing/crowded",
    "opportunity_summary": "brief summary of the opportunity if genuine"
}}"""


class ConvergenceDetector:
    """Detect convergence patterns across signals from different sources."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.rate_limiter = get_rate_limiter("anthropic")
        self.db = get_database()

    async def detect(
        self,
        signals: List[ProcessedSignal],
        min_signals: int = 3,
        similarity_threshold: float = 0.75
    ) -> List[PatternMatchCreate]:
        """
        Detect convergence patterns in a list of signals.

        Args:
            signals: List of processed signals with embeddings
            min_signals: Minimum signals required to form a pattern
            similarity_threshold: Embedding similarity threshold for clustering

        Returns:
            List of detected patterns
        """
        if len(signals) < min_signals:
            return []

        # Extract embeddings (filter out None)
        embeddings = []
        signal_map = {}
        for i, s in enumerate(signals):
            if s.embedding:
                embeddings.append(s.embedding)
                signal_map[len(embeddings) - 1] = s

        if len(embeddings) < min_signals:
            return []

        # Cluster by embedding similarity
        clusters = cluster_by_embedding(
            embeddings,
            threshold=similarity_threshold,
            min_cluster_size=min_signals
        )

        patterns = []
        for cluster_indices in clusters:
            # Get signals in this cluster
            cluster_signals = [signal_map[i] for i in cluster_indices if i in signal_map]

            if len(cluster_signals) < min_signals:
                continue

            # Check for source diversity
            source_categories = set(s.raw_signal_id for s in cluster_signals)

            # Must have signals from at least 2 different sources
            if len(source_categories) < 2:
                continue

            # Analyze convergence with LLM
            pattern = await self._analyze_convergence(cluster_signals)

            if pattern:
                patterns.append(pattern)

        return patterns

    async def _analyze_convergence(
        self,
        signals: List[ProcessedSignal]
    ) -> Optional[PatternMatchCreate]:
        """Analyze a cluster of signals for convergence."""
        try:
            await self.rate_limiter.acquire()

            # Format signals for prompt
            formatted = []
            source_categories = set()

            for s in signals:
                source_categories.add(s.signal_type)
                formatted.append({
                    "type": s.signal_type,
                    "title": s.title,
                    "summary": s.summary,
                    "keywords": s.keywords,
                    "entities": s.entities.model_dump() if s.entities else {}
                })

            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": CONVERGENCE_PROMPT.format(
                        formatted_signals=json.dumps(formatted, indent=2),
                        source_categories=", ".join(source_categories)
                    )
                }]
            )

            # Parse response
            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            result = json.loads(response_text)

            # Only create pattern if genuine
            if not result.get("is_genuine", False):
                logger.debug("Cluster determined not to be genuine convergence")
                return None

            confidence = float(result.get("confidence", 0.5))
            if confidence < 0.5:
                logger.debug(f"Convergence confidence too low: {confidence}")
                return None

            # Calculate opportunity score
            # Based on confidence, timing, and signal count
            timing_multiplier = {
                "early": 0.9,
                "emerging": 1.0,
                "growing": 0.8,
                "crowded": 0.5
            }.get(result.get("timing", "emerging"), 0.7)

            opportunity_score = confidence * timing_multiplier * min(1.0, len(signals) / 5)

            # Determine primary thesis alignment
            thesis_scores = self._aggregate_thesis_scores(signals)
            primary_thesis = max(thesis_scores.items(), key=lambda x: x[1] or 0)[0]

            return PatternMatchCreate(
                pattern_type="convergence",
                signal_ids=[s.id for s in signals],
                signal_count=len(signals),
                title=result.get("title", "Convergence Pattern"),
                description=result.get("theme", ""),
                hypothesis=result.get("hypothesis", ""),
                confidence_score=confidence,
                opportunity_score=opportunity_score,
                primary_thesis_alignment=primary_thesis,
                thesis_scores=thesis_scores
            )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse convergence analysis", error=str(e))
            return None
        except Exception as e:
            logger.error("Convergence analysis failed", error=str(e))
            return None

    def _aggregate_thesis_scores(self, signals: List[ProcessedSignal]) -> Dict[str, float]:
        """Aggregate thesis scores across signals."""
        scores = {
            "ai_leverage": [],
            "trust_scarcity": [],
            "physical_digital": [],
            "incumbent_decay": [],
            "speed_advantage": [],
            "execution_fit": []
        }

        for s in signals:
            if s.thesis_scores:
                if s.thesis_scores.ai_leverage:
                    scores["ai_leverage"].append(s.thesis_scores.ai_leverage)
                if s.thesis_scores.trust_scarcity:
                    scores["trust_scarcity"].append(s.thesis_scores.trust_scarcity)
                if s.thesis_scores.physical_digital:
                    scores["physical_digital"].append(s.thesis_scores.physical_digital)
                if s.thesis_scores.incumbent_decay:
                    scores["incumbent_decay"].append(s.thesis_scores.incumbent_decay)
                if s.thesis_scores.speed_advantage:
                    scores["speed_advantage"].append(s.thesis_scores.speed_advantage)
                if s.thesis_scores.execution_fit:
                    scores["execution_fit"].append(s.thesis_scores.execution_fit)

        return {
            k: sum(v) / len(v) if v else None
            for k, v in scores.items()
        }


# Singleton
_detector: Optional[ConvergenceDetector] = None


def get_convergence_detector() -> ConvergenceDetector:
    """Get convergence detector singleton."""
    global _detector
    if _detector is None:
        _detector = ConvergenceDetector()
    return _detector

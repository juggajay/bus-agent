"""Velocity spike pattern detection."""

from typing import List, Dict, Optional
from uuid import UUID

from ..database import ProcessedSignal, PatternMatchCreate, get_database
from ..processors import get_velocity_tracker
from ..utils import get_logger

logger = get_logger(__name__)


class VelocitySpikeDetector:
    """Detect velocity spike patterns in signals."""

    def __init__(self):
        self.velocity_tracker = get_velocity_tracker()
        self.db = get_database()

    async def detect(
        self,
        signals: List[ProcessedSignal],
        threshold: float = 0.8
    ) -> List[PatternMatchCreate]:
        """
        Detect velocity spike patterns.

        Args:
            signals: List of processed signals
            threshold: Minimum velocity score to consider a spike

        Returns:
            List of detected patterns
        """
        # Find high-velocity signals
        high_velocity_signals = [
            s for s in signals
            if s.velocity_score and s.velocity_score >= threshold
        ]

        if not high_velocity_signals:
            return []

        # Group by related keywords/topics
        grouped = self._group_by_topic(high_velocity_signals)

        patterns = []
        for topic, topic_signals in grouped.items():
            if len(topic_signals) < 2:
                continue

            # Calculate aggregate metrics
            avg_velocity = sum(s.velocity_score or 0 for s in topic_signals) / len(topic_signals)
            max_velocity = max(s.velocity_score or 0 for s in topic_signals)

            # Calculate opportunity score
            # High velocity + multiple signals = higher opportunity
            opportunity_score = min(1.0, avg_velocity * (1 + len(topic_signals) / 10))

            # Aggregate thesis scores
            thesis_scores = self._aggregate_thesis_scores(topic_signals)
            primary_thesis = max(thesis_scores.items(), key=lambda x: x[1] or 0)[0]

            patterns.append(PatternMatchCreate(
                pattern_type="velocity_spike",
                signal_ids=[s.id for s in topic_signals],
                signal_count=len(topic_signals),
                title=f"Velocity Spike: {topic}",
                description=f"Multiple signals showing rapid acceleration around '{topic}'",
                hypothesis=f"The topic '{topic}' is experiencing unusual growth. This could indicate emerging demand or interest.",
                confidence_score=min(1.0, avg_velocity),
                opportunity_score=opportunity_score,
                primary_thesis_alignment=primary_thesis,
                thesis_scores=thesis_scores
            ))

        return patterns

    def _group_by_topic(
        self,
        signals: List[ProcessedSignal]
    ) -> Dict[str, List[ProcessedSignal]]:
        """Group signals by common keywords/topics."""
        groups: Dict[str, List[ProcessedSignal]] = {}

        for signal in signals:
            # Use first keyword as primary topic, or signal type
            if signal.keywords and len(signal.keywords) > 0:
                topic = signal.keywords[0]
            else:
                topic = signal.signal_type or "unknown"

            if topic not in groups:
                groups[topic] = []
            groups[topic].append(signal)

        return groups

    def _aggregate_thesis_scores(self, signals: List[ProcessedSignal]) -> Dict[str, float]:
        """Aggregate thesis scores across signals - Solo SaaS Finder v2.0."""
        scores = {
            "demand_evidence": [],
            "competition_gap": [],
            "trend_timing": [],
            "solo_buildability": [],
            "clear_monetisation": [],
            "regulatory_simplicity": []
        }

        for s in signals:
            if s.thesis_scores:
                if s.thesis_scores.demand_evidence:
                    scores["demand_evidence"].append(s.thesis_scores.demand_evidence)
                if s.thesis_scores.competition_gap:
                    scores["competition_gap"].append(s.thesis_scores.competition_gap)
                if s.thesis_scores.trend_timing:
                    scores["trend_timing"].append(s.thesis_scores.trend_timing)
                if s.thesis_scores.solo_buildability:
                    scores["solo_buildability"].append(s.thesis_scores.solo_buildability)
                if s.thesis_scores.clear_monetisation:
                    scores["clear_monetisation"].append(s.thesis_scores.clear_monetisation)
                if s.thesis_scores.regulatory_simplicity:
                    scores["regulatory_simplicity"].append(s.thesis_scores.regulatory_simplicity)

        return {
            k: sum(v) / len(v) if v else None
            for k, v in scores.items()
        }


# Singleton
_detector: Optional[VelocitySpikeDetector] = None


def get_velocity_spike_detector() -> VelocitySpikeDetector:
    """Get velocity spike detector singleton."""
    global _detector
    if _detector is None:
        _detector = VelocitySpikeDetector()
    return _detector

"""Main pattern detection orchestrator."""

from typing import List, Optional
from datetime import datetime

from ..database import (
    ProcessedSignal, PatternMatch, PatternMatchCreate,
    get_database
)
from ..utils import get_logger
from .convergence import get_convergence_detector
from .velocity_spike import get_velocity_spike_detector
from .gap_detector import get_gap_detector
from .timing import get_timing_analyzer

logger = get_logger(__name__)


class PatternDetector:
    """Orchestrate pattern detection across all detectors."""

    def __init__(self):
        self.db = get_database()
        self.convergence_detector = get_convergence_detector()
        self.velocity_detector = get_velocity_spike_detector()
        self.gap_detector = get_gap_detector()
        self.timing_analyzer = get_timing_analyzer()

    async def detect_all(
        self,
        signals: Optional[List[ProcessedSignal]] = None,
        days: int = 30
    ) -> List[PatternMatch]:
        """
        Run all pattern detectors on signals.

        Args:
            signals: Optional list of signals to analyze.
                    If not provided, fetches recent signals from database.
            days: Number of days of signals to analyze if fetching from database.

        Returns:
            List of detected and stored patterns
        """
        # Get signals if not provided
        if signals is None:
            signals = await self.db.get_processed_signals(days=days)

        if not signals:
            logger.info("No signals to analyze for patterns")
            return []

        logger.info(f"Running pattern detection on {len(signals)} signals")

        all_patterns: List[PatternMatchCreate] = []

        # Run convergence detection
        try:
            convergence_patterns = await self.convergence_detector.detect(signals)
            all_patterns.extend(convergence_patterns)
            logger.info(f"Found {len(convergence_patterns)} convergence patterns")
        except Exception as e:
            logger.error("Convergence detection failed", error=str(e))

        # Run velocity spike detection
        try:
            velocity_patterns = await self.velocity_detector.detect(signals)
            all_patterns.extend(velocity_patterns)
            logger.info(f"Found {len(velocity_patterns)} velocity patterns")
        except Exception as e:
            logger.error("Velocity detection failed", error=str(e))

        # Run gap detection
        try:
            gap_patterns = await self.gap_detector.detect(signals)
            all_patterns.extend(gap_patterns)
            logger.info(f"Found {len(gap_patterns)} gap patterns")
        except Exception as e:
            logger.error("Gap detection failed", error=str(e))

        # Store patterns and add timing analysis
        stored_patterns = []
        for pattern_create in all_patterns:
            try:
                # Store pattern
                pattern = await self.db.insert_pattern(pattern_create)

                # Get related signals for timing analysis
                related_signals = [
                    s for s in signals
                    if s.id in pattern_create.signal_ids
                ]

                # Analyze timing
                timing = await self.timing_analyzer.analyze(pattern, related_signals)

                # Update pattern with timing info (if we had an update method)
                # For now, timing is stored in the hypothesis field

                stored_patterns.append(pattern)

            except Exception as e:
                logger.error("Failed to store pattern", error=str(e))

        logger.info(f"Pattern detection complete. Found {len(stored_patterns)} patterns")

        return stored_patterns

    async def detect_anomalies(
        self,
        velocity_threshold: float = 0.9
    ) -> List[PatternMatch]:
        """
        Quick anomaly detection for daily monitoring.

        Args:
            velocity_threshold: Threshold for velocity spikes

        Returns:
            List of anomaly patterns
        """
        # Get recent signals (last 7 days)
        signals = await self.db.get_processed_signals(days=7)

        if not signals:
            return []

        # Only run velocity spike detection for anomalies
        patterns = await self.velocity_detector.detect(
            signals,
            threshold=velocity_threshold
        )

        # Store and return
        stored = []
        for pattern_create in patterns:
            try:
                pattern = await self.db.insert_pattern(pattern_create)
                stored.append(pattern)
            except Exception as e:
                logger.error("Failed to store anomaly pattern", error=str(e))

        return stored


# Singleton
_detector: Optional[PatternDetector] = None


def get_pattern_detector() -> PatternDetector:
    """Get pattern detector singleton."""
    global _detector
    if _detector is None:
        _detector = PatternDetector()
    return _detector

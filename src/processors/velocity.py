"""Velocity tracking for signals."""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from ..utils import get_logger

logger = get_logger(__name__)


def calculate_velocity_score(
    mention_counts: Dict[str, int],
    baseline_growth: float = 2.0
) -> float:
    """
    Calculate velocity score based on mention counts across time windows.

    Args:
        mention_counts: Dictionary with time windows as keys.
            e.g., {'7d': 10, '14d': 15, '30d': 20}
        baseline_growth: Week-over-week growth rate considered "normal"

    Returns:
        Velocity score between 0 and 1.
        Higher scores indicate faster acceleration.
    """
    count_7d = mention_counts.get('7d', 0)
    count_14d = mention_counts.get('14d', 0)
    count_30d = mention_counts.get('30d', 0)

    if count_7d == 0:
        return 0.0

    # Calculate week-over-week growth
    # Compare last 7 days to previous 7 days (days 8-14)
    previous_week = count_14d - count_7d

    if previous_week > 0:
        wow_growth = count_7d / previous_week
    else:
        # No previous week data, use current count as indicator
        wow_growth = min(count_7d / 5, 3.0)  # Cap at 3x

    # Calculate month-over-month trend
    if count_30d > 0:
        recent_share = count_7d / count_30d  # What portion of monthly is recent?
        # If >50% is in last week, that's accelerating
        acceleration = recent_share / 0.25  # 0.25 would be even distribution
    else:
        acceleration = 1.0

    # Combine metrics
    # High wow_growth and high acceleration = high velocity
    raw_velocity = (wow_growth / baseline_growth) * (acceleration ** 0.5)

    # Normalize to 0-1 scale
    # Values of 2x+ growth get high scores
    return min(1.0, raw_velocity / 2.0)


class VelocityTracker:
    """Track velocity of keywords/topics over time."""

    def __init__(self):
        # In-memory storage for development
        # In production, this would use the database
        self._counts: Dict[str, List[tuple]] = defaultdict(list)

    def record_mention(
        self,
        keyword: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Record a mention of a keyword."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        self._counts[keyword.lower()].append(timestamp)

    def get_mention_counts(
        self,
        keyword: str,
        reference_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Get mention counts for different time windows."""
        if reference_time is None:
            reference_time = datetime.utcnow()

        keyword = keyword.lower()
        mentions = self._counts.get(keyword, [])

        cutoff_7d = reference_time - timedelta(days=7)
        cutoff_14d = reference_time - timedelta(days=14)
        cutoff_30d = reference_time - timedelta(days=30)

        return {
            '7d': sum(1 for m in mentions if m >= cutoff_7d),
            '14d': sum(1 for m in mentions if m >= cutoff_14d),
            '30d': sum(1 for m in mentions if m >= cutoff_30d)
        }

    def get_velocity_score(
        self,
        keyword: str,
        reference_time: Optional[datetime] = None
    ) -> float:
        """Calculate velocity score for a keyword."""
        counts = self.get_mention_counts(keyword, reference_time)
        return calculate_velocity_score(counts)

    def get_top_accelerating(
        self,
        min_mentions: int = 5,
        top_k: int = 20
    ) -> List[tuple]:
        """
        Get keywords with highest velocity.

        Args:
            min_mentions: Minimum mentions in last 30 days to consider
            top_k: Number of results to return

        Returns:
            List of (keyword, velocity_score, mention_counts) tuples
        """
        results = []

        for keyword in self._counts.keys():
            counts = self.get_mention_counts(keyword)

            if counts['30d'] < min_mentions:
                continue

            velocity = calculate_velocity_score(counts)
            results.append((keyword, velocity, counts))

        # Sort by velocity descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    def detect_velocity_spikes(
        self,
        threshold: float = 0.8,
        min_mentions: int = 5
    ) -> List[tuple]:
        """
        Detect keywords with velocity above threshold.

        Args:
            threshold: Minimum velocity score to consider a spike
            min_mentions: Minimum mentions to consider

        Returns:
            List of (keyword, velocity_score, mention_counts) tuples
        """
        results = []

        for keyword in self._counts.keys():
            counts = self.get_mention_counts(keyword)

            if counts['30d'] < min_mentions:
                continue

            velocity = calculate_velocity_score(counts)

            if velocity >= threshold:
                results.append((keyword, velocity, counts))

        # Sort by velocity descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results


# Global tracker instance
_tracker: Optional[VelocityTracker] = None


def get_velocity_tracker() -> VelocityTracker:
    """Get velocity tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = VelocityTracker()
    return _tracker

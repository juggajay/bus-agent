"""Anomaly alerts and notifications."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from ..database import ProcessedSignal, PatternMatch, get_database
from ..patterns import get_pattern_detector
from ..utils import get_logger, get_settings

logger = get_logger(__name__)


class AlertUrgency(str, Enum):
    """Alert urgency levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Alert:
    """An anomaly alert."""
    id: str
    alert_type: str
    title: str
    description: str
    urgency: AlertUrgency
    thesis_alignment: Optional[str]
    detected_at: datetime
    data: Dict[str, Any]


class AlertSystem:
    """System for detecting and managing alerts."""

    def __init__(self):
        self.db = get_database()
        self.pattern_detector = get_pattern_detector()
        self.settings = get_settings()
        self._alerts: List[Alert] = []

    async def check_for_anomalies(self) -> List[Alert]:
        """
        Check for anomalies and generate alerts.

        Returns:
            List of new alerts
        """
        alerts = []

        # Check for velocity spikes
        velocity_alerts = await self._check_velocity_spikes()
        alerts.extend(velocity_alerts)

        # Check for high-confidence patterns
        pattern_alerts = await self._check_new_patterns()
        alerts.extend(pattern_alerts)

        # Check for regulatory changes
        regulatory_alerts = await self._check_regulatory_signals()
        alerts.extend(regulatory_alerts)

        # Store alerts
        self._alerts.extend(alerts)

        return alerts

    async def _check_velocity_spikes(self, threshold: float = 0.9) -> List[Alert]:
        """Check for velocity spike anomalies."""
        alerts = []

        signals = await self.db.get_processed_signals(days=7)
        high_velocity = [s for s in signals if s.velocity_score and s.velocity_score >= threshold]

        for signal in high_velocity:
            alert = Alert(
                id=f"velocity_{signal.id}",
                alert_type="velocity_spike",
                title=f"Velocity Spike: {signal.title[:50]}",
                description=f"Signal showing unusual acceleration (velocity: {signal.velocity_score:.2f})",
                urgency=AlertUrgency.HIGH if signal.velocity_score > 0.95 else AlertUrgency.MEDIUM,
                thesis_alignment=self._get_primary_thesis(signal),
                detected_at=datetime.utcnow(),
                data={
                    "signal_id": str(signal.id),
                    "velocity_score": signal.velocity_score,
                    "keywords": signal.keywords,
                    "signal_type": signal.signal_type
                }
            )
            alerts.append(alert)

        return alerts

    async def _check_new_patterns(self, min_confidence: float = 0.8) -> List[Alert]:
        """Check for new high-confidence patterns."""
        alerts = []

        patterns = await self.db.get_patterns(status="new", min_score=min_confidence)

        for pattern in patterns:
            if pattern.confidence_score >= min_confidence:
                alert = Alert(
                    id=f"pattern_{pattern.id}",
                    alert_type="new_pattern",
                    title=f"New Pattern: {pattern.title[:50]}",
                    description=pattern.hypothesis or pattern.description or "High-confidence pattern detected",
                    urgency=AlertUrgency.HIGH if pattern.opportunity_score > 0.8 else AlertUrgency.MEDIUM,
                    thesis_alignment=pattern.primary_thesis_alignment,
                    detected_at=datetime.utcnow(),
                    data={
                        "pattern_id": str(pattern.id),
                        "pattern_type": pattern.pattern_type,
                        "confidence": pattern.confidence_score,
                        "opportunity_score": pattern.opportunity_score
                    }
                )
                alerts.append(alert)

        return alerts

    async def _check_regulatory_signals(self) -> List[Alert]:
        """Check for new regulatory signals."""
        alerts = []

        signals = await self.db.get_processed_signals(days=7)
        regulatory_signals = [s for s in signals if s.signal_type == "regulatory"]

        for signal in regulatory_signals:
            # Only alert on high-scoring regulatory signals
            if self._has_high_thesis_score(signal):
                alert = Alert(
                    id=f"regulatory_{signal.id}",
                    alert_type="regulatory_change",
                    title=f"Regulatory: {signal.title[:50]}",
                    description=signal.summary or "New regulatory signal detected",
                    urgency=AlertUrgency.MEDIUM,
                    thesis_alignment=self._get_primary_thesis(signal),
                    detected_at=datetime.utcnow(),
                    data={
                        "signal_id": str(signal.id),
                        "geography": signal.geography,
                        "keywords": signal.keywords
                    }
                )
                alerts.append(alert)

        return alerts

    def _get_primary_thesis(self, signal: ProcessedSignal) -> Optional[str]:
        """Get the primary thesis alignment for a signal."""
        if not signal.thesis_scores:
            return None

        scores = {
            "ai_leverage": signal.thesis_scores.ai_leverage,
            "trust_scarcity": signal.thesis_scores.trust_scarcity,
            "physical_digital": signal.thesis_scores.physical_digital,
            "incumbent_decay": signal.thesis_scores.incumbent_decay,
            "speed_advantage": signal.thesis_scores.speed_advantage,
            "execution_fit": signal.thesis_scores.execution_fit
        }

        # Filter out None values
        scores = {k: v for k, v in scores.items() if v is not None}

        if not scores:
            return None

        return max(scores.items(), key=lambda x: x[1])[0]

    def _has_high_thesis_score(self, signal: ProcessedSignal, threshold: int = 7) -> bool:
        """Check if signal has any high thesis score."""
        if not signal.thesis_scores:
            return False

        scores = [
            signal.thesis_scores.ai_leverage,
            signal.thesis_scores.trust_scarcity,
            signal.thesis_scores.physical_digital,
            signal.thesis_scores.incumbent_decay,
            signal.thesis_scores.speed_advantage,
            signal.thesis_scores.execution_fit
        ]

        return any(s and s >= threshold for s in scores)

    def get_pending_alerts(self) -> List[Alert]:
        """Get all pending alerts."""
        return self._alerts

    def dismiss_alert(self, alert_id: str) -> bool:
        """Dismiss an alert by ID."""
        for i, alert in enumerate(self._alerts):
            if alert.id == alert_id:
                self._alerts.pop(i)
                return True
        return False

    def format_alert_notification(self, alert: Alert) -> Dict[str, str]:
        """Format an alert as a notification."""
        urgency_emoji = {
            AlertUrgency.HIGH: "🔴",
            AlertUrgency.MEDIUM: "🟡",
            AlertUrgency.LOW: "🟢"
        }

        return {
            "title": f"{urgency_emoji[alert.urgency]} {alert.title}",
            "body": alert.description,
            "urgency": alert.urgency.value,
            "thesis": alert.thesis_alignment or "N/A",
            "timestamp": alert.detected_at.isoformat()
        }


# Singleton
_alert_system: Optional[AlertSystem] = None


def get_alert_system() -> AlertSystem:
    """Get alert system singleton."""
    global _alert_system
    if _alert_system is None:
        _alert_system = AlertSystem()
    return _alert_system

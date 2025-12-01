"""Digest generation and delivery."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

from ..database import (
    ProcessedSignal, PatternMatch, Opportunity,
    DigestContent,
    get_database
)
from ..reasoning import get_synthesizer
from ..utils import get_logger, get_settings

logger = get_logger(__name__)


class DigestGenerator:
    """Generate periodic digests of intelligence findings."""

    def __init__(self):
        self.db = get_database()
        self.synthesizer = get_synthesizer()

    async def generate_weekly_digest(self) -> DigestContent:
        """Generate a weekly digest."""
        try:
            # Get data from last 7 days
            signals = await self.db.get_processed_signals(days=7)
            patterns = await self.db.get_patterns(status="new")
            opportunities = await self.db.get_opportunities(status="new")

            # Filter to last 7 days - handle both datetime and string types
            cutoff = datetime.utcnow() - timedelta(days=7)

            def parse_datetime(dt):
                if dt is None:
                    return datetime.utcnow()
                if isinstance(dt, datetime):
                    # Make naive if timezone-aware for comparison
                    if dt.tzinfo is not None:
                        return dt.replace(tzinfo=None)
                    return dt
                if isinstance(dt, str):
                    try:
                        parsed = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                        # Make naive for comparison
                        if parsed.tzinfo is not None:
                            return parsed.replace(tzinfo=None)
                        return parsed
                    except:
                        return datetime.utcnow()
                return datetime.utcnow()

            patterns = [p for p in patterns if parse_datetime(p.created_at) >= cutoff]
            opportunities = [o for o in opportunities if parse_datetime(o.created_at) >= cutoff]

            # Generate digest content
            digest_data = await self.synthesizer.generate_digest(
                period="weekly",
                signals=signals,
                patterns=patterns,
                opportunities=opportunities
            )

            # Get velocity spikes
            velocity_spikes = [{
                "topic": s.keywords[0] if s.keywords else "unknown",
                "velocity": s.velocity_score,
                "signal_type": s.signal_type
            } for s in signals if s.velocity_score and s.velocity_score > 0.7]

            return DigestContent(
                period="weekly",
                generated_at=datetime.utcnow(),
                signals_processed=len(signals),
                patterns_detected=len(patterns),
                opportunities_identified=len(opportunities),
                top_patterns=digest_data.get("pattern_summaries", [])[:5],
                new_opportunities=digest_data.get("opportunity_summaries", [])[:5],
                velocity_spikes=velocity_spikes[:5],
                key_insight=digest_data.get("key_insight", "No key insight generated"),
                recommended_actions=digest_data.get("recommended_actions", [])[:3],
                top_build_ready_ideas=digest_data.get("top_build_ready_ideas", [])[:5],
                emerging_trends=digest_data.get("emerging_trends", [])[:5],
                pass_list=digest_data.get("pass_list", [])[:5],
                this_week_action=digest_data.get("this_week_action")
            )
        except Exception as e:
            logger.error(f"Failed to generate weekly digest: {str(e)}")
            # Return a minimal digest on error
            return DigestContent(
                period="weekly",
                generated_at=datetime.utcnow(),
                signals_processed=0,
                patterns_detected=0,
                opportunities_identified=0,
                top_patterns=[],
                new_opportunities=[],
                velocity_spikes=[],
                key_insight=f"Digest generation failed: {str(e)}",
                recommended_actions=["Check logs for errors"]
            )

    async def generate_monthly_digest(self) -> DigestContent:
        """Generate a monthly digest."""
        try:
            # Get data from last 30 days
            signals = await self.db.get_processed_signals(days=30)
            patterns = await self.db.get_patterns()
            opportunities = await self.db.get_opportunities()

            # Filter to last 30 days - handle both datetime and string types
            cutoff = datetime.utcnow() - timedelta(days=30)

            def parse_datetime(dt):
                if dt is None:
                    return datetime.utcnow()
                if isinstance(dt, datetime):
                    # Make naive if timezone-aware for comparison
                    if dt.tzinfo is not None:
                        return dt.replace(tzinfo=None)
                    return dt
                if isinstance(dt, str):
                    try:
                        parsed = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                        # Make naive for comparison
                        if parsed.tzinfo is not None:
                            return parsed.replace(tzinfo=None)
                        return parsed
                    except:
                        return datetime.utcnow()
                return datetime.utcnow()

            patterns = [p for p in patterns if parse_datetime(p.created_at) >= cutoff]
            opportunities = [o for o in opportunities if parse_datetime(o.created_at) >= cutoff]

            # Generate digest content
            digest_data = await self.synthesizer.generate_digest(
                period="monthly",
                signals=signals,
                patterns=patterns,
                opportunities=opportunities
            )

            velocity_spikes = [{
                "topic": s.keywords[0] if s.keywords else "unknown",
                "velocity": s.velocity_score,
                "signal_type": s.signal_type
            } for s in signals if s.velocity_score and s.velocity_score > 0.7]

            return DigestContent(
                period="monthly",
                generated_at=datetime.utcnow(),
                signals_processed=len(signals),
                patterns_detected=len(patterns),
                opportunities_identified=len(opportunities),
                top_patterns=digest_data.get("pattern_summaries", [])[:5],
                new_opportunities=digest_data.get("opportunity_summaries", [])[:5],
                velocity_spikes=velocity_spikes[:5],
                key_insight=digest_data.get("key_insight", "No key insight generated"),
                recommended_actions=digest_data.get("recommended_actions", [])[:3],
                top_build_ready_ideas=digest_data.get("top_build_ready_ideas", [])[:5],
                emerging_trends=digest_data.get("emerging_trends", [])[:5],
                pass_list=digest_data.get("pass_list", [])[:5],
                this_week_action=digest_data.get("this_week_action")
            )
        except Exception as e:
            logger.error(f"Failed to generate monthly digest: {str(e)}")
            # Return a minimal digest on error
            return DigestContent(
                period="monthly",
                generated_at=datetime.utcnow(),
                signals_processed=0,
                patterns_detected=0,
                opportunities_identified=0,
                top_patterns=[],
                new_opportunities=[],
                velocity_spikes=[],
                key_insight=f"Digest generation failed: {str(e)}",
                recommended_actions=["Check logs for errors"]
            )

    def format_digest_email(self, digest: DigestContent) -> Dict[str, str]:
        """Format digest as email content."""
        subject = f"Opportunity Intelligence {digest.period.title()} Digest - {digest.generated_at.strftime('%Y-%m-%d')}"

        body_parts = [
            f"# {digest.period.title()} Intelligence Digest",
            f"Generated: {digest.generated_at.strftime('%Y-%m-%d %H:%M')} UTC",
            "",
            f"## Key Insight",
            digest.key_insight,
            "",
            f"## Statistics",
            f"- Signals processed: {digest.signals_processed}",
            f"- Patterns detected: {digest.patterns_detected}",
            f"- Opportunities identified: {digest.opportunities_identified}",
            ""
        ]

        if digest.recommended_actions:
            body_parts.append("## Recommended Actions")
            for i, action in enumerate(digest.recommended_actions, 1):
                body_parts.append(f"{i}. {action}")
            body_parts.append("")

        if digest.top_patterns:
            body_parts.append("## Top Patterns")
            for pattern in digest.top_patterns:
                body_parts.append(f"### {pattern.get('title', 'Pattern')}")
                body_parts.append(pattern.get('summary', ''))
                if pattern.get('relevance'):
                    body_parts.append(f"*Relevance: {pattern['relevance']}*")
                body_parts.append("")

        if digest.new_opportunities:
            body_parts.append("## New Opportunities")
            for opp in digest.new_opportunities:
                body_parts.append(f"### {opp.get('title', 'Opportunity')}")
                body_parts.append(opp.get('summary', ''))
                if opp.get('action'):
                    body_parts.append(f"*Recommended action: {opp['action']}*")
                body_parts.append("")

        if digest.velocity_spikes:
            body_parts.append("## Velocity Alerts")
            body_parts.append("Topics showing unusual acceleration:")
            for spike in digest.velocity_spikes:
                body_parts.append(f"- {spike.get('topic', 'unknown')} (velocity: {spike.get('velocity', 0):.2f})")
            body_parts.append("")

        body_parts.append("---")
        body_parts.append("*Generated by Opportunity Intelligence Agent*")

        return {
            "subject": subject,
            "body": "\n".join(body_parts)
        }


class DigestDelivery:
    """Handle digest delivery via email."""

    def __init__(self):
        self.settings = get_settings()

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email. Placeholder for actual implementation."""
        if not self.settings.smtp_host:
            logger.warning("SMTP not configured, skipping email delivery")
            return False

        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg['From'] = self.settings.smtp_user
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                use_tls=True
            )

            logger.info(f"Digest email sent to {to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email", error=str(e))
            return False

    async def deliver_digest(self, digest: DigestContent) -> bool:
        """Deliver a digest via configured channels."""
        generator = DigestGenerator()
        email_content = generator.format_digest_email(digest)

        if self.settings.notification_email:
            return await self.send_email(
                to=self.settings.notification_email,
                subject=email_content["subject"],
                body=email_content["body"]
            )

        return False


# Singletons
_generator: Optional[DigestGenerator] = None
_delivery: Optional[DigestDelivery] = None


def get_digest_generator() -> DigestGenerator:
    """Get digest generator singleton."""
    global _generator
    if _generator is None:
        _generator = DigestGenerator()
    return _generator


def get_digest_delivery() -> DigestDelivery:
    """Get digest delivery singleton."""
    global _delivery
    if _delivery is None:
        _delivery = DigestDelivery()
    return _delivery

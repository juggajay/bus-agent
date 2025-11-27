"""Scheduled jobs for data collection and analysis."""

from datetime import datetime
from typing import Optional
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..collectors import registry, register_all_collectors
from ..processors import get_pipeline
from ..patterns import get_pattern_detector
from ..reasoning import get_opportunity_generator, get_synthesizer
from ..interface import get_digest_generator, get_digest_delivery, get_alert_system
from ..database import get_database
from ..utils import get_logger, get_settings

logger = get_logger(__name__)


class JobScheduler:
    """Scheduler for periodic jobs."""

    def __init__(self):
        self.settings = get_settings()
        self.scheduler = AsyncIOScheduler(timezone=self.settings.timezone)
        self._setup_jobs()

    def _setup_jobs(self):
        """Set up all scheduled jobs."""
        # Weekly collection - Every Monday at 6 AM
        self.scheduler.add_job(
            self.run_weekly_collection,
            CronTrigger(day_of_week='mon', hour=6, minute=0),
            id='weekly_collection',
            name='Weekly Data Collection',
            replace_existing=True
        )

        # Monthly collection - 1st of each month at 6 AM
        self.scheduler.add_job(
            self.run_monthly_collection,
            CronTrigger(day=1, hour=6, minute=0),
            id='monthly_collection',
            name='Monthly Data Collection',
            replace_existing=True
        )

        # Daily processing - Every day at 7 AM
        self.scheduler.add_job(
            self.run_daily_processing,
            CronTrigger(hour=7, minute=0),
            id='daily_processing',
            name='Daily Signal Processing',
            replace_existing=True
        )

        # Weekly analysis - Every Monday at 8 AM
        self.scheduler.add_job(
            self.run_weekly_analysis,
            CronTrigger(day_of_week='mon', hour=8, minute=0),
            id='weekly_analysis',
            name='Weekly Pattern Analysis',
            replace_existing=True
        )

        # Weekly digest - Every Monday at 9 AM
        self.scheduler.add_job(
            self.send_weekly_digest,
            CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='weekly_digest',
            name='Weekly Digest Delivery',
            replace_existing=True
        )

        # Monthly digest - 1st of each month at 9 AM
        self.scheduler.add_job(
            self.send_monthly_digest,
            CronTrigger(day=1, hour=9, minute=0),
            id='monthly_digest',
            name='Monthly Digest Delivery',
            replace_existing=True
        )

        # Daily anomaly check - Every day at 10 AM
        self.scheduler.add_job(
            self.check_anomalies,
            CronTrigger(hour=10, minute=0),
            id='anomaly_check',
            name='Daily Anomaly Check',
            replace_existing=True
        )

        # Quarterly synthesis - 15th of Jan, Apr, Jul, Oct at 8 AM
        self.scheduler.add_job(
            self.run_quarterly_synthesis,
            CronTrigger(month='1,4,7,10', day=15, hour=8, minute=0),
            id='quarterly_synthesis',
            name='Quarterly Synthesis',
            replace_existing=True
        )

    def start(self):
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("Job scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Job scheduler stopped")

    async def run_weekly_collection(self):
        """Run weekly data collection from all sources."""
        logger.info("Starting weekly collection job")
        db = get_database()
        run = await db.start_analysis_run("weekly_collection")

        try:
            register_all_collectors()

            # Run all collectors
            results = await registry.run_all()

            total_signals = sum(v for v in results.values() if v > 0)

            await db.complete_analysis_run(
                run.id,
                patterns_detected=0,
                opportunities_generated=0,
                summary=f"Collected {total_signals} signals from {len(results)} sources"
            )

            logger.info(f"Weekly collection complete: {total_signals} signals")

        except Exception as e:
            logger.error("Weekly collection failed", error=str(e))
            await db.complete_analysis_run(
                run.id,
                patterns_detected=0,
                opportunities_generated=0,
                error_message=str(e)
            )

    async def run_monthly_collection(self):
        """Run monthly data collection (regulatory, funding sources)."""
        logger.info("Starting monthly collection job")
        db = get_database()
        run = await db.start_analysis_run("monthly_collection")

        try:
            register_all_collectors()

            # Run collectors by category
            results = await registry.run_category("regulatory")
            results.update(await registry.run_category("money_flow"))

            total_signals = sum(v for v in results.values() if v > 0)

            await db.complete_analysis_run(
                run.id,
                patterns_detected=0,
                opportunities_generated=0,
                summary=f"Monthly collection: {total_signals} signals"
            )

            logger.info(f"Monthly collection complete: {total_signals} signals")

        except Exception as e:
            logger.error("Monthly collection failed", error=str(e))
            await db.complete_analysis_run(
                run.id,
                patterns_detected=0,
                opportunities_generated=0,
                error_message=str(e)
            )

    async def run_daily_processing(self):
        """Process unprocessed signals."""
        logger.info("Starting daily processing job")

        try:
            pipeline = get_pipeline()
            count = await pipeline.process_unprocessed(limit=500)
            logger.info(f"Daily processing complete: {count} signals processed")

        except Exception as e:
            logger.error("Daily processing failed", error=str(e))

    async def run_weekly_analysis(self):
        """Run weekly pattern detection and opportunity generation."""
        logger.info("Starting weekly analysis job")
        db = get_database()
        run = await db.start_analysis_run("weekly_analysis")

        try:
            # Detect patterns
            detector = get_pattern_detector()
            patterns = await detector.detect_all(days=7)

            # Generate opportunities from high-score patterns
            generator = get_opportunity_generator()
            signals = await db.get_processed_signals(days=7)
            new_patterns = [p for p in patterns if p.opportunity_score >= 0.5]
            opportunities = await generator.generate_from_patterns(new_patterns, signals)

            await db.complete_analysis_run(
                run.id,
                patterns_detected=len(patterns),
                opportunities_generated=len(opportunities),
                summary=f"Weekly analysis: {len(patterns)} patterns, {len(opportunities)} opportunities"
            )

            logger.info(f"Weekly analysis complete: {len(patterns)} patterns, {len(opportunities)} opportunities")

        except Exception as e:
            logger.error("Weekly analysis failed", error=str(e))
            await db.complete_analysis_run(
                run.id,
                patterns_detected=0,
                opportunities_generated=0,
                error_message=str(e)
            )

    async def send_weekly_digest(self):
        """Generate and send weekly digest."""
        logger.info("Generating weekly digest")

        try:
            generator = get_digest_generator()
            delivery = get_digest_delivery()

            digest = await generator.generate_weekly_digest()
            await delivery.deliver_digest(digest)

            logger.info("Weekly digest sent")

        except Exception as e:
            logger.error("Weekly digest failed", error=str(e))

    async def send_monthly_digest(self):
        """Generate and send monthly digest."""
        logger.info("Generating monthly digest")

        try:
            generator = get_digest_generator()
            delivery = get_digest_delivery()

            digest = await generator.generate_monthly_digest()
            await delivery.deliver_digest(digest)

            logger.info("Monthly digest sent")

        except Exception as e:
            logger.error("Monthly digest failed", error=str(e))

    async def check_anomalies(self):
        """Check for anomalies and send alerts."""
        logger.info("Checking for anomalies")

        try:
            alert_system = get_alert_system()
            alerts = await alert_system.check_for_anomalies()

            if alerts:
                logger.info(f"Found {len(alerts)} anomaly alerts")
                # In production, would send notifications here

        except Exception as e:
            logger.error("Anomaly check failed", error=str(e))

    async def run_quarterly_synthesis(self):
        """Run quarterly synthesis and review."""
        logger.info("Starting quarterly synthesis")
        db = get_database()
        run = await db.start_analysis_run("quarterly_synthesis")

        try:
            # Get quarter identifier
            now = datetime.now()
            quarter = f"Q{(now.month - 1) // 3 + 1} {now.year}"

            # Get data
            signals = await db.get_processed_signals(days=90)
            patterns = await db.get_patterns()
            opportunities = await db.get_opportunities()

            # Generate synthesis
            synthesizer = get_synthesizer()
            synthesis = await synthesizer.generate_quarterly_synthesis(
                quarter=quarter,
                signals=signals,
                patterns=patterns,
                opportunities=opportunities
            )

            await db.complete_analysis_run(
                run.id,
                patterns_detected=len(patterns),
                opportunities_generated=len(opportunities),
                summary=f"Quarterly synthesis for {quarter} complete"
            )

            logger.info(f"Quarterly synthesis complete for {quarter}")

        except Exception as e:
            logger.error("Quarterly synthesis failed", error=str(e))
            await db.complete_analysis_run(
                run.id,
                patterns_detected=0,
                opportunities_generated=0,
                error_message=str(e)
            )


# Singleton
_scheduler: Optional[JobScheduler] = None


def get_scheduler() -> JobScheduler:
    """Get scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler

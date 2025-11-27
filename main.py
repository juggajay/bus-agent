#!/usr/bin/env python3
"""Main entry point for the Opportunity Intelligence Agent."""

import asyncio
import argparse
from dotenv import load_dotenv

load_dotenv()


def run_api():
    """Run the FastAPI server."""
    import uvicorn
    from src.interface.api import app
    from src.utils import get_settings

    settings = get_settings()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower()
    )


def run_scheduler():
    """Run the job scheduler."""
    import asyncio
    from src.scheduler import get_scheduler
    from src.utils import setup_logging, get_settings, get_logger

    settings = get_settings()
    setup_logging(settings.log_level)
    logger = get_logger(__name__)

    scheduler = get_scheduler()
    scheduler.start()

    logger.info("Scheduler running. Press Ctrl+C to stop.")

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop()
        logger.info("Scheduler stopped")


async def run_once():
    """Run the full pipeline once."""
    from src.collectors import registry, register_all_collectors
    from src.processors import get_pipeline
    from src.patterns import get_pattern_detector
    from src.reasoning import get_opportunity_generator
    from src.database import get_database
    from src.utils import setup_logging, get_settings, get_logger

    settings = get_settings()
    setup_logging(settings.log_level)
    logger = get_logger(__name__)

    logger.info("Running full pipeline...")

    # Collect
    logger.info("Step 1: Collecting data...")
    register_all_collectors()
    results = await registry.run_all()
    total_collected = sum(v for v in results.values() if v > 0)
    logger.info(f"Collected {total_collected} signals")

    # Process
    logger.info("Step 2: Processing signals...")
    pipeline = get_pipeline()
    processed = await pipeline.process_unprocessed(limit=500)
    logger.info(f"Processed {processed} signals")

    # Detect patterns
    logger.info("Step 3: Detecting patterns...")
    detector = get_pattern_detector()
    patterns = await detector.detect_all(days=30)
    logger.info(f"Detected {len(patterns)} patterns")

    # Generate opportunities
    logger.info("Step 4: Generating opportunities...")
    db = get_database()
    generator = get_opportunity_generator()
    new_patterns = await db.get_patterns(status="new", min_score=0.5)
    signals = await db.get_processed_signals(days=30)
    opportunities = await generator.generate_from_patterns(new_patterns, signals)
    logger.info(f"Generated {len(opportunities)} opportunities")

    logger.info("Pipeline complete!")

    # Print summary
    print("\n" + "="*60)
    print("PIPELINE SUMMARY")
    print("="*60)
    print(f"Signals collected: {total_collected}")
    print(f"Signals processed: {processed}")
    print(f"Patterns detected: {len(patterns)}")
    print(f"Opportunities generated: {len(opportunities)}")
    print("="*60)

    if opportunities:
        print("\nTOP OPPORTUNITIES:")
        for i, opp in enumerate(opportunities[:5], 1):
            print(f"\n{i}. {opp.title}")
            print(f"   Timing: {opp.timing_stage}")
            print(f"   Thesis: {opp.primary_thesis}")
            if opp.summary:
                print(f"   Summary: {opp.summary[:100]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Opportunity Intelligence Agent"
    )
    parser.add_argument(
        "mode",
        choices=["api", "scheduler", "once"],
        help="Run mode: api (web server), scheduler (background jobs), once (single pipeline run)"
    )

    args = parser.parse_args()

    if args.mode == "api":
        run_api()
    elif args.mode == "scheduler":
        run_scheduler()
    elif args.mode == "once":
        asyncio.run(run_once())


if __name__ == "__main__":
    main()

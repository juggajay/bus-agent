#!/usr/bin/env python3
"""Script to backfill data and reprocess signals."""

import asyncio
import argparse
from dotenv import load_dotenv

load_dotenv()

from src.collectors import registry, register_all_collectors
from src.processors import get_pipeline
from src.patterns import get_pattern_detector
from src.reasoning import get_opportunity_generator
from src.database import get_database
from src.utils import setup_logging, get_logger

logger = get_logger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Backfill data")
    parser.add_argument(
        "--collect",
        action="store_true",
        help="Run collection"
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Reprocess all signals (warning: may overwrite existing processed data)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for processing"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.collect:
        logger.info("Running collection...")
        register_all_collectors()
        results = await registry.run_all()
        total = sum(v for v in results.values() if v > 0)
        logger.info(f"Collected {total} total signals")

    if args.reprocess:
        logger.info("Reprocessing signals...")
        pipeline = get_pipeline()

        # Process in batches
        total_processed = 0
        while True:
            count = await pipeline.process_unprocessed(limit=args.batch_size)
            if count == 0:
                break
            total_processed += count
            logger.info(f"Processed batch: {count} signals (total: {total_processed})")

        logger.info(f"Reprocessing complete: {total_processed} signals")

    # Run full analysis after backfill
    if args.collect or args.reprocess:
        logger.info("Running pattern detection...")
        detector = get_pattern_detector()
        patterns = await detector.detect_all(days=90)
        logger.info(f"Detected {len(patterns)} patterns")

        logger.info("Generating opportunities...")
        db = get_database()
        generator = get_opportunity_generator()
        signals = await db.get_processed_signals(days=90)
        new_patterns = await db.get_patterns(status="new", min_score=0.5)
        opportunities = await generator.generate_from_patterns(new_patterns, signals)
        logger.info(f"Generated {len(opportunities)} opportunities")


if __name__ == "__main__":
    asyncio.run(main())

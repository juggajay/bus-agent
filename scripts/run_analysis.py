#!/usr/bin/env python3
"""Script to run analysis pipeline manually."""

import asyncio
import argparse
from dotenv import load_dotenv

load_dotenv()

from src.processors import get_pipeline
from src.patterns import get_pattern_detector
from src.reasoning import get_opportunity_generator
from src.database import get_database
from src.utils import setup_logging, get_logger

logger = get_logger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Run analysis pipeline")
    parser.add_argument(
        "--process",
        action="store_true",
        help="Process unprocessed signals"
    )
    parser.add_argument(
        "--detect-patterns",
        action="store_true",
        help="Run pattern detection"
    )
    parser.add_argument(
        "--generate-opportunities",
        action="store_true",
        help="Generate opportunities from patterns"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline (process + detect + generate)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of data to analyze"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum signals to process"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.5,
        help="Minimum opportunity score for generation"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.full or (not args.process and not args.detect_patterns and not args.generate_opportunities):
        # Run full pipeline
        args.process = True
        args.detect_patterns = True
        args.generate_opportunities = True

    if args.process:
        logger.info("Processing unprocessed signals...")
        pipeline = get_pipeline()
        count = await pipeline.process_unprocessed(limit=args.limit)
        logger.info(f"Processed {count} signals")

    if args.detect_patterns:
        logger.info(f"Detecting patterns (last {args.days} days)...")
        detector = get_pattern_detector()
        patterns = await detector.detect_all(days=args.days)
        logger.info(f"Detected {len(patterns)} patterns")

        for pattern in patterns:
            logger.info(f"  - {pattern.pattern_type}: {pattern.title} (score: {pattern.opportunity_score:.2f})")

    if args.generate_opportunities:
        logger.info("Generating opportunities...")
        db = get_database()
        generator = get_opportunity_generator()

        patterns = await db.get_patterns(status="new", min_score=args.min_score)
        signals = await db.get_processed_signals(days=args.days)

        opportunities = await generator.generate_from_patterns(patterns, signals, args.min_score)
        logger.info(f"Generated {len(opportunities)} opportunities")

        for opp in opportunities:
            logger.info(f"  - {opp.title} ({opp.timing_stage})")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Script to run data collection manually."""

import asyncio
import argparse
from dotenv import load_dotenv

load_dotenv()

from src.collectors import registry, register_all_collectors
from src.utils import setup_logging, get_logger

logger = get_logger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Run data collection")
    parser.add_argument(
        "--source",
        type=str,
        help="Specific source to collect from (e.g., 'google_trends', 'github_trending')"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Category to collect from (e.g., 'mass_behaviour', 'builder')"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    # Register collectors
    register_all_collectors()

    if args.source:
        # Run specific collector
        collector = registry.get(args.source)
        if not collector:
            logger.error(f"Unknown collector: {args.source}")
            return

        logger.info(f"Running collector: {args.source}")
        count = await collector.run()
        logger.info(f"Collected {count} signals from {args.source}")

    elif args.category:
        # Run category
        logger.info(f"Running collectors for category: {args.category}")
        results = await registry.run_category(args.category)
        for name, count in results.items():
            logger.info(f"  {name}: {count} signals")

    else:
        # Run all collectors
        logger.info("Running all collectors")
        results = await registry.run_all()
        total = sum(v for v in results.values() if v > 0)
        logger.info(f"Collection complete. Total: {total} signals")
        for name, count in results.items():
            status = "OK" if count >= 0 else "FAILED"
            logger.info(f"  {name}: {count} [{status}]")


if __name__ == "__main__":
    asyncio.run(main())

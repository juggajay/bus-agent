"""
Regenerate opportunities with the new Solo SaaS Finder v2.0 prompts and scoring.

This script:
1. Clears existing opportunities (optional)
2. Gets all patterns
3. Regenerates opportunities using new prompts

Run with: python scripts/regenerate_opportunities.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_database
from src.reasoning import get_opportunity_generator
from src.utils import get_logger

logger = get_logger(__name__)


async def regenerate_opportunities(
    clear_existing: bool = False,
    min_pattern_score: float = 0.5,
    days: int = 30
):
    """
    Regenerate all opportunities with new v2.0 prompts.

    Args:
        clear_existing: Whether to clear existing opportunities first
        min_pattern_score: Minimum pattern score to consider
        days: Days of signals to consider
    """
    db = get_database()
    generator = get_opportunity_generator()

    print(f"\n{'='*60}")
    print("Solo SaaS Finder v2.0 - Opportunity Regeneration")
    print(f"{'='*60}\n")

    if clear_existing:
        print("Clearing existing opportunities...")
        # Note: This would need a delete method - for now we'll just generate new ones
        print("(Skipping clear - delete manually if needed)")

    # Get patterns
    patterns = await db.get_patterns(min_score=min_pattern_score)
    print(f"Found {len(patterns)} patterns with score >= {min_pattern_score}")

    # Get processed signals (excluding disqualified)
    all_signals = await db.get_processed_signals(days=days)
    signals = [s for s in all_signals if not getattr(s, 'is_disqualified', False)]
    print(f"Found {len(signals)} valid signals (excluded {len(all_signals) - len(signals)} disqualified)")

    if not patterns:
        print("\nNo patterns to process. Run pattern detection first.")
        return

    print(f"\nGenerating opportunities from {len(patterns)} patterns...")

    generated = 0
    failed = 0

    for i, pattern in enumerate(patterns):
        try:
            print(f"\n[{i+1}/{len(patterns)}] Processing pattern: {pattern.title[:50]}...")

            # Get related signals
            related_signals = [
                s for s in signals
                if s.id in (pattern.signal_ids or [])
            ]

            if not related_signals:
                print(f"  Skipping - no valid related signals")
                continue

            # Generate opportunity
            opportunity = await generator.generate_from_pattern(pattern, related_signals)

            if opportunity:
                print(f"  Generated: {opportunity.title[:50]}")
                print(f"  Verdict: {getattr(opportunity, 'verdict', 'N/A')}")
                print(f"  Overall Score: {getattr(opportunity, 'overall_score', 'N/A')}/10")
                generated += 1
            else:
                print(f"  Failed to generate opportunity")
                failed += 1

        except Exception as e:
            logger.error(f"Failed to generate opportunity for pattern {pattern.id}", error=str(e))
            failed += 1

    print(f"\n{'='*60}")
    print("Opportunity Regeneration Complete!")
    print(f"{'='*60}")
    print(f"Total patterns processed: {len(patterns)}")
    print(f"Opportunities generated: {generated}")
    print(f"Failed: {failed}")

    # Summary of generated opportunities
    if generated > 0:
        print("\n--- Generated Opportunities Summary ---")
        opportunities = await db.get_opportunities()
        recent = opportunities[:10]

        for opp in recent:
            verdict = getattr(opp, 'verdict', 'N/A')
            score = getattr(opp, 'overall_score', 'N/A')
            print(f"\n{opp.title}")
            print(f"  Type: {opp.opportunity_type}")
            print(f"  Verdict: {verdict}")
            print(f"  Score: {score}/10")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Regenerate opportunities with Solo SaaS Finder v2.0")
    parser.add_argument("--clear", action="store_true", help="Clear existing opportunities first")
    parser.add_argument("--min-score", type=float, default=0.5, help="Minimum pattern score")
    parser.add_argument("--days", type=int, default=30, help="Days of signals to consider")

    args = parser.parse_args()

    asyncio.run(regenerate_opportunities(
        clear_existing=args.clear,
        min_pattern_score=args.min_score,
        days=args.days
    ))

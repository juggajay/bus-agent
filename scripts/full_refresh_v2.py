"""
Full refresh for Solo SaaS Finder v2.0

This script:
1. Clears processed_signals, pattern_matches, and opportunities
2. Reprocesses all raw signals with new v2.0 scoring
3. Detects patterns
4. Generates opportunities with new SaaS-focused prompts

Run with: python scripts/full_refresh_v2.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_database
from src.processors import get_pipeline
from src.reasoning import get_pattern_detector, get_opportunity_generator
from src.utils import get_logger

logger = get_logger(__name__)


async def full_refresh():
    """Full refresh with v2.0 scoring."""
    db = get_database()

    print(f"\n{'='*60}")
    print("Solo SaaS Finder v2.0 - Full Refresh")
    print(f"{'='*60}\n")

    # Step 1: Clear existing data
    print("Step 1: Clearing existing processed data...")
    try:
        db.client.table("opportunities").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  ✓ Cleared opportunities")
    except Exception as e:
        print(f"  ! Error clearing opportunities: {e}")

    try:
        db.client.table("pattern_matches").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  ✓ Cleared pattern_matches")
    except Exception as e:
        print(f"  ! Error clearing pattern_matches: {e}")

    try:
        db.client.table("processed_signals").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print("  ✓ Cleared processed_signals")
    except Exception as e:
        print(f"  ! Error clearing processed_signals: {e}")

    # Step 2: Get raw signals
    print("\nStep 2: Fetching raw signals...")
    raw_signals = await db.get_recent_signals(days=90)
    print(f"  Found {len(raw_signals)} raw signals to process")

    if not raw_signals:
        print("\nNo raw signals found. Run collection first:")
        print("  POST /pipeline/collect")
        return

    # Step 3: Process signals with new v2.0 scoring
    print("\nStep 3: Processing signals with v2.0 scoring...")
    pipeline = get_pipeline()

    processed_count = 0
    disqualified_count = 0
    failed_count = 0

    for i, signal in enumerate(raw_signals):
        try:
            result = await pipeline.process_signal(signal)
            if result:
                processed_count += 1
                if getattr(result, 'is_disqualified', False):
                    disqualified_count += 1
                if (i + 1) % 10 == 0:
                    print(f"  Processed {i + 1}/{len(raw_signals)} signals...")
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Failed to process signal {signal.id}", error=str(e))
            failed_count += 1

        # Rate limiting
        await asyncio.sleep(0.5)

    print(f"\n  ✓ Processed: {processed_count}")
    print(f"  ✓ Disqualified (regulated industries): {disqualified_count}")
    print(f"  ! Failed: {failed_count}")

    # Step 4: Detect patterns
    print("\nStep 4: Detecting patterns...")
    detector = get_pattern_detector()

    # Get freshly processed signals (excluding disqualified)
    processed_signals = await db.get_processed_signals(days=90)
    valid_signals = [s for s in processed_signals if not getattr(s, 'is_disqualified', False)]
    print(f"  Analyzing {len(valid_signals)} valid signals...")

    patterns = await detector.detect_patterns(valid_signals)
    print(f"  ✓ Detected {len(patterns)} patterns")

    # Step 5: Generate opportunities
    print("\nStep 5: Generating opportunities with v2.0 prompts...")
    generator = get_opportunity_generator()

    # Get stored patterns
    stored_patterns = await db.get_patterns(min_score=0.4)

    opportunities_generated = 0
    for pattern in stored_patterns:
        try:
            # Get related signals
            related_signals = [
                s for s in valid_signals
                if s.id in (pattern.signal_ids or [])
            ]

            if related_signals:
                opportunity = await generator.generate_from_pattern(pattern, related_signals)
                if opportunity:
                    opportunities_generated += 1
                    verdict = getattr(opportunity, 'verdict', 'N/A')
                    print(f"  Generated: {opportunity.title[:40]}... [{verdict}]")
        except Exception as e:
            logger.error(f"Failed to generate opportunity for pattern {pattern.id}", error=str(e))

        await asyncio.sleep(1)  # Rate limiting for LLM calls

    print(f"\n  ✓ Generated {opportunities_generated} opportunities")

    # Summary
    print(f"\n{'='*60}")
    print("Full Refresh Complete!")
    print(f"{'='*60}")
    print(f"Raw signals processed: {processed_count}")
    print(f"Disqualified (regulated): {disqualified_count}")
    print(f"Patterns detected: {len(patterns)}")
    print(f"Opportunities generated: {opportunities_generated}")

    # Show top opportunities
    if opportunities_generated > 0:
        print("\n--- Top Opportunities ---")
        opportunities = await db.get_opportunities()

        # Sort by verdict priority
        verdict_order = {"BUILD NOW": 0, "EXPLORE": 1, "MONITOR": 2, "PASS": 3}
        sorted_opps = sorted(
            opportunities,
            key=lambda o: (verdict_order.get(getattr(o, 'verdict', 'PASS'), 4), -(getattr(o, 'overall_score', 0) or 0))
        )

        for opp in sorted_opps[:5]:
            verdict = getattr(opp, 'verdict', 'N/A')
            score = getattr(opp, 'overall_score', 'N/A')
            print(f"\n[{verdict}] {opp.title}")
            print(f"  Score: {score}/10 | Type: {opp.opportunity_type}")
            if getattr(opp, 'one_liner', None):
                print(f"  {opp.one_liner}")


if __name__ == "__main__":
    asyncio.run(full_refresh())

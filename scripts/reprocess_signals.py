"""
Reprocess existing signals with the new Solo SaaS Finder v2.0 scoring.

This script:
1. Fetches all processed signals
2. Re-runs them through the new classification and thesis scoring
3. Updates the database with new scores

Run with: python scripts/reprocess_signals.py
"""

import asyncio
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_database
from src.processors import get_classifier, get_thesis_scorer
from src.utils import get_logger

logger = get_logger(__name__)


async def reprocess_all_signals(batch_size: int = 50, days: int = 90):
    """
    Reprocess all signals with the new v2.0 scoring.

    Args:
        batch_size: Number of signals to process at a time
        days: How many days back to reprocess
    """
    db = get_database()
    classifier = get_classifier()
    scorer = get_thesis_scorer()

    print(f"\n{'='*60}")
    print("Solo SaaS Finder v2.0 - Signal Reprocessing")
    print(f"{'='*60}\n")

    # Get all processed signals
    signals = await db.get_processed_signals(days=days)
    total = len(signals)

    print(f"Found {total} processed signals to reprocess")
    print(f"Processing in batches of {batch_size}\n")

    processed = 0
    updated = 0
    failed = 0
    disqualified = 0

    for i in range(0, total, batch_size):
        batch = signals[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(total-1)//batch_size + 1}...")

        for signal in batch:
            try:
                # Get the raw signal content
                raw_signals = await db.get_recent_signals(days=days)
                raw_signal = next(
                    (r for r in raw_signals if str(r.id) == str(signal.raw_signal_id)),
                    None
                )

                if not raw_signal:
                    logger.warning(f"Raw signal not found for {signal.id}")
                    failed += 1
                    continue

                # Re-classify with new SaaS-focused prompts
                classification = await classifier.classify(raw_signal)

                # Re-score with new thesis factors
                raw_content_str = json.dumps(raw_signal.raw_content)[:5000]
                score_result = await scorer.score(
                    signal_type=classification["signal_type"],
                    summary=classification["summary"],
                    entities=classification["entities"].model_dump(),
                    keywords=classification["keywords"],
                    industry=classification.get("industry", ""),
                    problem_summary=classification.get("problem_summary", ""),
                    demand_evidence=classification.get("demand_evidence_level", ""),
                    raw_content=raw_content_str
                )

                # Update the signal in database
                update_data = {
                    "signal_type": classification["signal_type"],
                    "signal_subtype": classification["signal_subtype"],
                    "summary": classification["summary"],
                    "problem_summary": classification.get("problem_summary", ""),
                    "demand_evidence_level": classification.get("demand_evidence_level", ""),
                    "score_demand_evidence": score_result["scores"].demand_evidence,
                    "score_competition_gap": score_result["scores"].competition_gap,
                    "score_trend_timing": score_result["scores"].trend_timing,
                    "score_solo_buildability": score_result["scores"].solo_buildability,
                    "score_clear_monetisation": score_result["scores"].clear_monetisation,
                    "score_regulatory_simplicity": score_result["scores"].regulatory_simplicity,
                    "is_disqualified": score_result.get("is_disqualified", False),
                    "disqualification_reason": score_result.get("disqualification_reason"),
                    "thesis_reasoning": score_result.get("reasoning", "")
                }

                # Update via direct Supabase call
                db.client.table("processed_signals").update(update_data).eq(
                    "id", str(signal.id)
                ).execute()

                updated += 1
                if score_result.get("is_disqualified"):
                    disqualified += 1

            except Exception as e:
                logger.error(f"Failed to reprocess signal {signal.id}", error=str(e))
                failed += 1

            processed += 1

        print(f"  Processed: {processed}/{total}, Updated: {updated}, Failed: {failed}, Disqualified: {disqualified}")

    print(f"\n{'='*60}")
    print("Reprocessing Complete!")
    print(f"{'='*60}")
    print(f"Total processed: {processed}")
    print(f"Successfully updated: {updated}")
    print(f"Failed: {failed}")
    print(f"Disqualified (regulated industries): {disqualified}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reprocess signals with Solo SaaS Finder v2.0 scoring")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing")
    parser.add_argument("--days", type=int, default=90, help="Days of history to reprocess")

    args = parser.parse_args()

    asyncio.run(reprocess_all_signals(batch_size=args.batch_size, days=args.days))

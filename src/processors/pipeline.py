"""Main processing pipeline for signals - Solo SaaS Finder v2.0"""

from typing import List, Optional
from datetime import datetime
import asyncio
import json

from ..database import (
    RawSignal, ProcessedSignalCreate,
    get_database
)
from ..utils import get_logger
from .classifier import get_classifier
from .thesis_scorer import get_thesis_scorer
from .embeddings import get_embedding_generator
from .novelty import calculate_novelty_score
from .velocity import get_velocity_tracker

logger = get_logger(__name__)


class ProcessingPipeline:
    """Pipeline for processing raw signals into enriched signals - Updated for Solo SaaS Finder v2.0"""

    def __init__(self):
        self.db = get_database()
        self.classifier = get_classifier()
        self.thesis_scorer = get_thesis_scorer()
        self.embedding_generator = get_embedding_generator()
        self.velocity_tracker = get_velocity_tracker()

    async def process_signal(self, raw_signal: RawSignal) -> Optional[ProcessedSignalCreate]:
        """Process a single raw signal through all stages with new SaaS-focused scoring."""
        try:
            logger.info(f"Processing signal", signal_id=str(raw_signal.id))

            # Stage 1: Classification (updated for SaaS focus)
            classification = await self.classifier.classify(raw_signal)

            # Stage 2: Thesis Scoring (new v2.0 scoring)
            raw_content_str = json.dumps(raw_signal.raw_content)[:5000]
            thesis_result = await self.thesis_scorer.score(
                signal_type=classification["signal_type"],
                summary=classification["summary"],
                entities=classification["entities"].model_dump(),
                keywords=classification["keywords"],
                industry=classification.get("industry", ""),
                problem_summary=classification.get("problem_summary", ""),
                demand_evidence=classification.get("demand_evidence_level", ""),
                raw_content=raw_content_str
            )

            # Stage 3: Generate Embedding
            # Combine title, summary, problem, and keywords for embedding
            text_for_embedding = " ".join([
                classification.get("title", ""),
                classification.get("summary", ""),
                classification.get("problem_summary", ""),
                " ".join(classification.get("keywords", []))
            ])
            embedding = await self.embedding_generator.generate(text_for_embedding)

            # Stage 4: Novelty Detection
            recent_embeddings = await self.db.get_recent_embeddings(days=7)
            novelty_score = calculate_novelty_score(embedding, recent_embeddings)

            # Stage 5: Velocity Tracking
            for keyword in classification.get("keywords", []):
                self.velocity_tracker.record_mention(keyword)

            # Calculate average velocity for this signal's keywords
            velocities = [
                self.velocity_tracker.get_velocity_score(kw)
                for kw in classification.get("keywords", [])
            ]
            velocity_score = sum(velocities) / len(velocities) if velocities else 0.0

            # Create processed signal with new v2.0 fields
            processed = ProcessedSignalCreate(
                raw_signal_id=raw_signal.id,
                signal_type=classification["signal_type"],
                signal_subtype=classification["signal_subtype"],
                title=classification["title"],
                summary=classification["summary"],
                # New v2.0 fields
                problem_summary=classification.get("problem_summary", ""),
                demand_evidence_level=classification.get("demand_evidence_level", ""),
                entities=classification["entities"],
                keywords=classification["keywords"],
                thesis_scores=thesis_result["scores"],
                thesis_reasoning=thesis_result.get("reasoning", ""),
                novelty_score=novelty_score,
                velocity_score=velocity_score,
                geography=raw_signal.geography,
                timing_stage=self._infer_timing_stage(
                    thesis_result["scores"],
                    velocity_score,
                    novelty_score
                ),
                # Disqualification tracking
                is_disqualified=thesis_result.get("is_disqualified", False),
                disqualification_reason=thesis_result.get("disqualification_reason")
            )

            # Store with embedding
            await self.db.insert_processed_signal(processed, embedding)

            logger.info(
                f"Signal processed successfully",
                signal_id=str(raw_signal.id),
                signal_type=classification["signal_type"],
                novelty=novelty_score,
                velocity=velocity_score,
                disqualified=thesis_result.get("is_disqualified", False)
            )

            return processed

        except Exception as e:
            logger.error(
                f"Failed to process signal",
                signal_id=str(raw_signal.id),
                error=str(e)
            )
            return None

    async def process_batch(self, raw_signals: List[RawSignal]) -> List[ProcessedSignalCreate]:
        """Process multiple signals."""
        results = []
        disqualified_count = 0

        for signal in raw_signals:
            result = await self.process_signal(signal)
            if result:
                results.append(result)
                if getattr(result, 'is_disqualified', False):
                    disqualified_count += 1

            # Small delay between signals to avoid rate limits
            await asyncio.sleep(0.5)

        if disqualified_count > 0:
            logger.info(f"Batch processing: {disqualified_count}/{len(results)} signals disqualified")

        return results

    async def process_unprocessed(self, limit: int = 100) -> int:
        """Process all unprocessed signals."""
        unprocessed = await self.db.get_unprocessed_signals(limit=limit)

        if not unprocessed:
            logger.info("No unprocessed signals found")
            return 0

        logger.info(f"Processing {len(unprocessed)} signals")

        results = await self.process_batch(unprocessed)

        logger.info(f"Processed {len(results)} signals successfully")

        return len(results)

    def _infer_timing_stage(
        self,
        thesis_scores,
        velocity_score: float,
        novelty_score: float
    ) -> str:
        """
        Infer timing stage from signal characteristics.

        Updated for Solo SaaS Finder v2.0:
        - High novelty + low velocity = Early (too nascent)
        - High novelty + high velocity = Emerging (sweet spot for building)
        - Low novelty + high velocity = Growing (still viable, more competition)
        - Low novelty + low velocity = Crowded or past peak (avoid)
        """
        if novelty_score > 0.7:
            if velocity_score > 0.5:
                return "emerging"
            else:
                return "early"
        else:
            if velocity_score > 0.5:
                return "growing"
            else:
                return "crowded"


# Singleton
_pipeline: Optional[ProcessingPipeline] = None


def get_pipeline() -> ProcessingPipeline:
    """Get processing pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = ProcessingPipeline()
    return _pipeline

"""Main processing pipeline for signals."""

from typing import List, Optional
from datetime import datetime
import asyncio

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
    """Pipeline for processing raw signals into enriched signals."""

    def __init__(self):
        self.db = get_database()
        self.classifier = get_classifier()
        self.thesis_scorer = get_thesis_scorer()
        self.embedding_generator = get_embedding_generator()
        self.velocity_tracker = get_velocity_tracker()

    async def process_signal(self, raw_signal: RawSignal) -> Optional[ProcessedSignalCreate]:
        """Process a single raw signal through all stages."""
        try:
            logger.info(f"Processing signal", signal_id=str(raw_signal.id))

            # Stage 1: Classification
            classification = await self.classifier.classify(raw_signal)

            # Stage 2: Thesis Scoring
            thesis_result = await self.thesis_scorer.score(
                signal_type=classification["signal_type"],
                summary=classification["summary"],
                entities=classification["entities"].model_dump(),
                keywords=classification["keywords"]
            )

            # Stage 3: Generate Embedding
            # Combine title, summary, and keywords for embedding
            text_for_embedding = " ".join([
                classification.get("title", ""),
                classification.get("summary", ""),
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

            # Create processed signal
            processed = ProcessedSignalCreate(
                raw_signal_id=raw_signal.id,
                signal_type=classification["signal_type"],
                signal_subtype=classification["signal_subtype"],
                title=classification["title"],
                summary=classification["summary"],
                entities=classification["entities"],
                keywords=classification["keywords"],
                thesis_scores=thesis_result["scores"],
                thesis_reasoning=thesis_result["reasoning"],
                novelty_score=novelty_score,
                velocity_score=velocity_score,
                geography=raw_signal.geography,
                timing_stage=self._infer_timing_stage(
                    thesis_result["scores"],
                    velocity_score,
                    novelty_score
                )
            )

            # Store with embedding
            await self.db.insert_processed_signal(processed, embedding)

            logger.info(
                f"Signal processed successfully",
                signal_id=str(raw_signal.id),
                signal_type=classification["signal_type"],
                novelty=novelty_score,
                velocity=velocity_score
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

        for signal in raw_signals:
            result = await self.process_signal(signal)
            if result:
                results.append(result)

            # Small delay between signals to avoid rate limits
            await asyncio.sleep(0.5)

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
        """Infer timing stage from signal characteristics."""
        # High novelty + low velocity = Early
        # High novelty + high velocity = Emerging
        # Low novelty + high velocity = Growing
        # Low novelty + low velocity = Crowded or past peak

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

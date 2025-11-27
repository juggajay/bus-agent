"""Base collector class and interfaces."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import asyncio

from ..database import RawSignalCreate, get_database
from ..utils import get_logger, get_rate_limiter, RateLimiter

logger = get_logger(__name__)


@dataclass
class CollectorConfig:
    """Configuration for a collector."""
    name: str
    source_type: str
    source_category: str
    rate_limiter_key: str = "default"
    enabled: bool = True
    retry_count: int = 3
    timeout_seconds: int = 30


class BaseCollector(ABC):
    """Base class for all data collectors."""

    def __init__(self, config: CollectorConfig):
        self.config = config
        self.rate_limiter: RateLimiter = get_rate_limiter(config.rate_limiter_key)
        self.db = get_database()

    @abstractmethod
    async def collect(self) -> List[RawSignalCreate]:
        """
        Collect signals from the source.

        Returns:
            List of raw signal objects ready for storage.
        """
        pass

    async def run(self) -> int:
        """
        Run the collector and store results.

        Returns:
            Number of signals collected.
        """
        if not self.config.enabled:
            logger.info(f"Collector {self.config.name} is disabled, skipping")
            return 0

        logger.info(f"Starting collection: {self.config.name}")

        # Start collection run tracking
        run = await self.db.start_collection_run(self.config.source_type)

        try:
            # Collect signals
            signals = await self.collect()

            if signals:
                # Store signals in database
                await self.db.insert_raw_signals_batch(signals)

            # Complete run tracking
            await self.db.complete_collection_run(
                run.id,
                signals_collected=len(signals)
            )

            logger.info(
                f"Collection complete: {self.config.name}",
                signals_collected=len(signals)
            )
            return len(signals)

        except Exception as e:
            logger.error(
                f"Collection failed: {self.config.name}",
                error=str(e)
            )
            await self.db.complete_collection_run(
                run.id,
                signals_collected=0,
                error_message=str(e)
            )
            raise

    def create_signal(
        self,
        raw_content: Dict[str, Any],
        source_url: Optional[str] = None,
        signal_date: Optional[datetime] = None,
        geography: Optional[str] = None
    ) -> RawSignalCreate:
        """Helper to create a properly formatted signal."""
        return RawSignalCreate(
            source_type=self.config.source_type,
            source_category=self.config.source_category,
            source_url=source_url,
            raw_content=raw_content,
            signal_date=signal_date.date() if signal_date else None,
            geography=geography
        )


class CollectorRegistry:
    """Registry for managing collectors."""

    def __init__(self):
        self._collectors: Dict[str, BaseCollector] = {}

    def register(self, collector: BaseCollector) -> None:
        """Register a collector."""
        self._collectors[collector.config.name] = collector

    def get(self, name: str) -> Optional[BaseCollector]:
        """Get a collector by name."""
        return self._collectors.get(name)

    def get_by_category(self, category: str) -> List[BaseCollector]:
        """Get all collectors in a category."""
        return [
            c for c in self._collectors.values()
            if c.config.source_category == category
        ]

    def get_all(self) -> List[BaseCollector]:
        """Get all registered collectors."""
        return list(self._collectors.values())

    async def run_all(self) -> Dict[str, int]:
        """Run all collectors and return results."""
        results = {}
        for name, collector in self._collectors.items():
            try:
                count = await collector.run()
                results[name] = count
            except Exception as e:
                logger.error(f"Collector {name} failed", error=str(e))
                results[name] = -1
        return results

    async def run_category(self, category: str) -> Dict[str, int]:
        """Run all collectors in a category."""
        collectors = self.get_by_category(category)
        results = {}
        for collector in collectors:
            try:
                count = await collector.run()
                results[collector.config.name] = count
            except Exception as e:
                logger.error(f"Collector {collector.config.name} failed", error=str(e))
                results[collector.config.name] = -1
        return results


# Global registry instance
registry = CollectorRegistry()

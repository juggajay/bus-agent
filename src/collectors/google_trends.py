"""Google Trends collector."""

from datetime import datetime
from typing import List, Optional
import asyncio

from pytrends.request import TrendReq

from .base import BaseCollector, CollectorConfig
from ..database import RawSignalCreate
from ..utils import get_logger

logger = get_logger(__name__)

# Categories to monitor
CATEGORIES = {
    0: "all",
    12: "business",
    5: "technology",
    7: "finance"
}

# Regions to monitor
REGIONS = ["US", "GB", "AU", "CA", "NZ"]


class GoogleTrendsCollector(BaseCollector):
    """Collector for Google Trends data."""

    def __init__(self):
        config = CollectorConfig(
            name="google_trends",
            source_type="google_trends",
            source_category="mass_behaviour",
            rate_limiter_key="google_trends"
        )
        super().__init__(config)
        self.pytrends = TrendReq(hl='en-US', tz=360)

    async def collect(self) -> List[RawSignalCreate]:
        """Collect trending searches and rising queries."""
        signals = []

        for region in REGIONS:
            try:
                await self.rate_limiter.acquire()

                # Get trending searches
                trending = await self._get_trending_searches(region)
                if trending:
                    signals.append(self.create_signal(
                        raw_content={
                            "type": "trending_searches",
                            "data": trending,
                            "region": region
                        },
                        geography=region
                    ))

                # Get rising queries for each category
                for cat_id, cat_name in CATEGORIES.items():
                    await self.rate_limiter.acquire()
                    rising = await self._get_rising_queries(region, cat_id)
                    if rising:
                        signals.append(self.create_signal(
                            raw_content={
                                "type": "rising_queries",
                                "category": cat_name,
                                "category_id": cat_id,
                                "data": rising,
                                "region": region
                            },
                            geography=region
                        ))

            except Exception as e:
                logger.error(f"Error collecting trends for {region}", error=str(e))
                continue

        return signals

    async def _get_trending_searches(self, region: str) -> Optional[List[dict]]:
        """Get trending searches for a region."""
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self.pytrends.trending_searches(pn=region.lower())
            )

            if df is not None and not df.empty:
                return df[0].tolist()[:20]  # Top 20 trends
            return None
        except Exception as e:
            logger.warning(f"Failed to get trending searches for {region}", error=str(e))
            return None

    async def _get_rising_queries(self, region: str, category: int) -> Optional[List[dict]]:
        """Get rising queries for a region and category."""
        try:
            loop = asyncio.get_event_loop()

            # Build payload
            await loop.run_in_executor(
                None,
                lambda: self.pytrends.build_payload(
                    kw_list=[''],
                    cat=category,
                    timeframe='today 1-m',
                    geo=region
                )
            )

            # Get related queries
            related = await loop.run_in_executor(
                None,
                self.pytrends.related_queries
            )

            if related and '' in related:
                rising_df = related['']['rising']
                if rising_df is not None and not rising_df.empty:
                    return rising_df.head(20).to_dict('records')
            return None
        except Exception as e:
            logger.warning(f"Failed to get rising queries for {region}/{category}", error=str(e))
            return None

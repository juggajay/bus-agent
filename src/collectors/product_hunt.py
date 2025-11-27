"""Product Hunt collector."""

from datetime import datetime, timedelta
from typing import List, Optional
import asyncio

import httpx
from bs4 import BeautifulSoup

from .base import BaseCollector, CollectorConfig
from ..database import RawSignalCreate
from ..utils import get_logger

logger = get_logger(__name__)


class ProductHuntCollector(BaseCollector):
    """Collector for Product Hunt launches."""

    def __init__(self):
        config = CollectorConfig(
            name="product_hunt",
            source_type="product_hunt",
            source_category="builder",
            rate_limiter_key="product_hunt"
        )
        super().__init__(config)

    async def collect(self) -> List[RawSignalCreate]:
        """Collect recent Product Hunt launches."""
        signals = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Today's products
            today_products = await self._get_products(client, "today")
            if today_products:
                signals.append(self.create_signal(
                    raw_content={
                        "type": "daily_products",
                        "period": "today",
                        "products": today_products
                    },
                    source_url="https://www.producthunt.com/",
                    geography="global"
                ))

            # Yesterday's products
            yesterday_products = await self._get_products(client, "yesterday")
            if yesterday_products:
                signals.append(self.create_signal(
                    raw_content={
                        "type": "daily_products",
                        "period": "yesterday",
                        "products": yesterday_products
                    },
                    source_url="https://www.producthunt.com/",
                    geography="global"
                ))

            # Weekly top products
            weekly_products = await self._get_products(client, "week")
            if weekly_products:
                signals.append(self.create_signal(
                    raw_content={
                        "type": "weekly_top",
                        "products": weekly_products
                    },
                    source_url="https://www.producthunt.com/",
                    geography="global"
                ))

        return signals

    async def _get_products(
        self,
        client: httpx.AsyncClient,
        period: str
    ) -> Optional[List[dict]]:
        """Get products for a given period."""
        try:
            await self.rate_limiter.acquire()

            # Construct URL based on period
            if period == "today":
                url = "https://www.producthunt.com/"
            elif period == "yesterday":
                yesterday = datetime.now() - timedelta(days=1)
                url = f"https://www.producthunt.com/leaderboard/daily/{yesterday.year}/{yesterday.month}/{yesterday.day}"
            elif period == "week":
                url = "https://www.producthunt.com/leaderboard/weekly"
            else:
                url = "https://www.producthunt.com/"

            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            return self._parse_products(response.text)

        except Exception as e:
            logger.warning(f"Failed to get Product Hunt {period}", error=str(e))
            return None

    def _parse_products(self, html: str) -> List[dict]:
        """Parse products from Product Hunt HTML."""
        products = []
        soup = BeautifulSoup(html, 'html.parser')

        # Product Hunt uses dynamic rendering, so we parse what we can
        # This may need adjustment based on their HTML structure
        for item in soup.select('[data-test="post-item"]'):
            try:
                # Try to extract product info
                name_elem = item.select_one('[data-test="post-name"]')
                tagline_elem = item.select_one('[data-test="tagline"]')
                link_elem = item.select_one('a[href*="/posts/"]')

                if name_elem:
                    name = name_elem.text.strip()
                    tagline = tagline_elem.text.strip() if tagline_elem else ""
                    url = f"https://www.producthunt.com{link_elem['href']}" if link_elem else ""

                    products.append({
                        "name": name,
                        "tagline": tagline,
                        "url": url
                    })

            except Exception as e:
                logger.debug(f"Error parsing product item", error=str(e))
                continue

        # Fallback: Try alternative selectors if above didn't work
        if not products:
            for item in soup.select('article, [class*="post"]'):
                try:
                    # Generic extraction attempt
                    links = item.select('a')
                    headings = item.select('h1, h2, h3')

                    if headings:
                        name = headings[0].text.strip()
                        url = ""
                        for link in links:
                            href = link.get('href', '')
                            if '/posts/' in href:
                                url = f"https://www.producthunt.com{href}" if href.startswith('/') else href
                                break

                        if name and len(name) > 2:
                            products.append({
                                "name": name,
                                "tagline": "",
                                "url": url
                            })

                except Exception:
                    continue

        return products[:30] if products else []
